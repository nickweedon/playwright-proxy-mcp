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
