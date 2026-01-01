# 5-second ping timeout breaks Streamable HTTP protocol for operations >5s

## Summary

The hardcoded 5-second ping timeout in `server.ts:117` breaks the MCP Streamable HTTP protocol for operations exceeding 5 seconds, making playwright-mcp unusable for common browser automation tasks. This affects **all HTTP-based MCP clients**, not just specific implementations.

Follow-up to #982 (closed without resolution).

## The Problem

When tool calls exceed 5 seconds (e.g., `browser_wait_for(6)`, slow page loads, complex interactions), the server:

1. **Blocks during execution** - Cannot send heartbeat pings while processing
2. **Times out and kills the session** - Returns 404 for all subsequent requests
3. **Loses all browser context** - Users must restart from scratch

## Real-World Impact

Common operations that fail:

| Operation | Duration | Result |
|-----------|----------|--------|
| Navigate to Amazon/LinkedIn | 5-10s | ❌ Timeout |
| `browser_wait_for` with `time: 6` | 6s | ❌ Timeout |
| Large page snapshots | 5-8s | ❌ Timeout |
| Complex multi-step workflows | 10-20s | ❌ Timeout |

**Example:**
```javascript
// Navigate to complex site (3-4s) + wait 3s = 6-7s total
browser_navigate({ url: "https://amazon.com/s?k=gloves" })
browser_wait_for({ time: 3 })  // ❌ Session terminated mid-operation
browser_snapshot({ limit: 200 })  // ❌ 404 session not found
```

## Why Client-Side Fixes Don't Work

Extensive testing and protocol analysis confirms this is a **server-side architectural issue**:

### Testing Results (Deterministic)
```
Duration | Tests | Result
---------|-------|--------
2s wait  | 4/4   | ✅ 100% success
4s wait  | 4/4   | ✅ 100% success
6s wait  | 4/4   | ❌ 100% timeout
8s wait  | 4/4   | ❌ 100% timeout
```

Clear threshold at exactly 5 seconds.

### Client Implementation Attempts (All Failed)

1. ✅ **Proactive client→server pings** - Server doesn't process them while blocked
2. ✅ **Threaded ping sender** - Bypasses event loop, but server-side blocking remains
3. ✅ **MCP SDK verification** - Protocol implemented correctly, GET SSE stream active

**Root cause:** The server **blocks during tool execution**, preventing it from sending heartbeat pings via the GET SSE stream. This violates the MCP Streamable HTTP protocol design, which explicitly supports concurrent server-to-client messaging during long operations.

## Technical Root Cause

Current behavior:
```typescript
async function handleToolCall(request) {
  startHeartbeat();  // Expects client response every 5s

  await executeTool();  // ❌ BLOCKS for 6+ seconds
                        // ❌ Cannot send pings while here

  // Session already killed by timeout
  return result;
}
```

The heartbeat mechanism should run **independently** of tool execution, not be blocked by it.

## Proposed Solutions

### Option 1: Configurable Timeout (Recommended)
Add environment variable:
```typescript
const PING_TIMEOUT = parseInt(process.env.MCP_PING_TIMEOUT_MS) || 5000;
```

**Benefits:** Zero breaking changes, users can set `MCP_PING_TIMEOUT_MS=30000`

### Option 2: Non-Blocking Heartbeat (Proper Fix)
Make heartbeat independent of tool execution:
```typescript
startBackgroundHeartbeat();  // Runs concurrently
await handleToolCall();      // Doesn't block heartbeat
```

**Benefits:** Fixes root cause, enables operations of any length

### Option 3: Increase Default (Quick Fix)
Change `5000` to `30000` in `server.ts:117`

**Benefits:** Immediate relief, one-line change

## Why This Matters

1. **Browser automation inherently needs >5s operations** - Waiting for content, navigating SPAs, processing large DOMs
2. **Affects all HTTP clients** - Python, Go, custom implementations
3. **Violates MCP protocol design** - Streamable HTTP supports concurrent messaging during long operations
4. **Drives users to alternatives** - Current timeout makes playwright-mcp unreliable for production

## Request

Please implement one of the proposed solutions. The current 5-second timeout is an artificial limitation that contradicts the MCP protocol's design and prevents playwright-mcp from handling real-world automation scenarios.

**Environment:**
- playwright-mcp: Latest (2025-12-31)
- MCP protocol: 2025-03-26 (Streamable HTTP)
- Transport: HTTP
- Reproduced across multiple client implementations
