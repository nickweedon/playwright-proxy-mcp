# Stealth Mode Documentation

This document explains the anti-detection capabilities available in the Playwright MCP Proxy server.

## Overview

The Playwright MCP Proxy includes a bundled JavaScript initialization script (`stealth.js`) that can make browser automation less detectable by bot detection systems. This is useful when scraping websites with anti-bot protections or when you need the browser to appear more like a real user.

## How It Works

The stealth implementation uses a JavaScript initialization script that runs **before** any page scripts execute. This script modifies browser properties and APIs commonly used to detect automation tools.

## Configuration

### Quick Start: ENABLE_STEALTH Macro

The easiest way to enable stealth mode is using the `ENABLE_STEALTH` convenience macro. This automatically configures optimal stealth settings:

```bash
# Global configuration (applies to all pools/instances)
PW_MCP_PROXY_ENABLE_STEALTH=true

# Pool-specific
PW_MCP_PROXY__MYPOOL_ENABLE_STEALTH=true

# Instance-specific
PW_MCP_PROXY__MYPOOL__0_ENABLE_STEALTH=true
```

When `ENABLE_STEALTH=true`, the following defaults are automatically applied (unless overridden by more specific configuration):
- `INIT_SCRIPT`: Set to bundled stealth.js path
- `HEADLESS`: Set to `false` (headed mode for more realistic behavior)
- `USER_AGENT`: Set to a recent Chrome user agent string

### Manual Configuration (Advanced)

For fine-grained control, you can manually configure stealth settings:

```bash
# Manually specify init script path
PW_MCP_PROXY_INIT_SCRIPT=/path/to/custom-stealth.js

# Custom user agent
PW_MCP_PROXY_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64)...

# Other stealth-related settings
PW_MCP_PROXY_HEADLESS=false
PW_MCP_PROXY_IGNORE_HTTPS_ERRORS=false
```

### Related Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PW_MCP_PROXY_ENABLE_STEALTH` | boolean | `false` | **Macro**: Auto-configure stealth settings (init script, headless, user agent) |
| `PW_MCP_PROXY_INIT_SCRIPT` | string | - | Path to initialization script (e.g., stealth.js) |
| `PW_MCP_PROXY_USER_AGENT` | string | (browser default) | Custom user agent string |
| `PW_MCP_PROXY_HEADLESS` | boolean | `true` | Run browser in headless mode |
| `PW_MCP_PROXY_IGNORE_HTTPS_ERRORS` | boolean | `false` | Ignore HTTPS certificate errors |

### Example Configuration

#### Simple (Using ENABLE_STEALTH Macro)

```bash
# Enable stealth mode with one setting
PW_MCP_PROXY_ENABLE_STEALTH=true

# Optional: Use persistent profile for cookies/cache
PW_MCP_PROXY_USER_DATA_DIR=/app/browser-profile

# Define pool
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
```

#### Advanced (Manual Configuration)

```bash
# Manually configure each stealth setting
PW_MCP_PROXY_INIT_SCRIPT=/opt/src/mcp/playwright-proxy-mcp/src/playwright_proxy_mcp/playwright/stealth.js
PW_MCP_PROXY_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
PW_MCP_PROXY_HEADLESS=false

# Optional: Use persistent profile for cookies/cache
PW_MCP_PROXY_USER_DATA_DIR=/app/browser-profile

# Define pool
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true
```

## Anti-Detection Techniques

The bundled `stealth.js` script implements these anti-detection techniques:

### 1. WebDriver Property Removal
- Removes `navigator.webdriver` property
- Sets it to `undefined` to match real browsers

### 2. Chrome Runtime Spoofing
- Adds `window.chrome.runtime` object
- Makes the browser appear to have Chrome extensions

### 3. Permissions API Override
- Handles permissions queries properly
- Returns realistic notification permission values

### 4. Plugin Array Spoofing
- Adds realistic plugin entries
- Mimics Chrome's PDF viewer, Native Client, etc.

### 5. Language Configuration
- Sets `navigator.languages` to realistic values
- Defaults to `['en-US', 'en']`

### 6. WebGL Vendor Masking
- Overrides WebGL vendor/renderer info
- Returns "Intel Inc." / "Intel Iris OpenGL Engine"
- Hides headless browser indicators

### 7. User Agent Data (Client Hints)
- Spoofs `navigator.userAgentData` for Chromium 90+
- Provides realistic brand and platform information

### 8. Battery API Masking
- Removes battery API (not available in headless mode)
- Returns realistic charging state

### 9. Connection Info
- Adds `navigator.connection` with realistic values
- Reports 4G connection with appropriate speeds

### 10. Media Devices
- Ensures `navigator.mediaDevices` exists
- Returns realistic device enumerations

### 11. Hardware Concurrency
- Sets CPU core count to realistic value (8 cores)

### 12. Device Memory
- Reports realistic RAM amount (8GB)

### 13. Screen Properties
- Matches screen dimensions to viewport
- Prevents dimension-based detection

### 14. Touch Events
- Adds touch support properties
- Makes browser appear touch-capable

### 15. Notification Permissions
- Sets realistic notification permission state

### 16. Canvas Fingerprinting Protection
- Basic protection against canvas fingerprinting
- Note: Advanced protection is commented out to avoid breaking legitimate canvas usage

### 17. Console Debug Protection
- Filters automation-related console messages

### 18. Error Stack Trace Cleaning
- Cleans error stack traces that might reveal automation

## Limitations

### What Stealth Mode Helps With:
✅ Simple bot detection checks (webdriver property, plugins, etc.)
✅ Basic fingerprinting techniques
✅ User-agent based filtering
✅ Headless browser detection

### What Stealth Mode Cannot Fully Prevent:
❌ Advanced bot detection services (Cloudflare Turnstile, DataDome, PerimeterX)
❌ Behavioral analysis (mouse movements, timing patterns)
❌ IP-based rate limiting
❌ CAPTCHAs and human verification challenges
❌ TLS fingerprinting

## Advanced Usage

### Custom Initialization Scripts

Create your own custom anti-detection script:

1. Create a JavaScript file (e.g., `custom-stealth.js`)
2. Set the configuration:
   ```bash
   PW_MCP_PROXY_INIT_SCRIPT=/path/to/custom-stealth.js
   ```

Your custom script will run instead of or in addition to other initialization logic.

### Combining with Other Techniques

For maximum stealth, combine the init script with:

1. **Realistic User Agents**: Use recent, common user agent strings
2. **Headed Mode**: Run with `PW_MCP_PROXY_HEADLESS=false`
3. **Persistent Profiles**: Use `PW_MCP_PROXY_USER_DATA_DIR` to maintain cookies/cache
4. **Proxy Rotation**: Use `PW_MCP_PROXY_PROXY_SERVER` with rotating proxies
5. **Realistic Viewport**: Use common resolutions like `1920x1080` or `1366x768`
6. **Device Emulation**: Use `PW_MCP_PROXY_DEVICE` to emulate real devices

### Example: Maximum Stealth Configuration

```bash
# Enable stealth mode (automatic configuration)
PW_MCP_PROXY_ENABLE_STEALTH=true

# Additional stealth-enhancing settings
PW_MCP_PROXY_VIEWPORT_SIZE=1920x1080
PW_MCP_PROXY_USER_DATA_DIR=/app/browser-profile
PW_MCP_PROXY_ISOLATED=false
PW_MCP_PROXY_SAVE_SESSION=true

# Pool configuration
PW_MCP_PROXY__DEFAULT_INSTANCES=1
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true

# Optional: Use proxy for IP rotation
# PW_MCP_PROXY_PROXY_SERVER=http://proxy.example.com:8080

# Optional: Override auto-configured user agent with custom one
# PW_MCP_PROXY_USER_AGENT=Mozilla/5.0 (Custom...)
```

## Testing Stealth Mode

Test your stealth configuration using bot detection test sites:

1. **arh.antoinevastel.com/bots**: Tests for headless browser detection
2. **bot.sannysoft.com**: Comprehensive bot detection test
3. **pixelscan.net**: Browser fingerprinting analysis
4. **browserleaks.com**: Various browser fingerprint tests

Example test:

```python
# Test stealth mode
result = await browser_navigate(url="https://bot.sannysoft.com")
screenshot = await browser_screenshot(fullPage=True)
# Check the screenshot for "WebDriver: false" and other passing tests
```

## Troubleshooting

### Stealth Script Not Loading

Check if the script file exists:
```bash
ls -la /opt/src/mcp/playwright-proxy-mcp/src/playwright_proxy_mcp/playwright/stealth.js
```

If using Docker, ensure the path is accessible inside the container.

### Still Being Detected

Try these additional measures:
1. Enable headed mode (`PW_MCP_PROXY_HEADLESS=false`)
2. Add realistic delays between actions
3. Use a residential proxy
4. Update user agent to latest Chrome version
5. Consider using a persistent browser profile
6. Verify the stealth script is actually loading (check browser console)

### Custom Script Not Working

Ensure:
1. The script path is absolute
2. The file is readable
3. The JavaScript syntax is valid
4. The script doesn't have runtime errors

Check logs for errors:
```bash
tail -f /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log
```

Or check server logs:
```bash
tail -f logs/playwright-proxy-mcp.log
```

## Best Practices

1. **Don't Over-Stealth**: Only use stealth mode when needed. It adds overhead and may cause issues with some websites.

2. **Test Regularly**: Bot detection evolves constantly. Test your stealth configuration regularly.

3. **Combine Techniques**: Use stealth mode with realistic behavior (delays, mouse movements, etc.)

4. **Respect Rate Limits**: Even with stealth mode, excessive requests will get you blocked.

5. **Use Real User Agents**: Keep user agents up-to-date with current browser versions.

6. **Consider Legal/Ethical Implications**: Ensure your use case complies with website terms of service and applicable laws.

## Performance Impact

Stealth mode has minimal performance impact:
- Script injection: < 10ms per page load
- Memory overhead: < 1MB
- No impact on network requests

## Security Considerations

The stealth script:
- Runs in the page context (has access to page JavaScript)
- Does NOT send data externally
- Does NOT modify user data or cookies
- Only modifies browser API responses

## References

This implementation is inspired by:
- [playwright-stealth](https://github.com/AtuboDad/playwright_stealth) (Python)
- [puppeteer-extra-plugin-stealth](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth) (Node.js)
- Various anti-detection research and techniques

## See Also

- [CUSTOMIZATION.md](CUSTOMIZATION.md) - Full configuration options
- [README](../README.md) - Basic usage and quick start
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
