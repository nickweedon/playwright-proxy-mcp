"""Tests for stealth configuration"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from playwright_proxy_mcp.playwright.config import load_playwright_config


class TestStealthConfig:
    """Test stealth configuration loading"""

    def test_stealth_mode_disabled_by_default(self):
        """Test that stealth mode is disabled by default"""
        with patch.dict(os.environ, {}, clear=True):
            config = load_playwright_config()
            assert "init_script" not in config

    def test_stealth_mode_enabled(self):
        """Test that stealth mode enables the bundled script"""
        with patch.dict(os.environ, {"PLAYWRIGHT_STEALTH_MODE": "true"}, clear=True):
            config = load_playwright_config()
            assert "init_script" in config
            assert config["init_script"].endswith("stealth.js")
            # Verify the file exists
            assert Path(config["init_script"]).exists()

    def test_custom_user_agent(self):
        """Test custom user agent configuration"""
        custom_ua = "Mozilla/5.0 (Custom Browser)"
        with patch.dict(os.environ, {"PLAYWRIGHT_USER_AGENT": custom_ua}, clear=True):
            config = load_playwright_config()
            assert config["user_agent"] == custom_ua

    def test_custom_init_script(self):
        """Test custom init script overrides bundled script"""
        custom_script = "/custom/path/to/script.js"
        with patch.dict(
            os.environ,
            {
                "PLAYWRIGHT_STEALTH_MODE": "true",
                "PLAYWRIGHT_INIT_SCRIPT": custom_script,
            },
            clear=True,
        ):
            config = load_playwright_config()
            assert config["init_script"] == custom_script

    def test_ignore_https_errors_default(self):
        """Test ignore HTTPS errors is false by default"""
        with patch.dict(os.environ, {}, clear=True):
            config = load_playwright_config()
            assert config["ignore_https_errors"] is False

    def test_ignore_https_errors_enabled(self):
        """Test ignore HTTPS errors can be enabled"""
        with patch.dict(os.environ, {"PLAYWRIGHT_IGNORE_HTTPS_ERRORS": "true"}, clear=True):
            config = load_playwright_config()
            assert config["ignore_https_errors"] is True

    def test_full_stealth_config(self):
        """Test complete stealth configuration"""
        custom_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0"
        with patch.dict(
            os.environ,
            {
                "PLAYWRIGHT_STEALTH_MODE": "true",
                "PLAYWRIGHT_USER_AGENT": custom_ua,
                "PLAYWRIGHT_IGNORE_HTTPS_ERRORS": "true",
                "PLAYWRIGHT_HEADLESS": "false",
            },
            clear=True,
        ):
            config = load_playwright_config()
            assert config["user_agent"] == custom_ua
            assert config["ignore_https_errors"] is True
            assert config["headless"] is False
            assert "init_script" in config
            assert config["init_script"].endswith("stealth.js")

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
