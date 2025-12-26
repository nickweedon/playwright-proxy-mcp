"""Tests for browser_execute_bulk tool."""

import pytest
from unittest.mock import AsyncMock, patch

# Import the implementation directly
from playwright_proxy_mcp.server import browser_execute_bulk as browser_execute_bulk_tool

# Get the actual function from the FunctionTool wrapper
browser_execute_bulk = browser_execute_bulk_tool.fn


@pytest.mark.asyncio
async def test_bulk_execution_basic():
    """Test basic sequential execution with selective results."""
    # Mock _call_playwright_tool
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        # Setup mock to return different results for each command
        mock_tool.side_effect = [
            {"status": "navigated"},
            {"status": "waited"},
            {"snapshot": "data"},
        ]

        # Execute bulk with 3 commands, only last returns result
        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
                {"tool": "browser_wait_for", "args": {"time": 1000}},
                {"tool": "browser_snapshot", "args": {}, "return_result": True},
            ]
        )

        # Verify execution
        assert result["success"] is True
        assert result["executed_count"] == 3
        assert result["total_count"] == 3
        assert result["stopped_at"] is None
        assert result["errors"] == [None, None, None]
        assert result["results"][0] is None  # Not requested
        assert result["results"][1] is None  # Not requested
        assert result["results"][2] == {"snapshot": "data"}  # Requested


@pytest.mark.asyncio
async def test_bulk_execution_return_all_results():
    """Test return_all_results parameter."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.side_effect = [
            {"status": "navigated"},
            {"status": "clicked"},
            {"snapshot": "data"},
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
                {"tool": "browser_click", "args": {"element": "button"}},
                {"tool": "browser_snapshot", "args": {}},
            ],
            return_all_results=True,
        )

        assert result["success"] is True
        assert result["executed_count"] == 3
        assert result["results"] == [
            {"status": "navigated"},
            {"status": "clicked"},
            {"snapshot": "data"},
        ]


@pytest.mark.asyncio
async def test_bulk_execution_stop_on_error():
    """Test stop_on_error halts at first failure."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        # First command succeeds, second fails
        mock_tool.side_effect = [
            {"status": "navigated"},
            RuntimeError("Navigation failed"),
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
                {"tool": "browser_click", "args": {"element": "button"}},
                {"tool": "browser_snapshot", "args": {}, "return_result": True},
            ],
            stop_on_error=True,
        )

        assert result["success"] is False
        assert result["executed_count"] == 2
        assert result["total_count"] == 3
        assert result["stopped_at"] == 1
        assert result["errors"][0] is None
        assert "Navigation failed" in result["errors"][1]
        assert result["errors"][2] is None  # Not executed, filled with None
        assert result["results"][0] is None
        assert result["results"][1] is None
        assert result["results"][2] is None  # Not executed


@pytest.mark.asyncio
async def test_bulk_execution_continue_on_error():
    """Test continue on error collects all errors."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        # Commands 1 and 3 fail, command 2 succeeds
        mock_tool.side_effect = [
            RuntimeError("First error"),
            {"status": "clicked"},
            RuntimeError("Third error"),
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
                {"tool": "browser_click", "args": {"element": "button"}},
                {"tool": "browser_snapshot", "args": {}, "return_result": True},
            ],
            stop_on_error=False,
            return_all_results=True,
        )

        assert result["success"] is False
        assert result["executed_count"] == 3
        assert result["total_count"] == 3
        assert result["stopped_at"] is None
        assert "First error" in result["errors"][0]
        assert result["errors"][1] is None
        assert "Third error" in result["errors"][2]
        assert result["results"][0] is None  # Failed
        assert result["results"][1] == {"status": "clicked"}
        assert result["results"][2] is None  # Failed


@pytest.mark.asyncio
async def test_bulk_execution_empty_commands():
    """Test empty commands array validation."""
    result = await browser_execute_bulk(commands=[])

    assert result["success"] is False
    assert result["executed_count"] == 0
    assert result["total_count"] == 0
    assert result["errors"] == ["commands array cannot be empty"]


@pytest.mark.asyncio
async def test_bulk_execution_invalid_command_structure():
    """Test validation of command structure."""
    # Test non-dict command
    result = await browser_execute_bulk(
        commands=[
            "not a dict",
        ]
    )
    assert result["success"] is False
    assert "not a dictionary" in result["errors"][0]

    # Test missing 'tool' field
    result = await browser_execute_bulk(
        commands=[
            {"args": {}},
        ]
    )
    assert result["success"] is False
    assert "missing required 'tool' field" in result["errors"][0]

    # Test missing 'args' field
    result = await browser_execute_bulk(
        commands=[
            {"tool": "browser_navigate"},
        ]
    )
    assert result["success"] is False
    assert "missing required 'args' field" in result["errors"][0]


@pytest.mark.asyncio
async def test_bulk_execution_single_command():
    """Test single command execution."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = {"status": "navigated"}

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}, "return_result": True},
            ]
        )

        assert result["success"] is True
        assert result["executed_count"] == 1
        assert result["total_count"] == 1
        assert result["results"] == [{"status": "navigated"}]


@pytest.mark.asyncio
async def test_bulk_execution_workflow_navigate_wait_snapshot():
    """Test navigate→wait→snapshot workflow pattern."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.side_effect = [
            {"success": True, "url": "https://example.com"},
            {"success": True},
            {"snapshot": "- button 'Submit' [ref=e1]\n- textbox 'Email' [ref=e2]"},
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": True}},
                {"tool": "browser_wait_for", "args": {"text": "Loaded"}},
                {"tool": "browser_snapshot", "args": {"output_format": "yaml"}, "return_result": True},
            ]
        )

        assert result["success"] is True
        assert result["executed_count"] == 3
        assert result["results"][2]["snapshot"] == "- button 'Submit' [ref=e1]\n- textbox 'Email' [ref=e2]"
        assert mock_tool.call_count == 3


@pytest.mark.asyncio
async def test_bulk_execution_workflow_form_filling():
    """Test form filling workflow pattern."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.side_effect = [
            {"success": True},  # navigate
            {"success": True},  # type
            {"success": True},  # click
            {"success": True},  # wait
            {"snapshot": "- heading 'Success' [ref=e1]"},  # snapshot
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com/form", "silent_mode": True}},
                {"tool": "browser_type", "args": {"element": "textbox", "ref": "e1", "text": "test@example.com"}},
                {"tool": "browser_click", "args": {"element": "button", "ref": "e2"}},
                {"tool": "browser_wait_for", "args": {"text": "Success"}},
                {"tool": "browser_snapshot", "args": {}, "return_result": True},
            ]
        )

        assert result["success"] is True
        assert result["executed_count"] == 5
        assert result["results"][4]["snapshot"] == "- heading 'Success' [ref=e1]"


@pytest.mark.asyncio
async def test_bulk_execution_mixed_response_types():
    """Test handling of different response types (dicts, strings, etc)."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        # Different return types: dict, dict, string (blob URI)
        mock_tool.side_effect = [
            {"success": True},
            {"snapshot": {"data": "value"}},
            "blob://123-abc.png",
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
                {"tool": "browser_snapshot", "args": {}, "return_result": True},
                {"tool": "browser_take_screenshot", "args": {}, "return_result": True},
            ],
            return_all_results=True,
        )

        assert result["success"] is True
        assert result["results"][0] == {"success": True}
        assert result["results"][1] == {"snapshot": {"data": "value"}}
        assert result["results"][2] == "blob://123-abc.png"


@pytest.mark.asyncio
async def test_bulk_execution_no_return_results():
    """Test execution with no return_result flags (all None)."""
    with patch("playwright_proxy_mcp.server._call_playwright_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.side_effect = [
            {"status": "ok"},
            {"status": "ok"},
            {"status": "ok"},
        ]

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
                {"tool": "browser_click", "args": {"element": "button"}},
                {"tool": "browser_wait_for", "args": {"time": 500}},
            ]
        )

        assert result["success"] is True
        assert result["executed_count"] == 3
        assert result["results"] == [None, None, None]
