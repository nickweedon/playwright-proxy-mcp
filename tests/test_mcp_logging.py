"""Tests for MCPLoggingMiddleware"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from playwright_proxy_mcp.middleware.mcp_logging import MCPLoggingMiddleware


class TestMCPLoggingMiddleware:
    """Tests for the MCPLoggingMiddleware class"""

    @pytest.fixture
    def middleware_default(self):
        """Create middleware with default settings"""
        return MCPLoggingMiddleware()

    @pytest.fixture
    def middleware_full_logging(self):
        """Create middleware with full logging enabled"""
        return MCPLoggingMiddleware(
            log_request_params=True, log_response_data=True, max_log_length=10000
        )

    @pytest.fixture
    def mock_context(self):
        """Create a mock MiddlewareContext"""
        context = MagicMock()
        context.message = MagicMock()
        return context

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function"""
        return AsyncMock(return_value={"result": "success"})

    def test_init_default(self, middleware_default):
        """Test middleware initialization with defaults"""
        assert middleware_default.log_request_params is True
        assert middleware_default.log_response_data is False
        assert middleware_default.max_log_length == 5000

    def test_init_full_logging(self, middleware_full_logging):
        """Test middleware initialization with full logging"""
        assert middleware_full_logging.log_request_params is True
        assert middleware_full_logging.log_response_data is True
        assert middleware_full_logging.max_log_length == 10000

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_request(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test that tool calls log request parameters"""
        # Setup mock context
        mock_context.message.name = "browser_navigate"
        mock_context.message.arguments = {"url": "https://example.com"}

        # Call middleware
        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_call_tool(mock_context, mock_call_next)

        # Verify result passed through
        assert result == {"result": "success"}

        # Verify logging occurred
        assert "CLIENT_MCP → Tool call: browser_navigate" in caplog.text
        assert "CLIENT_MCP   Tool 'browser_navigate' arguments:" in caplog.text
        assert "https://example.com" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_response(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test that tool calls log response data when enabled"""
        # Setup mock context
        mock_context.message.name = "browser_navigate"
        mock_context.message.arguments = {"url": "https://example.com"}
        mock_call_next.return_value = {"content": [{"type": "text", "text": "Page loaded"}]}

        # Call middleware
        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_call_tool(mock_context, mock_call_next)

        # Verify result passed through
        assert result["content"][0]["text"] == "Page loaded"

        # Verify response logging occurred
        assert "CLIENT_MCP ← Tool result: browser_navigate" in caplog.text
        assert "CLIENT_MCP   Tool 'browser_navigate' result:" in caplog.text
        assert "Page loaded" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_no_response_logging_when_disabled(
        self, middleware_default, mock_context, mock_call_next, caplog
    ):
        """Test that response data is not logged when log_response_data=False"""
        # Setup mock context
        mock_context.message.name = "browser_navigate"
        mock_context.message.arguments = {"url": "https://example.com"}
        mock_call_next.return_value = {"content": [{"type": "text", "text": "Page loaded"}]}

        # Call middleware (default has log_response_data=False)
        with caplog.at_level(logging.INFO):
            await middleware_default.on_call_tool(mock_context, mock_call_next)

        # Verify response logging did NOT occur
        assert "CLIENT_MCP   Tool 'browser_navigate' result:" not in caplog.text
        assert "Page loaded" not in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_timing(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test that tool calls log execution time"""
        # Setup mock context
        mock_context.message.name = "browser_navigate"
        mock_context.message.arguments = {"url": "https://example.com"}

        # Call middleware
        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_call_tool(mock_context, mock_call_next)

        # Verify timing logged
        assert "CLIENT_MCP ← Tool result: browser_navigate" in caplog.text
        assert "ms)" in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_logs_errors(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test that tool errors are logged"""
        # Setup mock context
        mock_context.message.name = "browser_navigate"
        mock_context.message.arguments = {"url": "https://example.com"}

        # Mock call_next to raise an error
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("Navigation failed"))

        # Call middleware and expect error
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_call_tool(mock_context, mock_call_next_error)

        # Verify error logging
        assert "CLIENT_MCP ✗ Tool error: browser_navigate" in caplog.text
        assert "RuntimeError: Navigation failed" in caplog.text

    def test_truncate_data_small(self, middleware_full_logging):
        """Test that small data is not truncated"""
        data = {"key": "value"}
        result = middleware_full_logging._truncate_data(data, max_length=100)
        assert '"key": "value"' in result
        assert "..." not in result

    def test_truncate_data_large(self, middleware_full_logging):
        """Test that large data is truncated"""
        data = {"key": "x" * 10000}
        result = middleware_full_logging._truncate_data(data, max_length=100)
        assert len(result) <= 150  # 100 + some buffer for truncation message
        assert "..." in result
        assert "chars total" in result

    def test_truncate_data_with_custom_max_length(self, middleware_full_logging):
        """Test truncation with custom max_log_length from init"""
        # middleware_full_logging has max_log_length=10000
        data = {"key": "x" * 5000}
        result = middleware_full_logging._truncate_data(
            data, max_length=middleware_full_logging.max_log_length
        )
        # Should not truncate because data is < 10000 chars
        assert "..." not in result

    @pytest.mark.asyncio
    async def test_on_read_resource(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test resource read logging"""
        # Setup mock context
        mock_context.message.uri = "playwright-proxy://status"

        # Call middleware
        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_read_resource(mock_context, mock_call_next)

        # Verify logging
        assert "CLIENT_MCP → Resource read: playwright-proxy://status" in caplog.text
        assert "CLIENT_MCP ← Resource result: playwright-proxy://status" in caplog.text

    @pytest.mark.asyncio
    async def test_on_get_prompt(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test prompt request logging"""
        # Setup mock context
        mock_context.message.name = "test_prompt"
        mock_context.message.arguments = {"arg1": "value1"}

        # Call middleware
        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_get_prompt(mock_context, mock_call_next)

        # Verify logging
        assert "CLIENT_MCP → Prompt request: test_prompt" in caplog.text
        assert "CLIENT_MCP   Prompt arguments:" in caplog.text
        assert "value1" in caplog.text

    @pytest.mark.asyncio
    async def test_on_initialize(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test initialization logging"""
        # Setup mock context with nested Pydantic models
        mock_context.message.params = MagicMock()
        mock_context.message.params.clientInfo = MagicMock()
        mock_context.message.params.clientInfo.name = "Claude Desktop"
        mock_context.message.params.clientInfo.version = "1.0.0"
        mock_context.message.params.protocolVersion = "2024-11-05"

        # Call middleware
        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_initialize(mock_context, mock_call_next)

        # Verify logging
        assert "CLIENT_MCP → Initialize: Claude Desktop v1.0.0" in caplog.text
        assert "protocol: 2024-11-05" in caplog.text
        assert "CLIENT_MCP ← Initialize complete" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_tools(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test list tools logging"""
        # Mock returns a list of tools
        mock_call_next.return_value = [{"name": "tool1"}, {"name": "tool2"}, {"name": "tool3"}]

        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_list_tools(mock_context, mock_call_next)

        assert len(result) == 3
        assert "CLIENT_MCP → List tools" in caplog.text
        assert "CLIENT_MCP ← List tools result: 3 tools" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_tools_error(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test list tools error logging"""
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("List tools failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_list_tools(mock_context, mock_call_next_error)

        assert "CLIENT_MCP ✗ List tools error:" in caplog.text
        assert "RuntimeError: List tools failed" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_resources(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test list resources logging"""
        mock_call_next.return_value = [{"uri": "res1"}, {"uri": "res2"}]

        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_list_resources(mock_context, mock_call_next)

        assert len(result) == 2
        assert "CLIENT_MCP → List resources" in caplog.text
        assert "CLIENT_MCP ← List resources result: 2 resources" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_resources_error(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test list resources error logging"""
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("List resources failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_list_resources(mock_context, mock_call_next_error)

        assert "CLIENT_MCP ✗ List resources error:" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_prompts(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test list prompts logging"""
        mock_call_next.return_value = [{"name": "prompt1"}]

        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_list_prompts(mock_context, mock_call_next)

        assert len(result) == 1
        assert "CLIENT_MCP → List prompts" in caplog.text
        assert "CLIENT_MCP ← List prompts result: 1 prompts" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_prompts_error(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test list prompts error logging"""
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("List prompts failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_list_prompts(mock_context, mock_call_next_error)

        assert "CLIENT_MCP ✗ List prompts error:" in caplog.text

    @pytest.mark.asyncio
    async def test_on_read_resource_error(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test resource read error logging"""
        mock_context.message.uri = "playwright-proxy://status"
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("Resource read failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_read_resource(mock_context, mock_call_next_error)

        assert "CLIENT_MCP ✗ Resource error: playwright-proxy://status" in caplog.text
        assert "RuntimeError: Resource read failed" in caplog.text

    @pytest.mark.asyncio
    async def test_on_get_prompt_error(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test prompt request error logging"""
        mock_context.message.name = "test_prompt"
        mock_context.message.arguments = {}
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("Prompt failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_get_prompt(mock_context, mock_call_next_error)

        assert "CLIENT_MCP ✗ Prompt error: test_prompt" in caplog.text

    @pytest.mark.asyncio
    async def test_on_initialize_error(
        self, middleware_full_logging, mock_context, caplog
    ):
        """Test initialization error logging"""
        mock_context.message.params = MagicMock()
        mock_context.message.params.clientInfo = MagicMock()
        mock_context.message.params.clientInfo.name = "Test Client"
        mock_context.message.params.clientInfo.version = "1.0.0"
        mock_context.message.params.protocolVersion = "2024-11-05"
        mock_call_next_error = AsyncMock(side_effect=RuntimeError("Init failed"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await middleware_full_logging.on_initialize(mock_context, mock_call_next_error)

        assert "CLIENT_MCP ✗ Initialize error:" in caplog.text

    @pytest.mark.asyncio
    async def test_on_initialize_no_params(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test initialization logging with missing params"""
        mock_context.message.params = None

        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_initialize(mock_context, mock_call_next)

        assert "CLIENT_MCP → Initialize: unknown vunknown (protocol: unknown)" in caplog.text

    @pytest.mark.asyncio
    async def test_on_initialize_no_client_info(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test initialization logging with missing client info"""
        mock_context.message.params = MagicMock()
        mock_context.message.params.clientInfo = None
        mock_context.message.params.protocolVersion = "2024-11-05"

        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_initialize(mock_context, mock_call_next)

        assert "CLIENT_MCP → Initialize: unknown vunknown (protocol: 2024-11-05)" in caplog.text

    def test_log_arguments_empty(self, middleware_full_logging, caplog):
        """Test logging empty arguments"""
        with caplog.at_level(logging.INFO):
            middleware_full_logging._log_arguments("test_tool", {})

        assert "CLIENT_MCP   Tool 'test_tool' arguments: (none)" in caplog.text

    def test_log_arguments_with_data(self, middleware_full_logging, caplog):
        """Test logging arguments with data"""
        with caplog.at_level(logging.INFO):
            middleware_full_logging._log_arguments("test_tool", {"key": "value"})

        assert "CLIENT_MCP   Tool 'test_tool' arguments:" in caplog.text
        assert "key" in caplog.text

    def test_log_result(self, middleware_full_logging, caplog):
        """Test logging result"""
        with caplog.at_level(logging.INFO):
            middleware_full_logging._log_result("test_tool", {"result": "success"})

        assert "CLIENT_MCP   Tool 'test_tool' result:" in caplog.text
        assert "success" in caplog.text

    def test_truncate_data_json_serialization_failure(self, middleware_full_logging):
        """Test truncation when JSON serialization fails"""
        # Create object that can't be JSON serialized
        class UnserializableObject:
            def __str__(self):
                return "unserializable_str_representation"

        data = {"obj": UnserializableObject()}
        result = middleware_full_logging._truncate_data(data, max_length=100)
        # Should fall back to str() representation
        assert "unserializable_str_representation" in result

    def test_truncate_data_str_fallback_truncation(self, middleware_full_logging):
        """Test truncation with str fallback for large data"""
        class LargeUnserializable:
            def __str__(self):
                return "x" * 10000

        data = LargeUnserializable()
        result = middleware_full_logging._truncate_data(data, max_length=100)
        assert len(result) <= 150
        assert "..." in result

    @pytest.mark.asyncio
    async def test_on_list_tools_empty_result(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test list tools with empty result"""
        mock_call_next.return_value = []

        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_list_tools(mock_context, mock_call_next)

        assert result == []
        assert "CLIENT_MCP ← List tools result: 0 tools" in caplog.text

    @pytest.mark.asyncio
    async def test_on_list_resources_none_result(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test list resources with None result"""
        mock_call_next.return_value = None

        with caplog.at_level(logging.INFO):
            result = await middleware_full_logging.on_list_resources(mock_context, mock_call_next)

        assert result is None
        assert "CLIENT_MCP ← List resources result: 0 resources" in caplog.text

    @pytest.mark.asyncio
    async def test_on_get_prompt_no_arguments(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test prompt request with no arguments"""
        mock_context.message.name = "test_prompt"
        mock_context.message.arguments = None

        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_get_prompt(mock_context, mock_call_next)

        assert "CLIENT_MCP → Prompt request: test_prompt" in caplog.text
        # Should not log arguments when None
        assert "Prompt arguments:" not in caplog.text

    @pytest.mark.asyncio
    async def test_on_call_tool_unknown_name(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test tool call with missing name attribute"""
        # Simulate missing name attribute
        del mock_context.message.name
        mock_context.message.arguments = {}

        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_call_tool(mock_context, mock_call_next)

        assert "CLIENT_MCP → Tool call: unknown" in caplog.text

    @pytest.mark.asyncio
    async def test_on_read_resource_unknown_uri(
        self, middleware_full_logging, mock_context, mock_call_next, caplog
    ):
        """Test resource read with missing uri attribute"""
        del mock_context.message.uri

        with caplog.at_level(logging.INFO):
            await middleware_full_logging.on_read_resource(mock_context, mock_call_next)

        assert "CLIENT_MCP → Resource read: unknown" in caplog.text
