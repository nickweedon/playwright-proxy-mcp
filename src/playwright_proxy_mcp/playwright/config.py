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


# Configuration key mappings for _apply_config_overrides
# Each tuple: (env_suffix, config_key, value_type)
# value_type: "str", "bool", "int_action", "int_navigation"
_CONFIG_KEY_MAPPINGS: list[tuple[str, str, str]] = [
    # Browser settings
    ("BROWSER", "browser", "str"),
    ("HEADLESS", "headless", "bool"),
    ("NO_SANDBOX", "no_sandbox", "bool"),
    ("DEVICE", "device", "str"),
    ("VIEWPORT_SIZE", "viewport_size", "str"),
    # Profile/storage
    ("ISOLATED", "isolated", "bool"),
    ("USER_DATA_DIR", "user_data_dir", "str"),
    ("STORAGE_STATE", "storage_state", "str"),
    # Network
    ("ALLOWED_ORIGINS", "allowed_origins", "str"),
    ("BLOCKED_ORIGINS", "blocked_origins", "str"),
    ("PROXY_SERVER", "proxy_server", "str"),
    # Capabilities
    ("CAPS", "caps", "str"),
    # Output
    ("SAVE_SESSION", "save_session", "bool"),
    ("SAVE_TRACE", "save_trace", "bool"),
    ("SAVE_VIDEO", "save_video", "str"),
    ("OUTPUT_DIR", "output_dir", "str"),
    # Timeouts
    ("TIMEOUT_ACTION", "timeout_action", "int_action"),
    ("TIMEOUT_NAVIGATION", "timeout_navigation", "int_navigation"),
    # Images
    ("IMAGE_RESPONSES", "image_responses", "str"),
    # Stealth
    ("USER_AGENT", "user_agent", "str"),
    ("INIT_SCRIPT", "init_script", "str"),
    ("IGNORE_HTTPS_ERRORS", "ignore_https_errors", "bool"),
    # Extension
    ("EXTENSION", "extension", "bool"),
    ("EXTENSION_TOKEN", "extension_token", "str"),
    # WSL Windows
    ("WSL_WINDOWS", "wsl_windows", "bool"),
]


def _apply_config_overrides(config: PlaywrightConfig, prefix: str) -> None:
    """
    Apply configuration overrides from environment variables with given prefix.

    This helper reduces code duplication across global, pool, and instance config parsing.
    Uses a data-driven approach with _CONFIG_KEY_MAPPINGS to reduce cyclomatic complexity.

    Args:
        config: Config dict to update in-place
        prefix: Environment variable prefix (e.g., "PW_MCP_PROXY_" or "PW_MCP_PROXY__POOL_")
    """
    for env_suffix, config_key, value_type in _CONFIG_KEY_MAPPINGS:
        env_var = f"{prefix}{env_suffix}"
        if os.getenv(env_var) is None:
            continue

        if value_type == "str":
            config[config_key] = os.getenv(env_var)  # type: ignore[literal-required]
        elif value_type == "bool":
            config[config_key] = _get_bool_env(env_var, False)  # type: ignore[literal-required]
        elif value_type == "int_action":
            config[config_key] = _get_int_env(env_var, 15000)  # type: ignore[literal-required]
        elif value_type == "int_navigation":
            config[config_key] = _get_int_env(env_var, 5000)  # type: ignore[literal-required]


def should_use_windows_node() -> bool:
    """
    Check if we should use Windows Node.js from WSL.

    Returns:
        True if PW_MCP_PROXY_WSL_WINDOWS is set
    """
    return bool(os.getenv("PW_MCP_PROXY_WSL_WINDOWS"))


def _parse_global_config() -> PlaywrightConfig:
    """
    Parse global configuration from PW_MCP_PROXY_* environment variables.

    These apply to all pools/instances unless overridden.
    """
    config: PlaywrightConfig = {}
    _apply_config_overrides(config, "PW_MCP_PROXY_")
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

    # Start with global config and apply pool-specific overrides
    pool_config = global_config.copy()
    _apply_config_overrides(pool_config, prefix)

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

    # Start with pool config and apply instance-specific overrides
    instance_config = pool_config.copy()
    _apply_config_overrides(instance_config, prefix)

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
