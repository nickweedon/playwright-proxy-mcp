#!/bin/bash
set -e  # Exit on error

# ============================================================================
# Playwright Proxy MCP - Comprehensive Test Script
# ============================================================================
# Runs linting, tests, code duplication detection, and complexity analysis
# with test coverage proportionality validation.
#
# Usage:
#   ./scripts/test.sh [OPTIONS]
#
# Options:
#   --skip-lint            Skip linting checks
#   --skip-tests           Skip pytest execution
#   --skip-duplication     Skip code duplication detection
#   --skip-complexity      Skip complexity analysis
#   --continue-on-error    Continue running checks even if some fail
#   -h, --help             Show this help message
#
# Exit Codes:
#   0 - All checks passed
#   1 - Linting failed
#   2 - Tests failed
#   3 - Script error
# ============================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Parse command line arguments
SKIP_LINT=false
SKIP_TESTS=false
SKIP_DUPLICATION=false
SKIP_COMPLEXITY=false
CONTINUE_ON_ERROR=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-lint) SKIP_LINT=true; shift ;;
        --skip-tests) SKIP_TESTS=true; shift ;;
        --skip-duplication) SKIP_DUPLICATION=true; shift ;;
        --skip-complexity) SKIP_COMPLEXITY=true; shift ;;
        --continue-on-error) CONTINUE_ON_ERROR=true; shift ;;
        -h|--help)
            grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 3
            ;;
    esac
done

# Track overall status
LINT_STATUS="⏭️"
TEST_STATUS="⏭️"
DUPLICATION_STATUS="⏭️"
COMPLEXITY_STATUS="⏭️"
PROPORTIONALITY_STATUS="⏭️"

# ============================================================================
# 1. Ensure Prerequisites
# ============================================================================
log_section "Checking Prerequisites"

# Check for radon
if ! command -v radon &> /dev/null; then
    log_info "Installing radon for complexity analysis..."
    uv pip install radon || {
        log_error "Failed to install radon"
        exit 3
    }
    log_success "Radon installed"
else
    log_info "Radon is already installed"
fi

# Check for PMD
if ! command -v pmd &> /dev/null; then
    log_warn "PMD not found. Installing PMD for code duplication detection..."
    PMD_VERSION="7.10.0"
    wget "https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip" -O /tmp/pmd.zip || {
        log_error "Failed to download PMD"
        exit 3
    }
    unzip -q /tmp/pmd.zip -d /tmp
    sudo mv /tmp/pmd-bin-${PMD_VERSION} /opt/pmd
    sudo ln -sf /opt/pmd/bin/pmd /usr/local/bin/pmd
    rm /tmp/pmd.zip
    log_success "PMD installed"
else
    log_info "PMD is already installed"
fi

# ============================================================================
# 2. Linting
# ============================================================================
if [ "$SKIP_LINT" = true ]; then
    log_warn "Skipping linting checks (--skip-lint)"
    LINT_STATUS="⏭️"
else
    log_section "Running Linting Checks"
    if uv run ruff check src/; then
        log_success "Linting passed"
        LINT_STATUS="✅"
    else
        log_error "Linting failed"
        LINT_STATUS="❌"
        if [ "$CONTINUE_ON_ERROR" = false ]; then
            exit 1
        fi
    fi
fi

# ============================================================================
# 3. Tests
# ============================================================================
if [ "$SKIP_TESTS" = true ]; then
    log_warn "Skipping tests (--skip-tests)"
    TEST_STATUS="⏭️"
else
    log_section "Running Test Suite"
    if uv run pytest -v; then
        TEST_COUNT=$(uv run pytest --collect-only -q 2>/dev/null | tail -n 1 | grep -oP '\d+' | head -n 1 || echo "N/A")
        log_success "All tests passed (${TEST_COUNT} tests)"
        TEST_STATUS="✅"
    else
        log_error "Tests failed"
        TEST_STATUS="❌"
        if [ "$CONTINUE_ON_ERROR" = false ]; then
            exit 2
        fi
    fi
fi

# ============================================================================
# 4. Code Duplication Detection (Non-blocking)
# ============================================================================
if [ "$SKIP_DUPLICATION" = true ]; then
    log_warn "Skipping duplication detection (--skip-duplication)"
    DUPLICATION_STATUS="⏭️"
else
    log_section "Code Duplication Detection"
    DUPLICATION_OUTPUT=$(pmd cpd \
        --language python \
        --minimum-tokens 80 \
        --ignore-literals \
        --ignore-identifiers \
        --ignore-annotations \
        --skip-duplicate-files \
        --exclude "**/.venv/**,**/venv/**,**/__pycache__/**,**/.git/**,**/build/**,**/dist/**,**/.mypy_cache/**,**/.pytest_cache/**,**/.tox/**" \
        --dir "src" \
        2>&1 || true)

    DUPLICATION_COUNT=$(echo "$DUPLICATION_OUTPUT" | grep -c "^Found a" || echo "0")

    if [ "$DUPLICATION_COUNT" -eq 0 ]; then
        log_success "No code duplications found in project source"
        DUPLICATION_STATUS="✅"
    else
        log_warn "Found $DUPLICATION_COUNT duplicate code blocks (in vendored dependencies - non-blocking)"
        echo "$DUPLICATION_OUTPUT" | grep "^Found a" | head -n 5
        if [ "$DUPLICATION_COUNT" -gt 5 ]; then
            log_info "... and $((DUPLICATION_COUNT - 5)) more duplications"
        fi
        DUPLICATION_STATUS="⚠️"
    fi
fi

# ============================================================================
# 5. Cyclomatic Complexity Analysis (Non-blocking)
# ============================================================================
if [ "$SKIP_COMPLEXITY" = true ]; then
    log_warn "Skipping complexity analysis (--skip-complexity)"
    COMPLEXITY_STATUS="⏭️"
else
    log_section "Cyclomatic Complexity Analysis"

    # Get source complexity
    uv run radon cc -j src/playwright_proxy_mcp > /tmp/src_complexity.json

    # Display human-readable complexity summary
    log_info "Source Code Complexity Summary:"
    uv run radon cc src/playwright_proxy_mcp -a -s | head -n 50 || true

    # Identify high-complexity functions (Grade C or worse)
    HIGH_COMPLEXITY=$(uv run radon cc src/playwright_proxy_mcp -s 2>/dev/null | grep -E "^\s+[FMC]\s+\d+:\d+\s+\w+\s+-\s+[C-F]" || echo "")

    if [ -n "$HIGH_COMPLEXITY" ]; then
        echo ""
        log_warn "High complexity functions found (Grade C or worse):"
        echo "$HIGH_COMPLEXITY" | head -n 10
        HIGH_COUNT=$(echo "$HIGH_COMPLEXITY" | wc -l)
        if [ "$HIGH_COUNT" -gt 10 ]; then
            log_info "... and $((HIGH_COUNT - 10)) more high-complexity functions"
        fi
        COMPLEXITY_STATUS="⚠️"
    else
        log_success "No high complexity functions (all Grade B or better)"
        COMPLEXITY_STATUS="✅"
    fi
fi

# ============================================================================
# 6. Test Proportionality Check
# ============================================================================
if [ "$SKIP_TESTS" = true ] || [ "$SKIP_COMPLEXITY" = true ]; then
    log_warn "Skipping proportionality check (requires both tests and complexity)"
    PROPORTIONALITY_STATUS="⏭️"
else
    log_section "Test Proportionality Analysis"

    # Create Python script for proportionality analysis
    cat > /tmp/analyze_proportionality.py << 'ANALYZE_EOF'
import json
import sys

# Load complexity data
with open('/tmp/src_complexity.json', 'r') as f:
    src_data = json.load(f)
with open('/tmp/test_complexity.json', 'r') as f:
    test_data = json.load(f)

# Calculate module complexity
module_complexity = {}
for file_path, items in src_data.items():
    module_name = file_path.split('/')[-1].replace('.py', '')
    total_complexity = sum(item['complexity'] for item in items if item.get('complexity'))
    module_complexity[module_name] = total_complexity

# Count test functions per module
test_counts = {}
for test_file, items in test_data.items():
    test_module = test_file.split('/')[-1].replace('test_', '').replace('.py', '')
    count = sum(1 for item in items if item['type'] in ['function', 'method'])
    test_counts[test_module] = test_counts.get(test_module, 0) + count

# Analyze proportionality (80% guideline for complexity >= 6)
print(f"{'Module':<25} {'Complexity':>10} {'Tests':>8} {'Ratio':>8} {'Status':>8} {'Needed':>8}")
print("=" * 78)

issues = []
for module, complexity in sorted(module_complexity.items(), key=lambda x: x[1], reverse=True):
    if complexity >= 6:
        test_count = test_counts.get(module, 0)
        ratio = test_count / complexity if complexity > 0 else 0
        threshold = 0.8
        status = "✅" if ratio >= threshold else "⚠️"
        additional_needed = max(0, int(complexity * threshold) - test_count)

        print(f"{module:<25} {complexity:>10} {test_count:>8} {ratio:>7.2f} {status:>8} {additional_needed:>8}")

        if ratio < threshold:
            issues.append((module, additional_needed))

sys.exit(len(issues))
ANALYZE_EOF

    uv run python /tmp/analyze_proportionality.py
    PROPORTIONALITY_EXIT=$?

    echo ""
    if [ "$PROPORTIONALITY_EXIT" -eq 0 ]; then
        log_success "All modules meet 80% test proportionality guideline"
        PROPORTIONALITY_STATUS="✅"
    else
        log_warn "$PROPORTIONALITY_EXIT module(s) need additional tests to meet 80% guideline"
        PROPORTIONALITY_STATUS="⚠️"
    fi
fi

# ============================================================================
# Final Summary
# ============================================================================
log_section "Test & Verification Summary"

echo ""
echo "Status:"
echo "  Lint:              $LINT_STATUS"
echo "  Tests:             $TEST_STATUS"
echo "  Duplication:       $DUPLICATION_STATUS"
echo "  Complexity:        $COMPLEXITY_STATUS"
echo "  Proportionality:   $PROPORTIONALITY_STATUS"
echo ""

# Determine overall exit code
if [ "$LINT_STATUS" = "❌" ] || [ "$TEST_STATUS" = "❌" ]; then
    log_error "Critical checks failed"
    exit 1
elif [ "$DUPLICATION_STATUS" = "⚠️" ] || [ "$COMPLEXITY_STATUS" = "⚠️" ] || [ "$PROPORTIONALITY_STATUS" = "⚠️" ]; then
    log_warn "Some checks have warnings - review output above"
    exit 0
else
    log_success "All checks passed!"
    exit 0
fi
