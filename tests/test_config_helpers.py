"""Tests for config helper functions."""

import os
import pytest
from playwright_proxy_mcp.playwright.config import _apply_config_overrides


class TestApplyConfigOverrides:
    """Tests for _apply_config_overrides helper function."""

    def test_applies_browser_setting(self, monkeypatch):
        """Test that browser setting is applied."""
        monkeypatch.setenv("TEST_PREFIX_BROWSER", "firefox")
        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["browser"] == "firefox"

    def test_applies_boolean_settings(self, monkeypatch):
        """Test that boolean settings are applied correctly."""
        monkeypatch.setenv("TEST_PREFIX_HEADLESS", "true")
        monkeypatch.setenv("TEST_PREFIX_NO_SANDBOX", "false")
        monkeypatch.setenv("TEST_PREFIX_ISOLATED", "1")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["headless"] is True
        assert config["no_sandbox"] is False
        assert config["isolated"] is True

    def test_applies_string_settings(self, monkeypatch):
        """Test that string settings are applied."""
        monkeypatch.setenv("TEST_PREFIX_DEVICE", "iPhone 12")
        monkeypatch.setenv("TEST_PREFIX_VIEWPORT_SIZE", "1920x1080")
        monkeypatch.setenv("TEST_PREFIX_USER_AGENT", "Custom Agent")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["device"] == "iPhone 12"
        assert config["viewport_size"] == "1920x1080"
        assert config["user_agent"] == "Custom Agent"

    def test_applies_timeout_settings(self, monkeypatch):
        """Test that timeout settings are applied as integers."""
        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_ACTION", "30000")
        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_NAVIGATION", "10000")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["timeout_action"] == 30000
        assert config["timeout_navigation"] == 10000

    def test_applies_network_settings(self, monkeypatch):
        """Test that network settings are applied."""
        monkeypatch.setenv("TEST_PREFIX_ALLOWED_ORIGINS", "https://example.com")
        monkeypatch.setenv("TEST_PREFIX_BLOCKED_ORIGINS", "https://ads.com")
        monkeypatch.setenv("TEST_PREFIX_PROXY_SERVER", "http://proxy:8080")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["allowed_origins"] == "https://example.com"
        assert config["blocked_origins"] == "https://ads.com"
        assert config["proxy_server"] == "http://proxy:8080"

    def test_applies_output_settings(self, monkeypatch):
        """Test that output settings are applied."""
        monkeypatch.setenv("TEST_PREFIX_SAVE_SESSION", "true")
        monkeypatch.setenv("TEST_PREFIX_SAVE_TRACE", "false")
        monkeypatch.setenv("TEST_PREFIX_SAVE_VIDEO", "on-failure")
        monkeypatch.setenv("TEST_PREFIX_OUTPUT_DIR", "/tmp/output")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["save_session"] is True
        assert config["save_trace"] is False
        assert config["save_video"] == "on-failure"
        assert config["output_dir"] == "/tmp/output"

    def test_applies_extension_settings(self, monkeypatch):
        """Test that extension settings are applied."""
        monkeypatch.setenv("TEST_PREFIX_EXTENSION", "true")
        monkeypatch.setenv("TEST_PREFIX_EXTENSION_TOKEN", "test-token-123")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["extension"] is True
        assert config["extension_token"] == "test-token-123"

    def test_applies_wsl_windows_setting(self, monkeypatch):
        """Test that WSL Windows setting is applied."""
        monkeypatch.setenv("TEST_PREFIX_WSL_WINDOWS", "true")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["wsl_windows"] is True

    def test_applies_stealth_settings(self, monkeypatch):
        """Test that stealth settings are applied."""
        monkeypatch.setenv("TEST_PREFIX_IGNORE_HTTPS_ERRORS", "true")
        monkeypatch.setenv("TEST_PREFIX_INIT_SCRIPT", "console.log('init')")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["ignore_https_errors"] is True
        assert config["init_script"] == "console.log('init')"

    def test_only_applies_settings_that_are_set(self, monkeypatch):
        """Test that only env vars that are set get applied."""
        monkeypatch.setenv("TEST_PREFIX_BROWSER", "chrome")
        # Don't set HEADLESS

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert "browser" in config
        assert "headless" not in config

    def test_updates_existing_config(self, monkeypatch):
        """Test that existing config values are overridden."""
        monkeypatch.setenv("TEST_PREFIX_BROWSER", "firefox")
        monkeypatch.setenv("TEST_PREFIX_HEADLESS", "false")

        config = {
            "browser": "chromium",
            "headless": True,
            "device": "iPad",
        }
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert config["browser"] == "firefox"  # Overridden
        assert config["headless"] is False  # Overridden
        assert config["device"] == "iPad"  # Preserved

    def test_works_with_different_prefixes(self, monkeypatch):
        """Test that function works with different prefixes."""
        monkeypatch.setenv("POOL_A_BROWSER", "firefox")
        monkeypatch.setenv("POOL_B_BROWSER", "chromium")

        config_a = {}
        _apply_config_overrides(config_a, "POOL_A_")
        assert config_a["browser"] == "firefox"

        config_b = {}
        _apply_config_overrides(config_b, "POOL_B_")
        assert config_b["browser"] == "chromium"

    def test_applies_all_settings_together(self, monkeypatch):
        """Test applying multiple settings at once."""
        monkeypatch.setenv("TEST_PREFIX_BROWSER", "firefox")
        monkeypatch.setenv("TEST_PREFIX_HEADLESS", "true")
        monkeypatch.setenv("TEST_PREFIX_DEVICE", "iPhone 12")
        monkeypatch.setenv("TEST_PREFIX_TIMEOUT_ACTION", "20000")
        monkeypatch.setenv("TEST_PREFIX_SAVE_SESSION", "true")

        config = {}
        _apply_config_overrides(config, "TEST_PREFIX_")

        assert len(config) == 5
        assert config["browser"] == "firefox"
        assert config["headless"] is True
        assert config["device"] == "iPhone 12"
        assert config["timeout_action"] == 20000
        assert config["save_session"] is True
