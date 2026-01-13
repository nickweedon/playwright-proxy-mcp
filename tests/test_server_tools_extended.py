"""
Extended tests for server.py MCP tools.

This test module extends coverage for browser interaction tools
that were not fully covered in the initial test suite.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from playwright_proxy_mcp.server import (
    browser_navigate_back,
    browser_drag,
    browser_hover,
    browser_select_option,
    browser_generate_locator,
    browser_fill_form,
    browser_mouse_move_xy,
    browser_mouse_click_xy,
    browser_mouse_drag_xy,
    browser_press_key,
    browser_verify_element_visible,
    browser_verify_text_visible,
    browser_verify_list_visible,
    browser_verify_value,
    browser_network_requests,
    browser_tabs,
    browser_console_messages,
    browser_handle_dialog,
    browser_file_upload,
    browser_start_tracing,
    browser_stop_tracing,
    browser_install,
    browser_run_code,
    browser_pool_status,
    get_proxy_status,
    _extract_yaml_from_response,
    _paginate_result_data,
    _fetch_fresh_snapshot,
    _process_snapshot_data,
)


@pytest.fixture
def mock_pool_manager():
    """Mock pool manager for testing."""
    pool_manager = MagicMock()
    pool = MagicMock()
    proxy_client = MagicMock()

    # Default instance ID for tests
    test_instance_id = "0"

    # Setup lease_instance context manager - returns (proxy_client, instance_id) tuple
    pool.lease_instance.return_value.__aenter__ = AsyncMock(return_value=(proxy_client, test_instance_id))
    pool.lease_instance.return_value.__aexit__ = AsyncMock(return_value=None)
    pool_manager.get_pool.return_value = pool

    return pool_manager, proxy_client


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestExtractYamlFromResponse:
    """Tests for _extract_yaml_from_response helper function."""

    def test_extracts_yaml_from_text_content(self):
        """Test extracting YAML from text content."""
        result = {
            "content": [
                {"type": "text", "text": "- role: button\n  name: Submit"}
            ]
        }
        yaml = _extract_yaml_from_response(result)
        assert yaml == "- role: button\n  name: Submit"

    def test_returns_none_for_missing_content(self):
        """Test that None is returned when content is missing."""
        result = {"other_field": "value"}
        yaml = _extract_yaml_from_response(result)
        assert yaml is None

    def test_returns_none_for_empty_content(self):
        """Test that None is returned for empty content."""
        result = {"content": []}
        yaml = _extract_yaml_from_response(result)
        assert yaml is None

    def test_returns_none_for_non_text_content(self):
        """Test that None is returned for non-text content."""
        result = {"content": [{"type": "image", "data": "base64data"}]}
        yaml = _extract_yaml_from_response(result)
        assert yaml is None


class TestPaginateResultData:
    """Tests for _paginate_result_data helper function."""

    def test_paginates_list_from_start(self):
        """Test pagination from the start of a list."""
        data = list(range(10))
        paginated, total, has_more = _paginate_result_data(data, offset=0, limit=3)

        assert paginated == [0, 1, 2]
        assert total == 10
        assert has_more is True

    def test_paginates_list_with_offset(self):
        """Test pagination with offset."""
        data = list(range(10))
        paginated, total, has_more = _paginate_result_data(data, offset=5, limit=3)

        assert paginated == [5, 6, 7]
        assert total == 10
        assert has_more is True

    def test_paginates_list_last_page(self):
        """Test pagination on last page."""
        data = list(range(10))
        paginated, total, has_more = _paginate_result_data(data, offset=7, limit=5)

        assert paginated == [7, 8, 9]
        assert total == 10
        assert has_more is False

    def test_paginates_single_item(self):
        """Test pagination of non-list item (wraps in list)."""
        data = {"key": "value"}
        paginated, total, has_more = _paginate_result_data(data, offset=0, limit=10)

        assert paginated == [{"key": "value"}]
        assert total == 1
        assert has_more is False

    def test_paginates_single_item_with_offset(self):
        """Test pagination of single item with offset beyond."""
        data = {"key": "value"}
        paginated, total, has_more = _paginate_result_data(data, offset=1, limit=10)

        assert paginated == []
        assert total == 1
        assert has_more is False

    def test_paginates_empty_list(self):
        """Test pagination of empty list."""
        data = []
        paginated, total, has_more = _paginate_result_data(data, offset=0, limit=10)

        assert paginated == []
        assert total == 0
        assert has_more is False


# =============================================================================
# Navigation Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserNavigateBack:
    """Tests for browser_navigate_back tool."""

    async def test_browser_navigate_back(self, mock_pool_manager):
        """Test navigate back functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "navigated_back"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_navigate_back.fn()

        assert result["status"] == "navigated_back"
        assert result["browser_instance"] == "0"
        proxy_client.call_tool.assert_called_once_with("browser_navigate_back", {})


# =============================================================================
# Interaction Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserDrag:
    """Tests for browser_drag tool."""

    async def test_browser_drag(self, mock_pool_manager):
        """Test drag and drop functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "dragged"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_drag.fn(
                startElement="Item 1",
                startRef="e1",
                endElement="Drop Zone",
                endRef="e2"
            )

        assert result["status"] == "dragged"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][0] == "browser_drag"
        assert call_args[0][1]["startElement"] == "Item 1"
        assert call_args[0][1]["endRef"] == "e2"


@pytest.mark.asyncio
class TestBrowserHover:
    """Tests for browser_hover tool."""

    async def test_browser_hover(self, mock_pool_manager):
        """Test hover functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "hovered"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_hover.fn(element="Menu Item", ref="e1")

        assert result["status"] == "hovered"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["element"] == "Menu Item"
        assert call_args[0][1]["ref"] == "e1"


@pytest.mark.asyncio
class TestBrowserSelectOption:
    """Tests for browser_select_option tool."""

    async def test_browser_select_option(self, mock_pool_manager):
        """Test select option functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "selected"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_select_option.fn(
                element="Country dropdown",
                ref="e1",
                values=["USA", "Canada"]
            )

        assert result["status"] == "selected"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["values"] == ["USA", "Canada"]


@pytest.mark.asyncio
class TestBrowserGenerateLocator:
    """Tests for browser_generate_locator tool."""

    async def test_browser_generate_locator(self, mock_pool_manager):
        """Test generate locator functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"locator": "page.getByRole('button', { name: 'Submit' })"}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_generate_locator.fn(element="Submit button", ref="e1")

        assert "locator" in result
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][0] == "browser_generate_locator"


@pytest.mark.asyncio
class TestBrowserFillForm:
    """Tests for browser_fill_form tool."""

    async def test_browser_fill_form(self, mock_pool_manager):
        """Test fill form functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "filled"})

        fields = [
            {"name": "Username", "type": "textbox", "ref": "e1", "value": "testuser"},
            {"name": "Accept Terms", "type": "checkbox", "ref": "e2", "value": "true"},
        ]

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_fill_form.fn(fields=fields)

        assert result["status"] == "filled"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["fields"] == fields


# =============================================================================
# Mouse Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserMouseTools:
    """Tests for mouse-related tools."""

    async def test_browser_mouse_move_xy(self, mock_pool_manager):
        """Test mouse move functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "moved"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_mouse_move_xy.fn(element="Canvas", x=100.5, y=200.5)

        assert result["status"] == "moved"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["x"] == 100.5
        assert call_args[0][1]["y"] == 200.5

    async def test_browser_mouse_click_xy(self, mock_pool_manager):
        """Test mouse click functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "clicked"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_mouse_click_xy.fn(element="Canvas", x=50.0, y=75.0)

        assert result["status"] == "clicked"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][0] == "browser_mouse_click_xy"

    async def test_browser_mouse_drag_xy(self, mock_pool_manager):
        """Test mouse drag functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "dragged"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_mouse_drag_xy.fn(
                element="Slider",
                startX=0.0,
                startY=50.0,
                endX=100.0,
                endY=50.0
            )

        assert result["status"] == "dragged"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["startX"] == 0.0
        assert call_args[0][1]["endX"] == 100.0


# =============================================================================
# Keyboard Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserKeyboardTools:
    """Tests for keyboard-related tools."""

    async def test_browser_press_key(self, mock_pool_manager):
        """Test press key functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "pressed"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_press_key.fn(key="Enter")

        assert result["status"] == "pressed"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["key"] == "Enter"


# =============================================================================
# Verification Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserVerificationTools:
    """Tests for verification tools."""

    async def test_browser_verify_element_visible(self, mock_pool_manager):
        """Test verify element visible functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"visible": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_verify_element_visible.fn(
                role="button",
                accessibleName="Submit"
            )

        assert result["visible"] is True
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][0] == "browser_verify_element_visible"

    async def test_browser_verify_text_visible(self, mock_pool_manager):
        """Test verify text visible functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"visible": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_verify_text_visible.fn(text="Welcome")

        assert result["visible"] is True
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["text"] == "Welcome"

    async def test_browser_verify_list_visible(self, mock_pool_manager):
        """Test verify list visible functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"visible": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_verify_list_visible.fn(
                element="Navigation menu",
                ref="e1",
                items=["Home", "About", "Contact"]
            )

        assert result["visible"] is True
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["items"] == ["Home", "About", "Contact"]

    async def test_browser_verify_value(self, mock_pool_manager):
        """Test verify value functionality."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"matches": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_verify_value.fn(
                type="textbox",
                element="Email field",
                ref="e1",
                value="test@example.com"
            )

        assert result["matches"] is True
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["value"] == "test@example.com"


# =============================================================================
# Network Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserNetworkTools:
    """Tests for network-related tools."""

    async def test_browser_network_requests_default(self, mock_pool_manager):
        """Test network requests with default params."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"requests": []})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_network_requests.fn()

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["includeStatic"] is False

    async def test_browser_network_requests_with_static(self, mock_pool_manager):
        """Test network requests including static resources."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"requests": [{"url": "image.png"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_network_requests.fn(includeStatic=True)

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["includeStatic"] is True


# =============================================================================
# Tab Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserTabTools:
    """Tests for tab management tools."""

    async def test_browser_tabs_list(self, mock_pool_manager):
        """Test listing tabs."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"tabs": [{"index": 0, "title": "Home"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_tabs.fn(action="list")

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["action"] == "list"
        assert "index" not in call_args[0][1]

    async def test_browser_tabs_select(self, mock_pool_manager):
        """Test selecting a tab."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"status": "selected"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_tabs.fn(action="select", index=2)

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["action"] == "select"
        assert call_args[0][1]["index"] == 2


# =============================================================================
# Console Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserConsoleTools:
    """Tests for console tools."""

    async def test_browser_console_messages_default(self, mock_pool_manager):
        """Test getting console messages with default level."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"messages": []})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_console_messages.fn()

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["level"] == "info"

    async def test_browser_console_messages_error_level(self, mock_pool_manager):
        """Test getting console messages with error level."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(
            return_value={"messages": [{"level": "error", "text": "Error occurred"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_console_messages.fn(level="error")

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["level"] == "error"


# =============================================================================
# Dialog Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserDialogTools:
    """Tests for dialog handling tools."""

    async def test_browser_handle_dialog_accept(self, mock_pool_manager):
        """Test accepting a dialog."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"handled": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_handle_dialog.fn(accept=True)

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["accept"] is True
        assert "promptText" not in call_args[0][1]

    async def test_browser_handle_dialog_with_prompt(self, mock_pool_manager):
        """Test handling a prompt dialog with text."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"handled": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_handle_dialog.fn(
                accept=True,
                promptText="User input"
            )

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["promptText"] == "User input"


# =============================================================================
# File Upload Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserFileUploadTools:
    """Tests for file upload tools."""

    async def test_browser_file_upload_with_paths(self, mock_pool_manager):
        """Test uploading files."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"uploaded": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_file_upload.fn(
                paths=["/path/to/file1.txt", "/path/to/file2.txt"]
            )

        call_args = proxy_client.call_tool.call_args
        assert call_args[0][1]["paths"] == ["/path/to/file1.txt", "/path/to/file2.txt"]

    async def test_browser_file_upload_cancel(self, mock_pool_manager):
        """Test canceling file upload."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"cancelled": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_file_upload.fn()

        call_args = proxy_client.call_tool.call_args
        assert "paths" not in call_args[0][1]


# =============================================================================
# Tracing Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserTracingTools:
    """Tests for tracing tools."""

    async def test_browser_start_tracing(self, mock_pool_manager):
        """Test starting trace recording."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"tracing": "started"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_start_tracing.fn()

        assert result["tracing"] == "started"
        assert result["browser_instance"] == "0"
        proxy_client.call_tool.assert_called_once_with("browser_start_tracing", {})

    async def test_browser_stop_tracing(self, mock_pool_manager):
        """Test stopping trace recording."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"tracing": "stopped"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_stop_tracing.fn()

        assert result["tracing"] == "stopped"
        assert result["browser_instance"] == "0"
        proxy_client.call_tool.assert_called_once_with("browser_stop_tracing", {})


# =============================================================================
# Installation Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserInstallTools:
    """Tests for browser installation tools."""

    async def test_browser_install(self, mock_pool_manager):
        """Test browser installation."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"installed": True})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_install.fn()

        assert result["installed"] is True
        assert result["browser_instance"] == "0"
        proxy_client.call_tool.assert_called_once_with("browser_install", {})


# =============================================================================
# Code Execution Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserRunCode:
    """Tests for browser_run_code tool."""

    async def test_browser_run_code(self, mock_pool_manager):
        """Test running Playwright code."""
        pool_manager, proxy_client = mock_pool_manager
        proxy_client.call_tool = AsyncMock(return_value={"result": "Page Title"})

        with patch("playwright_proxy_mcp.server.pool_manager", pool_manager):
            result = await browser_run_code.fn(
                code="async (page) => await page.title()"
            )

        assert result["result"] == "Page Title"
        assert result["browser_instance"] == "0"
        call_args = proxy_client.call_tool.call_args
        assert "async (page)" in call_args[0][1]["code"]


# =============================================================================
# Pool Status Tool Tests
# =============================================================================


@pytest.mark.asyncio
class TestBrowserPoolStatus:
    """Tests for browser_pool_status tool."""

    async def test_browser_pool_status_all_pools(self):
        """Test getting status of all pools."""
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_status = AsyncMock(
            return_value={
                "pools": [{"name": "DEFAULT", "instances": 1}],
                "summary": {"total_pools": 1}
            }
        )

        with patch("playwright_proxy_mcp.server.pool_manager", mock_pool_manager):
            result = await browser_pool_status.fn()

        mock_pool_manager.get_status.assert_called_once_with(None)
        assert len(result["pools"]) == 1

    async def test_browser_pool_status_specific_pool(self):
        """Test getting status of specific pool."""
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_status = AsyncMock(
            return_value={"pools": [{"name": "ISOLATED"}]}
        )

        with patch("playwright_proxy_mcp.server.pool_manager", mock_pool_manager):
            result = await browser_pool_status.fn(pool_name="ISOLATED")

        mock_pool_manager.get_status.assert_called_once_with("ISOLATED")

    async def test_browser_pool_status_no_pool_manager(self):
        """Test error when pool manager not initialized."""
        with patch("playwright_proxy_mcp.server.pool_manager", None):
            with pytest.raises(RuntimeError, match="Pool manager not initialized"):
                await browser_pool_status.fn()


# =============================================================================
# Resource Tests
# =============================================================================


@pytest.mark.asyncio
class TestGetProxyStatus:
    """Tests for get_proxy_status resource."""

    async def test_returns_running_status(self):
        """Test status when proxy is running."""
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_status = AsyncMock(
            return_value={
                "summary": {"total_instances": 3, "healthy_instances": 2}
            }
        )

        with patch("playwright_proxy_mcp.server.pool_manager", mock_pool_manager):
            # Access the underlying function via .fn
            status = await get_proxy_status.fn()

        assert "running" in status
        assert "2/3" in status

    async def test_returns_not_initialized_status(self):
        """Test status when proxy not initialized."""
        with patch("playwright_proxy_mcp.server.pool_manager", None):
            # Access the underlying function via .fn
            status = await get_proxy_status.fn()

        assert "not initialized" in status
