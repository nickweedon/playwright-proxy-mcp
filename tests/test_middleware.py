"""
Tests for binary interception middleware
"""

import base64
from unittest.mock import AsyncMock, Mock

import pytest

from playwright_proxy_mcp.playwright.middleware import BinaryInterceptionMiddleware


@pytest.fixture
def mock_blob_manager():
    """Create a mock blob manager."""
    manager = Mock()
    manager.store_base64_data = AsyncMock()
    return manager


@pytest.fixture
def middleware(mock_blob_manager):
    """Create middleware instance."""
    return BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)


class TestBinaryInterceptionMiddleware:
    """Tests for BinaryInterceptionMiddleware."""

    def test_init(self, mock_blob_manager):
        """Test middleware initialization."""
        middleware = BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=100)

        assert middleware.blob_manager == mock_blob_manager
        assert middleware.size_threshold_bytes == 100 * 1024

    @pytest.mark.asyncio
    async def test_intercept_response_non_dict(self, middleware):
        """Test that non-dict responses are returned unchanged."""
        result = await middleware.intercept_response("some_tool", "string response")
        assert result == "string response"

        result = await middleware.intercept_response("some_tool", 123)
        assert result == 123

        result = await middleware.intercept_response("some_tool", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_intercept_response_calltoolresult_conversion(self, middleware):
        """Test that CallToolResult dataclass is converted to dict."""
        from dataclasses import dataclass
        from typing import Any

        @dataclass
        class MockCallToolResult:
            """Mock CallToolResult matching FastMCP Client's dataclass structure."""
            content: list[Any]
            structured_content: dict[str, Any] | None = None
            meta: dict[str, Any] | None = None
            data: Any = None
            is_error: bool = False

        # Create a mock CallToolResult
        mock_result = MockCallToolResult(
            content=[{"type": "text", "text": "Hello"}],
            structured_content=None,
            meta={"foo": "bar"},
            data=None,
            is_error=False,
        )

        # Test conversion for non-binary tool (should convert but not transform)
        result = await middleware.intercept_response("non_binary_tool", mock_result)

        # Should be converted to dict
        assert isinstance(result, dict)
        assert result["content"] == [{"type": "text", "text": "Hello"}]
        assert result["structured_content"] is None
        assert result["meta"] == {"foo": "bar"}
        assert result["data"] is None
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_intercept_response_non_binary_tool(self, middleware):
        """Test that responses from non-binary tools are returned unchanged."""
        response = {"status": "success", "data": "some data"}

        result = await middleware.intercept_response("non_binary_tool", response)

        assert result == response

    @pytest.mark.asyncio
    async def test_intercept_response_binary_tool_small_data(self, middleware):
        """Test that small binary data is not stored as blob."""
        # Create small data (less than 50KB threshold)
        small_data = b"x" * 100
        base64_data = base64.b64encode(small_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {"screenshot": data_uri}

        result = await middleware.intercept_response("playwright_screenshot", response)

        # Data should not be transformed
        assert result == response

    @pytest.mark.asyncio
    async def test_intercept_response_binary_tool_large_data(self, middleware, mock_blob_manager):
        """Test that large binary data is stored as blob."""
        # Create large data (more than 50KB threshold)
        large_data = b"x" * (60 * 1024)  # 60KB
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {"screenshot": data_uri}

        # Mock blob storage
        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test-123.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_screenshot", response)

        # Should have blob reference instead of data
        assert result["screenshot"] == "blob://test-123.png"
        assert result["screenshot_size_kb"] == len(large_data) // 1024
        assert result["screenshot_mime_type"] == "image/png"
        assert result["screenshot_blob_retrieval_tool"] == "get_blob"
        assert "screenshot_expires_at" in result

        # Verify blob storage was called
        mock_blob_manager.store_base64_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_intercept_response_nested_data(self, middleware, mock_blob_manager):
        """Test that nested data is processed recursively."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {
            "status": "success",
            "result": {
                "screenshot": data_uri,
                "other": "data",
            },
        }

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_screenshot", response)

        assert result["status"] == "success"
        assert result["result"]["screenshot"] == "blob://test.png"
        assert result["result"]["other"] == "data"

    @pytest.mark.asyncio
    async def test_should_store_as_blob_data_uri(self, middleware):
        """Test detection of data URI that should be stored."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        result = await middleware._should_store_as_blob(data_uri)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_store_as_blob_small_data_uri(self, middleware):
        """Test that small data URI is not stored."""
        small_data = b"x" * 100
        base64_data = base64.b64encode(small_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        result = await middleware._should_store_as_blob(data_uri)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_store_as_blob_plain_base64(self, middleware):
        """Test detection of plain base64 string."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")

        result = await middleware._should_store_as_blob(base64_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_store_as_blob_not_base64(self, middleware):
        """Test that non-base64 string is not stored."""
        result = await middleware._should_store_as_blob("This is not base64!")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_store_as_blob_short_string(self, middleware):
        """Test that short strings are not stored."""
        result = await middleware._should_store_as_blob("short")
        assert result is False

    @pytest.mark.asyncio
    async def test_store_as_blob(self, middleware, mock_blob_manager):
        """Test storing data as blob."""
        data_uri = "data:image/png;base64,SGVsbG8="

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.png",
            "size_bytes": 5,
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware._store_as_blob(data_uri, "screenshot", "playwright_screenshot")

        assert result["blob_id"] == "blob://test.png"

        # Verify blob manager was called with correct arguments
        mock_blob_manager.store_base64_data.assert_called_once()
        call_args = mock_blob_manager.store_base64_data.call_args
        assert call_args[1]["base64_data"] == data_uri
        assert call_args[1]["filename"] == "playwright_screenshot_screenshot.png"
        assert call_args[1]["tags"] == ["playwright_screenshot", "screenshot"]

    def test_get_extension_from_data_uri_png(self, middleware):
        """Test extracting .png extension from data URI."""
        data_uri = "data:image/png;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".png"

    def test_get_extension_from_data_uri_jpeg(self, middleware):
        """Test extracting .jpg extension from data URI."""
        data_uri = "data:image/jpeg;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".jpg"

    def test_get_extension_from_data_uri_pdf(self, middleware):
        """Test extracting .pdf extension from data URI."""
        data_uri = "data:application/pdf;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".pdf"

    def test_get_extension_from_data_uri_webp(self, middleware):
        """Test extracting .webp extension from data URI."""
        data_uri = "data:image/webp;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".webp"

    def test_get_extension_from_data_uri_video(self, middleware):
        """Test extracting video extension from data URI."""
        data_uri = "data:video/webm;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".webm"

    def test_get_extension_from_data_uri_unknown(self, middleware):
        """Test unknown MIME type returns .bin."""
        data_uri = "data:application/unknown;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".bin"

    def test_get_extension_from_data_uri_no_prefix(self, middleware):
        """Test plain base64 without data URI returns .bin."""
        assert middleware._get_extension_from_data_uri("SGVsbG8=") == ".bin"

    @pytest.mark.asyncio
    async def test_binary_tools_constant(self, middleware):
        """Test that BINARY_TOOLS is defined correctly."""
        assert "playwright_screenshot" in middleware.BINARY_TOOLS
        assert "playwright_pdf" in middleware.BINARY_TOOLS
        assert "playwright_save_as_pdf" in middleware.BINARY_TOOLS

    @pytest.mark.asyncio
    async def test_conditional_binary_tools_constant(self, middleware):
        """Test that CONDITIONAL_BINARY_TOOLS is defined."""
        assert "playwright_get_console" in middleware.CONDITIONAL_BINARY_TOOLS
        assert "playwright_download" in middleware.CONDITIONAL_BINARY_TOOLS

    @pytest.mark.asyncio
    async def test_intercept_pdf_tool(self, middleware, mock_blob_manager):
        """Test intercepting PDF tool response."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{base64_data}"

        response = {"pdf": data_uri}

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.pdf",
            "size_bytes": len(large_data),
            "mime_type": "application/pdf",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_pdf", response)

        assert result["pdf"] == "blob://test.pdf"


class TestBinaryInterceptionMiddlewareExtended:
    """Extended tests for BinaryInterceptionMiddleware."""

    @pytest.fixture
    def mock_blob_manager(self):
        manager = Mock()
        manager.store_base64_data = AsyncMock()
        return manager

    @pytest.fixture
    def middleware(self, mock_blob_manager):
        return BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)

    def test_get_extension_from_data_uri_gif(self, middleware):
        """Test extracting .gif extension from data URI."""
        data_uri = "data:image/gif;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".gif"

    def test_get_extension_from_data_uri_svg(self, middleware):
        """Test extracting .svg extension from data URI."""
        data_uri = "data:image/svg+xml;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".svg"

    def test_get_extension_from_data_uri_mp4(self, middleware):
        """Test extracting .mp4 extension from data URI."""
        data_uri = "data:video/mp4;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".mp4"

    @pytest.mark.asyncio
    async def test_should_store_as_blob_very_short_string(self, middleware):
        """Test that very short strings are not stored as blobs."""
        result = await middleware._should_store_as_blob("ab")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_store_as_blob_with_whitespace(self, middleware):
        """Test that strings with whitespace are not detected as base64."""
        result = await middleware._should_store_as_blob("This has spaces")
        assert result is False

    @pytest.mark.asyncio
    async def test_intercept_response_list_type(self, middleware):
        """Test that list responses are processed."""
        response = [{"status": "ok"}]
        result = await middleware.intercept_response("playwright_screenshot", response)
        assert result == response

    @pytest.mark.asyncio
    async def test_intercept_response_empty_dict(self, middleware):
        """Test that empty dict responses are returned unchanged."""
        response = {}
        result = await middleware.intercept_response("any_tool", response)
        assert result == {}

    def test_object_to_dict_with_dataclass(self, middleware):
        """Test _object_to_dict converts dataclass to dict."""
        from dataclasses import dataclass

        @dataclass
        class TestData:
            value: str
            count: int

        obj = TestData(value="test", count=42)
        result = middleware._object_to_dict(obj)

        assert result == {"value": "test", "count": 42}

    @pytest.mark.asyncio
    async def test_intercept_response_with_error_flag(self, middleware):
        """Test intercepting response that has is_error=True."""
        from dataclasses import dataclass
        from typing import Any

        @dataclass
        class MockCallToolResult:
            content: list[Any]
            is_error: bool = False

        mock_result = MockCallToolResult(
            content=[{"type": "text", "text": "Error message"}],
            is_error=True,
        )

        result = await middleware.intercept_response("some_tool", mock_result)

        assert isinstance(result, dict)
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_intercept_response_preserves_structure(self, middleware):
        """Test that intercept_response preserves overall response structure."""
        response = {
            "status": "success",
            "metadata": {"timestamp": "2024-01-01", "count": 5},
            "items": [1, 2, 3],
        }

        result = await middleware.intercept_response("some_tool", response)

        assert result == response

    @pytest.mark.asyncio
    async def test_conditional_binary_tool_with_binary_data(self, middleware, mock_blob_manager):
        """Test conditional binary tool processes binary data."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {"data": data_uri}

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_download", response)

        assert result["data"] == "blob://test.png"

    @pytest.mark.asyncio
    async def test_should_store_as_blob_empty_string(self, middleware):
        """Test _should_store_as_blob with empty string."""
        result = await middleware._should_store_as_blob("")
        assert result is False

    def test_object_to_dict_nested(self, middleware):
        """Test _object_to_dict with nested objects."""
        from dataclasses import dataclass

        @dataclass
        class Inner:
            value: str

        @dataclass
        class Outer:
            inner: Inner
            name: str

        obj = Outer(inner=Inner(value="nested"), name="outer")
        result = middleware._object_to_dict(obj)

        assert result == {"inner": {"value": "nested"}, "name": "outer"}

    @pytest.mark.asyncio
    async def test_intercept_response_multiple_binary_fields(self, middleware, mock_blob_manager):
        """Test intercepting response with multiple binary fields."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {"screenshot1": data_uri, "screenshot2": data_uri}

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_screenshot", response)

        # Both fields should be replaced
        assert result["screenshot1"] == "blob://test.png"
        assert result["screenshot2"] == "blob://test.png"

    def test_get_extension_from_data_uri_octet_stream(self, middleware):
        """Test extension for octet-stream MIME type returns .bin (unknown type)."""
        data_uri = "data:application/octet-stream;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".bin"

    def test_get_extension_from_data_uri_tar(self, middleware):
        """Test extension for tar MIME type."""
        data_uri = "data:application/x-tar;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".tar"

    def test_get_extension_from_data_uri_zip(self, middleware):
        """Test extension for zip MIME type."""
        data_uri = "data:application/zip;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".zip"

    @pytest.mark.asyncio
    async def test_should_store_as_blob_with_special_chars(self, middleware):
        """Test that strings with special characters are not stored as base64."""
        result = await middleware._should_store_as_blob("Hello! @#$%^&*()")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_store_as_blob_url_string(self, middleware):
        """Test that URL strings are not stored as blobs."""
        result = await middleware._should_store_as_blob("https://example.com/image.png")
        assert result is False

    def test_object_to_dict_with_simple_dataclass(self, middleware):
        """Test _object_to_dict with a simple dataclass."""
        from dataclasses import dataclass

        @dataclass
        class Item:
            name: str
            count: int

        item = Item(name="test", count=5)
        result = middleware._object_to_dict(item)

        assert result == {"name": "test", "count": 5}

    def test_object_to_dict_with_optional_fields(self, middleware):
        """Test _object_to_dict with dataclass containing optional fields."""
        from dataclasses import dataclass
        from typing import Optional

        @dataclass
        class OptionalData:
            required: str
            optional: Optional[str] = None

        obj = OptionalData(required="value")
        result = middleware._object_to_dict(obj)

        assert result == {"required": "value", "optional": None}

    def test_get_extension_from_data_uri_svg(self, middleware):
        """Test extension for SVG MIME type."""
        data_uri = "data:image/svg+xml;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".svg"

    def test_get_extension_from_data_uri_webp(self, middleware):
        """Test extension for WebP MIME type."""
        data_uri = "data:image/webp;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".webp"

    @pytest.mark.asyncio
    async def test_should_store_as_blob_empty_base64(self, middleware):
        """Test that empty base64 data is not stored as blob (below threshold)."""
        # Empty base64 data
        result = await middleware._should_store_as_blob("data:image/png;base64,")
        assert result is False

    @pytest.mark.asyncio
    async def test_intercept_response_preserves_non_binary_fields(self, middleware, mock_blob_manager):
        """Test that non-binary fields are preserved during interception."""
        response = {
            "status": "success",
            "count": 42,
            "url": "https://example.com",
            "nested": {"key": "value"}
        }

        result = await middleware.intercept_response("some_tool", response)

        # All non-binary fields should be preserved
        assert result["status"] == "success"
        assert result["count"] == 42
        assert result["url"] == "https://example.com"
        assert result["nested"] == {"key": "value"}
