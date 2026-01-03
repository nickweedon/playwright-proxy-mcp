# Browser Pools Implementation Status

## Completed Components

### 1. Dependency Management ✅
- **File**: `pyproject.toml`
- **Change**: Added `leasedkeyq>=0.0.7` dependency
- **Status**: Complete
- **Tested**: Yes (via pytest)

### 2. Configuration System ✅
- **File**: `src/playwright_proxy_mcp/playwright/config.py`
- **Changes**:
  - Added new TypedDict classes: `InstanceConfig`, `PoolConfig`, `PoolManagerConfig`
  - Implemented `_parse_global_config()` for `PW_MCP_PROXY_*` vars
  - Implemented `_discover_pools()` to find pool definitions (with correct regex patterns)
  - Implemented `_parse_pool_config()` with precedence resolution
  - Implemented `_parse_instance_config()` with instance overrides
  - Implemented `_validate_alias()` to prevent numeric conflicts
  - Implemented `_validate_pool_config()` for duplicate alias checking
  - Implemented `load_pool_manager_config()` as main entry point
  - Updated `should_use_windows_node()` to check both old and new env vars
  - **REMOVED** `load_playwright_config()` - deprecated PLAYWRIGHT_* env vars no longer supported
- **Status**: Complete
- **Tested**: Yes - All config tests updated to use PW_MCP_PROXY_* env vars
- **Test File**: `tests/test_pool_config.py`

### 3. Pool Manager ✅
- **File**: `src/playwright_proxy_mcp/playwright/pool_manager.py` (NEW)
- **Components**:
  - `BrowserInstance` class: Wraps proxy client + process manager
  - `BrowserPool` class: Manages pool with FIFO leasing via `leasedkeyq`
  - `PoolManager` class: Manages multiple pools
  - Async context managers for RAII lease pattern
  - Health checking with bypass (no lease acquisition)
  - Background health check loop (20s interval)
  - Status reporting for pool observability
- **Status**: Complete
- **Tested**: No

## Remaining Implementation Tasks

### 4. Server Integration ⏸️
- **File**: `src/playwright_proxy_mcp/server.py`
- **Required Changes**:

#### 4.1 Global State (lines ~46-50)
```python
# OLD:
proxy_client = None

# NEW:
pool_manager = None
```

#### 4.2 Lifespan Context (lines ~51-110)
```python
# NEW:
async def lifespan_context(server):
    global middleware, pool_manager, navigation_cache

    # Load pool config
    pool_manager_config = load_pool_manager_config()

    # Initialize pool manager
    pool_manager = PoolManager(pool_manager_config, blob_manager, middleware)
    await pool_manager.initialize()
```

#### 4.3 Helper Function (line ~160-174)
```python
# OLD:
async def _call_playwright_tool(tool_name, arguments):
    if not proxy_client or not await proxy_client.is_healthy():
        raise ToolError("Proxy client not available or unhealthy")

    return await proxy_client.call_tool(actual_tool_name, arguments)

# NEW:
async def _call_playwright_tool(
    tool_name,
    arguments,
    browser_pool: str | None = None,
    browser_instance: str | None = None
):
    if not pool_manager:
        raise ToolError("Pool manager not initialized")

    async with pool_manager.lease_instance(browser_pool, browser_instance) as client:
        return await client.call_tool(actual_tool_name, arguments)
```

#### 4.4 Update ALL Tool Signatures (43+ tools)
Every tool needs two new optional parameters:

```python
# Example for browser_navigate
@mcp.tool()
async def browser_navigate(
    url: str,
    timeout: int = 30000,
    wait_until: str = "domcontentloaded",
    silent_mode: bool = False,
    flatten: bool = False,
    jmespath_query: str | None = None,
    output_format: str = "yaml",
    limit: int | None = None,
    offset: int = 0,
    cache_key: str | None = None,
    browser_pool: str | None = None,  # NEW
    browser_instance: str | None = None,  # NEW
) -> dict:
    # ...implementation
```

Tools to update:
- `browser_navigate`
- `browser_snapshot`
- `browser_click`
- `browser_fill`
- `browser_select`
- `browser_hover`
- `browser_type`
- `browser_screenshot`
- `browser_evaluate`
- `browser_execute_bulk` (special handling - single lease for all commands)
- `browser_wait_for`
- `browser_tabs`
- `browser_select_tab`
- `browser_close_tab`
- `browser_cookies_get`
- `browser_cookies_set`
- `browser_cookies_clear`
- `browser_console`
- `browser_download`
- `browser_upload`
- `browser_pdf`
- `browser_accessibility`
- `browser_drag_and_drop`
- `browser_mouse_move`
- `browser_mouse_click`
- `browser_mouse_dblclick`
- `browser_mouse_down`
- `browser_mouse_up`
- `browser_mouse_wheel`
- `browser_keyboard_down`
- `browser_keyboard_up`
- `browser_keyboard_press`
- `browser_keyboard_type`
- `browser_keyboard_insert_text`
- `browser_focus`
- `browser_blur`
- `browser_check`
- `browser_uncheck`
- `browser_scroll`
- `browser_get_attribute`
- `browser_get_property`
- `browser_is_visible`
- `browser_is_enabled`
- `browser_is_checked`
- `browser_inner_text`
- `browser_inner_html`

#### 4.5 Special Tool: browser_execute_bulk
```python
@mcp.tool()
async def browser_execute_bulk(
    commands: list[dict],
    stop_on_error: bool = True,
    browser_pool: str | None = None,  # NEW
    browser_instance: str | None = None,  # NEW
) -> dict:
    # Single lease for all commands
    async with pool_manager.lease_instance(browser_pool, browser_instance) as client:
        # Execute all commands on same client
        results = []
        errors = []

        for cmd in commands:
            # Execute command
            # ...

        return {"results": results, "errors": errors}
```

### 5. New Tool: browser_pool_status ⏸️
- **File**: `src/playwright_proxy_mcp/server.py`
- **Implementation**:

```python
@mcp.tool()
async def browser_pool_status(pool_name: str | None = None) -> dict:
    """
    Monitor pool health, instance status, and lease activity.

    Args:
        pool_name: Specific pool name, or None for all pools

    Returns:
        Dictionary with pool/instance status information

    Response structure:
    {
        "pools": [
            {
                "name": "SESSIONLESS",
                "description": "General web scraping and navigation",
                "is_default": true,
                "total_instances": 5,
                "healthy_instances": 4,
                "leased_instances": 2,
                "available_instances": 2,
                "instances": [
                    {
                        "id": "0",
                        "alias": null,
                        "status": "healthy",
                        "leased": true,
                        "lease_duration_ms": 1523,
                        "lease_started_at": "2026-01-02T10:15:30.123Z",
                        "browser": "chromium",
                        "headless": true,
                        "process_id": 12345,
                        "health_check": {
                            "last_check": "2026-01-02T10:15:31.456Z",
                            "responsive": true,
                            "error": null
                        }
                    },
                    # ... more instances
                ]
            }
        ],
        "summary": {
            "total_pools": 2,
            "total_instances": 7,
            "healthy_instances": 6,
            "failed_instances": 1,
            "leased_instances": 2,
            "available_instances": 4
        }
    }
    """
    if not pool_manager:
        raise ToolError("Pool manager not initialized")

    return await pool_manager.get_status(pool_name)
```

### 6. Documentation Updates ⏸️

#### 6.1 CLAUDE.md
Add section:
```markdown
## Browser Pools (v2.0.0)

All browser tools support pool-based execution via optional parameters:

- `browser_pool`: Pool name (defaults to pool with `IS_DEFAULT=true`)
- `browser_instance`: Instance ID or alias (defaults to FIFO selection)

### Configuration

Pools are configured via environment variables:

\`\`\`bash
# Global defaults
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_HEADLESS=true

# Pool definition
PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true

# Instance override
PW_MCP_PROXY__DEFAULT__0_BROWSER=firefox
PW_MCP_PROXY__DEFAULT__0_ALIAS=debug_browser
\`\`\`

### Usage Examples

\`\`\`python
# Use default pool, any instance
await browser_navigate(url="https://example.com")

# Use specific pool
await browser_navigate(url="https://example.com", browser_pool="ISOLATED")

# Use specific instance by ID
await browser_navigate(url="https://example.com", browser_pool="DEFAULT", browser_instance="0")

# Use specific instance by alias
await browser_navigate(url="https://example.com", browser_instance="debug_browser")

# Check pool status
status = await browser_pool_status()
\`\`\`

### Migration from v1.x

Old env vars (`PLAYWRIGHT_*`) are deprecated. Migrate to `PW_MCP_PROXY_*`:

\`\`\`bash
# v1.x
PLAYWRIGHT_BROWSER=chromium
PLAYWRIGHT_HEADLESS=false

# v2.0.0 (simplest migration)
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_HEADLESS=false
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
\`\`\`
```

#### 6.2 README.md
Add configuration examples and migration guide.

#### 6.3 BROWSER_POOLS_SPEC.md
Add clarifications per plan file:
- Alias validation rules (line ~421)
- Shared resources note (line ~73)
- Health check bypass (lines 748-758)
- Default pool error (lines 814-837)

### 7. Testing ⏸️

#### Unit Tests Needed
- `tests/test_config.py`:
  - Test `_parse_global_config()`
  - Test `_discover_pools()`
  - Test `_parse_pool_config()`
  - Test `_parse_instance_config()`
  - Test `_validate_alias()`
  - Test `load_pool_manager_config()`
  - Test precedence (instance > pool > global)
  - Test validation errors (no default, multiple defaults, duplicate aliases, etc.)

- `tests/test_pool_manager.py`:
  - Test `BrowserPool.initialize()`
  - Test `BrowserPool.lease_instance()` (FIFO, by ID, by alias)
  - Test lease context manager cleanup (RAII)
  - Test health checking
  - Test pool status reporting
  - Test `PoolManager.initialize()`
  - Test `PoolManager.get_pool()`
  - Test default pool fallback
  - Test concurrent leasing

#### Integration Tests Needed
- `tests/test_integration_pools.py`:
  - Test multi-pool navigation
  - Test instance affinity (same instance across requests)
  - Test health check during lease
  - Test pool exhaustion (all instances busy)
  - Test instance failure recovery

### 8. Environment File Examples ✅

Example env files created:

#### `.env.example.single-pool` ✅
```bash
# Single pool configuration (simplest)
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_HEADLESS=true

PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
```

#### `.env.example.multi-pool`
```bash
# Global defaults
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_TIMEOUT_ACTION=15000

# Pool 1: Chromium (default)
PW_MCP_PROXY__CHROMIUM_INSTANCES=5
PW_MCP_PROXY__CHROMIUM_IS_DEFAULT=true
PW_MCP_PROXY__CHROMIUM_BROWSER=chromium
PW_MCP_PROXY__CHROMIUM_DESCRIPTION="General-purpose web scraping"

# Pool 2: Firefox
PW_MCP_PROXY__FIREFOX_INSTANCES=3
PW_MCP_PROXY__FIREFOX_BROWSER=firefox
PW_MCP_PROXY__FIREFOX_DESCRIPTION="Cross-browser testing"

# Pool 3: Isolated
PW_MCP_PROXY__ISOLATED_INSTANCES=2
PW_MCP_PROXY__ISOLATED_ISOLATED=true
PW_MCP_PROXY__ISOLATED_DESCRIPTION="Isolated sessions"
```

#### `.env.example.instance-overrides`
```bash
# Global config
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_HEADLESS=true

# Pool config
PW_MCP_PROXY__BROWSERS_INSTANCES=3
PW_MCP_PROXY__BROWSERS_IS_DEFAULT=true

# Instance 0: Edge
PW_MCP_PROXY__BROWSERS__0_BROWSER=msedge
PW_MCP_PROXY__BROWSERS__0_ALIAS=edge_main

# Instance 1: Firefox (debug)
PW_MCP_PROXY__BROWSERS__1_BROWSER=firefox
PW_MCP_PROXY__BROWSERS__1_HEADLESS=false
PW_MCP_PROXY__BROWSERS__1_ALIAS=firefox_debug

# Instance 2: Chromium (default settings)
```

## Estimated Implementation Time

- [x] Config parser: **Complete**
- [x] Pool manager: **Complete**
- [ ] Server integration (43+ tools): **8-12 hours** (large, repetitive)
- [ ] browser_pool_status tool: **30 minutes**
- [ ] Documentation updates: **2 hours**
- [ ] Unit tests: **4 hours**
- [ ] Integration tests: **4 hours**
- [ ] Example env files: **30 minutes**

**Total remaining**: ~19-23 hours

## Breaking Changes

**This is a BREAKING CHANGE**. Users must:

1. Rename all `PLAYWRIGHT_*` environment variables to `PW_MCP_PROXY_*`
2. Add pool definitions with `INSTANCES` and `IS_DEFAULT`
3. Update any automation scripts referencing old env vars

### Migration Example

```bash
# Before (v1.x)
PLAYWRIGHT_BROWSER=firefox
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_TIMEOUT_ACTION=30000

# After (v2.0.0) - Option A: Global config
PW_MCP_PROXY_BROWSER=firefox
PW_MCP_PROXY_HEADLESS=false
PW_MCP_PROXY_TIMEOUT_ACTION=30000
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true

# After (v2.0.0) - Option B: Pool config
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
PW_MCP_PROXY__DEFAULT_BROWSER=firefox
PW_MCP_PROXY__DEFAULT_HEADLESS=false
PW_MCP_PROXY__DEFAULT_TIMEOUT_ACTION=30000
```

## Next Steps

1. **Test configuration parser** - Create simple unit tests to validate config loading
2. **Test pool manager** - Verify lease/release mechanics and health checks
3. **Update server.py** - Integrate pool manager (largest task)
4. **Add browser_pool_status tool**
5. **Update documentation**
6. **Write comprehensive tests**
7. **Create example env files**
8. **Test migration path** from v1.x

## Notes

- The configuration parser and pool manager are complete but **untested**
- Server integration requires touching **43+ tool functions**
- This is the largest refactoring since the project's inception
- Consider implementing incrementally (config → pool manager → server → tools)
- Migration guide is critical for existing users (though spec says "no external users yet")
