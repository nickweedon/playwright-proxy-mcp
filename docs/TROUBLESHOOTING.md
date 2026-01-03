# Troubleshooting Guide

This guide provides solutions to common issues with the Playwright MCP Proxy.

## Best Practices for browser_wait_for

### Recommendation: Avoid Unnecessary Waits

Playwright has built-in implicit waits that make explicit `browser_wait_for` calls unnecessary in most cases:

```json
// ❌ UNNECESSARY (implicit waits already handle this)
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}},
    {"tool": "browser_wait_for", "args": {"time": 3}},
    {"tool": "browser_snapshot", "args": {...}, "return_result": true}
  ]
}

// ✅ RECOMMENDED (let implicit waits handle it)
{
  "commands": [
    {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}},
    {"tool": "browser_snapshot", "args": {...}, "return_result": true}
  ]
}
```

**Why this works:**
- `browser_navigate` waits for page load events
- `browser_snapshot` waits for DOM stability
- Playwright selectors auto-wait for elements

### When to Use browser_wait_for

Use `browser_wait_for` for dynamic content that loads after page load:

```json
// ✅ GOOD (wait for specific content)
{"tool": "browser_wait_for", "args": {"text": "Product loaded"}}

// ✅ GOOD (wait for loading indicator to disappear)
{"tool": "browser_wait_for", "args": {"textGone": "Loading..."}}
```

**Benefits:**
- Waits only as long as necessary
- More reliable than arbitrary time waits
- Fails fast if content never appears (timeout configured via `PW_MCP_PROXY_TIMEOUT_ACTION`)

## Server Startup Issues

### npx Command Not Found

**Problem:** `npx: command not found`

**Solution:**
```bash
# Check Node.js is installed
node --version
npx --version

# Install Node.js if missing (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Playwright Browser Installation Fails

**Problem:** Browser executables not found

**Solution:**
```bash
# Install browsers manually
npx playwright@latest install chromium --with-deps

# For all browsers
npx playwright@latest install --with-deps
```

### Pool Configuration Errors

**Problem:** `No default pool defined` or `Pool missing INSTANCES configuration`

**Solution:** Ensure your `.env` file has proper pool configuration:

```bash
# Minimum required configuration
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
```

**Common mistakes:**
- Missing `_INSTANCES` definition
- No pool has `IS_DEFAULT=true`
- Multiple pools with `IS_DEFAULT=true`
- Using old `PLAYWRIGHT_*` variables (deprecated in v2.0.0)

## Blob Storage Issues

### Blob Directory Not Writable

**Problem:** Permission errors when storing blobs

**Solution:**
```bash
# Create directory with proper permissions
sudo mkdir -p /mnt/blob-storage
sudo chown $USER:$USER /mnt/blob-storage
chmod -R 755 /mnt/blob-storage
```

### Blob Storage Full

**Problem:** Disk space exhausted

**Solution:**
```bash
# Check disk usage
df -h /mnt/blob-storage

# Reduce TTL to clean up faster
BLOB_TTL_HOURS=6  # Default is 24

# Manual cleanup
find /mnt/blob-storage -type f -mtime +1 -delete
```

## Docker Issues

### Container Won't Start

**Problem:** Container exits immediately

**Solution:**
```bash
# Check logs
docker compose logs -f

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

### High Memory Usage

**Problem:** Container consumes excessive memory

**Solution:** Reduce instance count or adjust Docker limits:

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

Or reduce browser instances:

```bash
# .env
PW_MCP_PROXY__DEFAULT_INSTANCES=1  # Reduce from 3
```

## WSL → Windows Issues

### cmd.exe Not Found

**Problem:** `cmd.exe not found in PATH` when using WSL→Windows mode

**Solution:**
```bash
# Verify cmd.exe is accessible
which cmd.exe

# If not, add Windows to PATH
export PATH="$PATH:/mnt/c/Windows/System32"

# Or disable WSL→Windows mode
unset PW_MCP_PROXY_WSL_WINDOWS
```

### Browsers Not Found (WSL→Windows)

**Problem:** Playwright can't find Windows browsers

**Solution:**
```bash
# Install Playwright browsers on Windows (from PowerShell)
npx playwright install chromium

# Verify installation
npx playwright install --dry-run
```

## Performance Issues

### Slow Navigation

**Problem:** Page loads take too long

**Solutions:**
- Increase timeout: `PW_MCP_PROXY_TIMEOUT_NAVIGATION=60000`
- Block unnecessary resources: `PW_MCP_PROXY_BLOCKED_ORIGINS=*.ads.example.com`
- Use faster browser: `PW_MCP_PROXY_BROWSER=chromium`

### High Token Usage

**Problem:** ARIA snapshots consuming too many tokens

**Solutions:**
- Use `silent_mode=true` for navigation when you don't need immediate snapshot
- Use JMESPath queries to filter: `jmespath_query='[?role == "button"]'`
- Use pagination: `limit=50`
- Use `output_format="json"` for more compact output

## Debugging

### Check Claude Desktop Logs

When working in the devcontainer, logs are mounted at:

```bash
# View last 50 lines
tail -n 50 /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log

# Follow logs in real-time
tail -f /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log

# Search for errors
grep -i error /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log
```

### Enable Debug Logging

Add to `.env`:

```bash
DEBUG=true
```

### Test MCP Server Directly

```bash
# Test with mcptools (from host, not container)
mcptools tools uv run --env-file host-test.env playwright-proxy-mcp

# Test specific tool
mcptools call browser_navigate --params '{"url":"https://example.com"}' \
  uv run --env-file host-test.env playwright-proxy-mcp
```

## Getting Help

1. Check the [README](../README.md) for basic usage
2. Review [CLAUDE.md](../CLAUDE.md) for configuration details
3. Search [playwright-mcp issues](https://github.com/microsoft/playwright-mcp/issues)
4. Open an issue with:
   - Error messages
   - Environment configuration (redact secrets)
   - Steps to reproduce
   - Logs (last 100 lines)
