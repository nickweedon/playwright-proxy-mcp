"""
Tests for configuration loading
"""

from playwright_proxy_mcp.playwright.config import load_blob_config, load_pool_manager_config


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
