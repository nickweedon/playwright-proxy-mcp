"""
Skeleton MCP Server

This is the main entry point for the MCP server. It registers all tools,
resources, and prompts that will be available to MCP clients.

To customize this server:
1. Add your API modules in the api/ directory
2. Import and register tools from those modules
3. Add resources for file/data access
4. Add prompts for common operations
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastmcp import FastMCP

from .client import get_client_config
from .api import example

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP(
    name="Skeleton MCP Server",
    instructions="""
    This is a skeleton MCP server template.

    Customize this description to explain what your MCP server does
    and how clients should interact with it.
    """,
)


def timing_middleware(func: Callable) -> Callable:
    """Middleware to log execution time for tools."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
            raise

    return wrapper


# =============================================================================
# TOOLS
# =============================================================================
# Register your MCP tools here. Tools are functions that can be called by
# MCP clients to perform actions.


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """
    Check the health status of the MCP server.

    Returns:
        A dictionary with the server status and configuration info.
    """
    config = get_client_config()
    return {
        "status": "healthy",
        "server": "Skeleton MCP Server",
        "version": "0.1.0",
        "api_configured": config.get("api_key") is not None,
    }


# Register tools from API modules
# Example: Import and register tools from your custom modules
mcp.tool()(example.list_items)
mcp.tool()(example.get_item)
mcp.tool()(example.create_item)
mcp.tool()(example.update_item)
mcp.tool()(example.delete_item)


# =============================================================================
# RESOURCES
# =============================================================================
# Register your MCP resources here. Resources provide read-only access to
# data that clients can retrieve.


@mcp.resource("skeleton://status")
async def get_status() -> str:
    """Get the current server status."""
    return "Server is running"


# =============================================================================
# PROMPTS
# =============================================================================
# Register your MCP prompts here. Prompts are templates that help guide
# how clients interact with your server.


@mcp.prompt()
def getting_started() -> str:
    """A prompt to help users get started with this MCP server."""
    return """
    Welcome to the Skeleton MCP Server!

    This server provides the following capabilities:

    1. health_check - Check if the server is running properly
    2. list_items - List all items (example)
    3. get_item - Get a specific item by ID
    4. create_item - Create a new item
    5. update_item - Update an existing item
    6. delete_item - Delete an item

    To get started, try calling the health_check tool to verify
    the server is configured correctly.
    """


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Run the MCP server."""
    logger.info("Starting Skeleton MCP Server...")
    mcp.run()


if __name__ == "__main__":
    main()
