"""
Tests for configuration loading
"""

import pytest
from playwright_proxy_mcp.playwright.config import (
    load_blob_config,
    load_pool_manager_config,
    _get_bool_env,
    _get_int_env,
    should_use_windows_node,
    _discover_pools,
    _parse_global_config,
    _parse_instance_config,
    _parse_pool_config,
    _validate_alias,
    _validate_pool_config,
    _apply_config_overrides,
)


class TestPlaywrightConfig:
    """Tests for Playwright configuration."""

    def test_load_default_config(self, monkeypatch):
        """Test loading default configuration."""
        # Set up a minimal pool configuration
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()

        # Check global defaults
        assert pool_config["global_config"]["browser"] == "chromium"
        assert pool_config["global_config"]["headless"] is False
        assert pool_config["global_config"]["caps"] == "vision,pdf"
        assert pool_config["global_config"]["timeout_action"] == 15000
        assert pool_config["global_config"]["timeout_navigation"] == 5000

    def test_load_config_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        # Set global config
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "false")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "10000")

        # Set up pool
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()

        assert pool_config["global_config"]["browser"] == "firefox"
        assert pool_config["global_config"]["headless"] is False
        assert pool_config["global_config"]["timeout_action"] == 10000


class TestBlobConfig:
    """Tests for blob storage configuration."""

    def test_load_default_blob_config(self):
        """Test loading default blob configuration."""
        config = load_blob_config()

        assert config["storage_root"] == "/mnt/blob-storage"
        assert config["max_size_mb"] == 500
        assert config["ttl_hours"] == 24
        assert config["size_threshold_kb"] == 50
        assert config["cleanup_interval_minutes"] == 60

    def test_load_blob_config_from_env(self, monkeypatch):
        """Test loading blob config from environment variables."""
        monkeypatch.setenv("BLOB_STORAGE_ROOT", "/tmp/blobs")
        monkeypatch.setenv("BLOB_MAX_SIZE_MB", "100")
        monkeypatch.setenv("BLOB_TTL_HOURS", "12")

        config = load_blob_config()

        assert config["storage_root"] == "/tmp/blobs"
        assert config["max_size_mb"] == 100
        assert config["ttl_hours"] == 12


class TestGetBoolEnv:
    """Tests for _get_bool_env helper function."""

    def test_returns_default_when_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL_VAR", raising=False)
        assert _get_bool_env("TEST_BOOL_VAR", True) is True
        assert _get_bool_env("TEST_BOOL_VAR", False) is False

    def test_true_values(self, monkeypatch):
        for value in ["true", "TRUE", "1", "yes", "on"]:
            monkeypatch.setenv("TEST_BOOL_VAR", value)
            assert _get_bool_env("TEST_BOOL_VAR", False) is True

    def test_false_values(self, monkeypatch):
        for value in ["false", "0", "no", "off", ""]:
            monkeypatch.setenv("TEST_BOOL_VAR", value)
            assert _get_bool_env("TEST_BOOL_VAR", True) is False


class TestGetIntEnv:
    """Tests for _get_int_env helper function."""

    def test_returns_default_when_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_INT_VAR", raising=False)
        assert _get_int_env("TEST_INT_VAR", 42) == 42

    def test_parses_valid_integer(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "123")
        assert _get_int_env("TEST_INT_VAR", 0) == 123

    def test_returns_default_for_invalid_value(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "invalid")
        assert _get_int_env("TEST_INT_VAR", 99) == 99


class TestShouldUseWindowsNode:
    """Tests for should_use_windows_node function."""

    def test_returns_false_when_not_set(self, monkeypatch):
        monkeypatch.delenv("PW_MCP_PROXY_WSL_WINDOWS", raising=False)
        assert should_use_windows_node() is False

    def test_returns_true_when_set(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY_WSL_WINDOWS", "1")
        assert should_use_windows_node() is True


class TestDiscoverPools:
    """Tests for _discover_pools function."""

    def test_discovers_pool_from_instances(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_INSTANCES", "2")
        pools = _discover_pools()
        assert "MYPOOL" in pools

    def test_discovers_multiple_pools(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY__P1_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__P2_INSTANCES", "2")
        pools = _discover_pools()
        assert "P1" in pools
        assert "P2" in pools


class TestParseGlobalConfig:
    """Tests for _parse_global_config function."""

    def test_parses_global_config(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "webkit")
        config = _parse_global_config()
        assert config["browser"] == "webkit"


class TestParseInstanceConfig:
    """Tests for _parse_instance_config function."""

    def test_parses_instance_with_alias(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY__POOL__0_ALIAS", "primary")
        pool_config = {"browser": "chromium"}
        instance = _parse_instance_config("POOL", "0", pool_config)
        assert instance["alias"] == "primary"

    def test_instance_inherits_pool_config(self, monkeypatch):
        pool_config = {"browser": "firefox", "headless": True}
        instance = _parse_instance_config("POOL", "1", pool_config)
        assert instance["config"]["browser"] == "firefox"


class TestValidateAlias:
    """Tests for _validate_alias function."""

    def test_valid_alias_passes(self):
        _validate_alias("primary", "POOL", "0")

    def test_numeric_alias_fails(self):
        with pytest.raises(ValueError, match="numeric"):
            _validate_alias("123", "POOL", "0")


class TestValidatePoolConfig:
    """Tests for _validate_pool_config function."""

    def test_valid_pool_passes(self):
        pool = {
            "name": "POOL",
            "instances": 1,
            "is_default": True,
            "description": "",
            "base_config": {},
            "instance_configs": [{"instance_id": "0", "alias": None, "config": {}}],
        }
        _validate_pool_config(pool, set())

    def test_duplicate_alias_fails(self):
        pool = {
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
        with pytest.raises(ValueError, match="Duplicate"):
            _validate_pool_config(pool, set())


class TestParsePoolConfig:
    """Tests for _parse_pool_config function."""

    def test_parses_pool(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__MYPOOL_IS_DEFAULT", "true")
        global_config = {"browser": "chromium"}
        pool = _parse_pool_config("MYPOOL", global_config)
        assert pool["name"] == "MYPOOL"
        assert pool["instances"] == 2

    def test_raises_on_missing_instances(self, monkeypatch):
        with pytest.raises(ValueError, match="INSTANCES"):
            _parse_pool_config("NOPOOL", {})


class TestLoadPoolManagerConfigValidation:
    """Tests for load_pool_manager_config validation."""

    def test_raises_on_no_pools(self, monkeypatch):
        from playwright_proxy_mcp.playwright import config
        monkeypatch.setattr(config, "_discover_pools", lambda: [])
        with pytest.raises(ValueError, match="No pools"):
            load_pool_manager_config()

    def test_raises_on_no_default(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "1")
        with pytest.raises(ValueError, match="No default"):
            load_pool_manager_config()

    def test_raises_on_multiple_defaults(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY__P1_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__P1_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__P2_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__P2_IS_DEFAULT", "true")
        with pytest.raises(ValueError, match="Multiple"):
            load_pool_manager_config()

    def test_raises_on_global_instances(self, monkeypatch):
        monkeypatch.setenv("PW_MCP_PROXY_INSTANCES", "5")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        with pytest.raises(ValueError, match="not allowed"):
            load_pool_manager_config()


class TestApplyConfigOverrides:
    """Tests for _apply_config_overrides function."""

    def test_apply_str_values(self, monkeypatch):
        """Test applying string config values."""
        monkeypatch.setenv("TEST_PREFIX_BROWSER", "webkit")
        monkeypatch.setenv("TEST_PREFIX_DEVICE", "iPhone 12")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("browser") == "webkit"
        assert config.get("device") == "iPhone 12"

    def test_apply_bool_values(self, monkeypatch):
        """Test applying boolean config values."""
        monkeypatch.setenv("TEST_PREFIX_HEADLESS", "true")
        monkeypatch.setenv("TEST_PREFIX_NO_SANDBOX", "false")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("headless") is True
        assert config.get("no_sandbox") is False

    def test_apply_int_action_values(self, monkeypatch):
        """Test applying timeout_action integer values."""
        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_ACTION", "30000")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("timeout_action") == 30000

    def test_apply_int_navigation_values(self, monkeypatch):
        """Test applying timeout_navigation integer values."""
        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_NAVIGATION", "60000")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("timeout_navigation") == 60000

    def test_apply_network_options(self, monkeypatch):
        """Test applying network config options."""
        monkeypatch.setenv("TEST_PREFIX_PROXY_SERVER", "http://proxy:8080")
        monkeypatch.setenv("TEST_PREFIX_ALLOWED_ORIGINS", "example.com")
        monkeypatch.setenv("TEST_PREFIX_BLOCKED_ORIGINS", "blocked.com")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("proxy_server") == "http://proxy:8080"
        assert config.get("allowed_origins") == "example.com"
        assert config.get("blocked_origins") == "blocked.com"

    def test_apply_output_options(self, monkeypatch):
        """Test applying output config options."""
        monkeypatch.setenv("TEST_PREFIX_OUTPUT_DIR", "/tmp/output")
        monkeypatch.setenv("TEST_PREFIX_SAVE_SESSION", "true")
        monkeypatch.setenv("TEST_PREFIX_SAVE_TRACE", "true")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("output_dir") == "/tmp/output"
        assert config.get("save_session") is True
        assert config.get("save_trace") is True

    def test_apply_profile_options(self, monkeypatch):
        """Test applying profile/storage options."""
        monkeypatch.setenv("TEST_PREFIX_USER_DATA_DIR", "/home/user/.browser")
        monkeypatch.setenv("TEST_PREFIX_STORAGE_STATE", "/path/to/state.json")
        monkeypatch.setenv("TEST_PREFIX_ISOLATED", "true")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("user_data_dir") == "/home/user/.browser"
        assert config.get("storage_state") == "/path/to/state.json"
        assert config.get("isolated") is True

    def test_apply_extension_options(self, monkeypatch):
        """Test applying extension options."""
        monkeypatch.setenv("TEST_PREFIX_EXTENSION", "true")
        monkeypatch.setenv("TEST_PREFIX_EXTENSION_TOKEN", "secret-token")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("extension") is True
        assert config.get("extension_token") == "secret-token"

    def test_apply_stealth_options(self, monkeypatch):
        """Test applying stealth options."""
        monkeypatch.setenv("TEST_PREFIX_USER_AGENT", "CustomBot/1.0")
        monkeypatch.setenv("TEST_PREFIX_INIT_SCRIPT", "/path/to/script.js")
        monkeypatch.setenv("TEST_PREFIX_IGNORE_HTTPS_ERRORS", "true")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("user_agent") == "CustomBot/1.0"
        assert config.get("init_script") == "/path/to/script.js"
        assert config.get("ignore_https_errors") is True

    def test_apply_wsl_windows_option(self, monkeypatch):
        """Test applying WSL Windows option."""
        monkeypatch.setenv("TEST_PREFIX_WSL_WINDOWS", "true")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("wsl_windows") is True

    def test_apply_missing_env_vars_ignored(self, monkeypatch):
        """Test that missing env vars are ignored."""
        monkeypatch.delenv("EMPTY_PREFIX_BROWSER", raising=False)
        config = {}
        _apply_config_overrides(config, "EMPTY_PREFIX_")
        assert "browser" not in config

    def test_apply_viewport_size(self, monkeypatch):
        """Test applying viewport size."""
        monkeypatch.setenv("TEST_PREFIX_VIEWPORT_SIZE", "1280x720")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("viewport_size") == "1280x720"

    def test_apply_image_responses(self, monkeypatch):
        """Test applying image responses."""
        monkeypatch.setenv("TEST_PREFIX_IMAGE_RESPONSES", "block")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")
        assert config.get("image_responses") == "block"


class TestPoolConfigCascade:
    """Tests for config cascade from global to pool to instance."""

    def test_config_cascade_full(self, monkeypatch):
        """Test full config cascade."""
        # Global config
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "chromium")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")
        # Pool config
        monkeypatch.setenv("PW_MCP_PROXY__POOL_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL_BROWSER", "firefox")
        # Instance config
        monkeypatch.setenv("PW_MCP_PROXY__POOL__1_BROWSER", "webkit")

        config = load_pool_manager_config()
        pool = config["pools"][0]

        # Instance 0 inherits pool config (firefox)
        assert pool["instance_configs"][0]["config"]["browser"] == "firefox"
        # Instance 1 overrides to webkit
        assert pool["instance_configs"][1]["config"]["browser"] == "webkit"

    def test_global_defaults_applied(self, monkeypatch):
        """Test that global defaults are applied correctly."""
        monkeypatch.setenv("PW_MCP_PROXY__DEF_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEF_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert config["global_config"]["browser"] == "chromium"
        assert config["global_config"]["headless"] is False
        assert config["global_config"]["caps"] == "vision,pdf"
        assert config["global_config"]["timeout_action"] == 15000
        assert config["global_config"]["timeout_navigation"] == 5000
        assert config["global_config"]["image_responses"] == "allow"
        assert config["global_config"]["viewport_size"] == "1920x1080"
