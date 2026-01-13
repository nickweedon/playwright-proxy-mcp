"""
Playwright MCP Proxy Server

A proxy server for Microsoft's playwright-mcp that provides efficient handling
of large binary data (screenshots, PDFs) through blob storage.

This server:
1. Runs playwright-mcp as a subprocess using npx
2. Proxies all playwright browser automation tools
3. Intercepts large binary responses and stores them as blobs
4. Returns blob:// URIs for large binary data (retrieval delegated to MCP Resource Server)
"""

import sys
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from .middleware import MCPLoggingMiddleware
from .playwright import (
    BinaryInterceptionMiddleware,
    PlaywrightBlobManager,
    PoolManager,
    load_blob_config,
    load_pool_manager_config,
)
from .utils.logging_config import get_logger, log_tool_result, setup_file_logging

# Configure logging using centralized utility
setup_file_logging(log_file="logs/playwright-proxy-mcp.log")
logger = get_logger(__name__)

# Log Python interpreter information at startup

logger.info(f"Python interpreter: {sys.executable}")
logger.info(f"Python version: {sys.version}")

# Global components
pool_manager_config = None
blob_config = None
blob_manager = None
middleware = None
pool_manager = None
navigation_cache = None


@asynccontextmanager
async def lifespan_context(server):
    """Lifespan context manager for startup and shutdown"""
    global pool_manager_config, blob_config, blob_manager
    global middleware, pool_manager, navigation_cache

    logger.info("Starting Playwright MCP Proxy (v2.0.0 - Browser Pools)...")

    try:
        # Load configuration
        pool_manager_config = load_pool_manager_config()
        blob_config = load_blob_config()

        logger.info(f"Blob storage: {blob_config['storage_root']}")
        logger.info(f"Blob threshold: {blob_config['size_threshold_kb']}KB")

        # Initialize blob storage
        blob_manager = PlaywrightBlobManager(blob_config)

        # Initialize middleware
        middleware = BinaryInterceptionMiddleware(blob_manager, blob_config["size_threshold_kb"])

        # Initialize navigation cache (global, shared across all pools)
        from .utils.navigation_cache import NavigationCache

        navigation_cache = NavigationCache(default_ttl=300)

        # Initialize pool manager
        pool_manager = PoolManager(pool_manager_config, blob_manager, middleware)
        await pool_manager.initialize()

        # Start blob cleanup task
        await blob_manager.start_cleanup_task()

        logger.info("Playwright MCP Proxy started successfully")

        # Yield control to the server
        yield

    except Exception as e:
        logger.error(f"Failed to start Playwright MCP Proxy: {e}", exc_info=True)
        raise

    finally:
        # Shutdown cleanup
        logger.info("Shutting down Playwright MCP Proxy...")

        try:
            # Stop cleanup task
            if blob_manager:
                await blob_manager.stop_cleanup_task()

            # Stop pool manager (stops all instances)
            if pool_manager:
                for pool in pool_manager.pools.values():
                    await pool.stop()

            logger.info("Playwright MCP Proxy shut down successfully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


# Initialize the MCP server
mcp = FastMCP(
    name="Playwright MCP Proxy",
    instructions="""
    This is a proxy server for Microsoft's playwright-mcp that provides
    efficient handling of large binary data (screenshots, PDFs) through
    blob storage.

    All playwright browser automation tools are available through this proxy.
    Large binary responses (>50KB by default) are automatically stored as blobs
    to reduce token usage.

    When a tool returns a blob reference (blob://timestamp-hash.png format),
    use a separate MCP Resource Server to retrieve, list, or delete blobs.
    This server only creates and returns blob:// URIs.

    """,
    lifespan=lifespan_context,
)

# Register MCP request/response logging middleware
# Logs all client MCP requests and responses with "CLIENT_MCP" prefix for easy filtering
# log_request_params=True: Log all tool parameters (at INFO level)
# log_response_data=True: Log all tool responses (at INFO level)
# max_log_length=10000: Log up to 10KB of data before truncation (full details)
mcp.add_middleware(
    MCPLoggingMiddleware(log_request_params=True, log_response_data=True, max_log_length=10000)
)


# =============================================================================
# PROXY TOOLS
# =============================================================================
# We need to manually proxy playwright-mcp tools since FastMCP's as_proxy
# requires a running server. We'll communicate directly with the subprocess.


async def _call_playwright_tool(
    tool_name: str,
    arguments: dict[str, Any],
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> Any:
    """
    Call a playwright-mcp tool through the pool manager.

    Args:
        tool_name: Name of the tool (with browser_ prefix)
        arguments: Tool arguments
        browser_pool: Optional pool name (defaults to default pool)
        browser_instance: Optional instance ID or alias (defaults to FIFO selection)

    Returns:
        Tool result (potentially transformed by middleware)
    """
    if not pool_manager:
        raise RuntimeError("Pool manager not initialized")

    # Get the appropriate pool
    pool = pool_manager.get_pool(browser_pool)

    # Lease an instance from the pool (RAII pattern via context manager)
    async with pool.lease_instance(browser_instance) as proxy_client:
        # Call tool through the leased proxy client
        return await proxy_client.call_tool(tool_name, arguments)


# =============================================================================
# NAVIGATION TOOLS
# =============================================================================


def _create_navigation_error(
    url: str,
    error: str,
    offset: int = 0,
    limit: int = 1000,
    cache_key: str = "",
    output_format: str = "yaml",
) -> dict[str, Any]:
    """Create a navigation error response."""
    from typing import cast

    from .types import NavigationResponse

    return cast(dict[str, Any], NavigationResponse(
        success=False,
        url=url,
        error=error,
        cache_key=cache_key,
        total_items=0,
        offset=offset,
        limit=limit,
        has_more=False,
        snapshot=None,
        output_format=output_format,
    ))


def _validate_navigation_params(
    output_format: str,
    offset: int,
    limit: int,
    flatten: bool,
    jmespath_query: str | None,
    cache_key: str | None,
) -> str | None:
    """
    Validate navigation parameters.

    Returns error message if validation fails, None if valid.
    """
    if output_format.lower() not in ["json", "yaml"]:
        return "output_format must be 'json' or 'yaml'"

    if offset < 0:
        return "offset must be non-negative"

    if limit < 1 or limit > 10000:
        return "limit must be between 1 and 10000"

    # Validate pagination requires flatten, JMESPath query, or cache_key
    if (offset > 0 or limit != 1000) and not flatten and not jmespath_query and not cache_key:
        return "Pagination (offset/limit) requires flatten=True, jmespath_query, or cache_key. ARIA snapshots are single tree structures without flattening or queries."

    return None


def _extract_yaml_from_response(raw_result: dict[str, Any]) -> str | None:
    """Extract YAML snapshot text from playwright response content."""
    if "content" not in raw_result:
        return None
    for item in raw_result["content"]:
        if isinstance(item, dict) and item.get("type") == "text":
            return item.get("text")
    return None


def _paginate_result_data(
    result_data: Any, offset: int, limit: int
) -> tuple[list[Any], int, bool]:
    """
    Apply pagination to result data.

    Args:
        result_data: Data to paginate (list or single item)
        offset: Starting index
        limit: Maximum items

    Returns:
        Tuple of (paginated_data, total_items, has_more)
    """
    if isinstance(result_data, list):
        total = len(result_data)
        paginated = result_data[offset : offset + limit]
        has_more = offset + limit < total
    else:
        result_data = [result_data]
        total = 1
        paginated = result_data if offset == 0 else []
        has_more = False

    return paginated, total, has_more


async def _fetch_fresh_snapshot(
    navigation_cache: Any,  # type: ignore[type-arg]
    call_playwright_fn: Any,
    tool_name: str,
    args: dict[str, Any],
    cache_url: str = "",
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> tuple[list[Any] | None, str, str | None]:
    """
    Fetch and cache a fresh ARIA snapshot via navigation or snapshot tool.

    Args:
        navigation_cache: Cache to store the snapshot
        call_playwright_fn: Function to call playwright tool
        tool_name: Tool to call ("browser_navigate" or "browser_snapshot")
        args: Arguments for the playwright call
        cache_url: URL to store in cache (empty for snapshots)
        browser_pool: Target browser pool name
        browser_instance: Target browser instance ID or alias

    Returns:
        Tuple of (snapshot_json, cache_key, error_message)
    """
    from .utils.aria_processor import parse_aria_snapshot

    raw_result = await call_playwright_fn(tool_name, args, browser_pool, browser_instance)

    if not isinstance(raw_result, dict):
        return None, "", f"Unexpected response format from {tool_name}"

    yaml_snapshot = _extract_yaml_from_response(raw_result)
    if not yaml_snapshot:
        return None, "", "No ARIA snapshot found in response"

    snapshot_json, parse_errors = parse_aria_snapshot(yaml_snapshot)
    if parse_errors:
        return None, "", f"ARIA snapshot parse errors: {'; '.join(parse_errors)}"

    key = navigation_cache.create(cache_url, snapshot_json)
    return snapshot_json, key, None


def _process_snapshot_data(
    snapshot_json: Any,
    flatten: bool,
    jmespath_query: str | None,
) -> tuple[Any, str | None]:
    """
    Process snapshot data with flattening and JMESPath query.

    Args:
        snapshot_json: Raw snapshot data
        flatten: Whether to flatten the ARIA tree
        jmespath_query: Optional JMESPath query to apply

    Returns:
        Tuple of (processed_data, error_message)
    """
    from .utils.aria_processor import apply_jmespath_query, flatten_aria_tree

    result_data = flatten_aria_tree(snapshot_json) if flatten else snapshot_json

    if jmespath_query:
        result_data, query_error = apply_jmespath_query(result_data, jmespath_query)
        if query_error:
            return None, query_error

    return result_data, None


@mcp.tool()
@log_tool_result(logger)
async def browser_navigate(
    url: str,
    silent_mode: bool = False,
    flatten: bool = False,
    jmespath_query: str | None = None,
    output_format: str = "yaml",
    cache_key: str | None = None,
    offset: int = 0,
    limit: int = 1000,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> Any:
    """
    Navigate to a URL and capture accessibility snapshot with advanced filtering.

    This tool navigates to the specified URL, captures an ARIA snapshot of the page,
    and supports advanced filtering, pagination, and output formatting to prevent
    context flooding from large snapshots.

    CONCURRENT BROWSER SESSIONS:
        This proxy supports multiple concurrent browser sessions through browser pools.
        Each pool contains one or more browser instances that can be used in parallel.
        Use browser_pool and browser_instance to target specific browsers for workflows
        requiring session isolation or parallel execution.

    Args:
        url: The URL to navigate to
        silent_mode: If True, suppress snapshot output (useful for navigation-only). Default: False
        flatten: If True, flatten ARIA tree to depth-first node list before pagination. Default: False

            When flatten=True, the hierarchical ARIA tree is converted to a flat list of nodes
            where each node is standalone with metadata:
            - _depth: Nesting level (0 = root)
            - _parent_role: Role of parent node (None for root)
            - _index: Position in flattened list

            This enables pagination of large raw snapshots without JMESPath queries.

            Example: A tree with 1 root element containing 500 nested nodes becomes a flat
            list of 501 nodes that can be paginated (e.g., limit=50 returns first 50 nodes).

            Use cases:
            - Paginating large raw snapshots (when JMESPath query not needed)
            - Discovering all elements in document order
            - Analyzing page structure depth

            Combines with jmespath_query: Flatten first, then filter (e.g., flatten=True,
            jmespath_query="[?_depth < 3]" returns only top 3 levels).

        jmespath_query: JMESPath expression to filter/transform the ARIA snapshot. Default: None

            The ARIA snapshot is converted from YAML to JSON, then the query is applied.

            ARIA SNAPSHOT STRUCTURE:
            ARIA snapshots are hierarchical JSON arrays where elements can contain children:
            [
              {
                "role": "document",
                "children": [
                  {
                    "role": "main",
                    "children": [
                      {"role": "heading", "name": {"value": "Title"}, "ref": "e1"},
                      {"role": "paragraph", "name": {"value": "Text"}, "ref": "e2"}
                    ]
                  }
                ]
              }
            ]

            CRITICAL: The root is always an ARRAY, and elements nest via "children" arrays.

            QUERY PATTERNS FOR NESTED STRUCTURES:
            - "[?role == 'heading']" - Find headings ONLY at root level (rarely useful)
            - "[].children[?role == 'heading']" - Find headings in first-level children
            - "[].children[].children[?role == 'heading']" - Find headings nested 2 levels deep
            - "[].children[].children[?role == 'heading'] | []" - Same but flatten results
            - To search ALL depths, chain multiple levels or use projection + filtering

            CRITICAL SYNTAX NOTE: Field names in ARIA JSON use special characters.
            You MUST use DOUBLE QUOTES for field identifiers, NOT backticks:
            - CORRECT: "role", "name", "name.value"
            - WRONG: `role` (backticks create literal strings, not field references)

            Standard JMESPath examples:
            - "[?role == 'button']" - Find buttons at root
            - "[].children[?role == 'button']" - Find buttons in first child level
            - "[?contains(nvl(name.value, ''), 'Submit')]" - Find elements with 'Submit' in name
            - "[].children[].children[?role == 'link'].name.value" - Extract link names from 2nd level
            - "[?role == 'textbox' && disabled == `true`]" - Find disabled textboxes

            Custom functions available:
            - nvl(value, default): Return default if value is null
            - int(value): Convert to integer (returns null on failure)
            - str(value): Convert to string
            - regex_replace(pattern, replacement, value): Regex substitution

            IMPORTANT: Use nvl() for safe filtering on nullable fields:
            - "[?contains(nvl(name.value, ''), 'text')]" - safe name search

        output_format: Format for snapshot output. Must be 'json' or 'yaml'. Default: 'yaml'
        cache_key: Reuse cached snapshot from previous navigation. Omit for fresh fetch. Default: None
        offset: Starting index for pagination. REQUIRES flatten=True, jmespath_query, or cache_key. Default: 0
        limit: Maximum items to return in paginated results (1-10000). REQUIRES flatten=True, jmespath_query, or cache_key. Default: 1000

            CRITICAL: Pagination (offset/limit) requires either flatten=True OR jmespath_query because
            raw ARIA snapshots are single hierarchical tree structures. Without flattening or a query,
            there is only one root element to return (not a list).

            Options for pagination:
            1. Use flatten=True to convert tree to flat node list
            2. Use jmespath_query to extract/filter specific elements
            3. Use cache_key to continue paginating previous results

            Example workflows:
            1. Flatten + paginate: browser_navigate(url="...", flatten=True, limit=50)
            2. Query + paginate: browser_navigate(url="...", jmespath_query="[].children[?role=='button']", limit=50)
            3. Next page: browser_navigate(url="...", cache_key="nav_abc123", offset=50, limit=50)

        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)

            Pools allow organizing browser instances with different configurations (e.g., different
            browsers, headless vs headed). When None, uses the pool marked with IS_DEFAULT=true.

            Example pool names: "DEFAULT", "FIREFOX", "ISOLATED"

        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

            Can be a numeric ID ("0", "1") or an alias configured via environment variables.
            When None, the first available (unleased) instance is used automatically.
            When specified, blocks until that specific instance becomes available.

            Use specific instances when you need session continuity across multiple tool calls
            (e.g., maintaining login state, multi-step workflows on the same page).

    Returns:
        NavigationResponse with navigation result and paginated snapshot.

        Response schema:
        {
            "success": bool,
            "url": str,
            "cache_key": str,  # Use this for subsequent paginated calls
            "total_items": int,  # Total items in snapshot (after query)
            "offset": int,
            "limit": int,
            "has_more": bool,  # True if more items available
            "snapshot": str | None,  # Formatted output or None if silent_mode
            "error": str | None,
            "output_format": str
        }

    Pagination Workflow:
        1. First call: browser_navigate(url="https://example.com", limit=50)
           - Returns cache_key="nav_abc123", has_more=True

        2. Next page: browser_navigate(url="https://example.com", cache_key="nav_abc123", offset=50, limit=50)
           - Reuses cached snapshot, returns next 50 items

        3. Continue until has_more=False

    Notes:
        - Cache entries expire after 5 minutes of inactivity
        - JMESPath queries are applied BEFORE pagination
        - silent_mode=True useful for navigation without token overhead
        - ARIA snapshots are hierarchical - query results may be nested objects

    See Also:
        - browser_snapshot: Capture snapshot without navigation
        - browser_take_screenshot: Visual screenshot instead of ARIA tree
    """
    from .types import NavigationResponse
    from .utils.aria_processor import format_output

    # Check if navigation_cache is initialized
    if navigation_cache is None:
        return _create_navigation_error(
            url, "Navigation cache not initialized", offset, limit, "", output_format
        )

    # Validate parameters
    validation_error = _validate_navigation_params(
        output_format, offset, limit, flatten, jmespath_query, cache_key
    )
    if validation_error:
        return _create_navigation_error(url, validation_error, offset, limit, "", output_format)

    # Silent mode: just navigate, no processing
    if silent_mode:
        try:
            await _call_playwright_tool("browser_navigate", {"url": url}, browser_pool, browser_instance)
            return NavigationResponse(
                success=True, url=url, cache_key="", total_items=0, offset=0, limit=limit,
                has_more=False, snapshot=None, error=None, output_format=output_format,
            )
        except Exception as e:
            return _create_navigation_error(url, f"Navigation failed: {e}", 0, limit, "", output_format)

    # Get or fetch snapshot data
    snapshot_json = None
    key = ""

    try:
        # Try cache first if key provided
        if cache_key:
            entry = navigation_cache.get(cache_key)
            if entry:
                snapshot_json = entry.snapshot_json
                key = cache_key

        # Fetch fresh if no cache or cache miss
        if snapshot_json is None:
            snapshot_json, key, error = await _fetch_fresh_snapshot(
                navigation_cache, _call_playwright_tool, "browser_navigate", {"url": url}, url,
                browser_pool, browser_instance
            )
            if error:
                return _create_navigation_error(url, error, offset, limit, "", output_format)

    except Exception as e:
        return _create_navigation_error(url, f"Navigation failed: {e}", offset, limit, "", output_format)

    # Process snapshot with flattening and query
    result_data, process_error = _process_snapshot_data(snapshot_json, flatten, jmespath_query)
    if process_error:
        return _create_navigation_error(url, process_error, offset, limit, key, output_format)

    # Apply pagination
    paginated_data, total, has_more = _paginate_result_data(result_data, offset, limit)

    # Return response
    return NavigationResponse(
        success=True, url=url, cache_key=key, total_items=total, offset=offset, limit=limit,
        has_more=has_more, snapshot=format_output(paginated_data, output_format),
        error=None, output_format=output_format.lower(),
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_navigate_back(
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Go back to the previous page.

    Args:
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Navigation result
    """
    return await _call_playwright_tool("browser_navigate_back", {}, browser_pool, browser_instance)


# =============================================================================
# BULK EXECUTION TOOL
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_execute_bulk(
    commands: list[dict[str, Any]],
    stop_on_error: bool = True,
    return_all_results: bool = False,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Execute multiple browser commands sequentially in a single call.

    Optimizes common workflows by reducing round-trip overhead. Useful for
    patterns like navigate→wait→snapshot or navigate→click→wait→extract.

    INSTANCE AFFINITY:
        When browser_pool and/or browser_instance are specified at the bulk level,
        ALL commands in the batch automatically use the same browser instance.
        This ensures session continuity across the entire workflow - login state,
        cookies, page context, and DOM state are preserved between commands.

        The instance is selected once at the start of execution and held for the
        entire batch. Individual commands do NOT need to specify browser_pool or
        browser_instance in their args (they are automatically injected).

        If a command explicitly specifies browser_pool or browser_instance in its
        args, those values override the bulk-level settings for that command only.

    Args:
        commands: Array of commands to execute sequentially. Each command:
            - tool (str, required): Tool name (e.g., "browser_navigate")
            - args (dict, required): Tool arguments as key-value pairs
            - return_result (bool, optional): Include result in response (default: False)

        stop_on_error: Stop execution on first error (default: True).
            If False, continues executing remaining commands and collects all errors.

        return_all_results: Return results from all commands (default: False).
            If False, only returns results where return_result=True.
            Note: Setting this to True may consume significant tokens for large responses.

        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
            All commands in the batch will use instances from this pool.

        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)
            When specified, all commands use this exact instance, ensuring session affinity.
            When None, an instance is selected via FIFO and used for the entire batch.

    Returns:
        BulkExecutionResponse with execution metadata and selective results.

        Response structure:
        {
            "success": bool,           # True if all commands succeeded
            "executed_count": int,     # Commands executed before stop/completion
            "total_count": int,        # Total commands in request
            "results": list[Any],      # Results array (null for non-returned)
            "errors": list[str|null],  # Errors array (null for successful)
            "stopped_at": int|null     # Index where stopped (if stop_on_error)
        }

    Common Workflow Examples:

        # Navigate, wait, extract (only return final snapshot)
        browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "...", "silent_mode": true}},
                {"tool": "browser_wait_for", "args": {"text": "Loaded"}},
                {"tool": "browser_snapshot", "args": {"jmespath_query": "...", "output_format": "json"}, "return_result": true}
            ]
        )

        # Multi-step interaction with explicit instance for session continuity
        browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "..."}},
                {"tool": "browser_click", "args": {"element": "button", "ref": "e1"}},
                {"tool": "browser_wait_for", "args": {"time": 1000}},
                {"tool": "browser_snapshot", "args": {}, "return_result": true}
            ],
            browser_pool="DEFAULT",
            browser_instance="0",  # All commands use instance 0
            stop_on_error=true,
            return_all_results=false
        )

        # Form filling workflow with automatic instance affinity
        browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "...", "silent_mode": true}},
                {"tool": "browser_type", "args": {"element": "textbox", "ref": "e1", "text": "value"}},
                {"tool": "browser_click", "args": {"element": "button", "ref": "e2"}},
                {"tool": "browser_wait_for", "args": {"text": "Success"}},
                {"tool": "browser_snapshot", "args": {"output_format": "json"}, "return_result": true}
            ],
            browser_pool="ISOLATED"  # FIFO selects an instance, used for all commands
        )

    Error Handling:
        - Invalid tool names are caught during execution
        - Missing required arguments cause immediate failure for that command
        - If stop_on_error=True, execution halts at first error
        - If stop_on_error=False, all commands execute and errors are collected

    Performance Notes:
        - Use silent_mode=True on navigation to skip large ARIA snapshots
        - Set return_result=True only on final/critical commands
        - Consider pagination for large result sets
        - Bulk execution with instance affinity is more efficient than separate tool calls
    """
    # Validate non-empty commands array
    if not commands:
        return {
            "success": False,
            "executed_count": 0,
            "total_count": 0,
            "results": [],
            "errors": ["commands array cannot be empty"],
            "stopped_at": None,
        }

    # Validate each command structure
    for idx, cmd in enumerate(commands):
        if not isinstance(cmd, dict):
            return {
                "success": False,
                "executed_count": 0,
                "total_count": len(commands),
                "results": [],
                "errors": [f"Command at index {idx} is not a dictionary"],
                "stopped_at": None,
            }
        if "tool" not in cmd:
            return {
                "success": False,
                "executed_count": 0,
                "total_count": len(commands),
                "results": [],
                "errors": [f"Command at index {idx} missing required 'tool' field"],
                "stopped_at": None,
            }
        if "args" not in cmd:
            return {
                "success": False,
                "executed_count": 0,
                "total_count": len(commands),
                "results": [],
                "errors": [f"Command at index {idx} missing required 'args' field"],
                "stopped_at": None,
            }

    # Map tool names to their wrapper functions
    # This ensures all custom logic (JMESPath, pagination, blob handling, etc.) is executed
    # Note: We need to access .fn to get the actual function from FunctionTool wrappers
    tool_registry = {
        # Navigation tools
        "browser_navigate": browser_navigate.fn,
        "browser_navigate_back": browser_navigate_back.fn,
        # Snapshot & interaction tools
        "browser_snapshot": browser_snapshot.fn,
        "browser_click": browser_click.fn,
        "browser_drag": browser_drag.fn,
        "browser_hover": browser_hover.fn,
        "browser_select_option": browser_select_option.fn,
        "browser_generate_locator": browser_generate_locator.fn,
        # Form interaction tools
        "browser_fill_form": browser_fill_form.fn,
        # Screenshot & PDF tools
        "browser_take_screenshot": browser_take_screenshot.fn,
        "browser_pdf_save": browser_pdf_save.fn,
        # Code execution tools
        "browser_run_code": browser_run_code.fn,
        "browser_evaluate": browser_evaluate.fn,
        # Mouse tools
        "browser_mouse_move_xy": browser_mouse_move_xy.fn,
        "browser_mouse_click_xy": browser_mouse_click_xy.fn,
        "browser_mouse_drag_xy": browser_mouse_drag_xy.fn,
        # Keyboard tools
        "browser_press_key": browser_press_key.fn,
        "browser_type": browser_type.fn,
        # Wait & timing tools
        "browser_wait_for": browser_wait_for.fn,
        # Verification/testing tools
        "browser_verify_element_visible": browser_verify_element_visible.fn,
        "browser_verify_text_visible": browser_verify_text_visible.fn,
        "browser_verify_list_visible": browser_verify_list_visible.fn,
        "browser_verify_value": browser_verify_value.fn,
        # Network tools
        "browser_network_requests": browser_network_requests.fn,
        # Tab management tools
        "browser_tabs": browser_tabs.fn,
        # Console tools
        "browser_console_messages": browser_console_messages.fn,
        # Dialog tools
        "browser_handle_dialog": browser_handle_dialog.fn,
        # File upload tools
        "browser_file_upload": browser_file_upload.fn,
        # Tracing tools
        "browser_start_tracing": browser_start_tracing.fn,
        "browser_stop_tracing": browser_stop_tracing.fn,
        # Installation tools
        "browser_install": browser_install.fn,
    }

    # Execute commands sequentially
    results: list[Any | None] = []
    errors: list[str | None] = []
    executed_count = 0
    stopped_at: int | None = None

    for idx, cmd in enumerate(commands):
        tool_name = cmd["tool"]
        args = cmd.get("args", {}).copy()  # Copy to avoid mutating original
        return_result = cmd.get("return_result", False) or return_all_results

        # Inject browser_pool/browser_instance for instance affinity (if not already specified)
        if browser_pool is not None and "browser_pool" not in args:
            args["browser_pool"] = browser_pool
        if browser_instance is not None and "browser_instance" not in args:
            args["browser_instance"] = browser_instance

        try:
            # Try to find wrapper function first
            if tool_name in tool_registry:
                # Call wrapper function (preserves JMESPath, pagination, blob handling, etc.)
                result = await tool_registry[tool_name](**args)
            else:
                # Fallback to direct call for any tools not in registry
                result = await _call_playwright_tool(
                    tool_name, args,
                    args.get("browser_pool"), args.get("browser_instance")
                )

            results.append(result if return_result else None)
            errors.append(None)
            executed_count += 1
        except Exception as e:
            # Continue silently - store error, null result
            results.append(None)
            errors.append(str(e))
            executed_count += 1

            if stop_on_error:
                stopped_at = idx
                break

    # Fill remaining slots if stopped early
    if stopped_at is not None:
        remaining = len(commands) - executed_count
        results.extend([None] * remaining)
        errors.extend([None] * remaining)

    return {
        "success": all(err is None for err in errors),
        "executed_count": executed_count,
        "total_count": len(commands),
        "results": results,
        "errors": errors,
        "stopped_at": stopped_at,
    }


# =============================================================================
# SCREENSHOT & PDF TOOLS
# =============================================================================


def _extract_blob_id_from_response(result: Any) -> str | None:
    """
    Extract blob ID from MCP response.

    Handles both dict and Pydantic model responses.
    """
    import re

    # Extract content field
    content = None
    if isinstance(result, dict):
        content = result.get("content")
    elif hasattr(result, "content"):
        content = result.content

    # Search for blob item in content list
    if content and isinstance(content, list):
        for item in content:
            # Handle both dict and object (Pydantic model) items
            item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            if item_type == "blob":
                blob_id = item.get("blob_id") if isinstance(item, dict) else getattr(item, "blob_id", None)
                if blob_id:
                    return blob_id

            # Also check text content for blob:// URLs
            text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
            if text and isinstance(text, str):
                # Extract blob:// URL from markdown links or plain text
                match = re.search(r'blob://[a-zA-Z0-9\-_.]+', text)
                if match:
                    return match.group(0)

    # Fallback: if result is already a string, return it
    if isinstance(result, str):
        return result

    return None


@mcp.tool()
@log_tool_result(logger)
async def browser_take_screenshot(
    type: str = "png",
    filename: str | None = None,
    element: str | None = None,
    ref: str | None = None,
    fullPage: bool | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> str:
    """
    Take a screenshot of the current page. You can't perform actions based on the screenshot, use browser_snapshot for actions.

    Screenshots are automatically stored as blobs and returned as blob:// URIs.
    Use a separate MCP Resource Server to retrieve blob data.

    Args:
        type: Image format for the screenshot. Must be 'png' or 'jpeg'. Default is 'png'.
        filename: File name to save the screenshot to. Defaults to page-{timestamp}.{png|jpeg} if not specified.
                  Prefer relative file names to stay within the output directory.
        element: Human-readable element description used to obtain permission to screenshot the element.
                 If not provided, the screenshot will be taken of viewport. If element is provided, ref must be provided too.
        ref: Exact target element reference from the page snapshot. If not provided, the screenshot will be taken of viewport.
             If ref is provided, element must be provided too.
        fullPage: When true, takes a screenshot of the full scrollable page, instead of the currently visible viewport.
                  Cannot be used with element screenshots.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Blob URI reference (blob://timestamp-hash.png or blob://timestamp-hash.jpeg)
    """
    args: dict[str, Any] = {"type": type}
    if filename is not None:
        args["filename"] = filename
    if element is not None:
        args["element"] = element
    if ref is not None:
        args["ref"] = ref
    if fullPage is not None:
        args["fullPage"] = fullPage

    result = await _call_playwright_tool("browser_take_screenshot", args, browser_pool, browser_instance)
    blob_id = _extract_blob_id_from_response(result)

    if not blob_id:
        raise RuntimeError(f"Failed to extract blob URI from screenshot result: {result}")

    return blob_id


@mcp.tool()
@log_tool_result(logger)
async def browser_pdf_save(
    filename: str | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> str:
    """
    Save page as PDF.

    PDFs are automatically stored as blobs and returned as blob:// URIs.
    Use a separate MCP Resource Server to retrieve blob data.

    Args:
        filename: File name to save the pdf to. Defaults to page-{timestamp}.pdf if not specified.
                  Prefer relative file names to stay within the output directory.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Blob URI reference (blob://timestamp-hash.pdf)
    """
    args = {}
    if filename is not None:
        args["filename"] = filename

    result = await _call_playwright_tool("browser_pdf_save", args, browser_pool, browser_instance)
    blob_id = _extract_blob_id_from_response(result)

    if not blob_id:
        raise RuntimeError(f"Failed to extract blob URI from PDF result: {result}")

    return blob_id


# =============================================================================
# CODE EXECUTION TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_run_code(
    code: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Run Playwright code snippet.

    Args:
        code: A JavaScript function containing Playwright code to execute. It will be invoked with a single
              argument, page, which you can use for any page interaction.
              For example: async (page) => { await page.getByRole('button', { name: 'Submit' }).click(); return await page.title(); }
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Code execution result
    """
    return await _call_playwright_tool("browser_run_code", {"code": code}, browser_pool, browser_instance)


def _create_evaluation_error(
    error: str,
    offset: int = 0,
    limit: int = 1000,
    cache_key: str = "",
) -> dict[str, Any]:
    """Create an evaluation error response."""
    from typing import cast

    from .types import EvaluationResponse

    return cast(dict[str, Any], EvaluationResponse(
        success=False,
        error=error,
        cache_key=cache_key,
        total_items=0,
        offset=offset,
        limit=limit,
        has_more=False,
        result=None,
    ))


def _validate_evaluation_params(offset: int, limit: int) -> str | None:
    """
    Validate evaluation parameters.

    Returns error message if validation fails, None if valid.
    """
    if offset < 0:
        return "offset must be non-negative"

    if limit < 1 or limit > 10000:
        return "limit must be between 1 and 10000"

    return None


@mcp.tool()
@log_tool_result(logger)
async def browser_evaluate(
    function: str,
    element: str | None = None,
    ref: str | None = None,
    cache_key: str | None = None,
    offset: int = 0,
    limit: int = 1000,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Evaluate JavaScript expression on page or element with optional pagination.

    This tool executes arbitrary JavaScript in the browser context and returns the
    result. When the result is an array or when pagination is needed, use the cache_key,
    offset, and limit parameters to retrieve data in pages.

    Args:
        function: JavaScript function to evaluate. Format depends on element parameter:
            - Without element: () => { /* code */ } - runs in page context
            - With element: (element) => { /* code */ } - runs with element as parameter

        element: Human-readable element description for permission control.
            When provided, JavaScript receives the element as first parameter.

        ref: Exact target element reference from page snapshot (e.g., "e1", "e42").
            Used with element parameter to identify specific DOM node.

        cache_key: Reuse cached evaluation result from previous call. Default: None
            When omitted on first call, a new cache entry is created and returned.
            Use the returned cache_key in subsequent calls to paginate the same result.

        offset: Starting index for pagination. Default: 0
            Must be non-negative. Use with limit to retrieve specific page of results.

        limit: Maximum items per page (1-10000). Default: 1000
            When combined with offset, enables paginated retrieval of large arrays.

    Returns:
        When pagination is used (offset > 0, limit != 1000, or cache_key provided):
            EvaluationResponse with paginated result:
            {
                "success": bool,
                "cache_key": str,      # For continuation
                "total_items": int,    # Total result count
                "offset": int,         # Current page offset
                "limit": int,          # Items per page
                "has_more": bool,      # True if more items available
                "result": list | Any,  # Paginated result (arrays or wrapped non-arrays)
                "error": str | None
            }

        When pagination is NOT used:
            Simple dict format: {"result": <any JSON-serializable value>}

    Pagination Workflow:
        1. First call: browser_evaluate(function="...", limit=50)
           Returns cache_key="nav_abc123", has_more=True, result=[... 50 items ...]

        2. Next page: browser_evaluate(function="...", cache_key="nav_abc123", offset=50, limit=50)
           Reuses cached result, returns next 50 items

        3. Continue until has_more=False

    Non-Array Results:
        When JavaScript returns a non-array value (number, string, object), it is
        automatically wrapped in a single-item array for pagination consistency:

        JavaScript: () => ({name: "John"})
        Response: {"result": [{"name": "John"}], "total_items": 1, ...}

    Common Use Cases:
        # Extract all links without pagination
        browser_evaluate(function="() => Array.from(document.links).map(a => a.href)")

        # Extract many links with pagination (first 100)
        browser_evaluate(
            function="() => Array.from(document.links).map(a => a.href)",
            limit=100
        )

        # Continue pagination
        browser_evaluate(
            function="() => Array.from(document.links).map(a => a.href)",
            cache_key="nav_abc123",
            offset=100,
            limit=100
        )

        # Evaluate on specific element
        browser_evaluate(
            function="(el) => el.innerText",
            element="Submit button",
            ref="e1"
        )

        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Notes:
        - Cache entries expire after 5 minutes of inactivity
        - For arrays with 1000 or fewer items, omit pagination parameters for simplicity
        - Non-array results are wrapped in single-item arrays when pagination is used

    See Also:
        - browser_navigate: Navigate and capture ARIA snapshot with pagination
        - browser_snapshot: Capture ARIA snapshot with JMESPath filtering
        - browser_run_code: Execute arbitrary page automation code
    """
    from .types import EvaluationResponse

    # Check if pagination is requested
    using_pagination = offset > 0 or limit != 1000 or cache_key is not None

    # Backward compatibility: no pagination
    if not using_pagination:
        args = {"function": function}
        if element is not None:
            args["element"] = element
        if ref is not None:
            args["ref"] = ref
        return await _call_playwright_tool("browser_evaluate", args, browser_pool, browser_instance)

    # Pagination mode: validate parameters
    validation_error = _validate_evaluation_params(offset, limit)
    if validation_error:
        return _create_evaluation_error(validation_error, offset, limit)

    # Check cache or evaluate fresh
    result_data = None
    key = ""

    # Access module-level variable as attribute (can be patched in tests)
    import sys
    current_module = sys.modules[__name__]
    nav_cache = getattr(current_module, 'navigation_cache', None)

    try:
        if cache_key and nav_cache is not None:
            # User provided explicit cache_key (from previous response)
            entry = nav_cache.get(cache_key)
            if entry:
                result_data = entry.snapshot_json  # Reuse cached result
                key = cache_key

        # Evaluate if not cached
        if result_data is None:
            # Call upstream playwright-mcp
            args = {"function": function}
            if element is not None:
                args["element"] = element
            if ref is not None:
                args["ref"] = ref

            raw_result = await _call_playwright_tool("browser_evaluate", args, browser_pool, browser_instance)

            # Extract result from {"result": ...} format
            result_data = raw_result.get("result")

            # Store in cache
            if nav_cache is not None:
                key = nav_cache.create("", result_data)

    except Exception as e:
        return _create_evaluation_error(f"Evaluation failed: {e}", offset, limit)

    # Wrap non-list results in array for consistent pagination
    if isinstance(result_data, list):
        total = len(result_data)
        paginated_data = result_data[offset : offset + limit]
        has_more = offset + limit < total
    else:
        # Single result - wrap in array
        total = 1
        if offset == 0:
            paginated_data = [result_data]
        else:
            paginated_data = []  # offset beyond single result
        has_more = False

    # Return paginated response
    from typing import cast
    return cast(dict[str, Any], EvaluationResponse(
        success=True,
        cache_key=key,
        total_items=total,
        offset=offset,
        limit=limit,
        has_more=has_more,
        result=paginated_data,
        error=None,
    ))


# =============================================================================
# PAGE SNAPSHOT & INTERACTION TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_snapshot(
    filename: str | None = None,
    silent_mode: bool = False,
    flatten: bool = False,
    jmespath_query: str | None = None,
    output_format: str = "yaml",
    cache_key: str | None = None,
    offset: int = 0,
    limit: int = 1000,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> Any:
    """
    Capture accessibility snapshot of the current page with advanced filtering.

    This tool captures an ARIA snapshot of the current page and supports advanced
    filtering, pagination, and output formatting to prevent context flooding from
    large snapshots. This is better than screenshot for automation.

    Args:
        filename: Save snapshot to markdown file instead of returning it in the response.
                  When provided, other filtering options are ignored.
        silent_mode: If True, suppress snapshot output (useful for snapshot-only). Default: False
        flatten: If True, flatten ARIA tree to depth-first node list before pagination. Default: False

            When flatten=True, the hierarchical ARIA tree is converted to a flat list of nodes
            where each node is standalone with metadata:
            - _depth: Nesting level (0 = root)
            - _parent_role: Role of parent node (None for root)
            - _index: Position in flattened list

            This enables pagination of large raw snapshots without JMESPath queries.

            Example: A tree with 1 root element containing 500 nested nodes becomes a flat
            list of 501 nodes that can be paginated (e.g., limit=50 returns first 50 nodes).

            Use cases:
            - Paginating large raw snapshots (when JMESPath query not needed)
            - Discovering all elements in document order
            - Analyzing page structure depth

            Combines with jmespath_query: Flatten first, then filter (e.g., flatten=True,
            jmespath_query="[?_depth < 3]" returns only top 3 levels).

        jmespath_query: JMESPath expression to filter/transform the ARIA snapshot. Default: None

            The ARIA snapshot is converted from YAML to JSON, then the query is applied.

            ARIA SNAPSHOT STRUCTURE:
            ARIA snapshots are hierarchical JSON arrays where elements can contain children:
            [
              {
                "role": "document",
                "children": [
                  {
                    "role": "main",
                    "children": [
                      {"role": "heading", "name": {"value": "Title"}, "ref": "e1"},
                      {"role": "paragraph", "name": {"value": "Text"}, "ref": "e2"}
                    ]
                  }
                ]
              }
            ]

            CRITICAL: The root is always an ARRAY, and elements nest via "children" arrays.

            QUERY PATTERNS FOR NESTED STRUCTURES:
            - "[?role == 'heading']" - Find headings ONLY at root level (rarely useful)
            - "[].children[?role == 'heading']" - Find headings in first-level children
            - "[].children[].children[?role == 'heading']" - Find headings nested 2 levels deep
            - "[].children[].children[?role == 'heading'] | []" - Same but flatten results
            - To search ALL depths, chain multiple levels or use projection + filtering

            CRITICAL SYNTAX NOTE: Field names in ARIA JSON use special characters.
            You MUST use DOUBLE QUOTES for field identifiers, NOT backticks:
            - CORRECT: "role", "name", "name.value"
            - WRONG: `role` (backticks create literal strings, not field references)

            Standard JMESPath examples:
            - "[?role == 'button']" - Find buttons at root
            - "[].children[?role == 'button']" - Find buttons in first child level
            - "[?contains(nvl(name.value, ''), 'Submit')]" - Find elements with 'Submit' in name
            - "[].children[].children[?role == 'link'].name.value" - Extract link names from 2nd level
            - "[?role == 'textbox' && disabled == `true`]" - Find disabled textboxes

            Custom functions available:
            - nvl(value, default): Return default if value is null
            - int(value): Convert to integer (returns null on failure)
            - str(value): Convert to string
            - regex_replace(pattern, replacement, value): Regex substitution

            IMPORTANT: Use nvl() for safe filtering on nullable fields:
            - "[?contains(nvl(name.value, ''), 'text')]" - safe name search

        output_format: Format for snapshot output. Must be 'json' or 'yaml'. Default: 'yaml'
        cache_key: Reuse cached snapshot from previous call. Omit for fresh fetch. Default: None
        offset: Starting index for pagination. REQUIRES flatten=True, jmespath_query, or cache_key. Default: 0
        limit: Maximum items to return in paginated results (1-10000). REQUIRES flatten=True, jmespath_query, or cache_key. Default: 1000

            CRITICAL: Pagination (offset/limit) requires either flatten=True OR jmespath_query because
            raw ARIA snapshots are single hierarchical tree structures. Without flattening or a query,
            there is only one root element to return (not a list).

            Options for pagination:
            1. Use flatten=True to convert tree to flat node list
            2. Use jmespath_query to extract/filter specific elements
            3. Use cache_key to continue paginating previous results

            Example workflows:
            1. Flatten + paginate: browser_snapshot(flatten=True, limit=50)
            2. Query + paginate: browser_snapshot(jmespath_query="[].children[?role=='button']", limit=50)
            3. Next page: browser_snapshot(cache_key="nav_abc123", offset=50, limit=50)

        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        NavigationResponse with snapshot result and paginated data (or file save confirmation).

        When filename is provided, returns standard playwright response.
        Otherwise, returns NavigationResponse with same schema as browser_navigate.

    Pagination Workflow:
        1. First call: browser_snapshot(limit=50)
           - Returns cache_key="nav_abc123", has_more=True

        2. Next page: browser_snapshot(cache_key="nav_abc123", offset=50, limit=50)
           - Reuses cached snapshot, returns next 50 items

        3. Continue until has_more=False

    Notes:
        - Cache entries expire after 5 minutes of inactivity
        - JMESPath queries are applied BEFORE pagination
        - silent_mode=True useful for capturing without token overhead
        - ARIA snapshots are hierarchical - query results may be nested objects

    See Also:
        - browser_navigate: Navigate and capture snapshot
        - browser_take_screenshot: Visual screenshot instead of ARIA tree
    """
    # If filename provided, use original behavior
    if filename is not None:
        return await _call_playwright_tool("browser_snapshot", {"filename": filename}, browser_pool, browser_instance)

    from .types import NavigationResponse
    from .utils.aria_processor import format_output

    # Check if navigation_cache is initialized
    if navigation_cache is None:
        return _create_navigation_error(
            "", "Navigation cache not initialized", offset, limit, "", output_format
        )

    # Validate parameters
    validation_error = _validate_navigation_params(
        output_format, offset, limit, flatten, jmespath_query, cache_key
    )
    if validation_error:
        return _create_navigation_error("", validation_error, offset, limit, "", output_format)

    # Silent mode: just capture, no processing
    if silent_mode:
        try:
            await _call_playwright_tool("browser_snapshot", {}, browser_pool, browser_instance)
            return NavigationResponse(
                success=True, url="", cache_key="", total_items=0, offset=0, limit=limit,
                has_more=False, snapshot=None, error=None, output_format=output_format,
            )
        except Exception as e:
            return _create_navigation_error("", f"Snapshot failed: {e}", 0, limit, "", output_format)

    # Get or fetch snapshot data
    snapshot_json = None
    key = ""

    try:
        # Try cache first if key provided
        if cache_key:
            entry = navigation_cache.get(cache_key)
            if entry:
                snapshot_json = entry.snapshot_json
                key = cache_key

        # Fetch fresh if no cache or cache miss
        if snapshot_json is None:
            snapshot_json, key, error = await _fetch_fresh_snapshot(
                navigation_cache, _call_playwright_tool, "browser_snapshot", {},
                "", browser_pool, browser_instance
            )
            if error:
                return _create_navigation_error("", error, offset, limit, "", output_format)

    except Exception as e:
        return _create_navigation_error("", f"Snapshot failed: {e}", offset, limit, "", output_format)

    # Process snapshot with flattening and query
    result_data, process_error = _process_snapshot_data(snapshot_json, flatten, jmespath_query)
    if process_error:
        return _create_navigation_error("", process_error, offset, limit, key, output_format)

    # Apply pagination
    paginated_data, total, has_more = _paginate_result_data(result_data, offset, limit)

    # Return response
    return NavigationResponse(
        success=True, url="", cache_key=key, total_items=total, offset=offset, limit=limit,
        has_more=has_more, snapshot=format_output(paginated_data, output_format),
        error=None, output_format=output_format.lower(),
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_click(
    element: str,
    ref: str,
    doubleClick: bool | None = None,
    button: str | None = None,
    modifiers: list[str] | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Perform click on a web page.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        doubleClick: Whether to perform a double click instead of a single click
        button: Button to click, must be 'left', 'right', or 'middle'. Defaults to 'left'.
        modifiers: Modifier keys to press. Can include: 'Alt', 'Control', 'ControlOrMeta', 'Meta', 'Shift'.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Click result
    """
    args: dict[str, Any] = {"element": element, "ref": ref}
    if doubleClick is not None:
        args["doubleClick"] = doubleClick
    if button is not None:
        args["button"] = button
    if modifiers is not None:
        args["modifiers"] = modifiers

    return await _call_playwright_tool("browser_click", args, browser_pool, browser_instance)


@mcp.tool()
@log_tool_result(logger)
async def browser_drag(
    startElement: str,
    startRef: str,
    endElement: str,
    endRef: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Perform drag and drop between two elements.

    Args:
        startElement: Human-readable source element description used to obtain the permission to interact with the element
        startRef: Exact source element reference from the page snapshot
        endElement: Human-readable target element description used to obtain the permission to interact with the element
        endRef: Exact target element reference from the page snapshot
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Drag result
    """
    return await _call_playwright_tool(
        "browser_drag",
        {
            "startElement": startElement,
            "startRef": startRef,
            "endElement": endElement,
            "endRef": endRef,
        },
        browser_pool,
        browser_instance,
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_hover(
    element: str,
    ref: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Hover over element on page.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Hover result
    """
    return await _call_playwright_tool("browser_hover", {"element": element, "ref": ref}, browser_pool, browser_instance)


@mcp.tool()
@log_tool_result(logger)
async def browser_select_option(
    element: str,
    ref: str,
    values: list[str],
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Select an option in a dropdown.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        values: Array of values to select in the dropdown. This can be a single value or multiple values.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Selection result
    """
    return await _call_playwright_tool(
        "browser_select_option", {"element": element, "ref": ref, "values": values},
        browser_pool, browser_instance
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_generate_locator(
    element: str,
    ref: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Generate locator for the given element to use in tests.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Generated locator
    """
    return await _call_playwright_tool("browser_generate_locator", {"element": element, "ref": ref}, browser_pool, browser_instance)


# =============================================================================
# FORM INTERACTION TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_fill_form(
    fields: list[dict[str, Any]],
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Fill multiple form fields.

    Args:
        fields: Fields to fill in. Each field is a dict with:
                - name (str): Human-readable field name
                - type (str): Type of the field. Must be 'textbox', 'checkbox', 'radio', 'combobox', or 'slider'.
                - ref (str): Exact target field reference from the page snapshot
                - value (str): Value to fill in the field. If the field is a checkbox, the value should be 'true' or 'false'.
                              If the field is a combobox, the value should be the text of the option.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Fill result
    """
    return await _call_playwright_tool("browser_fill_form", {"fields": fields}, browser_pool, browser_instance)


# =============================================================================
# MOUSE TOOLS (VISION CAPABILITY)
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_mouse_move_xy(
    element: str,
    x: float,
    y: float,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Move mouse to a given position.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        x: X coordinate
        y: Y coordinate
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Mouse move result
    """
    return await _call_playwright_tool(
        "browser_mouse_move_xy", {"element": element, "x": x, "y": y},
        browser_pool, browser_instance
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_mouse_click_xy(
    element: str,
    x: float,
    y: float,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Click left mouse button at a given position.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        x: X coordinate
        y: Y coordinate
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Mouse click result
    """
    return await _call_playwright_tool(
        "browser_mouse_click_xy", {"element": element, "x": x, "y": y},
        browser_pool, browser_instance
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_mouse_drag_xy(
    element: str,
    startX: float,
    startY: float,
    endX: float,
    endY: float,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Drag left mouse button to a given position.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        startX: Start X coordinate
        startY: Start Y coordinate
        endX: End X coordinate
        endY: End Y coordinate
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Mouse drag result
    """
    return await _call_playwright_tool(
        "browser_mouse_drag_xy",
        {
            "element": element,
            "startX": startX,
            "startY": startY,
            "endX": endX,
            "endY": endY,
        },
        browser_pool,
        browser_instance,
    )


# =============================================================================
# KEYBOARD TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_press_key(
    key: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Press a key on the keyboard.

    Args:
        key: Name of the key to press or a character to generate, such as 'ArrowLeft' or 'a'
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Key press result
    """
    return await _call_playwright_tool("browser_press_key", {"key": key}, browser_pool, browser_instance)


@mcp.tool()
@log_tool_result(logger)
async def browser_type(
    element: str,
    ref: str,
    text: str,
    submit: bool | None = None,
    slowly: bool | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Type text into editable element.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        text: Text to type into the element
        submit: Whether to submit entered text (press Enter after)
        slowly: Whether to type one character at a time. Useful for triggering key handlers in the page.
                By default entire text is filled in at once.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Type result
    """
    args: dict[str, Any] = {"element": element, "ref": ref, "text": text}
    if submit is not None:
        args["submit"] = submit
    if slowly is not None:
        args["slowly"] = slowly

    return await _call_playwright_tool("browser_type", args, browser_pool, browser_instance)


# =============================================================================
# WAIT & TIMING TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_wait_for(
    time: float | None = None,
    text: str | None = None,
    textGone: str | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Wait for text to appear or disappear or a specified time to pass.

    Args:
        time: The time to wait in seconds
        text: The text to wait for
        textGone: The text to wait for to disappear
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Wait result
    """
    # With stdio transport, no need to chunk waits - no ping timeout issue
    args = {}
    if time is not None:
        args["time"] = time
    if text is not None:
        args["text"] = text
    if textGone is not None:
        args["textGone"] = textGone

    return await _call_playwright_tool("browser_wait_for", args, browser_pool, browser_instance)


# =============================================================================
# VERIFICATION/TESTING TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_verify_element_visible(
    role: str,
    accessibleName: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Verify element is visible on the page.

    Args:
        role: ROLE of the element. Can be found in the snapshot like this: - {ROLE} "Accessible Name":
        accessibleName: ACCESSIBLE_NAME of the element. Can be found in the snapshot like this: - role "{ACCESSIBLE_NAME}"
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Verification result
    """
    return await _call_playwright_tool(
        "browser_verify_element_visible", {"role": role, "accessibleName": accessibleName},
        browser_pool, browser_instance
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_verify_text_visible(
    text: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Verify text is visible on the page. Prefer browser_verify_element_visible if possible.

    Args:
        text: TEXT to verify. Can be found in the snapshot like this: - role "Accessible Name": {TEXT} or like this: - text: {TEXT}
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Verification result
    """
    return await _call_playwright_tool("browser_verify_text_visible", {"text": text}, browser_pool, browser_instance)


@mcp.tool()
@log_tool_result(logger)
async def browser_verify_list_visible(
    element: str,
    ref: str,
    items: list[str],
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Verify list is visible on the page.

    Args:
        element: Human-readable list description
        ref: Exact target element reference that points to the list
        items: Items to verify
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Verification result
    """
    return await _call_playwright_tool(
        "browser_verify_list_visible", {"element": element, "ref": ref, "items": items},
        browser_pool, browser_instance
    )


@mcp.tool()
@log_tool_result(logger)
async def browser_verify_value(
    type: str,
    element: str,
    ref: str,
    value: str,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Verify element value.

    Args:
        type: Type of the element. Must be 'textbox', 'checkbox', 'radio', 'combobox', or 'slider'.
        element: Human-readable element description
        ref: Exact target element reference that points to the element
        value: Value to verify. For checkbox, use "true" or "false".
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Verification result
    """
    return await _call_playwright_tool(
        "browser_verify_value", {"type": type, "element": element, "ref": ref, "value": value},
        browser_pool, browser_instance
    )


# =============================================================================
# NETWORK TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_network_requests(
    includeStatic: bool = False,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Returns all network requests since loading the page.

    Args:
        includeStatic: Whether to include successful static resources like images, fonts, scripts, etc. Defaults to false.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        List of network requests
    """
    return await _call_playwright_tool("browser_network_requests", {"includeStatic": includeStatic}, browser_pool, browser_instance)


# =============================================================================
# TAB MANAGEMENT TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_tabs(
    action: str,
    index: int | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    List, create, close, or select a browser tab.

    Args:
        action: Operation to perform. Must be 'list', 'new', 'close', or 'select'.
        index: Tab index, used for close/select. If omitted for close, current tab is closed.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Tab operation result
    """
    args: dict[str, Any] = {"action": action}
    if index is not None:
        args["index"] = index

    return await _call_playwright_tool("browser_tabs", args, browser_pool, browser_instance)


# =============================================================================
# CONSOLE TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_console_messages(
    level: str = "info",
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Returns all console messages.

    Args:
        level: Level of the console messages to return. Each level includes the messages of more severe levels.
               Must be 'error', 'warning', 'info', or 'debug'. Defaults to "info".
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        List of console messages
    """
    return await _call_playwright_tool("browser_console_messages", {"level": level}, browser_pool, browser_instance)


# =============================================================================
# DIALOG TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_handle_dialog(
    accept: bool,
    promptText: str | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Handle a dialog.

    Args:
        accept: Whether to accept the dialog.
        promptText: The text of the prompt in case of a prompt dialog.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Dialog handling result
    """
    args: dict[str, Any] = {"accept": accept}
    if promptText is not None:
        args["promptText"] = promptText

    return await _call_playwright_tool("browser_handle_dialog", args, browser_pool, browser_instance)


# =============================================================================
# FILE UPLOAD TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_file_upload(
    paths: list[str] | None = None,
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Upload one or multiple files.

    Args:
        paths: The absolute paths to the files to upload. Can be single file or multiple files.
               If omitted, file chooser is cancelled.
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        File upload result
    """
    args = {}
    if paths is not None:
        args["paths"] = paths

    return await _call_playwright_tool("browser_file_upload", args, browser_pool, browser_instance)


# =============================================================================
# TRACING TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_start_tracing(
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Start trace recording.

    Args:
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Trace start result
    """
    return await _call_playwright_tool("browser_start_tracing", {}, browser_pool, browser_instance)


@mcp.tool()
@log_tool_result(logger)
async def browser_stop_tracing(
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Stop trace recording.

    Args:
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Trace stop result
    """
    return await _call_playwright_tool("browser_stop_tracing", {}, browser_pool, browser_instance)


# =============================================================================
# INSTALLATION TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_install(
    browser_pool: str | None = None,
    browser_instance: str | None = None,
) -> dict[str, Any]:
    """
    Install the browser specified in the config. Call this if you get an error about the browser not being installed.

    Args:
        browser_pool: Target a specific browser pool by name. Default: None (uses default pool)
        browser_instance: Target a specific instance within the pool. Default: None (FIFO selection)

    Returns:
        Installation result
    """
    return await _call_playwright_tool("browser_install", {}, browser_pool, browser_instance)


# =============================================================================
# POOL MANAGEMENT TOOLS
# =============================================================================


@mcp.tool()
@log_tool_result(logger)
async def browser_pool_status(pool_name: str | None = None) -> dict[str, Any]:
    """
    Get status of browser pools including health, lease activity, and instance details.

    This tool provides real-time monitoring of all browser pools or a specific pool,
    showing instance health, availability, and lease status.

    Args:
        pool_name: Name of specific pool to query (e.g., "ISOLATED", "SESSIONLESS").
                  If None, returns status for all pools.

    Returns:
        Dictionary with pool status information:
        {
            "pools": [
                {
                    "name": str,              # Pool name
                    "description": str,       # Pool description
                    "is_default": bool,       # Whether this is the default pool
                    "total_instances": int,   # Total instances in pool
                    "healthy_instances": int, # Instances passing health checks
                    "failed_instances": int,  # Instances that failed health checks
                    "leased_instances": int,  # Currently leased instances
                    "available_instances": int, # Healthy and unleased instances
                    "instances": [
                        {
                            "id": str,          # Instance ID (numeric)
                            "alias": str|None,  # Instance alias (if configured)
                            "healthy": bool,    # Health check status
                            "leased": bool,     # Whether currently leased
                            "lease_duration_ms": int|None,  # Time leased (if leased)
                            "browser": str,     # Browser type
                            "headless": bool,   # Headless mode
                            "process_id": int|None,  # OS process ID
                            "health_check": {
                                "last_check": str,    # ISO timestamp
                                "responsive": bool,   # Responded to ping
                                "error": str|None     # Error if unhealthy
                            }
                        }
                    ]
                }
            ],
            "summary": {
                "total_pools": int,
                "total_instances": int,
                "healthy_instances": int,
                "failed_instances": int,
                "leased_instances": int,
                "available_instances": int
            }
        }

    Examples:
        # Get status of all pools
        status = await browser_pool_status()
        for pool in status["pools"]:
            print(f"{pool['name']}: {pool['available_instances']}/{pool['total_instances']} available")

        # Get status of specific pool
        status = await browser_pool_status(pool_name="ISOLATED")
        pool = status["pools"][0]
        if pool["available_instances"] == 0:
            print("Warning: ISOLATED pool has no available instances")

        # Monitor long-running leases
        status = await browser_pool_status()
        for pool in status["pools"]:
            for instance in pool["instances"]:
                if instance["leased"] and instance["lease_duration_ms"] > 60000:
                    print(f"Instance {instance['id']} in {pool['name']} leased for {instance['lease_duration_ms']}ms")
    """
    if not pool_manager:
        raise RuntimeError("Pool manager not initialized")

    return await pool_manager.get_status(pool_name)


# =============================================================================
# RESOURCES
# =============================================================================


@mcp.resource("playwright-proxy://status")
async def get_proxy_status() -> str:
    """Get the current proxy status"""
    if pool_manager:
        status = await pool_manager.get_status()
        total = status["summary"]["total_instances"]
        healthy = status["summary"]["healthy_instances"]
        return f"Playwright MCP Proxy is running ({healthy}/{total} instances healthy)"
    else:
        return "Playwright MCP Proxy is not initialized"


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Run the MCP proxy server"""
    logger.info("Initializing Playwright MCP Proxy Server...")
    mcp.run()


if __name__ == "__main__":
    main()
