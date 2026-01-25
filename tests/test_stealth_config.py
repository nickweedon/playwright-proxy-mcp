"""Tests for stealth configuration"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from playwright_proxy_mcp.playwright.config import load_pool_manager_config


class TestStealthConfig:
    """Test stealth configuration loading"""

    def test_stealth_mode_disabled_by_default(self):
        """Test that stealth mode is disabled by default"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            # init_script should not be in global config when stealth mode is disabled
            assert "init_script" not in pool_config["global_config"]

    def test_custom_user_agent(self):
        """Test custom user agent configuration"""
        custom_ua = "Mozilla/5.0 (Custom Browser)"
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY_USER_AGENT": custom_ua,
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            assert pool_config["global_config"]["user_agent"] == custom_ua

    def test_ignore_https_errors_default(self):
        """Test ignore HTTPS errors is false by default (not in config when unset)"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            # ignore_https_errors should not be in config when env var is not set
            assert "ignore_https_errors" not in pool_config["global_config"]

    def test_ignore_https_errors_enabled(self):
        """Test ignore HTTPS errors can be enabled"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY_IGNORE_HTTPS_ERRORS": "true",
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            assert pool_config["global_config"]["ignore_https_errors"] is True

    def test_stealth_script_exists(self):
        """Test that the bundled stealth.js file exists"""
        # Get the path to the stealth script
        from playwright_proxy_mcp.playwright import config as config_module

        stealth_script_path = Path(config_module.__file__).parent / "stealth.js"
        assert stealth_script_path.exists(), f"Stealth script not found at {stealth_script_path}"

        # Verify it has content
        content = stealth_script_path.read_text()
        assert len(content) > 100, "Stealth script appears to be empty or too small"

        # Check for key anti-detection techniques
        assert "navigator.webdriver" in content
        assert "chrome.runtime" in content
        assert "WebGL" in content
        assert "plugins" in content

    def test_enable_stealth_macro_global(self):
        """Test that ENABLE_STEALTH macro applies stealth defaults at global level"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY_ENABLE_STEALTH": "true",
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            global_config = pool_config["global_config"]

            # Check that stealth defaults were applied
            assert "init_script" in global_config
            assert global_config["init_script"].endswith("stealth.js")
            assert "headless" in global_config
            assert global_config["headless"] is False
            assert "user_agent" in global_config
            assert "Chrome" in global_config["user_agent"]

    def test_enable_stealth_macro_pool_level(self):
        """Test that ENABLE_STEALTH macro works at pool level"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
                "PW_MCP_PROXY__STEALTH_INSTANCES": "1",
                "PW_MCP_PROXY__STEALTH_ENABLE_STEALTH": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()

            # Global config should not have stealth settings
            assert "init_script" not in pool_config["global_config"]

            # Find the STEALTH pool
            stealth_pool = None
            for pool in pool_config["pools"]:
                if pool["name"] == "STEALTH":
                    stealth_pool = pool
                    break

            assert stealth_pool is not None, "STEALTH pool not found"

            # Check that stealth defaults were applied to pool
            base_config = stealth_pool["base_config"]
            assert "init_script" in base_config
            assert base_config["init_script"].endswith("stealth.js")
            assert "headless" in base_config
            assert base_config["headless"] is False
            assert "user_agent" in base_config

    def test_enable_stealth_macro_instance_level(self):
        """Test that ENABLE_STEALTH macro works at instance level"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "2",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
                "PW_MCP_PROXY__DEFAULT__0_ENABLE_STEALTH": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()

            # Get the DEFAULT pool
            default_pool = pool_config["pools"][0]
            assert default_pool["name"] == "DEFAULT"

            # Instance 0 should have stealth init_script (key indicator of stealth macro)
            instance_0_config = default_pool["instance_configs"][0]["config"]
            assert "init_script" in instance_0_config
            assert instance_0_config["init_script"].endswith("stealth.js")
            assert "user_agent" in instance_0_config
            assert "Chrome" in instance_0_config["user_agent"]

            # Instance 1 should NOT have stealth init_script (key difference)
            instance_1_config = default_pool["instance_configs"][1]["config"]
            assert "init_script" not in instance_1_config
            # Note: user_agent from stealth macro should not be in instance 1
            # (it might inherit headless from global defaults, which is OK)

    def test_enable_stealth_respects_manual_overrides(self):
        """Test that manual config can override ENABLE_STEALTH defaults"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY_ENABLE_STEALTH": "true",
                "PW_MCP_PROXY_HEADLESS": "true",  # Override to stay headless
                "PW_MCP_PROXY_USER_AGENT": "CustomAgent/1.0",
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            global_config = pool_config["global_config"]

            # init_script should be set by macro
            assert "init_script" in global_config
            assert global_config["init_script"].endswith("stealth.js")

            # But headless and user_agent should use manual overrides
            assert global_config["headless"] is True
            assert global_config["user_agent"] == "CustomAgent/1.0"

    def test_enable_stealth_false_no_defaults(self):
        """Test that ENABLE_STEALTH=false does not apply stealth macro defaults"""
        with patch.dict(
            os.environ,
            {
                "PW_MCP_PROXY_ENABLE_STEALTH": "false",
                "PW_MCP_PROXY__DEFAULT_INSTANCES": "1",
                "PW_MCP_PROXY__DEFAULT_IS_DEFAULT": "true",
            },
            clear=True,
        ):
            pool_config = load_pool_manager_config()
            global_config = pool_config["global_config"]

            # Stealth-specific settings should not be applied
            assert "init_script" not in global_config
            assert "user_agent" not in global_config
            # Note: headless might have a default value from config loader (not stealth macro)
            # The key is that init_script and user_agent are NOT set
