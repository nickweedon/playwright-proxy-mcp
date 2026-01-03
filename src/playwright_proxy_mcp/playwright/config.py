"""
Configuration management for Playwright MCP Proxy

Loads configuration from environment variables with sensible defaults
for both playwright-mcp subprocess and blob storage.

Version 2.0.0: Supports browser pools with hierarchical configuration
(Global → Pool → Instance precedence)
"""

import logging
import os
import re
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
# Try multiple paths for .env file
env_loaded = False
for env_path in [
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent.parent / ".env",
    Path.home() / ".env",
]:
    if env_path.exists():
        logger.info(f"Loading environment from: {env_path}")
        load_dotenv(env_path)
        env_loaded = True
        break

if not env_loaded:
    logger.warning("No .env file found, using system environment variables only")


class PlaywrightConfig(TypedDict, total=False):
    """Configuration for playwright-mcp subprocess"""

    # Browser settings
    browser: str
    headless: bool
    no_sandbox: bool
    device: str | None
    viewport_size: str | None

    # Profile/storage
    isolated: bool
    user_data_dir: str | None
    storage_state: str | None

    # Network
    allowed_origins: str | None
    blocked_origins: str | None
    proxy_server: str | None

    # Capabilities
    caps: str

    # Output
    save_session: bool
    save_trace: bool
    save_video: str | None
    output_dir: str

    # Timeouts (milliseconds)
    timeout_action: int
    timeout_navigation: int

    # Images
    image_responses: str

    # Stealth settings
    user_agent: str | None
    init_script: str | None
    ignore_https_errors: bool

    # Extension support
    extension: bool
    extension_token: str | None

    # WSL Windows mode
    wsl_windows: bool


class BlobConfig(TypedDict):
    """Configuration for blob storage"""

    storage_root: str
    max_size_mb: int
    ttl_hours: int
    size_threshold_kb: int
    cleanup_interval_minutes: int


class InstanceConfig(TypedDict):
    """Configuration for a single browser instance"""

    instance_id: str
    alias: str | None
    config: PlaywrightConfig


class PoolConfig(TypedDict):
    """Configuration for a browser pool"""

    name: str
    instances: int
    is_default: bool
    description: str
    instance_configs: list[InstanceConfig]
    base_config: PlaywrightConfig  # Pool-level config (applied to all instances)


class PoolManagerConfig(TypedDict):
    """Complete pool manager configuration"""

    pools: list[PoolConfig]
    default_pool_name: str
    global_config: PlaywrightConfig


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer environment variable"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def should_use_windows_node() -> bool:
    """
    Check if we should use Windows Node.js from WSL.

    Returns:
        True if PLAYWRIGHT_WSL_WINDOWS or PW_MCP_PROXY_WSL_WINDOWS is set
    """
    return bool(os.getenv("PLAYWRIGHT_WSL_WINDOWS") or os.getenv("PW_MCP_PROXY_WSL_WINDOWS"))


def _parse_global_config() -> PlaywrightConfig:
    """
    Parse global configuration from PW_MCP_PROXY_* environment variables.

    These apply to all pools/instances unless overridden.
    """
    config: PlaywrightConfig = {}

    # Browser settings
    if browser := os.getenv("PW_MCP_PROXY_BROWSER"):
        config["browser"] = browser
    if headless := os.getenv("PW_MCP_PROXY_HEADLESS"):
        config["headless"] = _get_bool_env("PW_MCP_PROXY_HEADLESS", False)
    if no_sandbox := os.getenv("PW_MCP_PROXY_NO_SANDBOX"):
        config["no_sandbox"] = _get_bool_env("PW_MCP_PROXY_NO_SANDBOX", False)
    if device := os.getenv("PW_MCP_PROXY_DEVICE"):
        config["device"] = device
    if viewport_size := os.getenv("PW_MCP_PROXY_VIEWPORT_SIZE"):
        config["viewport_size"] = viewport_size

    # Profile/storage
    if isolated := os.getenv("PW_MCP_PROXY_ISOLATED"):
        config["isolated"] = _get_bool_env("PW_MCP_PROXY_ISOLATED", False)
    if user_data_dir := os.getenv("PW_MCP_PROXY_USER_DATA_DIR"):
        config["user_data_dir"] = user_data_dir
    if storage_state := os.getenv("PW_MCP_PROXY_STORAGE_STATE"):
        config["storage_state"] = storage_state

    # Network
    if allowed_origins := os.getenv("PW_MCP_PROXY_ALLOWED_ORIGINS"):
        config["allowed_origins"] = allowed_origins
    if blocked_origins := os.getenv("PW_MCP_PROXY_BLOCKED_ORIGINS"):
        config["blocked_origins"] = blocked_origins
    if proxy_server := os.getenv("PW_MCP_PROXY_PROXY_SERVER"):
        config["proxy_server"] = proxy_server

    # Capabilities
    if caps := os.getenv("PW_MCP_PROXY_CAPS"):
        config["caps"] = caps

    # Output
    if save_session := os.getenv("PW_MCP_PROXY_SAVE_SESSION"):
        config["save_session"] = _get_bool_env("PW_MCP_PROXY_SAVE_SESSION", False)
    if save_trace := os.getenv("PW_MCP_PROXY_SAVE_TRACE"):
        config["save_trace"] = _get_bool_env("PW_MCP_PROXY_SAVE_TRACE", False)
    if save_video := os.getenv("PW_MCP_PROXY_SAVE_VIDEO"):
        config["save_video"] = save_video
    if output_dir := os.getenv("PW_MCP_PROXY_OUTPUT_DIR"):
        config["output_dir"] = output_dir

    # Timeouts
    if timeout_action := os.getenv("PW_MCP_PROXY_TIMEOUT_ACTION"):
        config["timeout_action"] = _get_int_env("PW_MCP_PROXY_TIMEOUT_ACTION", 15000)
    if timeout_navigation := os.getenv("PW_MCP_PROXY_TIMEOUT_NAVIGATION"):
        config["timeout_navigation"] = _get_int_env("PW_MCP_PROXY_TIMEOUT_NAVIGATION", 5000)

    # Images
    if image_responses := os.getenv("PW_MCP_PROXY_IMAGE_RESPONSES"):
        config["image_responses"] = image_responses

    # Stealth
    if user_agent := os.getenv("PW_MCP_PROXY_USER_AGENT"):
        config["user_agent"] = user_agent
    if init_script := os.getenv("PW_MCP_PROXY_INIT_SCRIPT"):
        config["init_script"] = init_script
    if ignore_https_errors := os.getenv("PW_MCP_PROXY_IGNORE_HTTPS_ERRORS"):
        config["ignore_https_errors"] = _get_bool_env("PW_MCP_PROXY_IGNORE_HTTPS_ERRORS", False)

    # Extension
    if extension := os.getenv("PW_MCP_PROXY_EXTENSION"):
        config["extension"] = _get_bool_env("PW_MCP_PROXY_EXTENSION", False)
    if extension_token := os.getenv("PW_MCP_PROXY_EXTENSION_TOKEN"):
        config["extension_token"] = extension_token

    # WSL Windows
    if wsl_windows := os.getenv("PW_MCP_PROXY_WSL_WINDOWS"):
        config["wsl_windows"] = _get_bool_env("PW_MCP_PROXY_WSL_WINDOWS", False)

    return config


def _discover_pools() -> list[str]:
    """
    Discover all pools defined in environment variables.

    Looks for PW_MCP_PROXY__<POOL_NAME>_* patterns.

    Pool-level vars: PW_MCP_PROXY__POOLNAME_CONFIGKEY
    Instance-level vars: PW_MCP_PROXY__POOLNAME__INSTANCEID_CONFIGKEY

    Returns:
        List of unique pool names
    """
    pools = set()

    # Pattern for pool-level config: PW_MCP_PROXY__<POOL>_<KEY>
    # Must have exactly one underscore after pool name (not double underscore)
    pool_pattern = re.compile(r"^PW_MCP_PROXY__([A-Z0-9_]+?)_([A-Z0-9_]+)$")

    # Pattern for instance-level config: PW_MCP_PROXY__<POOL>__<ID>_<KEY>
    instance_pattern = re.compile(r"^PW_MCP_PROXY__([A-Z0-9_]+?)__\d+_")

    logger.debug("Scanning environment for pool definitions...")
    pool_vars = []
    instance_vars = []

    for key in os.environ:
        # Check for pool-level vars
        if match := pool_pattern.match(key):
            pool_name = match.group(1)
            pools.add(pool_name)
            pool_vars.append(key)
        # Check for instance-level vars
        elif match := instance_pattern.match(key):
            pool_name = match.group(1)
            pools.add(pool_name)
            instance_vars.append(key)

    discovered = sorted(pools)
    logger.info(f"Discovered {len(discovered)} pool(s): {discovered}")
    logger.debug(f"Pool-level vars: {pool_vars}")
    logger.debug(f"Instance-level vars: {instance_vars}")

    return discovered


def _parse_pool_config(pool_name: str, global_config: PlaywrightConfig) -> PoolConfig:
    """
    Parse pool-level configuration.

    Args:
        pool_name: Name of the pool
        global_config: Global config to use as base

    Returns:
        PoolConfig with pool-level settings
    """
    prefix = f"PW_MCP_PROXY__{pool_name}_"

    # Start with global config
    pool_config = global_config.copy()

    # Pool-specific overrides
    if browser := os.getenv(f"{prefix}BROWSER"):
        pool_config["browser"] = browser
    if headless := os.getenv(f"{prefix}HEADLESS"):
        pool_config["headless"] = _get_bool_env(f"{prefix}HEADLESS", False)
    if no_sandbox := os.getenv(f"{prefix}NO_SANDBOX"):
        pool_config["no_sandbox"] = _get_bool_env(f"{prefix}NO_SANDBOX", False)
    if device := os.getenv(f"{prefix}DEVICE"):
        pool_config["device"] = device
    if viewport_size := os.getenv(f"{prefix}VIEWPORT_SIZE"):
        pool_config["viewport_size"] = viewport_size
    if isolated := os.getenv(f"{prefix}ISOLATED"):
        pool_config["isolated"] = _get_bool_env(f"{prefix}ISOLATED", False)
    if user_data_dir := os.getenv(f"{prefix}USER_DATA_DIR"):
        pool_config["user_data_dir"] = user_data_dir
    if storage_state := os.getenv(f"{prefix}STORAGE_STATE"):
        pool_config["storage_state"] = storage_state
    if allowed_origins := os.getenv(f"{prefix}ALLOWED_ORIGINS"):
        pool_config["allowed_origins"] = allowed_origins
    if blocked_origins := os.getenv(f"{prefix}BLOCKED_ORIGINS"):
        pool_config["blocked_origins"] = blocked_origins
    if proxy_server := os.getenv(f"{prefix}PROXY_SERVER"):
        pool_config["proxy_server"] = proxy_server
    if caps := os.getenv(f"{prefix}CAPS"):
        pool_config["caps"] = caps
    if save_session := os.getenv(f"{prefix}SAVE_SESSION"):
        pool_config["save_session"] = _get_bool_env(f"{prefix}SAVE_SESSION", False)
    if save_trace := os.getenv(f"{prefix}SAVE_TRACE"):
        pool_config["save_trace"] = _get_bool_env(f"{prefix}SAVE_TRACE", False)
    if save_video := os.getenv(f"{prefix}SAVE_VIDEO"):
        pool_config["save_video"] = save_video
    if output_dir := os.getenv(f"{prefix}OUTPUT_DIR"):
        pool_config["output_dir"] = output_dir
    if timeout_action := os.getenv(f"{prefix}TIMEOUT_ACTION"):
        pool_config["timeout_action"] = _get_int_env(f"{prefix}TIMEOUT_ACTION", 15000)
    if timeout_navigation := os.getenv(f"{prefix}TIMEOUT_NAVIGATION"):
        pool_config["timeout_navigation"] = _get_int_env(f"{prefix}TIMEOUT_NAVIGATION", 5000)
    if image_responses := os.getenv(f"{prefix}IMAGE_RESPONSES"):
        pool_config["image_responses"] = image_responses
    if user_agent := os.getenv(f"{prefix}USER_AGENT"):
        pool_config["user_agent"] = user_agent
    if init_script := os.getenv(f"{prefix}INIT_SCRIPT"):
        pool_config["init_script"] = init_script
    if ignore_https_errors := os.getenv(f"{prefix}IGNORE_HTTPS_ERRORS"):
        pool_config["ignore_https_errors"] = _get_bool_env(f"{prefix}IGNORE_HTTPS_ERRORS", False)
    if extension := os.getenv(f"{prefix}EXTENSION"):
        pool_config["extension"] = _get_bool_env(f"{prefix}EXTENSION", False)
    if extension_token := os.getenv(f"{prefix}EXTENSION_TOKEN"):
        pool_config["extension_token"] = extension_token
    if wsl_windows := os.getenv(f"{prefix}WSL_WINDOWS"):
        pool_config["wsl_windows"] = _get_bool_env(f"{prefix}WSL_WINDOWS", False)

    # Required pool-level settings
    instances = _get_int_env(f"{prefix}INSTANCES", 0)
    if instances == 0:
        raise ValueError(f"Pool '{pool_name}' missing required INSTANCES configuration")

    is_default = _get_bool_env(f"{prefix}IS_DEFAULT", False)
    description = os.getenv(f"{prefix}DESCRIPTION", "")

    # Parse instance-level configs
    instance_configs = []
    for i in range(instances):
        instance_config = _parse_instance_config(pool_name, str(i), pool_config)
        instance_configs.append(instance_config)

    return {
        "name": pool_name,
        "instances": instances,
        "is_default": is_default,
        "description": description,
        "base_config": pool_config,
        "instance_configs": instance_configs,
    }


def _parse_instance_config(
    pool_name: str, instance_id: str, pool_config: PlaywrightConfig
) -> InstanceConfig:
    """
    Parse instance-level configuration.

    Args:
        pool_name: Name of the pool
        instance_id: Instance ID (numeric string)
        pool_config: Pool-level config to use as base

    Returns:
        InstanceConfig with instance-level settings
    """
    prefix = f"PW_MCP_PROXY__{pool_name}__{instance_id}_"

    # Start with pool config
    instance_config = pool_config.copy()

    # Instance-specific overrides
    if browser := os.getenv(f"{prefix}BROWSER"):
        instance_config["browser"] = browser
    if headless := os.getenv(f"{prefix}HEADLESS"):
        instance_config["headless"] = _get_bool_env(f"{prefix}HEADLESS", False)
    if no_sandbox := os.getenv(f"{prefix}NO_SANDBOX"):
        instance_config["no_sandbox"] = _get_bool_env(f"{prefix}NO_SANDBOX", False)
    if device := os.getenv(f"{prefix}DEVICE"):
        instance_config["device"] = device
    if viewport_size := os.getenv(f"{prefix}VIEWPORT_SIZE"):
        instance_config["viewport_size"] = viewport_size
    if isolated := os.getenv(f"{prefix}ISOLATED"):
        instance_config["isolated"] = _get_bool_env(f"{prefix}ISOLATED", False)
    if user_data_dir := os.getenv(f"{prefix}USER_DATA_DIR"):
        instance_config["user_data_dir"] = user_data_dir
    if storage_state := os.getenv(f"{prefix}STORAGE_STATE"):
        instance_config["storage_state"] = storage_state
    if allowed_origins := os.getenv(f"{prefix}ALLOWED_ORIGINS"):
        instance_config["allowed_origins"] = allowed_origins
    if blocked_origins := os.getenv(f"{prefix}BLOCKED_ORIGINS"):
        instance_config["blocked_origins"] = blocked_origins
    if proxy_server := os.getenv(f"{prefix}PROXY_SERVER"):
        instance_config["proxy_server"] = proxy_server
    if caps := os.getenv(f"{prefix}CAPS"):
        instance_config["caps"] = caps
    if save_session := os.getenv(f"{prefix}SAVE_SESSION"):
        instance_config["save_session"] = _get_bool_env(f"{prefix}SAVE_SESSION", False)
    if save_trace := os.getenv(f"{prefix}SAVE_TRACE"):
        instance_config["save_trace"] = _get_bool_env(f"{prefix}SAVE_TRACE", False)
    if save_video := os.getenv(f"{prefix}SAVE_VIDEO"):
        instance_config["save_video"] = save_video
    if output_dir := os.getenv(f"{prefix}OUTPUT_DIR"):
        instance_config["output_dir"] = output_dir
    if timeout_action := os.getenv(f"{prefix}TIMEOUT_ACTION"):
        instance_config["timeout_action"] = _get_int_env(f"{prefix}TIMEOUT_ACTION", 15000)
    if timeout_navigation := os.getenv(f"{prefix}TIMEOUT_NAVIGATION"):
        instance_config["timeout_navigation"] = _get_int_env(f"{prefix}TIMEOUT_NAVIGATION", 5000)
    if image_responses := os.getenv(f"{prefix}IMAGE_RESPONSES"):
        instance_config["image_responses"] = image_responses
    if user_agent := os.getenv(f"{prefix}USER_AGENT"):
        instance_config["user_agent"] = user_agent
    if init_script := os.getenv(f"{prefix}INIT_SCRIPT"):
        instance_config["init_script"] = init_script
    if ignore_https_errors := os.getenv(f"{prefix}IGNORE_HTTPS_ERRORS"):
        instance_config["ignore_https_errors"] = _get_bool_env(
            f"{prefix}IGNORE_HTTPS_ERRORS", False
        )
    if extension := os.getenv(f"{prefix}EXTENSION"):
        instance_config["extension"] = _get_bool_env(f"{prefix}EXTENSION", False)
    if extension_token := os.getenv(f"{prefix}EXTENSION_TOKEN"):
        instance_config["extension_token"] = extension_token
    if wsl_windows := os.getenv(f"{prefix}WSL_WINDOWS"):
        instance_config["wsl_windows"] = _get_bool_env(f"{prefix}WSL_WINDOWS", False)

    # Instance-only setting: ALIAS
    alias = os.getenv(f"{prefix}ALIAS")

    return {"instance_id": instance_id, "alias": alias, "config": instance_config}


def _validate_alias(alias: str, pool_name: str, instance_id: str) -> None:
    """
    Validate instance alias.

    Args:
        alias: Alias to validate
        pool_name: Pool name (for error messages)
        instance_id: Instance ID (for error messages)

    Raises:
        ValueError: If alias is invalid
    """
    # Check if alias matches numeric pattern (reserved for instance IDs)
    if re.match(r"^\d+$", alias):
        raise ValueError(
            f"Pool '{pool_name}' instance {instance_id}: "
            f"Alias '{alias}' looks like instance ID (numeric pattern reserved)"
        )


def _validate_pool_config(pool_config: PoolConfig, all_aliases: set[str]) -> None:
    """
    Validate pool configuration.

    Args:
        pool_config: Pool configuration to validate
        all_aliases: Set to track aliases for uniqueness checking

    Raises:
        ValueError: If configuration is invalid
    """
    pool_name = pool_config["name"]

    # Validate aliases
    for instance_cfg in pool_config["instance_configs"]:
        if alias := instance_cfg["alias"]:
            # Check alias format
            _validate_alias(alias, pool_name, instance_cfg["instance_id"])

            # Check uniqueness within pool
            alias_key = f"{pool_name}:{alias}"
            if alias_key in all_aliases:
                raise ValueError(
                    f"Pool '{pool_name}': Duplicate alias '{alias}' "
                    f"(aliases must be unique within pool)"
                )
            all_aliases.add(alias_key)


def load_pool_manager_config() -> PoolManagerConfig:
    """
    Load complete pool manager configuration from environment variables.

    Returns:
        PoolManagerConfig with all pools and settings

    Raises:
        ValueError: If configuration is invalid
    """
    logger.info("="*60)
    logger.info("Loading Pool Manager Configuration (v2.0.0)")
    logger.info("="*60)

    # Check for invalid global INSTANCES setting
    if os.getenv("PW_MCP_PROXY_INSTANCES"):
        logger.error("PW_MCP_PROXY_INSTANCES found in environment (not allowed)")
        raise ValueError(
            "PW_MCP_PROXY_INSTANCES is not allowed. "
            "Each pool must define INSTANCES explicitly: PW_MCP_PROXY__<POOL>_INSTANCES"
        )

    # Parse global config
    logger.info("Parsing global configuration...")
    global_config = _parse_global_config()
    logger.debug(f"Global config keys set: {list(global_config.keys())}")

    # Apply defaults to global config
    if "browser" not in global_config:
        global_config["browser"] = "chromium"
    if "headless" not in global_config:
        global_config["headless"] = False
    if "caps" not in global_config:
        global_config["caps"] = "vision,pdf"
    if "timeout_action" not in global_config:
        global_config["timeout_action"] = 15000
    if "timeout_navigation" not in global_config:
        global_config["timeout_navigation"] = 5000
    if "image_responses" not in global_config:
        global_config["image_responses"] = "allow"
    if "viewport_size" not in global_config:
        global_config["viewport_size"] = "1920x1080"

    logger.info(f"Global defaults: browser={global_config['browser']}, "
                f"headless={global_config['headless']}")

    # Discover pools
    pool_names = _discover_pools()

    if not pool_names:
        logger.error("No pools defined in environment")
        logger.error("Expected at least one: PW_MCP_PROXY__<POOL>_INSTANCES=N")
        raise ValueError(
            "No pools defined. Define at least one pool: PW_MCP_PROXY__<POOL>_INSTANCES=N"
        )

    # Parse pool configs
    pools = []
    all_aliases: set[str] = set()

    for pool_name in pool_names:
        logger.info(f"Parsing pool '{pool_name}'...")
        pool_config = _parse_pool_config(pool_name, global_config)
        logger.info(f"  Pool '{pool_name}': {pool_config['instances']} instance(s), "
                   f"default={pool_config['is_default']}, "
                   f"browser={pool_config['base_config'].get('browser', 'N/A')}")
        _validate_pool_config(pool_config, all_aliases)
        pools.append(pool_config)

    # Validate exactly one default pool
    logger.info("Validating default pool configuration...")
    default_pools = [p for p in pools if p["is_default"]]

    if not default_pools:
        logger.error("No default pool defined (IS_DEFAULT=true required for one pool)")
        raise ValueError("No default pool defined. Set IS_DEFAULT=true for one pool")
    if len(default_pools) > 1:
        default_names = [p["name"] for p in default_pools]
        logger.error(f"Multiple default pools defined: {', '.join(default_names)}")
        raise ValueError(
            f"Multiple default pools defined: {', '.join(default_names)}. "
            f"Only one pool can have IS_DEFAULT=true"
        )

    default_pool_name = default_pools[0]["name"]
    logger.info(f"Default pool: '{default_pool_name}'")
    logger.info("="*60)
    logger.info("Pool Manager Configuration Loaded Successfully")
    logger.info(f"Total pools: {len(pools)}")
    logger.info(f"Total instances: {sum(p['instances'] for p in pools)}")
    logger.info("="*60)

    return {
        "pools": pools,
        "default_pool_name": default_pool_name,
        "global_config": global_config,
    }


def load_playwright_config() -> PlaywrightConfig:
    """
    Load playwright-mcp configuration from PLAYWRIGHT_* environment variables.

    This loads a single instance configuration, useful for testing or
    simple deployments. For production with browser pools, use
    load_pool_manager_config() instead.

    Returns:
        PlaywrightConfig with all settings
    """
    config: PlaywrightConfig = {
        "browser": os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        "headless": _get_bool_env("PLAYWRIGHT_HEADLESS", False),
        "no_sandbox": _get_bool_env("PLAYWRIGHT_NO_SANDBOX", False),
        "isolated": _get_bool_env("PLAYWRIGHT_ISOLATED", False),
        "caps": os.getenv("PLAYWRIGHT_CAPS", "vision,pdf"),
        "save_session": _get_bool_env("PLAYWRIGHT_SAVE_SESSION", False),
        "save_trace": _get_bool_env("PLAYWRIGHT_SAVE_TRACE", False),
        "timeout_action": _get_int_env("PLAYWRIGHT_TIMEOUT_ACTION", 15000),
        "timeout_navigation": _get_int_env("PLAYWRIGHT_TIMEOUT_NAVIGATION", 5000),
        "image_responses": os.getenv("PLAYWRIGHT_IMAGE_RESPONSES", "allow"),
        "ignore_https_errors": _get_bool_env("PLAYWRIGHT_IGNORE_HTTPS_ERRORS", False),
    }

    # Optional settings - only include if set
    if device := os.getenv("PLAYWRIGHT_DEVICE"):
        config["device"] = device

    # Default viewport size to 1920x1080
    config["viewport_size"] = os.getenv("PLAYWRIGHT_VIEWPORT_SIZE", "1920x1080")

    if user_data_dir := os.getenv("PLAYWRIGHT_USER_DATA_DIR"):
        config["user_data_dir"] = user_data_dir

    if output_dir := os.getenv("PLAYWRIGHT_OUTPUT_DIR"):
        config["output_dir"] = output_dir

    if storage_state := os.getenv("PLAYWRIGHT_STORAGE_STATE"):
        config["storage_state"] = storage_state

    if allowed_origins := os.getenv("PLAYWRIGHT_ALLOWED_ORIGINS"):
        config["allowed_origins"] = allowed_origins

    if blocked_origins := os.getenv("PLAYWRIGHT_BLOCKED_ORIGINS"):
        config["blocked_origins"] = blocked_origins

    if proxy_server := os.getenv("PLAYWRIGHT_PROXY_SERVER"):
        config["proxy_server"] = proxy_server

    if save_video := os.getenv("PLAYWRIGHT_SAVE_VIDEO"):
        config["save_video"] = save_video

    # Stealth settings
    if user_agent := os.getenv("PLAYWRIGHT_USER_AGENT"):
        config["user_agent"] = user_agent

    # Default to bundled stealth script if stealth mode is enabled
    if _get_bool_env("PLAYWRIGHT_STEALTH_MODE", False):
        # Use bundled stealth.js script
        stealth_script_path = Path(__file__).parent / "stealth.js"
        if stealth_script_path.exists():
            config["init_script"] = str(stealth_script_path)

    # Allow custom init script to override
    if init_script := os.getenv("PLAYWRIGHT_INIT_SCRIPT"):
        config["init_script"] = init_script

    # Extension support
    config["extension"] = _get_bool_env("PLAYWRIGHT_EXTENSION", False)

    if extension_token := os.getenv("PLAYWRIGHT_MCP_EXTENSION_TOKEN"):
        config["extension_token"] = extension_token

    return config


def load_blob_config() -> BlobConfig:
    """
    Load blob storage configuration from environment variables.

    Returns:
        BlobConfig with all settings
    """
    return {
        "storage_root": os.getenv("BLOB_STORAGE_ROOT", "/mnt/blob-storage"),
        "max_size_mb": _get_int_env("BLOB_MAX_SIZE_MB", 500),
        "ttl_hours": _get_int_env("BLOB_TTL_HOURS", 24),
        "size_threshold_kb": _get_int_env("BLOB_SIZE_THRESHOLD_KB", 50),
        "cleanup_interval_minutes": _get_int_env("BLOB_CLEANUP_INTERVAL_MINUTES", 60),
    }
