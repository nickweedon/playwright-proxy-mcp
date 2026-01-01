# Troubleshooting: browser_wait_for Hang Issue

## Problem Summary

The `browser_wait_for` tool can cause indefinite hangs when used in Docker containers with `browser_execute_bulk`, particularly after navigation operations and before snapshot operations.

**Failing Command Example:**
```json
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://www.amazon.com/s?k=gloves", "silent_mode": true}},
    {"tool": "browser_wait_for", "args": {"time": 3}},  // ⚠️ This hangs
    {"tool": "browser_snapshot", "args": {"flatten": true, "limit": 200, "output_format": "json"}, "return_result": true}
  ],
  "stop_on_error": true
}
```

## Root Causes

### 1. MCP Ping Timeout (Issue #982)

**Source:** [microsoft/playwright-mcp#982](https://github.com/microsoft/playwright-mcp/issues/982)

The playwright-mcp server has a **hardcoded 5-second ping timeout** that terminates connections when operations take longer than 5 seconds without responding to MCP ping requests.

**Impact:**
- Operations like `browser_wait_for` with `time: 3` (seconds) should complete in 3 seconds
- However, if the total operation time (navigation + wait + snapshot) exceeds 5 seconds, the MCP server kills the session
- The proxy may still be waiting for a response while the upstream server has already disconnected

**Why This Affects Docker:**
- Each `docker run` creates a fresh container with cold start overhead
- Cold starts add latency to browser initialization
- Amazon and other complex sites may take longer to respond
- Combined time easily exceeds 5-second ping timeout

### 2. Browser Wait Hang (Issue #141)

**Source:** [microsoft/playwright-mcp#141](https://github.com/microsoft/playwright-mcp/issues/141)

The MCP server can hang when `browser_wait` is called and the client connection is interrupted before explicit `browser_close`.

**Impact:**
- When ping timeout occurs during `browser_wait_for`, the connection is severed mid-operation
- The playwright-mcp server may not properly clean up the wait operation
- This leaves the wait operation in a zombie state, causing the proxy to hang waiting for a response

**Resolution:**
- Issue #141 was resolved by PR #144 ("fix: exit watchdog should listen for SIGINT/SIGTERM")
- However, the ping timeout issue (#982) was closed without resolution
- The combination still causes problems in Docker environments

## Diagnostic Scripts

### 1. diagnose-wait-hang.sh

Comprehensive diagnostic script that tests three scenarios:

```bash
./diagnose-wait-hang.sh
```

**Test 1:** Minimal bulk with wait_for (example.com + 3s wait)
- **Purpose:** Verify wait_for works in simple, fast scenarios
- **Expected:** Should PASS (< 5 seconds total time)

**Test 2:** Amazon bulk command (navigate + wait + snapshot)
- **Purpose:** Reproduce the original failing case
- **Expected:** May FAIL/HANG (> 5 seconds due to Amazon + wait)

**Test 3:** Amazon WITHOUT wait_for (navigate + snapshot only)
- **Purpose:** Isolate whether wait_for is the cause
- **Expected:** If PASS but Test 2 fails, wait_for is the culprit

### 2. bulk-wait-debug.sh

Simpler script focusing on container state isolation (earlier analysis):

```bash
./bulk-wait-debug.sh
```

## Solutions

### Solution 1: Remove Unnecessary wait_for Calls (Recommended)

In most cases, explicit `browser_wait_for` calls are **unnecessary** because:

1. **Playwright has implicit waits**: Selectors automatically wait for elements
2. **browser_snapshot waits for DOM**: The snapshot operation itself ensures page stability
3. **Navigation waits for load events**: `browser_navigate` waits for the page to load

**Example Fix:**
```json
// ❌ BEFORE (with unnecessary wait)
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}},
    {"tool": "browser_wait_for", "args": {"time": 3}},  // Remove this
    {"tool": "browser_snapshot", "args": {...}, "return_result": true}
  ]
}

// ✅ AFTER (without wait_for)
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}},
    {"tool": "browser_snapshot", "args": {...}, "return_result": true}  // Snapshot already waits
  ]
}
```

### Solution 2: Use Conditional Waits (When Needed)

If you **must** wait for dynamic content, use `browser_wait_for` with **text** or **textGone** instead of **time**:

```json
// ❌ BAD (arbitrary time wait)
{"tool": "browser_wait_for", "args": {"time": 3}}

// ✅ GOOD (wait for specific content)
{"tool": "browser_wait_for", "args": {"text": "Product loaded"}}

// ✅ GOOD (wait for loading indicator to disappear)
{"tool": "browser_wait_for", "args": {"textGone": "Loading..."}}
```

**Benefits:**
- Waits only as long as necessary (may be < 1 second)
- More reliable than arbitrary time waits
- Less likely to hit ping timeout

### Solution 3: Reduce Total Operation Time

Keep bulk operations under 5 seconds to avoid ping timeout:

```json
// ❌ BAD (too many operations, may exceed 5s)
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://amazon.com", "silent_mode": true}},
    {"tool": "browser_wait_for", "args": {"time": 3}},
    {"tool": "browser_snapshot", "args": {"flatten": true, "limit": 1000, "output_format": "json"}, "return_result": true}
  ]
}

// ✅ GOOD (split into smaller chunks)
// First call: Navigate
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://amazon.com", "silent_mode": true}}
  ]
}

// Second call: Snapshot (using cache for pagination if needed)
{
  "commands": [
    {"tool": "browser_snapshot", "args": {"limit": 200, "output_format": "json"}, "return_result": true}
  ]
}
```

### Solution 4: Increase Proxy Timeout (Limited Help)

The proxy already has a 90-second timeout (see [proxy_client.py:209](../src/playwright_proxy_mcp/playwright/proxy_client.py#L209)), which is much higher than the upstream 5-second ping timeout.

**Environment Variables:**
```bash
# These control Playwright timeouts (NOT MCP ping timeout)
export PLAYWRIGHT_TIMEOUT_ACTION=15000      # 15 seconds for actions
export PLAYWRIGHT_TIMEOUT_NAVIGATION=5000   # 5 seconds for navigation

# MCP ping timeout is hardcoded in upstream (cannot be configured)
```

**Note:** Increasing these timeouts doesn't help with the MCP ping timeout issue.

## Testing Your Fix

After removing `browser_wait_for` or switching to conditional waits, test with:

```bash
# Run the diagnostic script
./diagnose-wait-hang.sh

# Or test your specific command
mcptools call browser_execute_bulk --params '<your_command>' \
  docker run --rm -i --env-file container-test.env \
  playwright-proxy-mcp:latest uv run playwright-proxy-mcp
```

**Success Indicators:**
- Command completes in < 30 seconds
- Response contains `"success": true`
- No timeout errors in logs

## Best Practices

1. **Avoid `time` parameter in `browser_wait_for`**
   - Use `text` or `textGone` for conditional waits
   - Let Playwright's implicit waits handle timing

2. **Use `silent_mode` for navigation**
   - Reduces token overhead
   - Faster execution (no ARIA snapshot processing)

3. **Paginate large snapshots**
   - Use `limit` parameter to chunk results
   - Reduces processing time per call

4. **Split long workflows**
   - Break bulk commands into smaller batches
   - Each batch should complete in < 5 seconds

5. **Monitor logs**
   - Check Claude Desktop logs: `/workspace/logs/mcp-server-playwright-proxy-mcp-docker.log`
   - Look for timeout errors or connection issues

## Related Documentation

- [CLAUDE.md - Bulk Command Execution](../CLAUDE.md#bulk-command-execution)
- [CLAUDE.md - ARIA Snapshot Management](../CLAUDE.md#aria-snapshot-management)
- [playwright-mcp#982 - MCP Ping Timeout](https://github.com/microsoft/playwright-mcp/issues/982)
- [playwright-mcp#141 - Browser Wait Hang](https://github.com/microsoft/playwright-mcp/issues/141)
