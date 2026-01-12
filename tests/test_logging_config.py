"""Tests for logging_config utilities"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from playwright_proxy_mcp.utils.logging_config import (
    get_logger,
    log_dict,
    log_tool_result,
    setup_file_logging,
)


class TestSetupFileLogging:
    """Tests for setup_file_logging function"""

    def test_setup_file_logging_default(self):
        """Test setup_file_logging with default parameters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_file_logging(log_file=log_file)

            assert logger is not None
            logger.info("Test message")

            # Verify log file was created
            assert log_file.exists()

    def test_setup_file_logging_custom_level(self):
        """Test setup_file_logging with custom log level"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_file_logging(log_file=log_file, level=logging.DEBUG)

            # Logger should accept DEBUG level messages
            assert logger.level <= logging.DEBUG

    def test_setup_file_logging_custom_format(self):
        """Test setup_file_logging with custom format string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            custom_format = "%(levelname)s: %(message)s"
            logger = setup_file_logging(log_file=log_file, format_string=custom_format)

            logger.info("Custom format test")
            assert log_file.exists()

    def test_setup_file_logging_creates_directory(self):
        """Test that setup_file_logging creates parent directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "nested" / "test.log"
            setup_file_logging(log_file=log_file)

            # Directory should be created
            assert log_file.parent.exists()

    def test_setup_file_logging_fallback_to_tmp(self):
        """Test fallback to /tmp when directory is not writable"""
        # Test with a path that already exists but writing fails
        # The fallback logic catches OSError and PermissionError
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file where we expect a directory - this simulates write failure
            blocking_file = Path(tmpdir) / "blocked"
            blocking_file.touch()

            # Try to use that file as a parent directory
            log_file = blocking_file / "test.log"

            # The function should catch the error and fall back to /tmp
            logger = setup_file_logging(log_file=log_file)
            assert logger is not None


class TestGetLogger:
    """Tests for get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test get_logger returns a logger instance"""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_same_name_returns_same_logger(self):
        """Test get_logger returns same logger for same name"""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")
        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """Test get_logger returns different loggers for different names"""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")
        assert logger1 is not logger2


class TestLogDict:
    """Tests for log_dict function"""

    def test_log_dict_logs_message_and_data(self, caplog):
        """Test log_dict logs message and key-value pairs"""
        logger = logging.getLogger("test_log_dict")

        with caplog.at_level(logging.INFO):
            log_dict(logger, "Test data:", {"name": "value1", "count": 42})

        assert "Test data:" in caplog.text
        assert "name: value1" in caplog.text
        assert "count: 42" in caplog.text

    def test_log_dict_redacts_sensitive_values(self, caplog):
        """Test log_dict redacts sensitive values"""
        logger = logging.getLogger("test_log_dict_sensitive")

        with caplog.at_level(logging.INFO):
            log_dict(
                logger,
                "Config:",
                {
                    "api_token": "secret123",
                    "password": "mypassword",
                    "secret_data": "abc",
                    "normal_value": "visible",
                },
            )

        assert "***REDACTED***" in caplog.text
        assert "secret123" not in caplog.text
        assert "mypassword" not in caplog.text
        assert "normal_value: visible" in caplog.text

    def test_log_dict_custom_level(self, caplog):
        """Test log_dict with custom log level"""
        logger = logging.getLogger("test_log_dict_level")

        with caplog.at_level(logging.WARNING):
            log_dict(logger, "Warning:", {"issue": "test"}, level=logging.WARNING)

        assert "Warning:" in caplog.text
        assert "issue: test" in caplog.text


class TestLogToolResult:
    """Tests for log_tool_result decorator"""

    @pytest.mark.asyncio
    async def test_log_tool_result_logs_json(self, caplog):
        """Test decorator logs result as JSON"""
        logger = logging.getLogger("test_tool_result")

        @log_tool_result(logger)
        async def test_tool():
            return {"result": "success", "count": 42}

        with caplog.at_level(logging.INFO):
            result = await test_tool()

        assert result == {"result": "success", "count": 42}
        assert "TOOL_RESULT [test_tool]" in caplog.text
        assert '"result": "success"' in caplog.text

    @pytest.mark.asyncio
    async def test_log_tool_result_without_logger(self, caplog):
        """Test decorator uses function module logger when not provided"""

        @log_tool_result()
        async def no_logger_tool():
            return {"value": 1}

        with caplog.at_level(logging.INFO):
            result = await no_logger_tool()

        assert result == {"value": 1}
        assert "TOOL_RESULT [no_logger_tool]" in caplog.text

    @pytest.mark.asyncio
    async def test_log_tool_result_non_json_serializable(self, caplog):
        """Test decorator handles non-JSON serializable results"""
        logger = logging.getLogger("test_non_json")

        class CustomObject:
            def __str__(self):
                return "custom_object_str"

        @log_tool_result(logger)
        async def custom_tool():
            return CustomObject()

        with caplog.at_level(logging.INFO):
            result = await custom_tool()

        # Should still return the result
        assert isinstance(result, CustomObject)
        # Should log something
        assert "TOOL_RESULT [custom_tool]" in caplog.text

    @pytest.mark.asyncio
    async def test_log_tool_result_preserves_function_name(self):
        """Test decorator preserves function name"""
        logger = logging.getLogger("test_preserve")

        @log_tool_result(logger)
        async def my_named_tool():
            return {}

        assert my_named_tool.__name__ == "my_named_tool"

    @pytest.mark.asyncio
    async def test_log_tool_result_with_arguments(self, caplog):
        """Test decorator works with function arguments"""
        logger = logging.getLogger("test_args")

        @log_tool_result(logger)
        async def tool_with_args(a, b, c=None):
            return {"sum": a + b, "c": c}

        with caplog.at_level(logging.INFO):
            result = await tool_with_args(1, 2, c="test")

        assert result == {"sum": 3, "c": "test"}
        assert "TOOL_RESULT [tool_with_args]" in caplog.text

    @pytest.mark.asyncio
    async def test_log_tool_result_with_exception(self, caplog):
        """Test decorator propagates exceptions"""
        logger = logging.getLogger("test_exception")

        @log_tool_result(logger)
        async def failing_tool():
            raise ValueError("Tool failed")

        with pytest.raises(ValueError, match="Tool failed"):
            await failing_tool()

    @pytest.mark.asyncio
    async def test_log_tool_result_serialization_fallback(self, caplog):
        """Test decorator falls back to str when JSON fails"""
        logger = logging.getLogger("test_fallback")

        # Create result that will cause JSON serialization to warn
        class PartiallySerializable:
            def __repr__(self):
                return "PartiallySerializable()"

        @log_tool_result(logger)
        async def partial_tool():
            # Return something that json.dumps with default=str will handle
            return {"obj": PartiallySerializable()}

        with caplog.at_level(logging.INFO):
            result = await partial_tool()

        assert "obj" in result
        assert "TOOL_RESULT [partial_tool]" in caplog.text
