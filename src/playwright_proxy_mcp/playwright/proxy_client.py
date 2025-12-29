"""
Proxy client integration for playwright-mcp

Manages the connection between FastMCP proxy and the playwright-mcp HTTP server,
integrating middleware for response transformation.

Uses FastMCP Client with StreamableHttpTransport for HTTP-based communication.
"""

import logging
import time
from typing import Any

from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

from .config import PLAYWRIGHT_HTTP_HOST, PLAYWRIGHT_HTTP_PORT
from .middleware import BinaryInterceptionMiddleware
from .process_manager import PlaywrightProcessManager

logger = logging.getLogger(__name__)


class PlaywrightProxyClient:
    """
    Custom proxy client that integrates process management and middleware.

    This class manages the playwright-mcp subprocess (running as HTTP server)
    and provides hooks for response transformation through middleware.
    """

    def __init__(
        self,
        process_manager: PlaywrightProcessManager,
        middleware: BinaryInterceptionMiddleware,
    ) -> None:
        """
        Initialize proxy client.

        Args:
            process_manager: Process manager for playwright-mcp
            middleware: Binary interception middleware
        """
        self.process_manager = process_manager
        self.middleware = middleware
        self._client: Client | None = None
        self._started = False
        self._available_tools: dict[str, Any] = {}

    async def start(self, config: Any) -> None:
        """
        Start the proxy client and playwright-mcp HTTP server.

        Args:
            config: Playwright configuration
        """
        if self._started:
            logger.warning("Proxy client already started")
            return

        logger.info("Starting playwright proxy client...")

        # Start playwright-mcp HTTP server subprocess
        await self.process_manager.start(config)

        # Create HTTP transport
        transport = StreamableHttpTransport(
            url=f"http://{PLAYWRIGHT_HTTP_HOST}:{PLAYWRIGHT_HTTP_PORT}/mcp"
        )

        # Create and connect FastMCP client
        self._client = Client(transport=transport)
        await self._client.__aenter__()

        # Discover available tools
        await self._discover_tools()

        self._started = True
        logger.info("Playwright proxy client started")

    async def stop(self) -> None:
        """Stop the proxy client and HTTP server subprocess"""
        if not self._started:
            return

        logger.info("Stopping playwright proxy client...")

        # Disconnect FastMCP client
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
            finally:
                self._client = None

        # Stop subprocess
        await self.process_manager.stop()

        self._started = False
        logger.info("Playwright proxy client stopped")

    async def is_healthy(self) -> bool:
        """
        Check if the proxy client is healthy.

        Returns:
            True if client is started and process is healthy
        """
        if not self._started or not self._client:
            return False

        return await self.process_manager.is_healthy()

    async def _discover_tools(self) -> None:
        """
        Discover available tools from playwright-mcp.
        """
        try:
            logger.info("UPSTREAM_MCP → Discovering tools...")

            # List tools via FastMCP client
            tools = await self._client.list_tools()

            # Convert to dictionary
            self._available_tools = {}
            for tool in tools:
                self._available_tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }

            logger.info(
                f"UPSTREAM_MCP ← Discovered {len(self._available_tools)} tools: "
                f"{', '.join(self._available_tools.keys())}"
            )

        except Exception as e:
            logger.error(f"UPSTREAM_MCP ✗ Tool discovery failed: {e}")
            raise RuntimeError(f"Failed to discover tools: {e}") from e

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on the upstream playwright-mcp server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result (potentially transformed by middleware)

        Raises:
            RuntimeError: If tool call fails
        """
        if not self._started or not self._client:
            raise RuntimeError("Proxy client not started")

        start_time = time.time()

        try:
            logger.info(f"UPSTREAM_MCP → Calling tool: {tool_name}")

            # Call tool via FastMCP client
            result = await self._client.call_tool(tool_name, arguments)

            # Check for errors
            if result.isError:
                # Extract error message from first content item
                error_text = (
                    result.content[0].text if result.content else "Unknown error"
                )
                raise RuntimeError(f"Tool call failed: {error_text}")

            # Transform through middleware
            transformed_result = await self.transform_response(tool_name, result)

            duration = (time.time() - start_time) * 1000  # ms
            logger.info(f"UPSTREAM_MCP ← Tool result: {tool_name} ({duration:.2f}ms)")

            return transformed_result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"UPSTREAM_MCP ✗ Tool call failed: {tool_name} ({duration:.2f}ms) - "
                f"{type(e).__name__}: {e}"
            )
            raise

    def get_available_tools(self) -> dict[str, Any]:
        """
        Get the list of available tools.

        Returns:
            Dictionary of tool name to tool definition
        """
        return self._available_tools.copy()

    async def transform_response(self, tool_name: str, response: Any) -> Any:
        """
        Transform a tool response through middleware.

        This is called after receiving a response from playwright-mcp to
        potentially intercept and store large binary data.

        Args:
            tool_name: Name of the tool that was called
            response: Response from playwright-mcp (CallToolResult)

        Returns:
            Potentially transformed response
        """
        try:
            return await self.middleware.intercept_response(tool_name, response)
        except Exception as e:
            logger.error(f"Error transforming response for {tool_name}: {e}")
            # Return original response if transformation fails
            return response

    def get_process(self) -> Any:
        """
        Get the underlying subprocess.

        Returns:
            The playwright-mcp subprocess
        """
        return self.process_manager.process
