# Playwright MCP Proxy

A proxy server for Microsoft's [playwright-mcp](https://github.com/microsoft/playwright-mcp) that provides efficient handling of large binary data (screenshots, PDFs) through blob storage and supports browser pools for concurrent operations.

**Version 2.0.0**: Now with browser pools! Run multiple isolated browser instances with different configurations simultaneously.

## Features

- **Browser Pools**: Multiple isolated browser instances organized into named pools with different configurations
- **Concurrent Operations**: Lease browser instances for exclusive use, enabling parallel browser automation
- **Playwright Browser Automation**: Full access to all playwright-mcp browser automation tools
- **Stealth Mode**: Built-in anti-detection capabilities (see [STEALTH.md](docs/STEALTH.md))
- **Efficient Binary Handling**: Large screenshots and PDFs automatically stored as blobs to reduce token usage
- **Blob Storage**: Built-in blob management using [mcp-mapped-resource-lib](https://github.com/nickweedon/mcp_mapped_resource_lib)
- **Automatic Cleanup**: TTL-based automatic expiration of old blobs
- **Docker Support**: Containerized deployment with multi-runtime support (Python + Node.js + Playwright)
- **Health Monitoring**: Real-time pool status and instance health checks

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ (for playwright-mcp)
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Docker (optional, for containerized deployment)

### Installation

1. Clone this repository:

```bash
git clone <this-repo> playwright-proxy-mcp
cd playwright-proxy-mcp
```

2. Install dependencies:

```bash
uv sync
```

3. Create your environment file:

```bash
cp .env.example.single-pool .env
# Edit .env with your configuration
```

4. Run the server:

```bash
uv run playwright-proxy-mcp
```

The server will:
- Start the playwright-mcp subprocess(es) via npx
- Initialize blob storage
- Initialize browser pools
- Listen for MCP client connections on stdio

## Browser Pools

### Overview

Browser pools allow you to run multiple browser instances with different configurations:

```bash
# Global defaults (apply to all pools)
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_HEADLESS=true

# Define a pool with 3 instances
PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
PW_MCP_PROXY__DEFAULT_DESCRIPTION="General purpose browsing"

# Instance-level overrides
PW_MCP_PROXY__DEFAULT__0_BROWSER=firefox      # Instance 0 uses Firefox
PW_MCP_PROXY__DEFAULT__1_ALIAS=debug          # Instance 1 has alias "debug"
PW_MCP_PROXY__DEFAULT__1_HEADLESS=false       # Instance 1 runs headed
```

### Using Pools

All browser tools accept optional `browser_pool` and `browser_instance` parameters:

```python
# Use default pool, FIFO instance selection
await browser_navigate(url="https://example.com")

# Use specific pool
await browser_navigate(url="https://example.com", browser_pool="FIREFOX")

# Use specific instance by alias
await browser_navigate(url="https://example.com", browser_instance="debug")
```

### Monitoring Pools

```python
# Get status of all pools
status = await browser_pool_status()
for pool in status["pools"]:
    print(f"{pool['name']}: {pool['available_instances']}/{pool['total_instances']} available")
```

See [docs/BROWSER_POOLS_SPEC.md](docs/BROWSER_POOLS_SPEC.md) for complete configuration reference.

## Docker Deployment

Build and run with Docker Compose:

```bash
docker compose up -d
```

This will:
- Build a container with Python, Node.js, and Playwright browsers
- Create persistent volumes for blob storage and playwright output
- Start the proxy server

## Configuration

Configure the proxy via environment variables in `.env`:

### Global Browser Settings

- `PW_MCP_PROXY_BROWSER`: Browser to use (chromium, firefox, webkit) - default: chromium
- `PW_MCP_PROXY_HEADLESS`: Run headless - default: true
- `PW_MCP_PROXY_CAPS`: Capabilities (vision,pdf,testing,tracing) - default: vision,pdf
- `PW_MCP_PROXY_TIMEOUT_ACTION`: Action timeout in ms - default: 15000
- `PW_MCP_PROXY_TIMEOUT_NAVIGATION`: Navigation timeout in ms - default: 30000

### Pool Configuration

- `PW_MCP_PROXY__<POOL>_INSTANCES`: Number of instances in pool
- `PW_MCP_PROXY__<POOL>_IS_DEFAULT`: Mark as default pool
- `PW_MCP_PROXY__<POOL>_DESCRIPTION`: Pool description
- `PW_MCP_PROXY__<POOL>__<ID>_BROWSER`: Browser for specific instance
- `PW_MCP_PROXY__<POOL>__<ID>_ALIAS`: Alias for specific instance
- `PW_MCP_PROXY__<POOL>__<ID>_HEADLESS`: Headless mode for specific instance

### Stealth Settings (Anti-Detection)

- `PW_MCP_PROXY_STEALTH_MODE`: Enable built-in stealth mode - default: false
- `PW_MCP_PROXY_USER_AGENT`: Custom user agent string - optional
- `PW_MCP_PROXY_INIT_SCRIPT`: Path to custom init script - optional
- `PW_MCP_PROXY_IGNORE_HTTPS_ERRORS`: Ignore HTTPS errors - default: false

See [docs/STEALTH.md](docs/STEALTH.md) for detailed stealth configuration.

### Blob Storage Settings

- `BLOB_STORAGE_ROOT`: Storage directory - default: /mnt/blob-storage
- `BLOB_MAX_SIZE_MB`: Max size per blob - default: 500
- `BLOB_TTL_HOURS`: Time-to-live for blobs - default: 24
- `BLOB_SIZE_THRESHOLD_KB`: Size threshold for blob storage - default: 50
- `BLOB_CLEANUP_INTERVAL_MINUTES`: Cleanup frequency - default: 60

See example env files in the repository root for complete configuration examples.

## How It Works

### Binary Data Interception

The proxy automatically detects large binary data in playwright tool responses:

1. When playwright tools return screenshots or PDFs
2. If the data size exceeds the threshold (default: 50KB)
3. The proxy stores the binary data as a blob
4. The response is transformed to include a blob reference instead

**Before (direct playwright-mcp):**
```json
{
  "screenshot": "data:image/png;base64,iVBORw0KGgo...500KB of data..."
}
```

**After (through proxy):**
```json
{
  "screenshot": "blob://1733577600-a3f2c1d9e4b5.png",
  "screenshot_size_kb": 500,
  "screenshot_mime_type": "image/png",
  "screenshot_expires_at": "2024-12-08T10:00:00Z"
}
```

### Retrieving Blobs

Blob retrieval is handled by a separate MCP Resource Server. See [mcp-mapped-resource-lib](https://github.com/nickweedon/mcp_mapped_resource_lib) for details.

## Available Tools

### Browser Tools

All playwright-mcp tools are available with browser pool support:

- `browser_navigate`: Navigate to a URL
- `browser_click`: Click an element
- `browser_fill`: Fill a form field
- `browser_screenshot`: Take a screenshot (auto-stored as blob if large)
- `browser_snapshot`: Get ARIA snapshot
- `browser_evaluate`: Execute JavaScript
- And 40+ more tools...

All tools accept optional `browser_pool` and `browser_instance` parameters.

### Pool Management

- `browser_pool_status(pool_name)`: Get pool health, lease activity, and instance status

## Architecture

```
┌─────────────────────────────────┐
│  MCP Client (Claude Desktop)   │
└────────────┬────────────────────┘
             │ stdio
┌────────────▼────────────────────┐
│  FastMCP Proxy (Python)         │
│  - Pool Manager                 │
│  - Binary Interception          │
│  - Blob Storage Integration     │
│  - Instance Leasing (FIFO)      │
└────────────┬────────────────────┘
             │ stdio (per instance)
┌────────────▼────────────────────┐
│  playwright-mcp instances       │
│  - Browser Automation           │
│  - Screenshot/PDF Generation    │
└─────────────────────────────────┘
```

## Testing

Run the test suite:

```bash
uv run pytest -v
```

Lint the code:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Project Structure

```
src/playwright_proxy_mcp/
├── server.py              # Main MCP proxy server
├── types.py               # TypedDict definitions
├── playwright/            # Playwright proxy components
│   ├── config.py         # Configuration loading (pool config)
│   ├── pool_manager.py   # Browser pool management
│   ├── process_manager.py # Subprocess management
│   ├── blob_manager.py   # Blob storage wrapper
│   ├── middleware.py     # Binary interception
│   └── proxy_client.py   # Stdio transport integration
└── utils/
    ├── navigation_cache.py     # TTL-based pagination cache
    ├── aria_processor.py       # ARIA snapshot processing
    └── jmespath_extensions.py  # Custom JMESPath functions
```

## Benefits

### Token Savings

Large screenshots can consume 50,000+ tokens. With blob storage:
- Screenshots stored as blobs use ~100 tokens for the reference
- Retrieve full data only when needed
- Automatic cleanup prevents storage bloat

### Concurrent Operations

Browser pools enable:
- Parallel browser automation
- Instance isolation for concurrent tasks
- Different browser configurations for different use cases

### Performance

- Faster response times for tool calls
- Reduced context window usage
- Efficient deduplication of identical screenshots
- FIFO instance leasing for fair resource allocation

## Troubleshooting

### npx not found

Ensure Node.js is installed and npx is in your PATH:

```bash
node --version
npx --version
```

### Playwright browser installation fails

Install browsers manually:

```bash
npx playwright@latest install chromium --with-deps
```

### Blob storage permissions

Ensure the blob storage directory is writable:

```bash
chmod -R 755 /mnt/blob-storage
```

### Pool not starting

Check the pool configuration in your `.env` file. Ensure:
- At least one pool has `IS_DEFAULT=true`
- Instance counts are valid (positive integers)
- No alias conflicts with numeric instance IDs

## License

MIT

## Contributing

Contributions welcome! Please open an issue or pull request.

## Resources

- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [FastMCP Documentation](https://gofastmcp.com)
- [MCP Mapped Resource Lib](https://github.com/nickweedon/mcp_mapped_resource_lib)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Browser Pools Specification](docs/BROWSER_POOLS_SPEC.md)
