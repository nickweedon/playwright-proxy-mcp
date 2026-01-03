# Browser Pools Specification

**Version**: 2.0.0
**Status**: Partially Implemented
**Breaking Change**: Yes

## Implementation Status

✅ **Implemented:**
- Pool manager with `LeasedKeyQueue` for instance leasing
- Hierarchical configuration (Global → Pool → Instance)
- Pool configuration parser and validation
- `browser_pool_status` tool for monitoring
- Health check infrastructure
- RAII pattern via async context managers

❌ **Not Yet Implemented:**
- `browser_pool` and `browser_instance` parameters on browser tools
- Tools currently use default pool only
- See [Implementation Checklist](#implementation-checklist) for details

**Current Behavior:** All browser tools use the default pool with automatic FIFO instance selection. Explicit pool/instance selection is not yet available in tool signatures.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Environment Variable Schema](#environment-variable-schema)
4. [Tool Interface](#tool-interface)
5. [Pool Manager Behavior](#pool-manager-behavior)
6. [Configuration Reference](#configuration-reference)
7. [Examples](#examples)
8. [Error Handling](#error-handling)
9. [Migration Notes](#migration-notes)

---

## Overview

### Summary

Version 2.0.0 introduces **browser pool** support, enabling the proxy to manage multiple upstream playwright-mcp process instances organized into logical pools. This allows:

- **Concurrent operations**: Multiple browser automation tasks running in parallel
- **Resource isolation**: Separate pools for different workloads (e.g., sessionless vs persistent)
- **Per-instance configuration**: Override pool defaults for specific instances
- **Load distribution**: Automatic FIFO leasing of available browser instances

### Key Changes

- ✅ Multiple browser pools, each with 1+ playwright-mcp processes
- ✅ New tool arguments: `browser_pool`, `browser_instance`
- ✅ New env var prefix: `PW_MCP_PROXY_` / `PW_MCP_PROXY__` (replaces `PLAYWRIGHT_`)
- ✅ Three-level configuration hierarchy: Global → Pool → Instance
- ✅ Pool manager with FIFO instance leasing via `leasedkeyq`
- ✅ Eager instance initialization at startup
- ⚠️ **Breaking**: All existing `PLAYWRIGHT_*` env vars must be renamed

---

## Architecture

### Component Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Proxy Server                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Pool Manager Registry                    │  │
│  │  ┌─────────────────┐  ┌─────────────────┐            │  │
│  │  │  Pool: DEFAULT  │  │ Pool: ISOLATED  │            │  │
│  │  │  (IS_DEFAULT)   │  │                 │            │  │
│  │  │  ┌───────────┐  │  │  ┌───────────┐  │            │  │
│  │  │  │Instance 0 │  │  │  │Instance 0 │  │            │  │
│  │  │  │(alias: "")│  │  │  │(alias: "")│  │            │  │
│  │  │  └───────────┘  │  │  └───────────┘  │            │  │
│  │  │  ┌───────────┐  │  │  ┌───────────┐  │            │  │
│  │  │  │Instance 1 │  │  │  │Instance 1 │  │            │  │
│  │  │  │(alias: "")│  │  │  │(alias: "")│  │            │  │
│  │  │  └───────────┘  │  │  └───────────┘  │            │  │
│  │  │  ┌───────────┐  │  │                 │            │  │
│  │  │  │Instance 2 │  │  │                 │            │  │
│  │  │  │(main_br.) │  │  │                 │            │  │
│  │  │  └───────────┘  │  │                 │            │  │
│  │  └─────────────────┘  └─────────────────┘            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Each instance = proxy_client.py → playwright-mcp process  │
└─────────────────────────────────────────────────────────────┘
```

**Shared Resources Across All Pools:**
- **Blob storage** (`blob_manager`): Single filesystem-based storage, content-addressable (SHA256)
- **Navigation cache** (`navigation_cache`): Global TTL-based cache for ARIA snapshot pagination

### Resource Leasing

- **Library**: [`leasedkeyq`](https://github.com/nickweedon/leasedkeyq)
- **Queue Type**: Blocking FIFO queue with dictionary key access
- **Scope**: One `LeasedKeyQ` per pool
- **Access Pattern**: RAII via async context manager (`async with`)
- **Behavior**:
  - **Specific instance requested**: Blocks until that instance is available
  - **No instance specified**: Leases first available instance (FIFO)
  - **Automatic cleanup**: Lease released when exiting context (even on exception)

---

## Environment Variable Schema

### Naming Convention

```
PW_MCP_PROXY_<CONFIG_KEY>=<value>                               # Global config
PW_MCP_PROXY__<POOL_NAME>_<CONFIG_KEY>=<value>                  # Pool-level config
PW_MCP_PROXY__<POOL_NAME>__<INSTANCE_ID>_<CONFIG_KEY>=<value>  # Instance override
```

**Rules**:
- Prefix: `PW_MCP_PROXY_` (single underscore for global, double for pool/instance)
- Pool name: Uppercase, alphanumeric + underscores
- Instance ID: Numeric string (`"0"`, `"1"`, etc.)
- Config key: Uppercase, alphanumeric + underscores
- Separators:
  - Single `_` after prefix for global config
  - Double `__` after prefix for pool/instance config
  - Single `_` between pool name and config key (pool level)
  - Double `__` between pool and instance ID (instance level)
  - Single `_` between instance ID and config key (instance level)

### Hierarchy

**Global settings** apply to all pools and instances unless overridden:

```bash
PW_MCP_PROXY_<CONFIG_KEY>=<value>
```

**Exception**: `INSTANCES`, `IS_DEFAULT`, and `ALIAS` **cannot** be set globally.

**Pool-level settings** apply to all instances in that pool unless overridden:

```bash
PW_MCP_PROXY__<POOL_NAME>_<CONFIG_KEY>=<value>
```

**Required pool keys**: Every pool **must** define `INSTANCES`.

**Instance-level overrides** apply only to that specific instance:

```bash
PW_MCP_PROXY__<POOL_NAME>__<INSTANCE_ID>_<CONFIG_KEY>=<value>
```

**Precedence**: Instance-level > Pool-level > Global

**Validation**: Setting `PW_MCP_PROXY_INSTANCES` (global) is an error. Each pool must explicitly define its instance count.

---

## Tool Interface

### Current Implementation

**Status:** Browser pool/instance selection is NOT yet exposed in tool signatures.

**Current Behavior:** All browser tools automatically use:
- The default pool (configured with `IS_DEFAULT=true`)
- FIFO instance selection (first available instance from default pool)

### Planned Tool Arguments (Not Yet Implemented)

The following parameters are planned but NOT yet available on browser tools:

#### `browser_pool` (string, optional) - PLANNED

- **Description**: Name of the pool to use
- **Default**: The pool with `IS_DEFAULT=true`
- **Validation**: Must reference an existing pool
- **Example**: `"SESSIONLESS"`, `"ISOLATED"`, `"TESTING"`
- **Status**: ❌ Not implemented

#### `browser_instance` (string, optional) - PLANNED

- **Description**: Specific instance within the pool
- **Default**: None (pool manager selects first available via FIFO)
- **Accepted values**:
  - Numeric ID: `"0"`, `"1"`, `"2"`, etc.
  - Alias: Any string set via `PW_MCP_PROXY__<POOL>__<ID>_ALIAS`
- **Behavior**: Blocks until specified instance is available
- **Status**: ❌ Not implemented

### Available Tools

- **`browser_pool_status`**: ✅ Implemented - Monitor pool health, instance status, and lease activity (see [Health Monitoring](#health-monitoring) section)

### Current Usage

```python
# ✅ CURRENT: Uses default pool, FIFO instance selection
await browser_navigate(url="https://example.com")

# ❌ PLANNED (not yet available): Use specific pool
# await browser_navigate(url="https://example.com", browser_pool="ISOLATED")

# ❌ PLANNED (not yet available): Use specific instance
# await browser_navigate(url="https://example.com", browser_pool="DEFAULT", browser_instance="0")
```

**Workaround:** To use multiple pools or specific instances, you currently need to deploy separate proxy instances with different configurations.

### Special Case: `browser_execute_bulk`

**Behavior**: All commands in a bulk execution use the **same** browser instance.

**Rationale**:
- Sequential commands operate on the same browser state
- Pagination caching works across bulk operations (cache is instance-agnostic)
- Single lease held for entire bulk operation via context manager

**Implementation**:

```python
async def browser_execute_bulk(
    commands: list[dict],
    browser_pool: str | None = None,
    browser_instance: str | None = None
) -> dict:
    """Execute multiple commands on same browser instance."""
    pool = pool_manager.get_pool(browser_pool or default_pool)

    # Single lease for all commands
    async with pool.lease_instance(browser_instance) as proxy_client:
        results = []
        for cmd in commands:
            result = await proxy_client.call_tool(cmd["tool"], cmd["args"])
            results.append(result)
        return {"results": results}
    # Lease released after all commands complete
```

**Example Usage**:

```python
await browser_execute_bulk(
    browser_pool="SESSIONLESS",
    browser_instance="2",  # All 3 commands use instance 2
    commands=[
        {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
        {"tool": "browser_wait_for", "args": {"text": "Loaded"}},
        {"tool": "browser_snapshot", "args": {}, "return_result": True}
    ]
)
# Instance 2 is leased once, used for all 3 commands, then released
```

---

## Pool Manager Behavior

### Startup Sequence

1. **Parse environment variables** into pool configurations:
   - Load global defaults (`PW_MCP_PROXY_*`)
   - Load pool configurations (`PW_MCP_PROXY__<POOL>_*`)
   - Load instance overrides (`PW_MCP_PROXY__<POOL>__<ID>_*`)
   - Apply precedence: Instance > Pool > Global
2. **Validate configuration**:
   - Each pool has `INSTANCES` defined (required, cannot be global)
   - Exactly one pool has `IS_DEFAULT=true`
   - `INSTANCES` not defined globally (validation error if found)
   - Instance IDs are sequential starting from 0
   - Aliases are unique within pool
   - All instance overrides reference valid instance IDs
3. **Initialize pools eagerly**:
   - Create `LeasedKeyQ` for each pool
   - Spawn all playwright-mcp processes (count = `INSTANCES`)
   - Create `proxy_client.py` wrapper for each process
   - Add all instances to pool's lease queue
4. **Register default pool** for tools without `browser_pool` argument

### Runtime Leasing

#### Context Manager Pattern (RAII)

The pool manager implements Python's **async context manager protocol** (`__aenter__` / `__aexit__`) to provide automatic lease acquisition and release using the `async with` idiom:

```python
# Pseudocode - Tool implementation pattern
async def execute_tool(tool_name, args, browser_pool=None, browser_instance=None):
    # 1. Select pool
    pool = pool_manager.get_pool(browser_pool or default_pool)

    # 2. Lease instance using context manager (RAII pattern)
    async with pool.lease_instance(browser_instance) as proxy_client:
        # 3. Execute tool on leased instance
        result = await proxy_client.call_tool(tool_name, args)
        return result
    # 4. Lease automatically released when exiting context
```

**Benefits of Context Manager Pattern**:
- **Automatic cleanup**: Lease always released, even if exception occurs
- **RAII (Resource Acquisition Is Initialization)**: Lease lifetime tied to scope
- **Exception safety**: No leaked resources if tool call fails
- **Readable**: Clear scope of resource ownership

#### Context Manager Implementation

The pool manager provides an async context manager that wraps `leasedkeyq`:

```python
class PoolManager:
    async def lease_instance(self, instance_key: str | None = None):
        """
        Async context manager for leasing browser instances.

        Args:
            instance_key: Specific instance ID/alias, or None for any available

        Yields:
            proxy_client: Leased browser instance

        Examples:
            # Lease any available instance (FIFO)
            async with pool.lease_instance() as client:
                await client.call_tool(...)

            # Lease specific instance by ID
            async with pool.lease_instance("0") as client:
                await client.call_tool(...)

            # Lease specific instance by alias
            async with pool.lease_instance("main_browser") as client:
                await client.call_tool(...)
        """
        if instance_key:
            # Blocks until specific instance available
            proxy_client = await self.leased_queue.lease(key=instance_key)
        else:
            # Leases first available (FIFO)
            proxy_client = await self.leased_queue.lease()

        try:
            yield proxy_client
        finally:
            # Always release, even on exception
            await self.leased_queue.release(proxy_client)
```

#### Exception Handling Example

The context manager ensures leases are always released, even when errors occur:

```python
async def browser_navigate_safe(url: str, browser_pool: str | None = None):
    """Example showing automatic cleanup on exception."""
    pool = pool_manager.get_pool(browser_pool or default_pool)

    try:
        async with pool.lease_instance() as proxy_client:
            # If this raises an exception...
            result = await proxy_client.call_tool("browser_navigate", {"url": url})
            return result
    except Exception as e:
        # ...the lease is still released before we get here
        logger.error(f"Navigation failed: {e}")
        raise
    # Context manager guarantees cleanup in both success and failure paths
```

#### Lease Behavior

| Scenario | Behavior |
|----------|----------|
| `browser_instance="0"` specified, instance 0 busy | **Blocks** until instance 0 available |
| `browser_instance="main_browser"` specified, instance 2 (aliased) busy | **Blocks** until instance 2 available |
| `browser_instance=None`, all instances busy | **Blocks** until any instance available |
| `browser_instance=None`, instances 1 and 3 idle | Leases instance with **earliest return** (FIFO) |
| Invalid `browser_instance` | **Error**: Instance not found in pool |
| Exception during tool execution | **Lease released** automatically via context manager cleanup |

---

## Configuration Reference

### Configuration Levels

Configuration can be specified at three levels with cascading precedence:

1. **Global** (`PW_MCP_PROXY_<KEY>`) - Applies to all pools and instances
2. **Pool** (`PW_MCP_PROXY__<POOL>_<KEY>`) - Applies to all instances in pool
3. **Instance** (`PW_MCP_PROXY__<POOL>__<ID>_<KEY>`) - Applies to specific instance

**Precedence**: Instance > Pool > Global

### Global-Level Config Keys

Most configuration keys can be set globally, **except pool-only and instance-only keys**:

**Cannot be set globally** (must be specified per-pool or per-instance):
- ❌ `INSTANCES` - Must be specified for each pool
- ❌ `IS_DEFAULT` - Must be specified for each pool (exactly one must be `true`)
- ❌ `ALIAS` - Must be specified per-instance

**Can be set globally**:
```bash
# Global defaults for all pools/instances
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_TIMEOUT=30000
PW_MCP_PROXY_ISOLATED=false
PW_MCP_PROXY_WSL_WINDOWS=false
```

### Pool-Level Config Keys

#### Required

| Key | Type | Description | Example | Notes |
|-----|------|-------------|---------|-------|
| `INSTANCES` | int | Number of instances in pool | `3` | **Must** be specified per-pool, **cannot** be global |

**CRITICAL**: Every pool **must** have `INSTANCES` defined. This cannot be set globally. Missing `INSTANCES` is a validation error.

#### Optional

| Key | Type | Default | Description | Example |
|-----|------|---------|-------------|---------|
| `IS_DEFAULT` | bool | `false` | Mark as default pool (only one allowed) | `true` |
| `DESCRIPTION` | str | `""` | Human-readable description of pool purpose | `"General web scraping pool"` |
| `ISOLATED` | bool | `false` | Run instances in isolated mode | `true` |
| `HEADLESS` | bool | `true` | Run browsers headless | `false` |
| `BROWSER` | str | `"chromium"` | Browser type | `"firefox"`, `"webkit"`, `"msedge"` |
| `WSL_WINDOWS` | bool | `false` | Use Windows Node.js from WSL | `true` |
| `TIMEOUT` | int | `30000` | Default timeout in milliseconds | `60000` |

### Instance-Level Config Keys

All global and pool-level keys can be overridden at instance level, **except**:
- ❌ `INSTANCES` (pool-only)
- ❌ `IS_DEFAULT` (pool-only)

#### Instance-Only Keys

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `ALIAS` | str | Friendly name for instance | `"main_browser"` |

#### Alias Validation Rules

Instance aliases must meet these requirements:
- **Pattern**: Must NOT match `/^\d+$/` (numeric strings reserved for instance IDs)
- **Uniqueness**: Must be unique within pool (no duplicate aliases)
- **Case-sensitivity**: Case-sensitive matching (`"Debug"` ≠ `"debug"`)
- **Validation**: Checked during config parsing; startup fails if violated

Examples:
- ✅ Valid: `"main_browser"`, `"debug-firefox"`, `"test1"`
- ❌ Invalid: `"0"` (looks like instance ID), `"123"` (numeric)

---

## Examples

### Example 1: Global Defaults with Single Pool

**Scenario**: Global defaults, simple setup with 3 instances

```bash
# .env
# Global defaults apply to all pools
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_TIMEOUT=30000

# Single pool configuration
PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
```

**Usage**:

```python
# Uses default pool, any available instance
await browser_navigate(url="https://example.com")
```

**Result**: 3 chromium processes (headless, 30s timeout), FIFO leasing

---

### Example 2: Global Defaults with Pool Overrides

**Scenario**: Global defaults, but different pool configurations

```bash
# Global defaults
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_BROWSER=chromium

# Default pool: Uses global defaults
PW_MCP_PROXY__SESSIONLESS_INSTANCES=5
PW_MCP_PROXY__SESSIONLESS_IS_DEFAULT=true

# Isolated pool: Overrides browser and headless
PW_MCP_PROXY__ISOLATED_INSTANCES=2
PW_MCP_PROXY__ISOLATED_HEADLESS=false
PW_MCP_PROXY__ISOLATED_BROWSER=firefox
PW_MCP_PROXY__ISOLATED_ISOLATED=true
```

**Usage**:

```python
# Uses SESSIONLESS pool (chromium, headless from global)
await browser_navigate(url="https://example.com")

# Uses ISOLATED pool (firefox, headed from pool override)
await browser_navigate(url="https://test.com", browser_pool="ISOLATED")
```

**Result**:
- SESSIONLESS: 5 headless chromium instances (inherits global config)
- ISOLATED: 2 headed firefox instances (overrides global config)

---

### Example 3: Full Hierarchy - Global, Pool, and Instance

**Scenario**: Maximum flexibility with all three configuration levels

```bash
# Global defaults
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_TIMEOUT=30000

# Pool defaults (inherits global where not specified)
PW_MCP_PROXY__BROWSERS_INSTANCES=3
PW_MCP_PROXY__BROWSERS_IS_DEFAULT=true
# HEADLESS, BROWSER, TIMEOUT inherited from global

# Instance 0: Override browser and add alias
PW_MCP_PROXY__BROWSERS__0_BROWSER=msedge
PW_MCP_PROXY__BROWSERS__0_ALIAS=edge_main
# HEADLESS=true (from global), TIMEOUT=30000 (from global)

# Instance 1: Override browser and headless, add alias
PW_MCP_PROXY__BROWSERS__1_BROWSER=firefox
PW_MCP_PROXY__BROWSERS__1_ALIAS=firefox_debug
PW_MCP_PROXY__BROWSERS__1_HEADLESS=false
# TIMEOUT=30000 (from global)

# Instance 2: Uses all global defaults
# BROWSER=chromium, HEADLESS=true, TIMEOUT=30000 (all from global)
```

**Effective Configuration**:

| Instance | Browser | Headless | Timeout | Source |
|----------|---------|----------|---------|--------|
| 0 (edge_main) | msedge | true | 30000 | browser=instance, rest=global |
| 1 (firefox_debug) | firefox | false | 30000 | browser/headless=instance, timeout=global |
| 2 | chromium | true | 30000 | all=global |

**Usage**:

```python
# Use Edge (headless)
await browser_navigate(url="https://example.com", browser_instance="edge_main")

# Use Firefox (headed for debugging)
await browser_navigate(url="https://example.com", browser_instance="firefox_debug")

# Use chromium (any available, likely instance 2)
await browser_navigate(url="https://example.com")
```

---

### Example 4: WSL to Windows with Global Config

**Scenario**: Running from WSL, using Windows browsers globally

```bash
# Global: All instances use Windows Node.js
PW_MCP_PROXY_WSL_WINDOWS=true
PW_MCP_PROXY_BROWSER=msedge
PW_MCP_PROXY_HEADLESS=false

# Pool inherits all global settings
PW_MCP_PROXY__WINDOWS_INSTANCES=2
PW_MCP_PROXY__WINDOWS_IS_DEFAULT=true
```

**Result**: 2 headed Edge browser processes running on Windows host, controlled from WSL

---

### Example 5: Multiple Pools with Shared Global Defaults and Descriptions

**Scenario**: 3 pools with distinct purposes, sharing common timeout/headless settings

```bash
# Global configuration shared by all pools
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_TIMEOUT=60000

# Pool 1: Chromium (default) - General purpose
PW_MCP_PROXY__CHROMIUM_INSTANCES=5
PW_MCP_PROXY__CHROMIUM_IS_DEFAULT=true
PW_MCP_PROXY__CHROMIUM_BROWSER=chromium
PW_MCP_PROXY__CHROMIUM_DESCRIPTION="General-purpose web scraping and navigation"

# Pool 2: Firefox - Cross-browser testing
PW_MCP_PROXY__FIREFOX_INSTANCES=3
PW_MCP_PROXY__FIREFOX_BROWSER=firefox
PW_MCP_PROXY__FIREFOX_DESCRIPTION="Cross-browser compatibility testing"

# Pool 3: WebKit - Mobile/Safari testing
PW_MCP_PROXY__WEBKIT_INSTANCES=2
PW_MCP_PROXY__WEBKIT_BROWSER=webkit
PW_MCP_PROXY__WEBKIT_DESCRIPTION="Mobile Safari and WebKit-specific testing"
```

**Result**: All pools share 60s timeout and headless mode, only browser type differs

**Usage with pool status**:

```python
# Discover available pools and their purposes
status = await browser_pool_status()
for pool in status["pools"]:
    print(f"{pool['name']}: {pool['description']}")
    print(f"  Available: {pool['available_instances']}/{pool['total_instances']}")

# Output:
# CHROMIUM: General-purpose web scraping and navigation
#   Available: 5/5
# FIREFOX: Cross-browser compatibility testing
#   Available: 3/3
# WEBKIT: Mobile Safari and WebKit-specific testing
#   Available: 2/2
```

---

## Health Monitoring

### `browser_pool_status` Tool

A new MCP tool for monitoring pool and instance health, lease status, and resource utilization.

#### Purpose

- View health status of all pools and instances
- Monitor which instances are currently leased (in-flight)
- Track lease duration for active operations
- Identify pool purpose via descriptions
- Diagnose resource contention issues

#### Usage

```python
# Get status of all pools
result = await browser_pool_status()

# Get status of specific pool
result = await browser_pool_status(pool_name="SESSIONLESS")
```

#### Response Structure

```json
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
        {
          "id": "1",
          "alias": "debug_browser",
          "status": "healthy",
          "leased": true,
          "lease_duration_ms": 3456,
          "lease_started_at": "2026-01-02T10:15:28.000Z",
          "browser": "firefox",
          "headless": false,
          "process_id": 12346,
          "health_check": {
            "last_check": "2026-01-02T10:15:31.789Z",
            "responsive": true,
            "error": null
          }
        },
        {
          "id": "2",
          "alias": null,
          "status": "failed",
          "leased": false,
          "lease_duration_ms": null,
          "lease_started_at": null,
          "browser": "chromium",
          "headless": true,
          "process_id": null,
          "health_check": {
            "last_check": "2026-01-02T10:15:20.000Z",
            "responsive": false,
            "error": "Process exited unexpectedly (code 1)"
          }
        }
        // ... 2 more instances (instances 3-4)
      ]
    },
    {
      "name": "ISOLATED",
      "description": "Isolated browser sessions for sensitive operations",
      "is_default": false,
      "total_instances": 2,
      "healthy_instances": 2,
      "leased_instances": 0,
      "available_instances": 2,
      "instances": [...]
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
```

#### Field Definitions

**Pool Fields**:
- `name`: Pool identifier
- `description`: Human-readable description from `DESCRIPTION` config
- `is_default`: Whether this is the default pool
- `total_instances`: Total configured instances
- `healthy_instances`: Count of responsive instances
- `leased_instances`: Count of currently leased instances
- `available_instances`: Count of healthy, unleased instances

**Instance Fields**:
- `id`: Instance numeric ID
- `alias`: Instance alias (if configured)
- `status`: Health status (`"healthy"`, `"failed"`, `"starting"`)
- `leased`: Whether instance is currently leased
- `lease_duration_ms`: Milliseconds since lease started (null if unleased)
- `lease_started_at`: ISO timestamp when lease started (null if unleased)
- `browser`: Browser type for this instance
- `headless`: Whether instance runs headless
- `process_id`: OS process ID (null if failed)
- `health_check`: Health check details

**Health Check Fields**:
- `last_check`: ISO timestamp of last health check
- `responsive`: Whether instance responded to health check
- `error`: Error message if health check failed (null if healthy)

#### Health Check Mechanism

Health checks run periodically (configurable interval, default 20 seconds):

1. **Process alive**: Check if playwright-mcp process is running
2. **Responsive**: Send ping command via MCP protocol
3. **Timeout**: Mark as failed if no response within 5 seconds
4. **Auto-recovery**: Optionally restart failed instances (future enhancement)

**Health Check Concurrency**: Health checks bypass the lease queue and directly probe subprocess health via `is_healthy()`. This prevents false negatives when all instances are leased but healthy.

**Current Implementation**: Uses existing health check logic from current proxy, extended to track per-instance state.

#### Example Workflow

```python
# Check pool status before bulk operation
status = await browser_pool_status(pool_name="SESSIONLESS")

if status["pools"][0]["available_instances"] < 3:
    print("Warning: Limited capacity in SESSIONLESS pool")
    # Consider using different pool
    await browser_navigate(url="...", browser_pool="ISOLATED")
else:
    await browser_navigate(url="...", browser_pool="SESSIONLESS")

# Monitor long-running operations
status = await browser_pool_status()
for pool in status["pools"]:
    for instance in pool["instances"]:
        if instance["leased"] and instance["lease_duration_ms"] > 60000:
            print(f"Warning: {pool['name']} instance {instance['id']} leased for {instance['lease_duration_ms']}ms")
```

#### Integration with Pool Manager

The pool manager tracks lease state:

```python
class PoolManager:
    def __init__(self):
        self.lease_tracking = {}  # {pool_name: {instance_id: LeaseInfo}}

    async def lease_instance(self, instance_key: str | None = None):
        # Track lease start
        lease_info = LeaseInfo(
            started_at=datetime.utcnow(),
            instance_id=instance_key
        )

        if instance_key:
            proxy_client = await self.leased_queue.lease(key=instance_key)
        else:
            proxy_client = await self.leased_queue.lease()

        # Record lease
        self.lease_tracking[self.pool_name][proxy_client.instance_id] = lease_info

        try:
            yield proxy_client
        finally:
            # Clear lease tracking
            del self.lease_tracking[self.pool_name][proxy_client.instance_id]
            await self.leased_queue.release(proxy_client)
```

---

## Error Handling

### Startup Validation Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `Pool missing INSTANCES configuration` | Pool defined without `PW_MCP_PROXY__<POOL>_INSTANCES` | Add `INSTANCES` config for pool |
| `Multiple default pools defined` | More than one pool has `IS_DEFAULT=true` | Set exactly one pool as default |
| `No default pool defined` | No pool has `IS_DEFAULT=true` | Set one pool's `IS_DEFAULT=true` |
| `Invalid instance ID in override` | `PW_MCP_PROXY__POOL__5_BROWSER=...` but `INSTANCES=3` | Use ID 0-2 or increase `INSTANCES` |
| `Duplicate alias in pool` | Two instances in same pool have same `ALIAS` | Use unique aliases per pool |
| `Invalid pool name in browser_pool` | Tool called with non-existent pool | Use existing pool name |
| `INSTANCES defined globally` | `PW_MCP_PROXY_INSTANCES=...` found | Move to pool level: `PW_MCP_PROXY__<POOL>_INSTANCES` |
| `No healthy instances in default pool` | User omits `browser_pool`, default pool exists but all instances failed | Return error: "Default pool '<name>' has no healthy instances. Specify explicit pool or restart failed instances." |

### Runtime Errors (Fail-Fast)

| Error | Cause | Behavior |
|-------|-------|----------|
| Process crash during tool call | Upstream playwright-mcp exits unexpectedly | Return error to caller immediately |
| Process crash while leased but idle | Process dies between operations | Mark instance as failed, remove from pool |
| Invalid `browser_instance` | Non-existent ID or alias | Return error to caller immediately |
| Timeout waiting for lease | All instances busy beyond timeout threshold | Return error to caller (configurable timeout) |

**Future Enhancement**: Auto-restart crashed instances (not in v2.0.0)

---

## Migration Notes

### Breaking Changes

**Version 1.x → 2.0.0**:

❌ **All `PLAYWRIGHT_*` environment variables must be renamed**

**Old (v1.x)**:
```bash
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_BROWSER=firefox
PLAYWRIGHT_WSL_WINDOWS=true
```

**New (v2.0.0) - Option A (Global config)**:
```bash
# Simplest migration: Use global config
PW_MCP_PROXY_HEADLESS=false
PW_MCP_PROXY_BROWSER=firefox
PW_MCP_PROXY_WSL_WINDOWS=true

# Create single default pool
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
```

**New (v2.0.0) - Option B (Pool config)**:
```bash
# Explicit pool-level config
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
PW_MCP_PROXY__DEFAULT_HEADLESS=false
PW_MCP_PROXY__DEFAULT_BROWSER=firefox
PW_MCP_PROXY__DEFAULT_WSL_WINDOWS=true
```

### Migration Checklist

1. ✅ Choose migration strategy:
   - **Option A**: Use global config (`PW_MCP_PROXY_*`) for simplicity
   - **Option B**: Use pool config (`PW_MCP_PROXY__<POOL>_*`) for explicit control
2. ✅ Rename all `PLAYWRIGHT_*` vars accordingly
3. ✅ Add `PW_MCP_PROXY__<POOL>_INSTANCES=1` (or more) for each pool
4. ✅ Add `PW_MCP_PROXY__<POOL>_IS_DEFAULT=true` to exactly one pool
5. ✅ Test startup validation (check logs for config errors)
6. ✅ Update any automation scripts that reference old env var names

### No Compatibility Layer

**Rationale**: This project has no external users yet, so backward compatibility is not required. Clean break allows simpler implementation.

---

## Implementation Checklist

- [ ] Add `leasedkeyq` dependency to `pyproject.toml`
- [ ] Create `src/playwright_proxy_mcp/pool_manager.py`
  - [ ] Pool configuration parser (global → pool → instance precedence)
  - [ ] Startup validation (default pool, instance IDs, aliases)
  - [ ] `LeasedKeyQ` integration (one per pool)
  - [ ] Async context manager implementation (`__aenter__` / `__aexit__`)
  - [ ] `lease_instance()` method returning context manager
  - [ ] Lease tracking for health monitoring (lease start time, instance ID)
  - [ ] Health check infrastructure (periodic checks, process monitoring)
- [ ] Update `src/playwright_proxy_mcp/config.py`
  - [ ] Global env var parsing (`PW_MCP_PROXY_*`)
  - [ ] Pool env var parsing (`PW_MCP_PROXY__<POOL>_*`)
  - [ ] Instance env var parsing (`PW_MCP_PROXY__<POOL>__<ID>_*`)
  - [ ] Parse `DESCRIPTION` config key for pools
  - [ ] Precedence resolution (instance > pool > global)
  - [ ] Validation rules:
    - [ ] Error if `PW_MCP_PROXY_INSTANCES` found (cannot be global)
    - [ ] Error if any pool missing `INSTANCES` config
    - [ ] Error if zero or multiple `IS_DEFAULT=true` pools
    - [ ] Error if duplicate aliases within pool
    - [ ] Error if instance overrides reference invalid instance IDs
  - [ ] Default pool detection
- [ ] Modify all tool signatures in `server.py`
  - [ ] Add `browser_pool` argument
  - [ ] Add `browser_instance` argument
  - [ ] Replace direct proxy_client calls with context manager pattern:
    ```python
    async with pool.lease_instance(browser_instance) as proxy_client:
        result = await proxy_client.call_tool(...)
    ```
- [ ] Implement `browser_pool_status` tool in `server.py`
  - [ ] Query all pools or specific pool
  - [ ] Collect health status from each instance
  - [ ] Include lease tracking data (in-flight status, duration)
  - [ ] Format hierarchical response with pool metadata
  - [ ] Include pool descriptions from config
- [ ] Update `browser_execute_bulk` to maintain single lease across all commands
- [ ] Add startup validation tests
- [ ] Add pool manager unit tests (context manager behavior, lease/release, health checks)
- [ ] Add integration tests (multi-instance scenarios, exception handling)
- [ ] Add `browser_pool_status` tests (all pools, specific pool, lease tracking)
- [ ] Update `CLAUDE.md` with new patterns (context manager usage, health monitoring)
- [ ] Update `README.md` with pool examples and `browser_pool_status` usage
- [ ] Create migration guide (this document)

---

## Future Enhancements (Post-v2.0.0)

- **Auto-restart**: Automatically restart crashed instances
- **Lazy initialization**: Start instances on-demand
- **Dynamic scaling**: Add/remove instances at runtime
- **Per-pool blob storage**: Isolate blob caches by pool
- **Custom lease strategies**: Round-robin, least-loaded, etc.
- **Graceful shutdown**: Drain leases before stopping instances
- **Health check configuration**: Configurable interval and timeout via env vars

---

## Glossary

- **Pool**: Logical group of playwright-mcp process instances
- **Instance**: Single playwright-mcp subprocess with unique configuration
- **Lease**: Temporary exclusive access to a browser instance
- **FIFO**: First-in-first-out (earliest-returned instance selected)
- **Eager initialization**: All instances started at proxy startup
- **Fail-fast**: Errors returned immediately without retry
- **RAII**: Resource Acquisition Is Initialization - pattern where resource lifetime is tied to object scope
- **Context Manager**: Python protocol for automatic resource cleanup using `with` statement (implements `__enter__`/`__exit__` or `__aenter__`/`__aexit__` for async)
- **Async Context Manager**: Async variant of context manager using `async with` (requires `__aenter__` and `__aexit__` methods)
