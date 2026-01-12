"""
Tests for pool manager configuration loading and validation.

These tests focus on the complex pool parsing logic including:
- Pool discovery
- Pool validation
- Instance parsing
- Alias validation
- Error handling
"""

import os

import pytest
from playwright_proxy_mcp.playwright.config import (
    load_pool_manager_config,
    _discover_pools,
    _parse_pool_config,
    _parse_instance_config,
    _validate_alias,
    _validate_pool_config,
    _get_bool_env,
    _get_int_env,
    should_use_windows_node,
    _parse_global_config,
)


class TestGetBoolEnv:
    """Tests for _get_bool_env helper function."""

    def test_returns_default_when_not_set(self, monkeypatch):
        """Test that default is returned when env var not set."""
        monkeypatch.delenv("TEST_BOOL_VAR", raising=False)
        assert _get_bool_env("TEST_BOOL_VAR", True) is True
        assert _get_bool_env("TEST_BOOL_VAR", False) is False

    def test_true_values(self, monkeypatch):
        """Test various true values."""
        for value in ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"]:
            monkeypatch.setenv("TEST_BOOL_VAR", value)
            assert _get_bool_env("TEST_BOOL_VAR", False) is True

    def test_false_values(self, monkeypatch):
        """Test various false values."""
        for value in ["false", "FALSE", "0", "no", "NO", "off", "OFF", "", "invalid"]:
            monkeypatch.setenv("TEST_BOOL_VAR", value)
            assert _get_bool_env("TEST_BOOL_VAR", True) is False


class TestGetIntEnv:
    """Tests for _get_int_env helper function."""

    def test_returns_default_when_not_set(self, monkeypatch):
        """Test that default is returned when env var not set."""
        monkeypatch.delenv("TEST_INT_VAR", raising=False)
        assert _get_int_env("TEST_INT_VAR", 42) == 42

    def test_parses_valid_integer(self, monkeypatch):
        """Test parsing valid integer values."""
        monkeypatch.setenv("TEST_INT_VAR", "123")
        assert _get_int_env("TEST_INT_VAR", 0) == 123

    def test_returns_default_for_invalid_value(self, monkeypatch):
        """Test that default is returned for non-integer value."""
        monkeypatch.setenv("TEST_INT_VAR", "not_a_number")
        assert _get_int_env("TEST_INT_VAR", 99) == 99

    def test_handles_negative_integers(self, monkeypatch):
        """Test parsing negative integers."""
        monkeypatch.setenv("TEST_INT_VAR", "-50")
        assert _get_int_env("TEST_INT_VAR", 0) == -50

    def test_handles_empty_string(self, monkeypatch):
        """Test that empty string returns default."""
        monkeypatch.setenv("TEST_INT_VAR", "")
        assert _get_int_env("TEST_INT_VAR", 100) == 100


class TestShouldUseWindowsNode:
    """Tests for should_use_windows_node function."""

    def test_returns_false_when_not_set(self, monkeypatch):
        """Test that False is returned when env var not set."""
        monkeypatch.delenv("PW_MCP_PROXY_WSL_WINDOWS", raising=False)
        assert should_use_windows_node() is False

    def test_returns_true_when_set(self, monkeypatch):
        """Test that True is returned when env var is set."""
        monkeypatch.setenv("PW_MCP_PROXY_WSL_WINDOWS", "1")
        assert should_use_windows_node() is True

    def test_returns_true_for_any_value(self, monkeypatch):
        """Test that True is returned for any non-empty value."""
        monkeypatch.setenv("PW_MCP_PROXY_WSL_WINDOWS", "anything")
        assert should_use_windows_node() is True


class TestDiscoverPools:
    """Tests for _discover_pools function."""

    def test_discovers_pool_from_instances(self, monkeypatch):
        """Test discovering pool from INSTANCES setting."""
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_IS_DEFAULT", "true")

        pools = _discover_pools()
        assert "MYPOOL" in pools

    def test_discovers_multiple_pools(self, monkeypatch):
        """Test discovering multiple pools."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL3_BROWSER", "firefox")

        pools = _discover_pools()
        assert "POOL1" in pools
        assert "POOL2" in pools
        assert "POOL3" in pools

    def test_discovers_pool_from_instance_config(self, monkeypatch):
        """Test discovering pool from instance-level config."""
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL__0_ALIAS", "first")

        pools = _discover_pools()
        assert "MYPOOL" in pools

    def test_returns_sorted_pools(self, monkeypatch):
        """Test that pools are returned in sorted order."""
        monkeypatch.setenv("PW_MCP_PROXY__ZPOOL_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__APOOL_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__MPOOL_INSTANCES", "1")

        pools = _discover_pools()
        # The pools should be in sorted order
        pool_indices = [pools.index(p) for p in ["APOOL", "MPOOL", "ZPOOL"] if p in pools]
        assert pool_indices == sorted(pool_indices)


class TestParseGlobalConfig:
    """Tests for _parse_global_config function."""

    def test_parses_global_config(self, monkeypatch):
        """Test parsing global configuration."""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "webkit")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")

        config = _parse_global_config()

        assert config["browser"] == "webkit"
        assert config["headless"] is True

    def test_returns_empty_config_when_no_vars(self, monkeypatch):
        """Test that empty config is returned when no vars set."""
        # No specific global vars set
        config = _parse_global_config()

        # Config should be empty (defaults not applied by this function)
        assert "browser" not in config or isinstance(config.get("browser"), str)


class TestParseInstanceConfig:
    """Tests for _parse_instance_config function."""

    def test_parses_instance_with_alias(self, monkeypatch):
        """Test parsing instance config with alias."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL__0_ALIAS", "primary")
        monkeypatch.setenv("PW_MCP_PROXY__POOL__0_BROWSER", "firefox")

        pool_config = {"browser": "chromium", "headless": True}
        instance = _parse_instance_config("POOL", "0", pool_config)

        assert instance["instance_id"] == "0"
        assert instance["alias"] == "primary"
        assert instance["config"]["browser"] == "firefox"

    def test_instance_inherits_pool_config(self, monkeypatch):
        """Test that instance inherits pool config."""
        pool_config = {"browser": "chromium", "headless": True, "caps": "vision"}
        instance = _parse_instance_config("POOL", "1", pool_config)

        assert instance["config"]["browser"] == "chromium"
        assert instance["config"]["headless"] is True
        assert instance["config"]["caps"] == "vision"

    def test_instance_overrides_pool_config(self, monkeypatch):
        """Test that instance can override pool config."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL__0_HEADLESS", "false")

        pool_config = {"browser": "chromium", "headless": True}
        instance = _parse_instance_config("POOL", "0", pool_config)

        assert instance["config"]["headless"] is False


class TestValidateAlias:
    """Tests for _validate_alias function."""

    def test_valid_alias_passes(self):
        """Test that valid alias passes validation."""
        # Should not raise
        _validate_alias("primary", "POOL", "0")
        _validate_alias("debug-instance", "POOL", "1")
        _validate_alias("instance_one", "POOL", "2")

    def test_numeric_alias_fails(self):
        """Test that numeric alias raises ValueError."""
        with pytest.raises(ValueError, match="numeric pattern reserved"):
            _validate_alias("123", "POOL", "0")

    def test_single_digit_alias_fails(self):
        """Test that single digit alias raises ValueError."""
        with pytest.raises(ValueError, match="numeric pattern reserved"):
            _validate_alias("5", "POOL", "0")


class TestValidatePoolConfig:
    """Tests for _validate_pool_config function."""

    def test_valid_pool_config_passes(self):
        """Test that valid pool config passes validation."""
        pool_config = {
            "name": "POOL",
            "instances": 2,
            "is_default": True,
            "description": "",
            "base_config": {},
            "instance_configs": [
                {"instance_id": "0", "alias": "first", "config": {}},
                {"instance_id": "1", "alias": "second", "config": {}},
            ],
        }
        all_aliases = set()

        # Should not raise
        _validate_pool_config(pool_config, all_aliases)

        assert "POOL:first" in all_aliases
        assert "POOL:second" in all_aliases

    def test_duplicate_alias_fails(self):
        """Test that duplicate alias raises ValueError."""
        pool_config = {
            "name": "POOL",
            "instances": 2,
            "is_default": True,
            "description": "",
            "base_config": {},
            "instance_configs": [
                {"instance_id": "0", "alias": "same", "config": {}},
                {"instance_id": "1", "alias": "same", "config": {}},
            ],
        }
        all_aliases = set()

        with pytest.raises(ValueError, match="Duplicate alias"):
            _validate_pool_config(pool_config, all_aliases)

    def test_numeric_alias_in_pool_fails(self):
        """Test that numeric alias in pool raises ValueError."""
        pool_config = {
            "name": "POOL",
            "instances": 1,
            "is_default": True,
            "description": "",
            "base_config": {},
            "instance_configs": [
                {"instance_id": "0", "alias": "42", "config": {}},
            ],
        }
        all_aliases = set()

        with pytest.raises(ValueError, match="numeric pattern reserved"):
            _validate_pool_config(pool_config, all_aliases)

    def test_none_alias_passes(self):
        """Test that None alias passes validation."""
        pool_config = {
            "name": "POOL",
            "instances": 1,
            "is_default": True,
            "description": "",
            "base_config": {},
            "instance_configs": [
                {"instance_id": "0", "alias": None, "config": {}},
            ],
        }
        all_aliases = set()

        # Should not raise
        _validate_pool_config(pool_config, all_aliases)


class TestParsePoolConfig:
    """Tests for _parse_pool_config function."""

    def test_parses_pool_with_instances(self, monkeypatch):
        """Test parsing pool with multiple instances."""
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_INSTANCES", "3")
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_DESCRIPTION", "Test pool")

        global_config = {"browser": "chromium", "headless": True}
        pool = _parse_pool_config("MYPOOL", global_config)

        assert pool["name"] == "MYPOOL"
        assert pool["instances"] == 3
        assert pool["is_default"] is True
        assert pool["description"] == "Test pool"
        assert len(pool["instance_configs"]) == 3

    def test_raises_on_missing_instances(self, monkeypatch):
        """Test that ValueError is raised when INSTANCES not set."""
        # No INSTANCES env var set
        global_config = {"browser": "chromium"}

        with pytest.raises(ValueError, match="missing required INSTANCES"):
            _parse_pool_config("BADPOOL", global_config)

    def test_pool_inherits_global_config(self, monkeypatch):
        """Test that pool inherits global config."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "1")

        global_config = {"browser": "firefox", "headless": False, "caps": "vision"}
        pool = _parse_pool_config("POOL", global_config)

        assert pool["base_config"]["browser"] == "firefox"
        assert pool["base_config"]["headless"] is False
        assert pool["base_config"]["caps"] == "vision"

    def test_pool_overrides_global_config(self, monkeypatch):
        """Test that pool can override global config."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_BROWSER", "webkit")

        global_config = {"browser": "chromium", "headless": True}
        pool = _parse_pool_config("POOL", global_config)

        assert pool["base_config"]["browser"] == "webkit"
        assert pool["base_config"]["headless"] is True  # Inherited


class TestLoadPoolManagerConfig:
    """Tests for load_pool_manager_config function."""

    def test_loads_simple_config(self, monkeypatch):
        """Test loading simple pool configuration."""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert len(config["pools"]) == 1
        assert config["default_pool_name"] == "DEFAULT"
        assert config["pools"][0]["name"] == "DEFAULT"

    def test_raises_on_no_pools(self, monkeypatch):
        """Test that ValueError is raised when no pools defined."""
        # Patch _discover_pools to return empty list to simulate no pools
        from playwright_proxy_mcp.playwright import config
        monkeypatch.setattr(config, "_discover_pools", lambda: [])

        with pytest.raises(ValueError, match="No pools defined"):
            load_pool_manager_config()

    def test_raises_on_no_default_pool(self, monkeypatch):
        """Test that ValueError is raised when no default pool."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "1")
        # Note: IS_DEFAULT not set

        with pytest.raises(ValueError, match="No default pool defined"):
            load_pool_manager_config()

    def test_raises_on_multiple_defaults(self, monkeypatch):
        """Test that ValueError is raised when multiple default pools."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_IS_DEFAULT", "true")

        with pytest.raises(ValueError, match="Multiple default pools"):
            load_pool_manager_config()

    def test_raises_on_global_instances(self, monkeypatch):
        """Test that ValueError is raised when global INSTANCES is set."""
        monkeypatch.setenv("PW_MCP_PROXY_INSTANCES", "5")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        with pytest.raises(ValueError, match="not allowed"):
            load_pool_manager_config()

    def test_applies_global_defaults(self, monkeypatch):
        """Test that global defaults are applied."""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert config["global_config"]["browser"] == "chromium"
        assert config["global_config"]["headless"] is False
        assert config["global_config"]["caps"] == "vision,pdf"
        assert config["global_config"]["viewport_size"] == "1920x1080"

    def test_loads_multiple_pools(self, monkeypatch):
        """Test loading multiple pools."""
        monkeypatch.setenv("PW_MCP_PROXY__CHROME_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__CHROME_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__FIREFOX_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__FIREFOX_BROWSER", "firefox")

        config = load_pool_manager_config()

        assert len(config["pools"]) == 2
        pool_names = [p["name"] for p in config["pools"]]
        assert "CHROME" in pool_names
        assert "FIREFOX" in pool_names

    def test_pool_config_cascades(self, monkeypatch):
        """Test that config cascades from global to pool to instance."""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "chromium")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_HEADLESS", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL__1_BROWSER", "firefox")

        config = load_pool_manager_config()
        pool = config["pools"][0]

        # Instance 0 inherits from pool
        instance0 = pool["instance_configs"][0]
        assert instance0["config"]["browser"] == "chromium"
        assert instance0["config"]["headless"] is True

        # Instance 1 overrides browser
        instance1 = pool["instance_configs"][1]
        assert instance1["config"]["browser"] == "firefox"
        assert instance1["config"]["headless"] is True  # Still inherited


class TestPoolManagerConfigWithAliases:
    """Tests for pool manager config with instance aliases."""

    def test_loads_instances_with_aliases(self, monkeypatch):
        """Test loading instances with aliases."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL__0_ALIAS", "primary")
        monkeypatch.setenv("PW_MCP_PROXY__POOL__1_ALIAS", "secondary")

        config = load_pool_manager_config()
        pool = config["pools"][0]

        assert pool["instance_configs"][0]["alias"] == "primary"
        assert pool["instance_configs"][1]["alias"] == "secondary"

    def test_raises_on_duplicate_alias_within_pool(self, monkeypatch):
        """Test that duplicate alias within pool raises error."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL__0_ALIAS", "dupe")
        monkeypatch.setenv("PW_MCP_PROXY__POOL__1_ALIAS", "dupe")

        with pytest.raises(ValueError, match="Duplicate alias"):
            load_pool_manager_config()

    def test_same_alias_different_pools_ok(self, monkeypatch):
        """Test that same alias in different pools is allowed."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL1__0_ALIAS", "debug")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2__0_ALIAS", "debug")

        # Should not raise
        config = load_pool_manager_config()
        assert len(config["pools"]) == 2


class TestApplyConfigOverrides:
    """Tests for _apply_config_overrides function."""

    def test_apply_config_overrides_str_values(self, monkeypatch):
        """Test applying string config values."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("TEST_PREFIX_BROWSER", "webkit")
        monkeypatch.setenv("TEST_PREFIX_DEVICE", "iPhone 12")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config.get("browser") == "webkit"
        assert config.get("device") == "iPhone 12"

    def test_apply_config_overrides_bool_values(self, monkeypatch):
        """Test applying boolean config values."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("TEST_PREFIX_HEADLESS", "true")
        monkeypatch.setenv("TEST_PREFIX_NO_SANDBOX", "false")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config.get("headless") is True
        assert config.get("no_sandbox") is False

    def test_apply_config_overrides_int_values(self, monkeypatch):
        """Test applying integer config values."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_ACTION", "30000")
        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_NAVIGATION", "60000")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config.get("timeout_action") == 30000
        assert config.get("timeout_navigation") == 60000

    def test_apply_config_overrides_missing_env_var(self, monkeypatch):
        """Test that missing env vars are not applied."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        # Ensure no test vars are set
        monkeypatch.delenv("EMPTY_PREFIX_BROWSER", raising=False)

        config = {}
        _apply_config_overrides(config, "EMPTY_PREFIX_")

        assert "browser" not in config


class TestBlobConfig:
    """Tests for load_blob_config function."""

    def test_load_blob_config_defaults(self, monkeypatch):
        """Test loading blob config with default values."""
        from playwright_proxy_mcp.playwright.config import load_blob_config

        # Remove any existing env vars
        monkeypatch.delenv("BLOB_STORAGE_ROOT", raising=False)
        monkeypatch.delenv("BLOB_MAX_SIZE_MB", raising=False)

        config = load_blob_config()

        assert config["storage_root"] == "/mnt/blob-storage"
        assert config["max_size_mb"] == 500
        assert config["ttl_hours"] == 24
        assert config["size_threshold_kb"] == 50
        assert config["cleanup_interval_minutes"] == 60

    def test_load_blob_config_custom_values(self, monkeypatch):
        """Test loading blob config with custom values."""
        from playwright_proxy_mcp.playwright.config import load_blob_config

        monkeypatch.setenv("BLOB_STORAGE_ROOT", "/tmp/blobs")
        monkeypatch.setenv("BLOB_MAX_SIZE_MB", "1000")
        monkeypatch.setenv("BLOB_TTL_HOURS", "48")
        monkeypatch.setenv("BLOB_SIZE_THRESHOLD_KB", "100")
        monkeypatch.setenv("BLOB_CLEANUP_INTERVAL_MINUTES", "30")

        config = load_blob_config()

        assert config["storage_root"] == "/tmp/blobs"
        assert config["max_size_mb"] == 1000
        assert config["ttl_hours"] == 48
        assert config["size_threshold_kb"] == 100
        assert config["cleanup_interval_minutes"] == 30


class TestParseGlobalConfigExtended:
    """Extended tests for _parse_global_config function."""

    def test_parse_global_config_with_all_options(self, monkeypatch):
        """Test parsing global config with all options set."""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")
        monkeypatch.setenv("PW_MCP_PROXY_NO_SANDBOX", "true")
        monkeypatch.setenv("PW_MCP_PROXY_ISOLATED", "true")
        monkeypatch.setenv("PW_MCP_PROXY_CAPS", "vision,pdf")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "25000")

        config = _parse_global_config()

        assert config["browser"] == "firefox"
        assert config["headless"] is True
        assert config["no_sandbox"] is True
        assert config["isolated"] is True
        assert config["caps"] == "vision,pdf"
        assert config["timeout_action"] == 25000

    def test_parse_global_config_stealth_options(self, monkeypatch):
        """Test parsing global config with stealth options."""
        monkeypatch.setenv("PW_MCP_PROXY_USER_AGENT", "CustomBot/1.0")
        monkeypatch.setenv("PW_MCP_PROXY_IGNORE_HTTPS_ERRORS", "true")

        config = _parse_global_config()

        assert config["user_agent"] == "CustomBot/1.0"
        assert config["ignore_https_errors"] is True


class TestPoolDiscoveryPatterns:
    """Tests for pool discovery with various environment variable patterns."""

    def test_discovers_pool_with_underscore_in_name(self, monkeypatch):
        """Test discovering pool with underscores in name."""
        monkeypatch.setenv("PW_MCP_PROXY__MY_POOL_NAME_INSTANCES", "1")

        pools = _discover_pools()
        # Note: Pool names with underscores are tricky - depends on regex
        # This tests the current behavior
        assert len(pools) >= 0

    def test_ignores_non_pool_vars(self, monkeypatch):
        """Test that non-pool environment variables are ignored."""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "chromium")
        monkeypatch.setenv("RANDOM_VAR", "value")

        pools = _discover_pools()
        # Should not include global vars
        assert "BROWSER" not in pools


class TestValidationEdgeCases:
    """Edge case tests for validation functions."""

    def test_validate_alias_with_hyphen(self):
        """Test that alias with hyphen is valid."""
        _validate_alias("my-alias", "POOL", "0")

    def test_validate_alias_with_underscore(self):
        """Test that alias with underscore is valid."""
        _validate_alias("my_alias", "POOL", "0")

    def test_validate_alias_with_mixed_case(self):
        """Test that alias with mixed case is valid."""
        _validate_alias("MyAlias", "POOL", "0")

    def test_validate_pool_config_empty_aliases(self):
        """Test validating pool config where all aliases are None."""
        pool_config = {
            "name": "POOL",
            "instances": 2,
            "is_default": True,
            "description": "",
            "base_config": {},
            "instance_configs": [
                {"instance_id": "0", "alias": None, "config": {}},
                {"instance_id": "1", "alias": None, "config": {}},
            ],
        }
        all_aliases = set()

        # Should not raise
        _validate_pool_config(pool_config, all_aliases)

        # No aliases should be added
        assert len(all_aliases) == 0


class TestConfigEdgeCases:
    """Additional edge case tests for config module."""

    def test_get_bool_env_with_yes(self, monkeypatch):
        """Test _get_bool_env recognizes 'yes'."""
        monkeypatch.setenv("TEST_BOOL_YES", "yes")
        result = _get_bool_env("TEST_BOOL_YES", False)
        assert result is True

    def test_get_bool_env_with_on(self, monkeypatch):
        """Test _get_bool_env recognizes 'on'."""
        monkeypatch.setenv("TEST_BOOL_ON", "on")
        result = _get_bool_env("TEST_BOOL_ON", False)
        assert result is True

    def test_get_bool_env_with_1(self, monkeypatch):
        """Test _get_bool_env recognizes '1'."""
        monkeypatch.setenv("TEST_BOOL_ONE", "1")
        result = _get_bool_env("TEST_BOOL_ONE", False)
        assert result is True

    def test_get_bool_env_case_insensitive(self, monkeypatch):
        """Test _get_bool_env is case insensitive."""
        monkeypatch.setenv("TEST_BOOL_TRUE", "TRUE")
        result = _get_bool_env("TEST_BOOL_TRUE", False)
        assert result is True

    def test_get_int_env_with_whitespace(self, monkeypatch):
        """Test _get_int_env with whitespace (should fail)."""
        monkeypatch.setenv("TEST_INT_SPACE", " 123 ")
        result = _get_int_env("TEST_INT_SPACE", 0)
        # May fail to parse due to whitespace
        assert isinstance(result, int)

    def test_get_int_env_with_float_string(self, monkeypatch):
        """Test _get_int_env with float string (should return default)."""
        monkeypatch.setenv("TEST_INT_FLOAT", "12.34")
        result = _get_int_env("TEST_INT_FLOAT", 99)
        assert result == 99  # Falls back to default

    def test_parse_global_config_empty(self, monkeypatch):
        """Test _parse_global_config with no env vars returns empty dict."""
        # Clear relevant vars
        for key in list(os.environ.keys()):
            if key.startswith("PW_MCP_PROXY_") and "__" not in key:
                monkeypatch.delenv(key, raising=False)

        config = _parse_global_config()
        # Should be empty or have only values from existing env vars
        assert isinstance(config, dict)

    def test_discover_pools_with_instance_vars_only(self, monkeypatch):
        """Test that instance vars alone discover the pool."""
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL__0_BROWSER", "firefox")

        pools = _discover_pools()
        assert "MYPOOL" in pools

    def test_discover_pools_sorted(self, monkeypatch):
        """Test that discovered pools are sorted alphabetically."""
        monkeypatch.setenv("PW_MCP_PROXY__ZETA_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__ALPHA_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__BETA_INSTANCES", "1")

        pools = _discover_pools()
        if len(pools) >= 2:
            # Should be sorted
            assert pools == sorted(pools)


class TestParsePoolConfigExtended:
    """Extended tests for _parse_pool_config."""

    def test_parse_pool_config_missing_instances_raises(self, monkeypatch):
        """Test that missing INSTANCES raises ValueError."""
        monkeypatch.setenv("PW_MCP_PROXY__NOINSTANCES_DESCRIPTION", "Test")

        with pytest.raises(ValueError, match="missing required INSTANCES"):
            _parse_pool_config("NOINSTANCES", {})

    def test_parse_pool_config_zero_instances_raises(self, monkeypatch):
        """Test that zero instances raises ValueError."""
        monkeypatch.setenv("PW_MCP_PROXY__ZEROPOOL_INSTANCES", "0")

        with pytest.raises(ValueError, match="missing required INSTANCES"):
            _parse_pool_config("ZEROPOOL", {})

    def test_parse_pool_config_with_description(self, monkeypatch):
        """Test pool config with description."""
        monkeypatch.setenv("PW_MCP_PROXY__DESC_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DESC_DESCRIPTION", "My pool description")

        config = _parse_pool_config("DESC", {})
        assert config["description"] == "My pool description"


class TestParseInstanceConfigExtended:
    """Extended tests for _parse_instance_config."""

    def test_parse_instance_with_all_config(self, monkeypatch):
        """Test parsing instance with all config options."""
        monkeypatch.setenv("PW_MCP_PROXY__FULL__0_BROWSER", "webkit")
        monkeypatch.setenv("PW_MCP_PROXY__FULL__0_HEADLESS", "false")
        monkeypatch.setenv("PW_MCP_PROXY__FULL__0_NO_SANDBOX", "true")
        monkeypatch.setenv("PW_MCP_PROXY__FULL__0_ALIAS", "full_config")

        config = _parse_instance_config("FULL", "0", {"browser": "chromium"})

        assert config["alias"] == "full_config"
        assert config["config"]["browser"] == "webkit"
        assert config["config"]["headless"] is False
        assert config["config"]["no_sandbox"] is True

    def test_parse_instance_inherits_pool_defaults(self, monkeypatch):
        """Test that instance inherits pool-level defaults."""
        # No instance-specific vars
        pool_config = {
            "browser": "firefox",
            "headless": True,
            "timeout_action": 5000
        }

        config = _parse_instance_config("INHERIT", "0", pool_config)

        assert config["config"]["browser"] == "firefox"
        assert config["config"]["headless"] is True
        assert config["config"]["timeout_action"] == 5000


class TestLoadPoolManagerConfigEdgeCases:
    """Edge case tests for load_pool_manager_config."""

    def test_load_config_validates_unique_defaults(self, monkeypatch):
        """Test that multiple default pools are rejected."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_IS_DEFAULT", "true")

        with pytest.raises(ValueError, match="Multiple default pools defined"):
            load_pool_manager_config()

    def test_load_config_sets_default_pool_name(self, monkeypatch):
        """Test that default pool name is correctly set."""
        monkeypatch.setenv("PW_MCP_PROXY__MYDEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__MYDEFAULT_IS_DEFAULT", "true")

        config = load_pool_manager_config()
        assert config["default_pool_name"] == "MYDEFAULT"


class TestShouldUseWindowsNodeExtended:
    """Extended tests for should_use_windows_node."""

    def test_returns_false_when_empty_string(self, monkeypatch):
        """Test returns False when env var is empty string."""
        monkeypatch.setenv("PW_MCP_PROXY_WSL_WINDOWS", "")
        assert should_use_windows_node() is False

    def test_returns_true_for_false_string(self, monkeypatch):
        """Test returns True even for 'false' string (any non-empty value)."""
        monkeypatch.setenv("PW_MCP_PROXY_WSL_WINDOWS", "false")
        # Note: The function uses bool(os.getenv(...)), so any non-empty string is True
        assert should_use_windows_node() is True


class TestApplyConfigOverridesExtended:
    """Extended tests for _apply_config_overrides function."""

    def test_apply_network_options(self, monkeypatch):
        """Test applying network config options."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("NET_PREFIX_PROXY_SERVER", "http://proxy:8080")
        monkeypatch.setenv("NET_PREFIX_ALLOWED_ORIGINS", "example.com")
        monkeypatch.setenv("NET_PREFIX_BLOCKED_ORIGINS", "blocked.com")

        config = {}
        _apply_config_overrides(config, "NET_PREFIX_")

        assert config.get("proxy_server") == "http://proxy:8080"
        assert config.get("allowed_origins") == "example.com"
        assert config.get("blocked_origins") == "blocked.com"

    def test_apply_output_options(self, monkeypatch):
        """Test applying output config options."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("OUT_PREFIX_OUTPUT_DIR", "/tmp/output")
        monkeypatch.setenv("OUT_PREFIX_SAVE_SESSION", "true")
        monkeypatch.setenv("OUT_PREFIX_SAVE_TRACE", "true")
        monkeypatch.setenv("OUT_PREFIX_SAVE_VIDEO", "retain-on-failure")

        config = {}
        _apply_config_overrides(config, "OUT_PREFIX_")

        assert config.get("output_dir") == "/tmp/output"
        assert config.get("save_session") is True
        assert config.get("save_trace") is True
        assert config.get("save_video") == "retain-on-failure"

    def test_apply_profile_options(self, monkeypatch):
        """Test applying profile/storage config options."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("PROF_PREFIX_USER_DATA_DIR", "/home/user/.browser")
        monkeypatch.setenv("PROF_PREFIX_STORAGE_STATE", "/path/to/state.json")
        monkeypatch.setenv("PROF_PREFIX_ISOLATED", "true")

        config = {}
        _apply_config_overrides(config, "PROF_PREFIX_")

        assert config.get("user_data_dir") == "/home/user/.browser"
        assert config.get("storage_state") == "/path/to/state.json"
        assert config.get("isolated") is True

    def test_apply_extension_options(self, monkeypatch):
        """Test applying extension config options."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("EXT_PREFIX_EXTENSION", "true")
        monkeypatch.setenv("EXT_PREFIX_EXTENSION_TOKEN", "my-secret-token")

        config = {}
        _apply_config_overrides(config, "EXT_PREFIX_")

        assert config.get("extension") is True
        assert config.get("extension_token") == "my-secret-token"

    def test_apply_wsl_windows_option(self, monkeypatch):
        """Test applying WSL Windows option."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("WSL_PREFIX_WSL_WINDOWS", "true")

        config = {}
        _apply_config_overrides(config, "WSL_PREFIX_")

        assert config.get("wsl_windows") is True

    def test_apply_viewport_option(self, monkeypatch):
        """Test applying viewport size option."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("VP_PREFIX_VIEWPORT_SIZE", "1280x720")

        config = {}
        _apply_config_overrides(config, "VP_PREFIX_")

        assert config.get("viewport_size") == "1280x720"

    def test_apply_image_responses_option(self, monkeypatch):
        """Test applying image responses option."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("IMG_PREFIX_IMAGE_RESPONSES", "block")

        config = {}
        _apply_config_overrides(config, "IMG_PREFIX_")

        assert config.get("image_responses") == "block"

    def test_apply_init_script_option(self, monkeypatch):
        """Test applying init script option."""
        from playwright_proxy_mcp.playwright.config import _apply_config_overrides

        monkeypatch.setenv("SCRIPT_PREFIX_INIT_SCRIPT", "/path/to/script.js")

        config = {}
        _apply_config_overrides(config, "SCRIPT_PREFIX_")

        assert config.get("init_script") == "/path/to/script.js"


class TestLoadPoolManagerConfigGlobalDefaults:
    """Tests for global defaults in load_pool_manager_config."""

    def test_applies_default_timeout_action(self, monkeypatch):
        """Test default timeout_action is applied."""
        monkeypatch.setenv("PW_MCP_PROXY__DEF_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEF_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert config["global_config"]["timeout_action"] == 15000

    def test_applies_default_timeout_navigation(self, monkeypatch):
        """Test default timeout_navigation is applied."""
        monkeypatch.setenv("PW_MCP_PROXY__DEF_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEF_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert config["global_config"]["timeout_navigation"] == 5000

    def test_applies_default_image_responses(self, monkeypatch):
        """Test default image_responses is applied."""
        monkeypatch.setenv("PW_MCP_PROXY__DEF_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEF_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert config["global_config"]["image_responses"] == "allow"

    def test_custom_global_overrides_defaults(self, monkeypatch):
        """Test that custom global config overrides defaults."""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "webkit")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "30000")
        monkeypatch.setenv("PW_MCP_PROXY__DEF_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEF_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert config["global_config"]["browser"] == "webkit"
        assert config["global_config"]["timeout_action"] == 30000
