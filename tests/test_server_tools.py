"""
Comprehensive tests for server.py MCP tools.

This test module covers the core browser interaction tools and helper functions
to improve test coverage for the high-complexity server.py module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from playwright_proxy_mcp.server import (
    browser_snapshot,
    browser_navigate,
    browser_evaluate,
    browser_execute_bulk,
    _extract_blob_id_from_response,
    _validate_navigation_params,
    _create_navigation_error,
    browser_take_screenshot,
    browser_pdf_save,
    _validate_evaluation_params,
    _create_evaluation_error,
    browser_click,
    browser_type,
    browser_wait_for,
)
from playwright_proxy_mcp.types import NavigationResponse, EvaluationResponse


@pytest.fixture
def mock_pool_manager():
    """Mock pool manager for testing."""
    pool_manager = MagicMock()
    pool = MagicMock()
    proxy_client = MagicMock()

    # Setup lease_instance context manager
    async def mock_lease():
        yield proxy_client

    pool.lease_instance.return_value.__aenter__ = AsyncMock(return_value=proxy_client)
    pool.lease_instance.return_value.__aexit__ = AsyncMock(return_value=None)
    pool_manager.get_pool.return_value = pool

    return pool_manager, proxy_client


class TestNavigationValidation:
    """Tests for navigation parameter validation."""

    def test_validate_navigation_params_valid(self):
        """Test validation with valid parameters."""
        # Should not raise
        _validate_navigation_params(
            url="https://example.com",
            silent=False,
            flatten=False,
            jmespath=None,
            output_format="yaml",
            offset=0,
            limit=1000
        )

    def test_validate_navigation_params_negative_offset(self):
        """Test validation rejects negative offset."""
        with pytest.raises(ValueError, match="offset must be >= 0"):
            _validate_navigation_params(
                url="https://example.com",
                offset=-1,
                limit=1000
            )

    def test_validate_navigation_params_invalid_limit_low(self):
        """Test validation rejects limit < 1."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            _validate_navigation_params(
                url="https://example.com",
                offset=0,
                limit=0
            )

    def test_validate_navigation_params_invalid_limit_high(self):
        """Test validation rejects limit > 10000."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            _validate_navigation_params(
                url="https://example.com",
                offset=0,
                limit=10001
            )

    def test_validate_navigation_params_invalid_output_format(self):
        """Test validation rejects invalid output format."""
        with pytest.raises(ValueError, match="output_format must be 'yaml' or 'json'"):
            _validate_navigation_params(
                url="https://example.com",
                output_format="xml"
            )


class TestEvaluationValidation:
    """Tests for evaluation parameter validation."""

    def test_validate_evaluation_params_valid(self):
        """Test validation with valid parameters."""
        # Should not raise
        _validate_evaluation_params(
            code="return 1 + 1;",
            offset=0,
            limit=1000
        )

    def test_validate_evaluation_params_negative_offset(self):
        """Test validation rejects negative offset."""
        with pytest.raises(ValueError, match="offset must be >= 0"):
            _validate_evaluation_params(
                code="return 1;",
                offset=-1,
                limit=1000
            )

    def test_validate_evaluation_params_invalid_limit_low(self):
        """Test validation rejects limit < 1."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            _validate_evaluation_params(
                code="return 1;",
                offset=0,
                limit=0
            )

    def test_validate_evaluation_params_invalid_limit_high(self):
        """Test validation rejects limit > 10000."""
        with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
            _validate_evaluation_params(
                code="return 1;",
                offset=0,
                limit=10001
            )


class TestBlobIdExtraction:
    """Tests for blob ID extraction from responses."""

    def test_extract_blob_id_from_markdown_link(self):
        """Test extracting blob ID from markdown link format."""
        response = {"content": [{"text": "Screenshot: [file.png](blob://12345-abc.png)"}]}
        blob_id = _extract_blob_id_from_response(response)
        assert blob_id == "blob://12345-abc.png"

    def test_extract_blob_id_from_direct_uri(self):
        """Test extracting blob ID from direct URI in text."""
        response = {"content": [{"text": "Saved as blob://98765-xyz.pdf"}]}
        blob_id = _extract_blob_id_from_response(response)
        assert blob_id == "blob://98765-xyz.pdf"

    def test_extract_blob_id_with_multiple_uris(self):
        """Test that first blob URI is extracted when multiple present."""
        response = {"content": [{"text": "First blob://111.png and blob://222.png"}]}
        blob_id = _extract_blob_id_from_response(response)
        assert blob_id == "blob://111.png"

    def test_extract_blob_id_not_found(self):
        """Test that None is returned when no blob URI found."""
        response = {"content": [{"text": "No blob URI here"}]}
        blob_id = _extract_blob_id_from_response(response)
        assert blob_id is None

    def test_extract_blob_id_empty_response(self):
        """Test extraction with empty response."""
        response = {"content": []}
        blob_id = _extract_blob_id_from_response(response)
        assert blob_id is None


class TestErrorCreation:
    """Tests for error message creation helpers."""

    def test_create_navigation_error_basic(self):
        """Test basic navigation error creation."""
        error = _create_navigation_error("Connection failed", "https://example.com")

        assert isinstance(error, NavigationResponse)
        assert error["success"] is False
        assert error["url"] == "https://example.com"
        assert error["error"] == "Connection failed"
        assert error["snapshot"] is None

    def test_create_navigation_error_with_cache_key(self):
        """Test navigation error with cache key."""
        error = _create_navigation_error(
            "Timeout error",
            "https://example.com",
            cache_key="nav_123"
        )

        assert error["cache_key"] == "nav_123"
        assert error["success"] is False

    def test_create_evaluation_error_basic(self):
        """Test basic evaluation error creation."""
        error = _create_evaluation_error("Syntax error", "invalid code")

        assert isinstance(error, EvaluationResponse)
        assert error["success"] is False
        assert error["code"] == "invalid code"
        assert error["error"] == "Syntax error"
        assert error["result"] is None


@pytest.mark.asyncio
class TestBrowserClick:
    """Tests for browser_click tool."""

    async def test_browser_click_basic(self, mock_pool_manager):
        """Test basic click operation."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "clicked"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_click(
                element="Login button",
                ref="button#login"
            )

        assert result == {"status": "clicked"}
        proxy_client.call_tool.assert_called_once()

    async def test_browser_click_with_optional_params(self, mock_pool_manager):
        """Test click with button and modifiers."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "clicked"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_click(
                element="Link",
                ref="a#mylink",
                button="right",
                modifiers=["Control"]
            )

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][0] == "browser_click"
        assert call_args[0][1]["button"] == "right"
        assert call_args[0][1]["modifiers"] == ["Control"]


@pytest.mark.asyncio
class TestBrowserType:
    """Tests for browser_type tool."""

    async def test_browser_type_basic(self, mock_pool_manager):
        """Test basic typing operation."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "typed"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_type(
                element="Username field",
                ref="input#username",
                text="testuser"
            )

        assert result == {"status": "typed"}
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["text"] == "testuser"


@pytest.mark.asyncio
class TestBrowserWaitFor:
    """Tests for browser_wait_for tool."""

    async def test_browser_wait_for_time(self, mock_pool_manager):
        """Test waiting for time."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "waited"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_wait_for(time=2.5)

        assert result == {"status": "waited"}
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["time"] == 2.5

    async def test_browser_wait_for_text(self, mock_pool_manager):
        """Test waiting for text to appear."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "found"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_wait_for(text="Welcome")

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["text"] == "Welcome"

    async def test_browser_wait_for_text_gone(self, mock_pool_manager):
        """Test waiting for text to disappear."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "gone"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_wait_for(textGone="Loading...")

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["textGone"] == "Loading..."


@pytest.mark.asyncio
class TestBrowserScreenshot:
    """Tests for browser_take_screenshot tool."""

    async def test_browser_take_screenshot_basic(self, mock_pool_manager):
        """Test basic screenshot."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"content": [{"text": "Screenshot: [file.png](blob://123.png)"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            blob_uri = await browser_take_screenshot(filename="test.png")

        assert blob_uri == "blob://123.png"

    async def test_browser_take_screenshot_full_page(self, mock_pool_manager):
        """Test full page screenshot."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"content": [{"text": "blob://456.png"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            blob_uri = await browser_take_screenshot(
                filename="full.png",
                fullPage=True
            )

        assert blob_uri == "blob://456.png"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["fullPage"] is True

    async def test_browser_take_screenshot_element(self, mock_pool_manager):
        """Test element screenshot."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"content": [{"text": "blob://789.png"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            blob_uri = await browser_take_screenshot(
                element="Logo",
                ref="img#logo"
            )

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["element"] == "Logo"
        assert call_args[0][1]["ref"] == "img#logo"

    async def test_browser_take_screenshot_no_blob_found(self, mock_pool_manager):
        """Test screenshot with no blob URI in response."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"content": [{"text": "No blob here"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            with pytest.raises(RuntimeError, match="Failed to extract blob URI"):
                await browser_take_screenshot(filename="test.png")


@pytest.mark.asyncio
class TestBrowserPdfSave:
    """Tests for browser_pdf_save tool."""

    async def test_browser_pdf_save_basic(self, mock_pool_manager):
        """Test basic PDF save."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"content": [{"text": "PDF: blob://123.pdf"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            blob_uri = await browser_pdf_save(filename="test.pdf")

        assert blob_uri == "blob://123.pdf"

    async def test_browser_pdf_save_no_filename(self, mock_pool_manager):
        """Test PDF save without filename."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"content": [{"text": "blob://auto.pdf"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            blob_uri = await browser_pdf_save()

        assert blob_uri == "blob://auto.pdf"
        call_args = proxy_client.call_tool.call_args
        assert "filename" not in call_args[0][1]
