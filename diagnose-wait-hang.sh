#!/bin/bash
# Comprehensive diagnostic script for browser_wait_for hang issue
# Based on playwright-mcp issues #141 and #982

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_note() { echo -e "${CYAN}[NOTE]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

IMAGE_NAME="playwright-proxy-mcp:latest"
ENV_FILE="container-test.env"

# Check prerequisites
if ! command -v mcptools &> /dev/null; then
    log_error "mcptools not found"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file $ENV_FILE not found"
    exit 1
fi

echo "========================================================================"
echo "  PLAYWRIGHT-MCP browser_wait_for HANG DIAGNOSTIC"
echo "========================================================================"
echo
log_info "This script diagnoses the hang issue with browser_wait_for"
log_note "Known upstream issues:"
log_note "  - Issue #141: MCP server hangs when browser_wait called before close"
log_note "  - Issue #982: 5-second MCP ping timeout kills long operations"
echo

# Test 1: Minimal bulk execution (should work - all in one session)
log_info "Test 1: Minimal bulk with wait_for (navigate + wait)"
echo "Command: navigate example.com → wait 3 seconds"

BULK_CMD_1='{"commands": [{"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": true}}, {"tool": "browser_wait_for", "args": {"time": 3}}], "stop_on_error": true}'

echo "Executing with 30-second timeout..."
if timeout 30s mcptools call browser_execute_bulk --params "$BULK_CMD_1" \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 | tee /tmp/test1.txt; then
    if grep -q '"success":true' /tmp/test1.txt; then
        log_success "Test 1 PASSED - wait_for works in bulk execution"
    else
        log_error "Test 1 FAILED - command executed but reported error"
        echo "Response:"
        cat /tmp/test1.txt | jq -C '.content[0].text' 2>/dev/null || cat /tmp/test1.txt | head -50
    fi
else
    log_error "Test 1 HUNG - browser_wait_for hangs even in bulk execution!"
    echo "This indicates an upstream playwright-mcp issue (see #141, #982)"
fi
echo

# Test 2: Amazon bulk command (the original failing case)
log_info "Test 2: Amazon bulk command (navigate + wait + snapshot)"
echo "Command: navigate amazon → wait 3 seconds → snapshot (200 items, flattened)"

AMAZON_CMD='{"commands": [{"tool": "browser_navigate", "args": {"url": "https://www.amazon.com/s?k=gloves", "silent_mode": true}}, {"tool": "browser_wait_for", "args": {"time": 3}}, {"tool": "browser_snapshot", "args": {"flatten": true, "limit": 200, "output_format": "json"}, "return_result": true}], "stop_on_error": true}'

echo "Executing with 120-second timeout (Amazon may be slow)..."
if timeout 120s mcptools call browser_execute_bulk --params "$AMAZON_CMD" \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 | tee /tmp/test2.txt; then
    if grep -q '"success":true' /tmp/test2.txt; then
        log_success "Test 2 PASSED - Amazon bulk command succeeded"
        echo "Response summary:"
        cat /tmp/test2.txt | jq -C '.content[0].text | fromjson | {success, executed_count, total_count, has_errors: (.errors | map(select(. != null)) | length > 0)}' 2>/dev/null || echo "(could not parse)"
    else
        log_error "Test 2 FAILED - command executed but reported error"
        echo "Response:"
        cat /tmp/test2.txt | jq -C '.content[0].text' 2>/dev/null | head -100 || cat /tmp/test2.txt | head -50
    fi
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        log_error "Test 2 TIMEOUT - Command exceeded 120 seconds"
        echo "Likely causes:"
        echo "  1. MCP ping timeout (5s hardcoded in upstream, see #982)"
        echo "  2. browser_wait_for hang issue (see #141)"
        echo "  3. Amazon blocking automated access"
        echo
        log_note "Try Test 3 to isolate the wait_for issue"
    else
        log_error "Test 2 FAILED - Command failed with exit code $EXIT_CODE"
    fi
fi
echo

# Test 3: Amazon without wait_for (isolate the hang)
log_info "Test 3: Amazon WITHOUT wait_for (navigate + snapshot only)"
echo "Command: navigate amazon → snapshot (no wait)"

NO_WAIT_CMD='{"commands": [{"tool": "browser_navigate", "args": {"url": "https://www.amazon.com/s?k=gloves", "silent_mode": true}}, {"tool": "browser_snapshot", "args": {"flatten": true, "limit": 200, "output_format": "json"}, "return_result": true}], "stop_on_error": true}'

echo "Executing with 90-second timeout..."
if timeout 90s mcptools call browser_execute_bulk --params "$NO_WAIT_CMD" \
  docker run --rm -i --env-file "$ENV_FILE" "$IMAGE_NAME" uv run playwright-proxy-mcp 2>&1 | tee /tmp/test3.txt; then
    if grep -q '"success":true' /tmp/test3.txt; then
        log_success "Test 3 PASSED - Amazon works WITHOUT wait_for"
        echo
        log_warn "DIAGNOSIS: browser_wait_for is the culprit!"
        echo "  → Test 2 (with wait_for) hung/failed"
        echo "  → Test 3 (without wait_for) succeeded"
        echo
        echo "RECOMMENDED SOLUTIONS:"
        echo "  1. Remove unnecessary browser_wait_for calls from bulk commands"
        echo "  2. Use implicit waits via Playwright's built-in selectors"
        echo "  3. Increase MCP ping timeout (if #982 gets fixed upstream)"
        echo "  4. Use browser_wait_for only when absolutely necessary"
    else
        log_error "Test 3 FAILED - Amazon fails even without wait_for"
        echo "This suggests Amazon blocking or network issue, not wait_for"
    fi
else
    log_error "Test 3 TIMEOUT - Amazon navigation itself is hanging"
    echo "This suggests Amazon is blocking automated access or network issue"
fi
echo

echo "========================================================================"
echo "  DIAGNOSTIC SUMMARY"
echo "========================================================================"
echo
echo "Results:"
[ -f /tmp/test1.txt ] && grep -q '"success":true' /tmp/test1.txt && echo "  ✓ Test 1: PASSED (wait_for works in simple case)" || echo "  ✗ Test 1: FAILED/HUNG"
[ -f /tmp/test2.txt ] && grep -q '"success":true' /tmp/test2.txt && echo "  ✓ Test 2: PASSED (Amazon with wait_for)" || echo "  ✗ Test 2: FAILED/HUNG"
[ -f /tmp/test3.txt ] && grep -q '"success":true' /tmp/test3.txt && echo "  ✓ Test 3: PASSED (Amazon without wait_for)" || echo "  ✗ Test 3: FAILED/HUNG"
echo
echo "Upstream Issues:"
echo "  - https://github.com/microsoft/playwright-mcp/issues/141 (wait hang)"
echo "  - https://github.com/microsoft/playwright-mcp/issues/982 (ping timeout)"
echo
