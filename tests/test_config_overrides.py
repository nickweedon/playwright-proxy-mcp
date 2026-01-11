"""
Comprehensive tests for config.py _apply_config_overrides function.

This module tests the high-complexity configuration override logic
to improve test coverage.
"""

import pytest
from playwright_proxy_mcp.playwright.config import (
    _apply_config_overrides,
    _discover_pools,
    _parse_pool_config,
    _parse_instance_config,
    _validate_pool_config,
    _validate_alias,
    PlaywrightConfig,
    InstanceConfig,
)


class TestApplyConfigOverridesComprehensive:
    """Comprehensive tests for _apply_config_overrides function."""

    def test_override_browser(self):
        """Test browser override."""
        base = PlaywrightConfig(browser="chromium")
        overrides = {"browser": "firefox"}

        result = _apply_config_overrides(base, overrides)

        assert result["browser"] == "firefox"

    def test_override_headless(self):
        """Test headless override."""
        base = PlaywrightConfig(headless=True)
        overrides = {"headless": False}

        result = _apply_config_overrides(base, overrides)

        assert result["headless"] is False

    def test_override_isolated(self):
        """Test isolated override."""
        base = PlaywrightConfig(isolated=False)
        overrides = {"isolated": True}

        result = _apply_config_overrides(base, overrides)

        assert result["isolated"] is True

    def test_override_save_session(self):
        """Test save_session override."""
        base = PlaywrightConfig(save_session=False)
        overrides = {"save_session": True}

        result = _apply_config_overrides(base, overrides)

        assert result["save_session"] is True

    def test_override_save_trace(self):
        """Test save_trace override."""
        base = PlaywrightConfig(save_trace=False)
        overrides = {"save_trace": True}

        result = _apply_config_overrides(base, overrides)

        assert result["save_trace"] is True

    def test_override_timeout(self):
        """Test timeout override."""
        base = PlaywrightConfig(timeout=30000)
        overrides = {"timeout": 60000}

        result = _apply_config_overrides(base, overrides)

        assert result["timeout"] == 60000

    def test_override_idle_timeout(self):
        """Test idle_timeout override."""
        base = PlaywrightConfig(idle_timeout=5000)
        overrides = {"idle_timeout": 10000}

        result = _apply_config_overrides(base, overrides)

        assert result["idle_timeout"] == 10000

    def test_override_output_dir(self):
        """Test output_dir override."""
        base = PlaywrightConfig(output_dir="/tmp/base")
        overrides = {"output_dir": "/tmp/override"}

        result = _apply_config_overrides(base, overrides)

        assert result["output_dir"] == "/tmp/override"

    def test_override_viewport_width(self):
        """Test viewport_width override."""
        base = PlaywrightConfig(viewport_width=1920)
        overrides = {"viewport_width": 1280}

        result = _apply_config_overrides(base, overrides)

        assert result["viewport_width"] == 1280

    def test_override_viewport_height(self):
        """Test viewport_height override."""
        base = PlaywrightConfig(viewport_height=1080)
        overrides = {"viewport_height": 720}

        result = _apply_config_overrides(base, overrides)

        assert result["viewport_height"] == 720

    def test_override_block_ads(self):
        """Test block_ads override."""
        base = PlaywrightConfig(block_ads=False)
        overrides = {"block_ads": True}

        result = _apply_config_overrides(base, overrides)

        assert result["block_ads"] is True

    def test_override_capture_har(self):
        """Test capture_har override."""
        base = PlaywrightConfig(capture_har=False)
        overrides = {"capture_har": True}

        result = _apply_config_overrides(base, overrides)

        assert result["capture_har"] is True

    def test_override_capture_console(self):
        """Test capture_console override."""
        base = PlaywrightConfig(capture_console=False)
        overrides = {"capture_console": True}

        result = _apply_config_overrides(base, overrides)

        assert result["capture_console"] is True

    def test_override_file_download(self):
        """Test file_download override."""
        base = PlaywrightConfig(file_download=False)
        overrides = {"file_download": True}

        result = _apply_config_overrides(base, overrides)

        assert result["file_download"] is True

    def test_override_extension_dir(self):
        """Test extension_dir override."""
        base = PlaywrightConfig(extension_dir=None)
        overrides = {"extension_dir": "/path/to/extensions"}

        result = _apply_config_overrides(base, overrides)

        assert result["extension_dir"] == "/path/to/extensions"

    def test_override_wsl_windows(self):
        """Test wsl_windows override."""
        base = PlaywrightConfig(wsl_windows=False)
        overrides = {"wsl_windows": True}

        result = _apply_config_overrides(base, overrides)

        assert result["wsl_windows"] is True

    def test_override_stealth_mode(self):
        """Test stealth_mode override."""
        base = PlaywrightConfig(stealth_mode=False)
        overrides = {"stealth_mode": True}

        result = _apply_config_overrides(base, overrides)

        assert result["stealth_mode"] is True

    def test_override_skip_automation_detection(self):
        """Test skip_automation_detection override."""
        base = PlaywrightConfig(skip_automation_detection=False)
        overrides = {"skip_automation_detection": True}

        result = _apply_config_overrides(base, overrides)

        assert result["skip_automation_detection"] is True

    def test_override_multiple_fields(self):
        """Test overriding multiple fields at once."""
        base = PlaywrightConfig(
            browser="chromium",
            headless=True,
            timeout=30000,
            viewport_width=1920
        )
        overrides = {
            "browser": "firefox",
            "headless": False,
            "timeout": 60000,
            "viewport_width": 1280,
            "stealth_mode": True
        }

        result = _apply_config_overrides(base, overrides)

        assert result["browser"] == "firefox"
        assert result["headless"] is False
        assert result["timeout"] == 60000
        assert result["viewport_width"] == 1280
        assert result["stealth_mode"] is True

    def test_override_empty_overrides(self):
        """Test that empty overrides don't change config."""
        base = PlaywrightConfig(browser="chromium", headless=True)
        overrides = {}

        result = _apply_config_overrides(base, overrides)

        assert result["browser"] == "chromium"
        assert result["headless"] is True

    def test_override_none_values_ignored(self):
        """Test that None values in overrides are ignored."""
        base = PlaywrightConfig(browser="chromium", timeout=30000)
        overrides = {"browser": "firefox", "timeout": None}

        result = _apply_config_overrides(base, overrides)

        assert result["browser"] == "firefox"
        assert result["timeout"] == 30000  # Not changed


class TestDiscoverPools:
    """Tests for _discover_pools function."""

    def test_discover_pools_from_env(self, monkeypatch):
        """Test discovering pools from environment variables."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1_INSTANCES", "2")
        monkeypatch.setenv("PW_MCP_PROXY__POOL2_INSTANCES", "1")
        monkeypatch.setenv("SOME_OTHER_VAR", "value")

        pools = _discover_pools()

        assert "POOL1" in pools
        assert "POOL2" in pools
        assert len(pools) == 2

    def test_discover_pools_no_pools(self, monkeypatch):
        """Test when no pool env vars are set."""
        # Clear all pool-related env vars
        for key in list(monkeypatch._setitem):
            if key.startswith("PW_MCP_PROXY__"):
                monkeypatch.delenv(key, raising=False)

        pools = _discover_pools()

        # Should discover the DEFAULT pool
        assert "DEFAULT" in pools


class TestValidatePoolConfig:
    """Tests for _validate_pool_config function."""

    def test_validate_valid_config(self):
        """Test validation of valid pool config."""
        config = {
            "POOL1": {
                "instances": [
                    InstanceConfig(id=0, alias=None, overrides={})
                ],
                "is_default": True
            }
        }

        # Should not raise
        _validate_pool_config(config, "POOL1")

    def test_validate_missing_default_pool(self):
        """Test validation fails when default pool is missing."""
        config = {
            "POOL1": {
                "instances": [],
                "is_default": False
            }
        }

        with pytest.raises(ValueError, match="No default pool configured"):
            _validate_pool_config(config, None)

    def test_validate_multiple_default_pools(self):
        """Test validation fails with multiple default pools."""
        config = {
            "POOL1": {
                "instances": [],
                "is_default": True
            },
            "POOL2": {
                "instances": [],
                "is_default": True
            }
        }

        with pytest.raises(ValueError, match="Multiple default pools"):
            _validate_pool_config(config, "POOL1")


class TestValidateAlias:
    """Tests for _validate_alias function."""

    def test_validate_valid_alias(self):
        """Test validation of valid alias."""
        # Should not raise
        _validate_alias("debug", "POOL1", [])

    def test_validate_duplicate_alias_in_pool(self):
        """Test validation fails with duplicate alias in same pool."""
        existing = [
            InstanceConfig(id=0, alias="debug", overrides={})
        ]

        with pytest.raises(ValueError, match="Duplicate alias 'debug'"):
            _validate_alias("debug", "POOL1", existing)

    def test_validate_alias_none_allowed(self):
        """Test that None alias is always allowed."""
        existing = [
            InstanceConfig(id=0, alias=None, overrides={})
        ]

        # Should not raise
        _validate_alias(None, "POOL1", existing)


class TestParseInstanceConfig:
    """Tests for _parse_instance_config function."""

    def test_parse_instance_with_alias(self, monkeypatch):
        """Test parsing instance with alias."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1__0_ALIAS", "debug")

        config = _parse_instance_config("POOL1", 0, {})

        assert config.id == 0
        assert config.alias == "debug"

    def test_parse_instance_with_overrides(self, monkeypatch):
        """Test parsing instance with config overrides."""
        monkeypatch.setenv("PW_MCP_PROXY__POOL1__0_BROWSER", "firefox")
        monkeypatch.setenv("PW_MCP_PROXY__POOL1__0_HEADLESS", "false")

        config = _parse_instance_config("POOL1", 0, {})

        assert config.overrides["browser"] == "firefox"
        assert config.overrides["headless"] == "false"

    def test_parse_instance_no_config(self):
        """Test parsing instance with no special config."""
        config = _parse_instance_config("POOL1", 0, {})

        assert config.id == 0
        assert config.alias is None
        assert config.overrides == {}
