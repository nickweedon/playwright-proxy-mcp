"""
Tests for playwright proxy client
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.playwright.proxy_client import PlaywrightProxyClient


@pytest.fixture
def mock_process_manager():
    """Create a mock process manager."""
    manager = Mock()
    manager.set_process = AsyncMock()
    manager.stop = AsyncMock()
    manager.is_healthy = AsyncMock(return_value=True)
    manager.process = None
    return manager


@pytest.fixture
def mock_middleware():
    """Create a mock middleware."""
    middleware = Mock()
    middleware.intercept_response = AsyncMock(side_effect=lambda tool, resp: resp)
    return middleware


@pytest.fixture
def proxy_client(mock_process_manager, mock_middleware):
    """Create a proxy client instance."""
    return PlaywrightProxyClient(mock_process_manager, mock_middleware)


class TestPlaywrightProxyClient:
    """Tests for PlaywrightProxyClient."""

    def test_init(self, mock_process_manager, mock_middleware):
        """Test proxy client initialization."""
        client = PlaywrightProxyClient(mock_process_manager, mock_middleware)

        assert client.process_manager == mock_process_manager
        assert client.middleware == mock_middleware
        assert not client._started

    @pytest.mark.asyncio
    async def test_start(self, proxy_client):
        """Test starting the proxy client."""
        config = {"browser": "chromium", "headless": True}

        # Mock StdioTransport
        mock_transport = Mock()
        mock_transport._process = None

        # Mock the FastMCP Client and its methods
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        # Patch StdioTransport and Client creation
        with patch('playwright_proxy_mcp.playwright.proxy_client.StdioTransport', return_value=mock_transport):
            with patch('playwright_proxy_mcp.playwright.proxy_client.Client', return_value=mock_client):
                with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                    await proxy_client.start(config)

        assert proxy_client._started
        assert proxy_client._client is not None
        assert proxy_client._transport is not None

    @pytest.mark.asyncio
    async def test_start_already_started(self, proxy_client):
        """Test starting when already started."""
        config = {"browser": "chromium"}

        # Mock StdioTransport
        mock_transport = Mock()
        mock_transport._process = None

        # Mock the FastMCP Client
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        # Patch Client creation
        with patch('playwright_proxy_mcp.playwright.proxy_client.StdioTransport', return_value=mock_transport):
            with patch('playwright_proxy_mcp.playwright.proxy_client.Client', return_value=mock_client):
                with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                    await proxy_client.start(config)
                    await proxy_client.start(config)  # Second call should be no-op

        # Should only start once
        assert proxy_client._started
        assert mock_client.__aenter__.call_count == 1

    @pytest.mark.asyncio
    async def test_stop(self, proxy_client, mock_process_manager):
        """Test stopping the proxy client."""
        # Mock the FastMCP Client
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        mock_transport = Mock()
        mock_transport._process = None

        # Patch Client creation
        with patch('playwright_proxy_mcp.playwright.proxy_client.StdioTransport', return_value=mock_transport):
            with patch('playwright_proxy_mcp.playwright.proxy_client.Client', return_value=mock_client):
                with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                    # Start first
                    await proxy_client.start({"browser": "chromium"})
                    await proxy_client.stop()

        assert not proxy_client._started
        mock_process_manager.stop.assert_called_once()
        mock_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_started(self, proxy_client, mock_process_manager):
        """Test stopping when not started."""
        await proxy_client.stop()

        # Should not call stop on process manager
        mock_process_manager.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_healthy_started(self, proxy_client):
        """Test health check when started and healthy."""
        proxy_client._started = True

        # Mock client with successful ping
        mock_client = Mock()
        mock_client.ping = AsyncMock(return_value=True)
        proxy_client._client = mock_client

        assert await proxy_client.is_healthy()
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_healthy_not_started(self, proxy_client):
        """Test health check when not started."""
        assert not await proxy_client.is_healthy()

    @pytest.mark.asyncio
    async def test_is_healthy_ping_fails(self, proxy_client):
        """Test health check when ping fails."""
        proxy_client._started = True

        # Mock client with failing ping
        mock_client = Mock()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection failed"))
        proxy_client._client = mock_client

        assert not await proxy_client.is_healthy()

    @pytest.mark.asyncio
    async def test_call_tool(self, proxy_client, mock_middleware):
        """Test calling a tool."""
        proxy_client._started = True

        # Mock client
        mock_result = Mock()
        mock_result.is_error = False
        mock_result.content = [Mock(text="Success")]

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        result = await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})

        mock_client.call_tool.assert_called_once_with("browser_navigate", {"url": "https://example.com"})
        mock_middleware.intercept_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_not_started(self, proxy_client):
        """Test calling a tool when not started."""
        with pytest.raises(RuntimeError, match="not started"):
            await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_call_tool_error_result(self, proxy_client):
        """Test calling a tool that returns an error."""
        proxy_client._started = True

        # Mock client with error result
        mock_result = Mock()
        mock_result.is_error = True
        mock_result.content = [Mock(text="Navigation failed")]

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        with pytest.raises(RuntimeError, match="Tool call failed"):
            await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})

    def test_get_available_tools(self, proxy_client):
        """Test getting available tools."""
        proxy_client._available_tools = {"tool1": {"name": "tool1"}, "tool2": {"name": "tool2"}}

        tools = proxy_client.get_available_tools()

        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    @pytest.mark.asyncio
    async def test_transform_response(self, proxy_client, mock_middleware):
        """Test transform_response."""
        mock_response = Mock()
        # intercept_response is an AsyncMock, so set its return value properly
        async def mock_intercept(tool, resp):
            return "transformed"
        mock_middleware.intercept_response = AsyncMock(side_effect=mock_intercept)

        result = await proxy_client.transform_response("browser_navigate", mock_response)

        assert result == "transformed"
        mock_middleware.intercept_response.assert_called_once_with("browser_navigate", mock_response)

    @pytest.mark.asyncio
    async def test_build_command_standard_mode(self, proxy_client):
        """Test command building in standard mode."""
        config = {"browser": "firefox", "headless": True, "viewport_size": "1024x768"}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        assert command[0] == '/usr/bin/npx'
        assert '@playwright/mcp@latest' in command
        assert '--browser' in command
        assert 'firefox' in command
        assert '--headless' in command
        assert '--viewport-size' in command
        # Verify NO HTTP args
        assert '--host' not in command
        assert '--port' not in command

    @pytest.mark.asyncio
    async def test_build_command_wsl_windows_mode(self, proxy_client):
        """Test command building in WSL-Windows mode."""
        config = {"browser": "chrome"}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=True):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='C:\\Windows\\System32\\cmd.exe'):
                command = proxy_client._build_command(config)

        assert 'cmd.exe' in command[0]
        assert '/c' in command
        assert 'npx.cmd' in command
        assert '@playwright/mcp@latest' in command

    def test_build_command_minimal_config(self, proxy_client):
        """Test command building with minimal configuration."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # Should only have npx and package
        assert command == ['/usr/bin/npx', '@playwright/mcp@latest']

    def test_build_command_all_boolean_flags(self, proxy_client):
        """Test command building with all boolean flags enabled."""
        config = {
            "headless": True,
            "no_sandbox": True,
            "isolated": True,
            "save_session": True,
            "save_trace": True,
            "ignore_https_errors": True,
            "extension": True,
            "shared_browser_context": True,
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        assert '--headless' in command
        assert '--no-sandbox' in command
        assert '--isolated' in command
        assert '--save-session' in command
        assert '--save-trace' in command
        assert '--ignore-https-errors' in command
        assert '--extension' in command
        assert '--shared-browser-context' in command

    def test_build_command_all_string_options(self, proxy_client):
        """Test command building with all string-based options."""
        config = {
            "browser": "chromium",
            "device": "iPhone 12",
            "viewport_size": "1920x1080",
            "user_data_dir": "/tmp/user-data",
            "storage_state": "/tmp/storage.json",
            "allowed_origins": "https://example.com",
            "blocked_origins": "https://ads.com",
            "proxy_server": "http://proxy:8080",
            "caps": "video",
            "save_video": "on-failure",
            "output_dir": "/tmp/output",
            "timeout_action": 30000,
            "timeout_navigation": 60000,
            "image_responses": "base64",
            "user_agent": "CustomAgent/1.0",
            "init_script": "/tmp/init.js",
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # Check all key-value pairs
        assert '--browser' in command and 'chromium' in command
        assert '--device' in command and 'iPhone 12' in command
        assert '--viewport-size' in command and '1920x1080' in command
        assert '--user-data-dir' in command and '/tmp/user-data' in command
        assert '--storage-state' in command and '/tmp/storage.json' in command
        assert '--allowed-origins' in command and 'https://example.com' in command
        assert '--blocked-origins' in command and 'https://ads.com' in command
        assert '--proxy-server' in command and 'http://proxy:8080' in command
        assert '--caps' in command and 'video' in command
        assert '--save-video' in command and 'on-failure' in command
        assert '--output-dir' in command and '/tmp/output' in command
        assert '--timeout-action' in command and '30000' in command
        assert '--timeout-navigation' in command and '60000' in command
        assert '--image-responses' in command and 'base64' in command
        assert '--user-agent' in command and 'CustomAgent/1.0' in command
        assert '--init-script' in command and '/tmp/init.js' in command

    def test_build_command_false_boolean_values(self, proxy_client):
        """Test that false boolean values don't add flags."""
        config = {
            "headless": False,
            "no_sandbox": False,
            "isolated": False,
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # False values should not add flags
        assert '--headless' not in command
        assert '--no-sandbox' not in command
        assert '--isolated' not in command

    def test_build_command_empty_string_values(self, proxy_client):
        """Test that empty string values don't add options."""
        config = {
            "device": "",
            "viewport_size": "",
            "user_agent": "",
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # Empty strings should not add options
        assert '--device' not in command
        assert '--viewport-size' not in command
        assert '--user-agent' not in command

    def test_build_command_npx_not_found_standard_mode(self, proxy_client):
        """Test error when npx is not found in standard mode."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value=None):
                with pytest.raises(RuntimeError, match="npx not found in PATH"):
                    proxy_client._build_command(config)

    def test_build_command_cmd_not_found_wsl_mode(self, proxy_client):
        """Test error when cmd.exe is not found in WSL mode."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=True):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value=None):
                with pytest.raises(RuntimeError, match="cmd.exe not found in PATH"):
                    proxy_client._build_command(config)

    def test_build_env_minimal(self, proxy_client):
        """Test environment building with minimal config."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.os.environ', {"PATH": "/usr/bin"}):
            env = proxy_client._build_env(config)

        assert "PATH" in env
        assert "PLAYWRIGHT_MCP_EXTENSION_TOKEN" not in env

    def test_build_env_with_extension_token(self, proxy_client):
        """Test environment building with extension token."""
        config = {"extension_token": "test-token-123"}

        with patch('playwright_proxy_mcp.playwright.proxy_client.os.environ', {"PATH": "/usr/bin"}):
            env = proxy_client._build_env(config)

        assert env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] == "test-token-123"

    def test_build_env_empty_extension_token(self, proxy_client):
        """Test that empty extension token is not added to env."""
        config = {"extension_token": ""}

        with patch('playwright_proxy_mcp.playwright.proxy_client.os.environ', {"PATH": "/usr/bin"}):
            env = proxy_client._build_env(config)

        assert "PLAYWRIGHT_MCP_EXTENSION_TOKEN" not in env


class TestProxyClientHelperMethods:
    """Tests for helper methods in PlaywrightProxyClient."""

    def test_add_browser_args_with_browser(self, proxy_client):
        """Test _add_browser_args with browser option."""
        command = []
        config = {"browser": "firefox"}
        proxy_client._add_browser_args(command, config)
        assert command == ["--browser", "firefox"]

    def test_add_browser_args_with_headless(self, proxy_client):
        """Test _add_browser_args with headless option."""
        command = []
        config = {"headless": True}
        proxy_client._add_browser_args(command, config)
        assert "--headless" in command

    def test_add_browser_args_without_headless(self, proxy_client):
        """Test _add_browser_args with headless=False."""
        command = []
        config = {"headless": False}
        proxy_client._add_browser_args(command, config)
        assert "--headless" not in command

    def test_add_browser_args_with_no_sandbox(self, proxy_client):
        """Test _add_browser_args with no_sandbox option."""
        command = []
        config = {"no_sandbox": True}
        proxy_client._add_browser_args(command, config)
        assert "--no-sandbox" in command

    def test_add_browser_args_with_device(self, proxy_client):
        """Test _add_browser_args with device option."""
        command = []
        config = {"device": "Pixel 5"}
        proxy_client._add_browser_args(command, config)
        assert command == ["--device", "Pixel 5"]

    def test_add_browser_args_with_viewport(self, proxy_client):
        """Test _add_browser_args with viewport_size option."""
        command = []
        config = {"viewport_size": "800x600"}
        proxy_client._add_browser_args(command, config)
        assert command == ["--viewport-size", "800x600"]

    def test_add_browser_args_with_isolated(self, proxy_client):
        """Test _add_browser_args with isolated option."""
        command = []
        config = {"isolated": True}
        proxy_client._add_browser_args(command, config)
        assert "--isolated" in command

    def test_add_session_args_with_user_data_dir(self, proxy_client):
        """Test _add_session_args with user_data_dir."""
        command = []
        config = {"user_data_dir": "/tmp/data"}
        proxy_client._add_session_args(command, config)
        assert command == ["--user-data-dir", "/tmp/data"]

    def test_add_session_args_with_storage_state(self, proxy_client):
        """Test _add_session_args with storage_state."""
        command = []
        config = {"storage_state": "/tmp/state.json"}
        proxy_client._add_session_args(command, config)
        assert command == ["--storage-state", "/tmp/state.json"]

    def test_add_session_args_with_save_session(self, proxy_client):
        """Test _add_session_args with save_session."""
        command = []
        config = {"save_session": True}
        proxy_client._add_session_args(command, config)
        assert "--save-session" in command

    def test_add_network_args_with_allowed_origins(self, proxy_client):
        """Test _add_network_args with allowed_origins."""
        command = []
        config = {"allowed_origins": "https://example.com"}
        proxy_client._add_network_args(command, config)
        assert command == ["--allowed-origins", "https://example.com"]

    def test_add_network_args_with_blocked_origins(self, proxy_client):
        """Test _add_network_args with blocked_origins."""
        command = []
        config = {"blocked_origins": "https://ads.com"}
        proxy_client._add_network_args(command, config)
        assert command == ["--blocked-origins", "https://ads.com"]

    def test_add_network_args_with_proxy_server(self, proxy_client):
        """Test _add_network_args with proxy_server."""
        command = []
        config = {"proxy_server": "http://proxy:8080"}
        proxy_client._add_network_args(command, config)
        assert command == ["--proxy-server", "http://proxy:8080"]

    def test_add_network_args_with_caps(self, proxy_client):
        """Test _add_network_args with caps."""
        command = []
        config = {"caps": "vision,pdf"}
        proxy_client._add_network_args(command, config)
        assert command == ["--caps", "vision,pdf"]

    def test_add_recording_args_with_save_trace(self, proxy_client):
        """Test _add_recording_args with save_trace."""
        command = []
        config = {"save_trace": True}
        proxy_client._add_recording_args(command, config)
        assert "--save-trace" in command

    def test_add_recording_args_with_save_video(self, proxy_client):
        """Test _add_recording_args with save_video."""
        command = []
        config = {"save_video": "on-failure"}
        proxy_client._add_recording_args(command, config)
        assert command == ["--save-video", "on-failure"]

    def test_add_recording_args_with_output_dir(self, proxy_client):
        """Test _add_recording_args with output_dir."""
        command = []
        config = {"output_dir": "/tmp/output"}
        proxy_client._add_recording_args(command, config)
        assert command == ["--output-dir", "/tmp/output"]

    def test_add_timeout_args_with_action(self, proxy_client):
        """Test _add_timeout_args with timeout_action."""
        command = []
        config = {"timeout_action": 20000}
        proxy_client._add_timeout_args(command, config)
        assert command == ["--timeout-action", "20000"]

    def test_add_timeout_args_with_navigation(self, proxy_client):
        """Test _add_timeout_args with timeout_navigation."""
        command = []
        config = {"timeout_navigation": 45000}
        proxy_client._add_timeout_args(command, config)
        assert command == ["--timeout-navigation", "45000"]

    def test_add_timeout_args_with_image_responses(self, proxy_client):
        """Test _add_timeout_args with image_responses."""
        command = []
        config = {"image_responses": "omit"}
        proxy_client._add_timeout_args(command, config)
        assert command == ["--image-responses", "omit"]

    def test_add_stealth_args_with_user_agent(self, proxy_client):
        """Test _add_stealth_args with user_agent."""
        command = []
        config = {"user_agent": "CustomBot/1.0"}
        proxy_client._add_stealth_args(command, config)
        assert command == ["--user-agent", "CustomBot/1.0"]

    def test_add_stealth_args_with_init_script(self, proxy_client):
        """Test _add_stealth_args with init_script."""
        command = []
        config = {"init_script": "/tmp/script.js"}
        proxy_client._add_stealth_args(command, config)
        assert command == ["--init-script", "/tmp/script.js"]

    def test_add_stealth_args_with_ignore_https_errors(self, proxy_client):
        """Test _add_stealth_args with ignore_https_errors."""
        command = []
        config = {"ignore_https_errors": True}
        proxy_client._add_stealth_args(command, config)
        assert "--ignore-https-errors" in command

    def test_add_extension_args_with_extension(self, proxy_client):
        """Test _add_extension_args with extension."""
        command = []
        config = {"extension": True}
        proxy_client._add_extension_args(command, config)
        assert "--extension" in command

    def test_add_extension_args_with_shared_context(self, proxy_client):
        """Test _add_extension_args with shared_browser_context."""
        command = []
        config = {"shared_browser_context": True}
        proxy_client._add_extension_args(command, config)
        assert "--shared-browser-context" in command

    def test_add_config_arguments_multiple(self, proxy_client):
        """Test _add_config_arguments with multiple options."""
        command = []
        config = {
            "browser": "webkit",
            "headless": True,
            "timeout_action": 30000,
            "caps": "vision",
        }
        proxy_client._add_config_arguments(command, config)
        assert "--browser" in command
        assert "webkit" in command
        assert "--headless" in command
        assert "--timeout-action" in command
        assert "30000" in command
        assert "--caps" in command
        assert "vision" in command


@pytest.mark.asyncio
class TestProxyClientToolCalls:
    """Additional tests for proxy client tool calls."""

    async def test_call_tool_timeout_handling(self, proxy_client):
        """Test timeout handling during tool calls."""
        import asyncio as aio

        proxy_client._started = True

        async def slow_call(*args, **kwargs):
            await aio.sleep(100)  # Very slow response
            return Mock()

        mock_client = Mock()
        mock_client.call_tool = slow_call
        proxy_client._client = mock_client

        # The internal call_tool timeout (90s) won't trigger, but external wait_for will
        # This tests that the call can be cancelled/timeout
        with pytest.raises((TimeoutError, asyncio.TimeoutError)):
            await asyncio.wait_for(
                proxy_client.call_tool("browser_navigate", {"url": "https://example.com"}),
                timeout=0.1
            )

    async def test_transform_response_error_handling(self, proxy_client, mock_middleware):
        """Test error handling in transform_response."""
        mock_middleware.intercept_response = AsyncMock(side_effect=ValueError("Bad data"))

        result = await proxy_client.transform_response("browser_navigate", {"data": "test"})

        # Should return original response on error
        assert result == {"data": "test"}

    async def test_discover_tools_no_client(self, proxy_client):
        """Test _discover_tools when client is None."""
        proxy_client._client = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await proxy_client._discover_tools()

    async def test_discover_tools_success(self, proxy_client):
        """Test successful tool discovery."""
        mock_tool = Mock()
        mock_tool.name = "browser_navigate"
        mock_tool.description = "Navigate to URL"
        mock_tool.inputSchema = {"type": "object"}

        mock_client = Mock()
        mock_client.list_tools = AsyncMock(return_value=[mock_tool])
        proxy_client._client = mock_client

        await proxy_client._discover_tools()

        assert "browser_navigate" in proxy_client._available_tools
        assert proxy_client._available_tools["browser_navigate"]["description"] == "Navigate to URL"

    async def test_call_tool_exception_handling(self, proxy_client):
        """Test exception handling in call_tool."""
        proxy_client._started = True

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(side_effect=ConnectionError("Lost connection"))
        proxy_client._client = mock_client

        with pytest.raises(ConnectionError, match="Lost connection"):
            await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})


class TestProxyClientBaseCommand:
    """Tests for _build_base_command and related methods."""

    def test_build_base_command_standard(self, proxy_client):
        """Test _build_base_command in standard mode."""
        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_base_command()
        assert command == ['/usr/bin/npx']

    def test_build_base_command_wsl(self, proxy_client):
        """Test _build_base_command in WSL mode."""
        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=True):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/mnt/c/Windows/System32/cmd.exe'):
                command = proxy_client._build_base_command()
        assert 'cmd.exe' in command[0]
        assert '/c' in command
        assert 'npx.cmd' in command

    def test_build_standard_command_success(self, proxy_client):
        """Test _build_standard_command with npx available."""
        with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/local/bin/npx'):
            command = proxy_client._build_standard_command()
        assert command == ['/usr/local/bin/npx']

    def test_build_standard_command_not_found(self, proxy_client):
        """Test _build_standard_command when npx not found."""
        with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value=None):
            with pytest.raises(RuntimeError, match="npx not found"):
                proxy_client._build_standard_command()

    def test_build_wsl_windows_command_success(self, proxy_client):
        """Test _build_wsl_windows_command with cmd.exe available."""
        with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/mnt/c/Windows/System32/cmd.exe'):
            command = proxy_client._build_wsl_windows_command()
        assert 'cmd.exe' in command[0]
        assert '/c' in command
        assert 'npx.cmd' in command

    def test_build_wsl_windows_command_not_found(self, proxy_client):
        """Test _build_wsl_windows_command when cmd.exe not found."""
        with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value=None):
            with pytest.raises(RuntimeError, match="cmd.exe not found"):
                proxy_client._build_wsl_windows_command()


class TestProxyClientEdgeCases:
    """Edge case tests for PlaywrightProxyClient."""

    @pytest.fixture
    def mock_process_manager(self):
        """Create a mock process manager."""
        manager = Mock()
        manager.set_process = AsyncMock()
        manager.stop = AsyncMock()
        manager.is_healthy = AsyncMock(return_value=True)
        manager.process = None
        return manager

    @pytest.fixture
    def mock_middleware(self):
        """Create a mock middleware."""
        middleware = Mock()
        middleware.intercept_response = AsyncMock(side_effect=lambda tool, resp: resp)
        return middleware

    @pytest.fixture
    def proxy_client(self, mock_process_manager, mock_middleware):
        """Create a proxy client instance."""
        return PlaywrightProxyClient(mock_process_manager, mock_middleware)

    def test_get_available_tools_empty(self, proxy_client):
        """Test get_available_tools returns empty dict initially."""
        tools = proxy_client.get_available_tools()
        assert tools == {}

    def test_get_available_tools_returns_copy(self, proxy_client):
        """Test get_available_tools returns a copy, not the original."""
        proxy_client._available_tools = {"test": {"name": "test"}}
        tools = proxy_client.get_available_tools()
        tools["new"] = {"name": "new"}
        assert "new" not in proxy_client._available_tools

    @pytest.mark.asyncio
    async def test_is_healthy_timeout(self, proxy_client):
        """Test is_healthy handles timeout."""
        proxy_client._started = True

        async def slow_ping(*args, **kwargs):
            await asyncio.sleep(10)
            return True

        mock_client = Mock()
        mock_client.ping = slow_ping
        proxy_client._client = mock_client

        # The internal timeout of 3.0 seconds should trigger
        result = await proxy_client.is_healthy()
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_client_error_handling(self, proxy_client, mock_process_manager):
        """Test stop handles client exit error gracefully."""
        proxy_client._started = True

        mock_client = Mock()
        mock_client.__aexit__ = AsyncMock(side_effect=RuntimeError("Exit error"))
        proxy_client._client = mock_client
        proxy_client._transport = Mock()

        # Should not raise
        await proxy_client.stop()

        assert not proxy_client._started
        assert proxy_client._client is None

    def test_add_browser_args_none_values(self, proxy_client):
        """Test _add_browser_args handles None values."""
        command = []
        config = {"device": None, "viewport_size": None}
        proxy_client._add_browser_args(command, config)
        assert "--device" not in command
        assert "--viewport-size" not in command

    def test_add_session_args_empty_values(self, proxy_client):
        """Test _add_session_args handles empty string values."""
        command = []
        config = {"user_data_dir": "", "storage_state": ""}
        proxy_client._add_session_args(command, config)
        assert "--user-data-dir" not in command
        assert "--storage-state" not in command

    def test_add_network_args_empty_caps(self, proxy_client):
        """Test _add_network_args handles empty caps."""
        command = []
        config = {"caps": ""}
        proxy_client._add_network_args(command, config)
        assert "--caps" not in command

    def test_add_stealth_args_empty_values(self, proxy_client):
        """Test _add_stealth_args handles empty values."""
        command = []
        config = {"user_agent": "", "init_script": ""}
        proxy_client._add_stealth_args(command, config)
        assert "--user-agent" not in command
        assert "--init-script" not in command

    @pytest.mark.asyncio
    async def test_call_tool_result_with_text_content(self, proxy_client, mock_middleware):
        """Test call_tool extracts error from TextContent."""
        from mcp.types import TextContent

        proxy_client._started = True

        mock_result = Mock()
        mock_result.is_error = True
        mock_result.content = [TextContent(type="text", text="Specific error message")]

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        with pytest.raises(RuntimeError, match="Specific error message"):
            await proxy_client.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_result_with_duck_typed_content(self, proxy_client, mock_middleware):
        """Test call_tool extracts error from duck-typed content."""
        proxy_client._started = True

        # Create a duck-typed object with .text attribute
        class DuckContent:
            text = "Duck typed error"

        mock_result = Mock()
        mock_result.is_error = True
        mock_result.content = [DuckContent()]

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        with pytest.raises(RuntimeError, match="Duck typed error"):
            await proxy_client.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_result_empty_content(self, proxy_client, mock_middleware):
        """Test call_tool handles empty content list."""
        proxy_client._started = True

        mock_result = Mock()
        mock_result.is_error = True
        mock_result.content = []

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        with pytest.raises(RuntimeError, match="Unknown error"):
            await proxy_client.call_tool("test_tool", {})
