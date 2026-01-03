"""
Extended tests for configuration loading
"""

from playwright_proxy_mcp.playwright.config import load_blob_config, load_pool_manager_config


class TestConfigEdgeCases:
    """Test edge cases in configuration loading."""

    def test_load_playwright_config_with_all_env_vars(self, monkeypatch):
        """Test loading all playwright config from environment."""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "webkit")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")
        monkeypatch.setenv("PW_MCP_PROXY_DEVICE", "iPhone 12")
        monkeypatch.setenv("PW_MCP_PROXY_VIEWPORT_SIZE", "1920x1080")
        monkeypatch.setenv("PW_MCP_PROXY_ISOLATED", "true")
        monkeypatch.setenv("PW_MCP_PROXY_USER_DATA_DIR", "/path/to/data")
        monkeypatch.setenv("PW_MCP_PROXY_STORAGE_STATE", "/path/to/state.json")
        monkeypatch.setenv("PW_MCP_PROXY_ALLOWED_ORIGINS", "example.com")
        monkeypatch.setenv("PW_MCP_PROXY_BLOCKED_ORIGINS", "ads.com")
        monkeypatch.setenv("PW_MCP_PROXY_PROXY_SERVER", "proxy.com:8080")
        monkeypatch.setenv("PW_MCP_PROXY_CAPS", "vision")
        monkeypatch.setenv("PW_MCP_PROXY_SAVE_SESSION", "true")
        monkeypatch.setenv("PW_MCP_PROXY_SAVE_TRACE", "true")
        monkeypatch.setenv("PW_MCP_PROXY_SAVE_VIDEO", "on-failure")
        monkeypatch.setenv("PW_MCP_PROXY_OUTPUT_DIR", "/output")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "15000")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_NAVIGATION", "90000")
        monkeypatch.setenv("PW_MCP_PROXY_IMAGE_RESPONSES", "base64")

        # Set up pool
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        config = pool_config["global_config"]

        assert config["browser"] == "webkit"
        assert config["headless"] is True
        assert config["device"] == "iPhone 12"
        assert config["viewport_size"] == "1920x1080"
        assert config["isolated"] is True
        assert config["user_data_dir"] == "/path/to/data"
        assert config["storage_state"] == "/path/to/state.json"
        assert config["allowed_origins"] == "example.com"
        assert config["blocked_origins"] == "ads.com"
        assert config["proxy_server"] == "proxy.com:8080"
        assert config["caps"] == "vision"
        assert config["save_session"] is True
        assert config["save_trace"] is True
        assert config["save_video"] == "on-failure"
        assert config["output_dir"] == "/output"
        assert config["timeout_action"] == 15000
        assert config["timeout_navigation"] == 90000
        assert config["image_responses"] == "base64"

    def test_load_blob_config_with_all_env_vars(self, monkeypatch):
        """Test loading all blob config from environment."""
        monkeypatch.setenv("BLOB_STORAGE_ROOT", "/custom/storage")
        monkeypatch.setenv("BLOB_MAX_SIZE_MB", "1000")
        monkeypatch.setenv("BLOB_TTL_HOURS", "48")
        monkeypatch.setenv("BLOB_SIZE_THRESHOLD_KB", "100")
        monkeypatch.setenv("BLOB_CLEANUP_INTERVAL_MINUTES", "30")

        config = load_blob_config()

        assert config["storage_root"] == "/custom/storage"
        assert config["max_size_mb"] == 1000
        assert config["ttl_hours"] == 48
        assert config["size_threshold_kb"] == 100
        assert config["cleanup_interval_minutes"] == 30

    def test_playwright_headless_string_true(self, monkeypatch):
        """Test that string 'true' is converted to boolean True."""
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        assert pool_config["global_config"]["headless"] is True

    def test_playwright_headless_string_false(self, monkeypatch):
        """Test that string 'false' is converted to boolean False."""
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "false")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        assert pool_config["global_config"]["headless"] is False

    def test_playwright_isolated_string(self, monkeypatch):
        """Test that isolated is converted to boolean."""
        monkeypatch.setenv("PW_MCP_PROXY_ISOLATED", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        assert pool_config["global_config"]["isolated"] is True

    def test_playwright_save_session_string(self, monkeypatch):
        """Test that save_session is converted to boolean."""
        monkeypatch.setenv("PW_MCP_PROXY_SAVE_SESSION", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        assert pool_config["global_config"]["save_session"] is True

    def test_playwright_save_trace_string(self, monkeypatch):
        """Test that save_trace is converted to boolean."""
        monkeypatch.setenv("PW_MCP_PROXY_SAVE_TRACE", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        assert pool_config["global_config"]["save_trace"] is True

    def test_playwright_timeout_int_conversion(self, monkeypatch):
        """Test that timeout values are converted to integers."""
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "7500")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_NAVIGATION", "45000")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        pool_config = load_pool_manager_config()
        config = pool_config["global_config"]

        assert isinstance(config["timeout_action"], int)
        assert config["timeout_action"] == 7500
        assert isinstance(config["timeout_navigation"], int)
        assert config["timeout_navigation"] == 45000

    def test_blob_config_int_conversion(self, monkeypatch):
        """Test that blob config values are converted to integers."""
        monkeypatch.setenv("BLOB_MAX_SIZE_MB", "250")
        monkeypatch.setenv("BLOB_TTL_HOURS", "36")
        monkeypatch.setenv("BLOB_SIZE_THRESHOLD_KB", "75")
        monkeypatch.setenv("BLOB_CLEANUP_INTERVAL_MINUTES", "45")

        config = load_blob_config()

        assert isinstance(config["max_size_mb"], int)
        assert config["max_size_mb"] == 250
        assert isinstance(config["ttl_hours"], int)
        assert config["ttl_hours"] == 36
        assert isinstance(config["size_threshold_kb"], int)
        assert config["size_threshold_kb"] == 75
        assert isinstance(config["cleanup_interval_minutes"], int)
        assert config["cleanup_interval_minutes"] == 45
