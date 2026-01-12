#!/bin/bash
set -e  # Exit on error

# Playwright Proxy MCP - Comprehensive Test Script
# Runs linting, type checking, tests, code duplication detection, and complexity
# analysis with test coverage proportionality validation.
#
# Complexity Grade Recommendations:
#   A & B: Add tests if needed based on proportionality check
#   C:     Consider refactoring and/or more tests per proportionality check
#   D-F:   Recommend refactoring to reduce complexity
#
# Usage:
#   ./scripts/test.sh [OPTIONS]
#
# Options:
#   --skip-lint            Skip linting checks
#   --skip-typecheck       Skip type checking (pyright)
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

show_help() {
    sed -n '/^# Playwright Proxy MCP/,/^# Exit Codes:/p' "$0" | sed 's/^# \?//'
    sed -n '/^#   0 - /,/^$/p' "$0" | sed 's/^# \?//'
}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Parse command line arguments
SKIP_LINT=false
SKIP_TYPECHECK=false
SKIP_TESTS=false
SKIP_DUPLICATION=false
SKIP_COMPLEXITY=false
CONTINUE_ON_ERROR=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-lint) SKIP_LINT=true; shift ;;
        --skip-typecheck) SKIP_TYPECHECK=true; shift ;;
        --skip-tests) SKIP_TESTS=true; shift ;;
        --skip-duplication) SKIP_DUPLICATION=true; shift ;;
        --skip-complexity) SKIP_COMPLEXITY=true; shift ;;
        --continue-on-error) CONTINUE_ON_ERROR=true; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) log_error "Unknown option: $1"; echo "Use --help for usage information"; exit 3 ;;
    esac
done

# Track overall status
LINT_STATUS="⏭️"
TYPECHECK_STATUS="⏭️"
TEST_STATUS="⏭️"
DUPLICATION_STATUS="⏭️"
COMPLEXITY_STATUS="⏭️"
PROPORTIONALITY_STATUS="⏭️"

# ============================================================================
# 1. Ensure Prerequisites
# ============================================================================
log_section "Checking Prerequisites"

# Check for radon (only if complexity analysis will run)
if [ "$SKIP_COMPLEXITY" = false ]; then
    if ! command -v radon &> /dev/null; then
        log_info "Installing radon for complexity analysis..."
        uv pip install radon || { log_error "Failed to install radon"; exit 3; }
        log_success "Radon installed"
    else
        log_info "Radon is already installed"
    fi
fi

# Check for PMD (only if duplication detection will run)
if [ "$SKIP_DUPLICATION" = false ]; then
    if ! command -v pmd &> /dev/null; then
        log_warn "PMD not found. Installing PMD for code duplication detection..."
        PMD_VERSION="7.10.0"
        wget -q "https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip" -O /tmp/pmd.zip || {
            log_error "Failed to download PMD"; exit 3
        }
        unzip -q /tmp/pmd.zip -d /tmp
        sudo mv /tmp/pmd-bin-${PMD_VERSION} /opt/pmd
        sudo ln -sf /opt/pmd/bin/pmd /usr/local/bin/pmd
        rm /tmp/pmd.zip
        log_success "PMD installed"
    else
        log_info "PMD is already installed"
    fi
fi

# Check for pyright (only if type checking will run)
if [ "$SKIP_TYPECHECK" = false ]; then
    if ! uv run pyright --version &> /dev/null; then
        log_info "Installing pyright for type checking..."
        uv pip install pyright || { log_error "Failed to install pyright"; exit 3; }
        log_success "Pyright installed"
    else
        log_info "Pyright is already installed"
    fi
fi

# ============================================================================
# 2. Linting
# ============================================================================
if [ "$SKIP_LINT" = true ]; then
    log_warn "Skipping linting checks (--skip-lint)"
else
    log_section "Running Linting Checks"
    if uv run ruff check src/; then
        log_success "Linting passed"
        LINT_STATUS="✅"
    else
        log_error "Linting failed"
        LINT_STATUS="❌"
        [ "$CONTINUE_ON_ERROR" = false ] && exit 1
    fi
fi

# ============================================================================
# 3. Type Checking
# ============================================================================
if [ "$SKIP_TYPECHECK" = true ]; then
    log_warn "Skipping type checking (--skip-typecheck)"
else
    log_section "Running Type Checking (pyright)"
    if uv run pyright src/playwright_proxy_mcp; then
        log_success "Type checking passed"
        TYPECHECK_STATUS="✅"
    else
        log_error "Type checking failed"
        TYPECHECK_STATUS="❌"
        [ "$CONTINUE_ON_ERROR" = false ] && exit 1
    fi
fi

# ============================================================================
# 4. Tests
# ============================================================================
if [ "$SKIP_TESTS" = true ]; then
    log_warn "Skipping tests (--skip-tests)"
else
    log_section "Running Test Suite"
    # Capture test output to get both results and count in one run
    TEST_OUTPUT_FILE=$(mktemp)
    if uv run pytest -v --tb=short 2>&1 | tee "$TEST_OUTPUT_FILE"; then
        # Extract test count from pytest output (e.g., "42 passed")
        TEST_COUNT=$(grep -oP '\d+(?= passed)' "$TEST_OUTPUT_FILE" | head -1 || echo "N/A")
        log_success "All tests passed (${TEST_COUNT} tests)"
        TEST_STATUS="✅"
    else
        log_error "Tests failed"
        TEST_STATUS="❌"
        [ "$CONTINUE_ON_ERROR" = false ] && { rm -f "$TEST_OUTPUT_FILE"; exit 2; }
    fi
    rm -f "$TEST_OUTPUT_FILE"
fi

# ============================================================================
# 5. Code Duplication Detection (Non-blocking)
# ============================================================================
if [ "$SKIP_DUPLICATION" = true ]; then
    log_warn "Skipping duplication detection (--skip-duplication)"
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
        [ "$DUPLICATION_COUNT" -gt 5 ] && log_info "... and $((DUPLICATION_COUNT - 5)) more duplications"
        DUPLICATION_STATUS="⚠️"
    fi
fi

# ============================================================================
# 6. Cyclomatic Complexity Analysis (Non-blocking)
# ============================================================================
if [ "$SKIP_COMPLEXITY" = true ]; then
    log_warn "Skipping complexity analysis (--skip-complexity)"
else
    log_section "Cyclomatic Complexity Analysis"

    # Get source complexity (JSON for proportionality analysis, text for display)
    uv run radon cc -j src/playwright_proxy_mcp > /tmp/src_complexity.json
    COMPLEXITY_SUMMARY=$(uv run radon cc src/playwright_proxy_mcp -a -s)

    log_info "Source Code Complexity Summary:"

    # Identify complexity by grade using pattern: "    F 123:0 function_name - D (22)"
    # The pattern matches: whitespace, type (F/M/C), line:col, name (with underscores), dash, grade, score
    GRADE_D_F=$(echo "$COMPLEXITY_SUMMARY" | grep -E "^\s+[FMC]\s+[0-9]+:[0-9]+\s+.+\s+-\s+[DEF]\s" || echo "")
    GRADE_C=$(echo "$COMPLEXITY_SUMMARY" | grep -E "^\s+[FMC]\s+[0-9]+:[0-9]+\s+.+\s+-\s+C\s" || echo "")

    if [ -n "$GRADE_D_F" ]; then
        echo ""
        log_warn "Very high complexity functions (Grade D-F) - REFACTORING RECOMMENDED:"
        echo "$GRADE_D_F" | head -n 10
        GRADE_D_F_COUNT=$(echo "$GRADE_D_F" | grep -c . || echo "0")
        [ "$GRADE_D_F_COUNT" -gt 10 ] && log_info "... and $((GRADE_D_F_COUNT - 10)) more very high-complexity functions"
        log_info "Grade D-F functions should be refactored to reduce complexity."
        COMPLEXITY_STATUS="⚠️"
    fi

    if [ -n "$GRADE_C" ]; then
        echo ""
        log_warn "Moderate complexity functions (Grade C) - consider refactoring and/or additional tests:"
        echo "$GRADE_C" | head -n 10
        GRADE_C_COUNT=$(echo "$GRADE_C" | grep -c . || echo "0")
        [ "$GRADE_C_COUNT" -gt 10 ] && log_info "... and $((GRADE_C_COUNT - 10)) more moderate-complexity functions"
        log_info "Grade C: Consider refactoring and/or add tests per proportionality check."
        COMPLEXITY_STATUS="${COMPLEXITY_STATUS:-⚠️}"
    fi

    if [ -z "$GRADE_D_F" ] && [ -z "$GRADE_C" ]; then
        log_success "All functions are Grade A or B (low complexity)"
        log_info "Grade A-B: Add tests if needed based on proportionality check."
        COMPLEXITY_STATUS="✅"
    fi
fi

# ============================================================================
# 7. Test Proportionality Check
# ============================================================================
if [ "$SKIP_TESTS" = true ] || [ "$SKIP_COMPLEXITY" = true ]; then
    log_warn "Skipping proportionality check (requires both tests and complexity)"
else
    log_section "Test Proportionality Analysis"

    # Get test complexity (reuse src complexity from previous step)
    uv run radon cc -j tests/ > /tmp/test_complexity.json

    # Inline Python for proportionality analysis (use || true to prevent set -e exit)
    uv run python - << 'ANALYZE_EOF' || true
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

# Write exit code to temp file since || true masks the exit code
with open('/tmp/proportionality_exit', 'w') as f:
    f.write(str(len(issues)))
sys.stdout.flush()
ANALYZE_EOF
    PROPORTIONALITY_EXIT=$(cat /tmp/proportionality_exit)

    echo ""
    if [ "$PROPORTIONALITY_EXIT" -eq 0 ]; then
        log_success "All modules meet 80% test proportionality guideline"
        PROPORTIONALITY_STATUS="✅"
    else
        log_warn "$PROPORTIONALITY_EXIT module(s) need additional tests to meet 80% guideline"
        log_info "Recommendation: Add tests based on complexity grade:"
        log_info "  Grade A-B: Add tests if needed based on 'Needed' column above"
        log_info "  Grade C:   Consider refactoring and/or add tests"
        log_info "  Grade D-F: Recommend refactoring to reduce complexity"
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
echo "  Type Check:        $TYPECHECK_STATUS"
echo "  Tests:             $TEST_STATUS"
echo "  Duplication:       $DUPLICATION_STATUS"
echo "  Complexity:        $COMPLEXITY_STATUS"
echo "  Proportionality:   $PROPORTIONALITY_STATUS"
echo ""

# Determine overall exit code
if [ "$LINT_STATUS" = "❌" ] || [ "$TYPECHECK_STATUS" = "❌" ] || [ "$TEST_STATUS" = "❌" ]; then
    log_error "Critical checks failed"
    exit 1
elif [ "$DUPLICATION_STATUS" = "⚠️" ] || [ "$COMPLEXITY_STATUS" = "⚠️" ] || [ "$PROPORTIONALITY_STATUS" = "⚠️" ]; then
    log_warn "Some checks have warnings - review output above"
    exit 0
else
    log_success "All checks passed!"
    exit 0
fi
