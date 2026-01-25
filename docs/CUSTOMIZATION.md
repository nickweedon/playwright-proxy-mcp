# Playwright MCP Proxy Customization Guide

This guide explains how to customize and extend the Playwright MCP Proxy.

## Configuration

All configuration is done through environment variables in the `.env` file using the `PW_MCP_PROXY_*` prefix.

### Environment Variable Hierarchy

Configuration uses a three-level hierarchy with cascading precedence:

1. **Global** (`PW_MCP_PROXY_<KEY>`) - Applies to all pools and instances
2. **Pool** (`PW_MCP_PROXY__<POOL>_<KEY>`) - Applies to all instances in pool
3. **Instance** (`PW_MCP_PROXY__<POOL>__<ID>_<KEY>`) - Applies to specific instance

**Precedence**: Instance > Pool > Global

### Basic Configuration

```bash
# Global defaults (apply to all pools/instances)
PW_MCP_PROXY_BROWSER=chromium  # chromium, firefox, webkit, msedge
PW_MCP_PROXY_HEADLESS=true
PW_MCP_PROXY_CAPS=vision,pdf
PW_MCP_PROXY_TIMEOUT_ACTION=15000
PW_MCP_PROXY_TIMEOUT_NAVIGATION=30000

# Define a pool (required)
PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
PW_MCP_PROXY__DEFAULT_DESCRIPTION="General purpose browsing"
```

### Pool-Specific Configuration

Override global settings for a specific pool:

```bash
# Global: Chromium
PW_MCP_PROXY_BROWSER=chromium

# Pool: Use Firefox instead
PW_MCP_PROXY__TESTING_INSTANCES=2
PW_MCP_PROXY__TESTING_BROWSER=firefox
PW_MCP_PROXY__TESTING_DESCRIPTION="Firefox testing pool"
```

### Instance-Specific Configuration

Override pool settings for a specific instance:

```bash
# Pool defaults
PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_BROWSER=chromium
PW_MCP_PROXY__DEFAULT_HEADLESS=true

# Instance 0: Use Edge
PW_MCP_PROXY__DEFAULT__0_BROWSER=msedge
PW_MCP_PROXY__DEFAULT__0_ALIAS=edge_main

# Instance 1: Debug mode (headed)
PW_MCP_PROXY__DEFAULT__1_HEADLESS=false
PW_MCP_PROXY__DEFAULT__1_ALIAS=debug_browser
PW_MCP_PROXY__DEFAULT__1_TIMEOUT_ACTION=30000

# Instance 2: Uses pool defaults
```

### Available Configuration Keys

#### Browser Settings
- `BROWSER`: Browser type (chromium, firefox, webkit, msedge)
- `HEADLESS`: Run headless (true/false)
- `NO_SANDBOX`: Disable sandbox (true/false)
- `DEVICE`: Device to emulate
- `VIEWPORT_SIZE`: Viewport dimensions (e.g., "1920x1080")

#### Profile/Storage
- `ISOLATED`: Run in isolated mode (true/false)
- `USER_DATA_DIR`: Persistent user data directory
- `STORAGE_STATE`: Path to storage state file

#### Network
- `ALLOWED_ORIGINS`: Comma-separated allowed origins
- `BLOCKED_ORIGINS`: Comma-separated blocked origins
- `PROXY_SERVER`: Proxy server URL

#### Capabilities
- `CAPS`: Comma-separated capabilities (vision,pdf,testing,tracing)

#### Output
- `SAVE_SESSION`: Save session data (true/false)
- `SAVE_TRACE`: Save execution traces (true/false)
- `SAVE_VIDEO`: Video recording mode
- `OUTPUT_DIR`: Output directory path

#### Timeouts (milliseconds)
- `TIMEOUT_ACTION`: Action timeout (default: 15000)
- `TIMEOUT_NAVIGATION`: Navigation timeout (default: 30000)

#### Images
- `IMAGE_RESPONSES`: Image handling (allow/block)

#### Stealth
- `ENABLE_STEALTH`: **Macro** - Auto-configure stealth settings (true/false)
- `USER_AGENT`: Custom user agent string
- `INIT_SCRIPT`: Path to custom initialization script
- `IGNORE_HTTPS_ERRORS`: Ignore HTTPS errors (true/false)

**Note**: `ENABLE_STEALTH=true` automatically configures `INIT_SCRIPT`, `HEADLESS`, and `USER_AGENT` for optimal stealth. Individual settings can override these defaults.

#### Extension Support
- `EXTENSION`: Enable extension support (true/false)
- `EXTENSION_TOKEN`: Extension authentication token

#### WSL→Windows
- `WSL_WINDOWS`: Use Windows Node.js from WSL (true/false)

### Blob Storage Configuration

Configure blob storage behavior:

```bash
# Storage location
BLOB_STORAGE_ROOT=/mnt/blob-storage

# Size limits
BLOB_MAX_SIZE_MB=500
BLOB_SIZE_THRESHOLD_KB=50  # When to use blob vs inline

# Cleanup
BLOB_TTL_HOURS=24
BLOB_CLEANUP_INTERVAL_MINUTES=60
```

See [.env.example.single-pool](../.env.example.single-pool), [.env.example.multi-pool](../.env.example.multi-pool), or [.env.example.instance-overrides](../.env.example.instance-overrides) for complete examples.

## Adding Custom Tools

While the proxy automatically forwards all playwright-mcp tools, you can add custom tools:

### 1. Create a New API Module

Create `src/playwright_proxy_mcp/api/custom_tools.py`:

```python
"""Custom tools for playwright proxy"""

async def analyze_screenshot(blob_id: str) -> dict:
    """
    Analyze a screenshot blob.

    Args:
        blob_id: The blob ID of the screenshot

    Returns:
        Analysis results
    """
    # Your custom logic here
    return {"analysis": "..."}
```

### 2. Register in server.py

In `src/playwright_proxy_mcp/server.py`:

```python
from .api import custom_tools

@mcp.tool()
async def analyze_screenshot(blob_id: str) -> dict:
    """Analyze a screenshot from blob storage"""
    return await custom_tools.analyze_screenshot(blob_id)
```

## Modifying Middleware Behavior

### Adjusting Binary Detection Threshold

Edit `src/playwright_proxy_mcp/playwright/middleware.py`:

```python
class BinaryInterceptionMiddleware:
    # Add more tools to always intercept
    BINARY_TOOLS = {
        "playwright_screenshot",
        "playwright_pdf",
        "playwright_save_as_pdf",
        "your_custom_binary_tool",  # Add here
    }
```

### Custom Response Transformation

Override the `intercept_response` method:

```python
async def intercept_response(self, tool_name: str, response: Any) -> Any:
    # Custom logic before standard interception
    if tool_name == "special_tool":
        # Do something special
        pass

    # Call parent implementation
    return await super().intercept_response(tool_name, response)
```

## Extending Configuration

### Adding New Configuration Options

1. Update `src/playwright_proxy_mcp/playwright/config.py`:

```python
class PlaywrightConfig(TypedDict, total=False):
    # ... existing fields ...
    custom_option: str  # Add your option
```

2. Update `_parse_global_config()` in `config.py`:

```python
def _parse_global_config() -> PlaywrightConfig:
    config: PlaywrightConfig = {}
    # ... existing config parsing ...

    # Add your custom option
    if custom_option := os.getenv("PW_MCP_PROXY_CUSTOM_OPTION"):
        config["custom_option"] = custom_option

    return config
```

3. Update `src/playwright_proxy_mcp/playwright/process_manager.py`:

```python
async def _build_command(self, config: PlaywrightConfig) -> list[str]:
    # ... existing command building ...

    # Add your custom option
    if "custom_option" in config:
        command.extend(["--custom-option", config["custom_option"]])
```

## Custom Blob Storage Logic

### Implementing Custom Cleanup Logic

Override cleanup behavior in `src/playwright_proxy_mcp/playwright/blob_manager.py`:

```python
async def cleanup_expired(self) -> int:
    """Custom cleanup logic"""
    # Your custom logic here

    # Call parent cleanup
    deleted = await super().cleanup_expired()

    # Additional cleanup
    # ...

    return deleted
```

### Custom Blob Metadata

Add custom metadata when storing blobs:

```python
async def store_base64_data(
    self, base64_data: str, filename: str, tags: list[str] | None = None
) -> dict[str, Any]:
    # Add custom tags
    custom_tags = ["custom-tag", "proxy-generated"]
    all_tags = (tags or []) + custom_tags

    # Call parent with enhanced tags
    return await super().store_base64_data(base64_data, filename, all_tags)
```

## Docker Customization

### Installing Additional Browser Engines

Edit `Dockerfile`:

```dockerfile
# Install multiple browsers instead of just chromium
RUN npx playwright@latest install chromium firefox webkit --with-deps
```

### Adding Custom System Dependencies

```dockerfile
# Add your dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    your-package \
    another-package \
    && rm -rf /var/lib/apt/lists/*
```

### Adjusting Resource Limits

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 8G      # Increase for heavy usage
      cpus: '4.0'
    reservations:
      memory: 4G
      cpus: '2.0'
```

## Testing Custom Features

Create tests in `tests/test_custom.py`:

```python
"""Tests for custom features"""

import pytest
from playwright_proxy_mcp.api import custom_tools


class TestCustomTools:
    """Tests for custom tools."""

    async def test_custom_tool(self):
        """Test custom tool functionality."""
        result = await custom_tools.analyze_screenshot("blob://test.png")
        assert "analysis" in result
```

Run tests:

```bash
uv run pytest tests/test_custom.py -v
```

## Troubleshooting

### Rebuilding After Changes

If you modify the package structure, rebuild:

```bash
uv sync
```

### Docker Rebuild

After Dockerfile changes:

```bash
docker compose build --no-cache
docker compose up -d
```

### Verifying Configuration

Check loaded configuration:

```bash
# Check pool configuration
uv run python -c "from playwright_proxy_mcp.playwright.config import load_pool_manager_config; import json; import os; os.environ['PW_MCP_PROXY__DEFAULT_INSTANCES']='1'; os.environ['PW_MCP_PROXY__DEFAULT_IS_DEFAULT']='true'; config = load_pool_manager_config(); print(json.dumps(config['global_config'], indent=2))"

# Check blob configuration
uv run python -c "from playwright_proxy_mcp.playwright.config import load_blob_config; import json; print(json.dumps(load_blob_config(), indent=2))"
```

## Best Practices

1. **Keep tools focused**: Each tool should do one thing well
2. **Use type hints**: Helps with documentation and catches errors
3. **Write tests**: Test your custom features thoroughly
4. **Document changes**: Update docstrings and README
5. **Handle errors gracefully**: Provide informative error messages
6. **Use environment variables**: Keep configuration flexible
7. **Monitor resource usage**: Browser automation can be memory-intensive

## See Also

- [README](../README.md) - Basic usage and quick start
- [CLAUDE.md](../CLAUDE.md) - Development guidelines and patterns
- [BROWSER_POOLS_SPEC.md](BROWSER_POOLS_SPEC.md) - Pool configuration reference
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
