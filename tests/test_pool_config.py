"""
Tests for browser pool configuration parser

Tests the hierarchical configuration system (Global → Pool → Instance)
"""

import os
import pytest

from playwright_proxy_mcp.playwright.config import (
    load_pool_manager_config,
    _discover_pools,
    _parse_global_config,
    _validate_alias,
)


class TestGlobalConfigParsing:
    """Test global configuration parsing"""

    def test_parse_global_config_empty(self, monkeypatch):
        """Test with no global config set"""
        # Clear all PW_MCP_PROXY env vars
        for key in list(os.environ.keys()):
            if key.startswith("PW_MCP_PROXY"):
                monkeypatch.delenv(key, raising=False)

        config = _parse_global_config()
        assert config == {}

    def test_parse_global_config_browser(self, monkeypatch):
        """Test parsing BROWSER global config"""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "firefox")

        config = _parse_global_config()
        assert config["browser"] == "firefox"

    def test_parse_global_config_multiple(self, monkeypatch):
        """Test parsing multiple global config values"""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "20000")

        config = _parse_global_config()
        assert config["browser"] == "firefox"
        assert config["headless"] is True
        assert config["timeout_action"] == 20000


class TestPoolDiscovery:
    """Test pool discovery from environment variables"""

    def test_discover_no_pools(self, monkeypatch):
        """Test when no pools are defined"""
        # Clear all pool env vars
        for key in list(os.environ.keys()):
            if key.startswith("PW_MCP_PROXY__"):
                monkeypatch.delenv(key, raising=False)

        pools = _discover_pools()
        assert pools == []

    def test_discover_single_pool(self, monkeypatch):
        """Test discovering single pool"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "3")

        pools = _discover_pools()
        assert pools == ["DEFAULT"]

    def test_discover_multiple_pools(self, monkeypatch):
        """Test discovering multiple pools"""
        monkeypatch.setenv("PW_MCP_PROXY__CHROMIUM_INSTANCES", "5")
        monkeypatch.setenv("PW_MCP_PROXY__FIREFOX_INSTANCES", "3")
        monkeypatch.setenv("PW_MCP_PROXY__WEBKIT_INSTANCES", "2")

        pools = _discover_pools()
        # Should be sorted alphabetically
        assert pools == ["CHROMIUM", "FIREFOX", "WEBKIT"]

    def test_discover_excludes_instance_vars(self, monkeypatch):
        """Test that instance-level vars don't create duplicate pools"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__0_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__1_BROWSER", "chrome")

        pools = _discover_pools()
        # Should only find DEFAULT once
        assert pools == ["DEFAULT"]


class TestAliasValidation:
    """Test alias validation rules"""

    def test_valid_alias(self):
        """Test that valid aliases pass validation"""
        # Should not raise
        _validate_alias("main_browser", "DEFAULT", "0")
        _validate_alias("debug-firefox", "DEFAULT", "1")
        _validate_alias("test1", "DEFAULT", "2")

    def test_numeric_alias_rejected(self):
        """Test that numeric aliases are rejected"""
        with pytest.raises(ValueError, match="looks like instance ID"):
            _validate_alias("0", "DEFAULT", "0")

        with pytest.raises(ValueError, match="looks like instance ID"):
            _validate_alias("123", "DEFAULT", "1")


class TestPoolManagerConfig:
    """Test complete pool manager configuration loading"""

    def setup_method(self):
        """Clear all relevant env vars before each test"""
        for key in list(os.environ.keys()):
            if key.startswith("PW_MCP_PROXY"):
                os.environ.pop(key, None)

    def test_no_pools_defined_error(self, monkeypatch):
        """Test error when no pools are defined"""
        # Clear all pool env vars
        for key in list(os.environ.keys()):
            if key.startswith("PW_MCP_PROXY__"):
                monkeypatch.delenv(key, raising=False)

        with pytest.raises(ValueError, match="No pools defined"):
            load_pool_manager_config()

    def test_missing_instances_error(self, monkeypatch):
        """Test error when pool missing INSTANCES"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        # Missing INSTANCES

        with pytest.raises(ValueError, match="missing required INSTANCES"):
            load_pool_manager_config()

    def test_global_instances_error(self, monkeypatch):
        """Test error when INSTANCES set globally"""
        monkeypatch.setenv("PW_MCP_PROXY_INSTANCES", "3")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        with pytest.raises(ValueError, match="PW_MCP_PROXY_INSTANCES is not allowed"):
            load_pool_manager_config()

    def test_no_default_pool_error(self, monkeypatch):
        """Test error when no default pool defined"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "3")
        # Missing IS_DEFAULT

        with pytest.raises(ValueError, match="No default pool defined"):
            load_pool_manager_config()

    def test_multiple_default_pools_error(self, monkeypatch):
        """Test error when multiple default pools"""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_INSTANCES", "3")
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_IS_DEFAULT", "true")

        with pytest.raises(ValueError, match="Multiple default pools defined"):
            load_pool_manager_config()

    def test_duplicate_alias_error(self, monkeypatch):
        """Test error when duplicate aliases in pool"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__0_ALIAS", "debug")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__1_ALIAS", "debug")  # Duplicate

        with pytest.raises(ValueError, match="Duplicate alias"):
            load_pool_manager_config()

    def test_single_pool_minimal_config(self, monkeypatch):
        """Test minimal valid configuration with single pool"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        assert len(config["pools"]) == 1
        assert config["default_pool_name"] == "DEFAULT"
        assert config["pools"][0]["name"] == "DEFAULT"
        assert config["pools"][0]["instances"] == 2
        assert config["pools"][0]["is_default"] is True

    def test_global_defaults_applied(self, monkeypatch):
        """Test that global defaults are applied to pools"""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY_HEADLESS", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        pool = config["pools"][0]
        assert pool["base_config"]["browser"] == "firefox"
        assert pool["base_config"]["headless"] is True

    def test_pool_overrides_global(self, monkeypatch):
        """Test that pool-level config overrides global"""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "chromium")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_BROWSER", "firefox")  # Override

        config = load_pool_manager_config()

        pool = config["pools"][0]
        assert pool["base_config"]["browser"] == "firefox"

    def test_instance_overrides_pool(self, monkeypatch):
        """Test that instance-level config overrides pool"""
        monkeypatch.setenv("PW_MCP_PROXY_BROWSER", "chromium")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__1_BROWSER", "webkit")  # Instance override

        config = load_pool_manager_config()

        pool = config["pools"][0]
        instance_configs = pool["instance_configs"]

        # Instance 0 uses pool default (firefox)
        assert instance_configs[0]["config"]["browser"] == "firefox"

        # Instance 1 uses instance override (webkit)
        assert instance_configs[1]["config"]["browser"] == "webkit"

    def test_instance_alias(self, monkeypatch):
        """Test instance alias configuration"""
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__0_ALIAS", "main_browser")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__1_ALIAS", "debug_browser")

        config = load_pool_manager_config()

        pool = config["pools"][0]
        instance_configs = pool["instance_configs"]

        assert instance_configs[0]["alias"] == "main_browser"
        assert instance_configs[1]["alias"] == "debug_browser"

    def test_multiple_pools(self, monkeypatch):
        """Test configuration with multiple pools"""
        # Pool 1: CHROMIUM (default)
        monkeypatch.setenv("PW_MCP_PROXY__CHROMIUM_INSTANCES", "5")
        monkeypatch.setenv("PW_MCP_PROXY__CHROMIUM_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__CHROMIUM_BROWSER", "chromium")
        monkeypatch.setenv("PW_MCP_PROXY__CHROMIUM_DESCRIPTION", "Main pool")

        # Pool 2: FIREFOX
        monkeypatch.setenv("PW_MCP_PROXY__FIREFOX_INSTANCES", "3")
        monkeypatch.setenv("PW_MCP_PROXY__FIREFOX_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY__FIREFOX_DESCRIPTION", "Firefox testing")

        config = load_pool_manager_config()

        assert len(config["pools"]) == 2
        assert config["default_pool_name"] == "CHROMIUM"

        # Find pools by name
        chromium_pool = next(p for p in config["pools"] if p["name"] == "CHROMIUM")
        firefox_pool = next(p for p in config["pools"] if p["name"] == "FIREFOX")

        assert chromium_pool["instances"] == 5
        assert chromium_pool["is_default"] is True
        assert chromium_pool["description"] == "Main pool"
        assert chromium_pool["base_config"]["browser"] == "chromium"

        assert firefox_pool["instances"] == 3
        assert firefox_pool["is_default"] is False
        assert firefox_pool["description"] == "Firefox testing"
        assert firefox_pool["base_config"]["browser"] == "firefox"

    def test_precedence_chain(self, monkeypatch):
        """Test complete precedence chain: Global → Pool → Instance"""
        # Global: timeout=10000
        monkeypatch.setenv("PW_MCP_PROXY_TIMEOUT_ACTION", "10000")

        # Pool: timeout=20000 (overrides global)
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "3")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_TIMEOUT_ACTION", "20000")

        # Instance 2: timeout=30000 (overrides pool)
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT__2_TIMEOUT_ACTION", "30000")

        config = load_pool_manager_config()

        pool = config["pools"][0]
        instances = pool["instance_configs"]

        # Instance 0: uses pool default (20000)
        assert instances[0]["config"]["timeout_action"] == 20000

        # Instance 1: uses pool default (20000)
        assert instances[1]["config"]["timeout_action"] == 20000

        # Instance 2: uses instance override (30000)
        assert instances[2]["config"]["timeout_action"] == 30000

    def test_wsl_windows_config(self, monkeypatch):
        """Test WSL Windows configuration"""
        monkeypatch.setenv("PW_MCP_PROXY_WSL_WINDOWS", "true")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_INSTANCES", "1")
        monkeypatch.setenv("PW_MCP_PROXY__DEFAULT_IS_DEFAULT", "true")

        config = load_pool_manager_config()

        pool = config["pools"][0]
        assert pool["base_config"]["wsl_windows"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
