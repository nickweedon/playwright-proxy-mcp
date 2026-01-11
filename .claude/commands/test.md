---
allowed-tools: Bash(./scripts/test.sh:*), Bash(uv:*), Bash(radon:*), Bash(pmd:*)
description: Run linting, tests, and validate test coverage is proportional to code complexity.
---

## Purpose

Run the comprehensive test validation pipeline and produce an actionable report for code quality improvements.

## Execution

Run the test script with `--continue-on-error` to capture all issues:

```bash
./scripts/test.sh --continue-on-error
```

## Checks Performed

| Check | Tool | Blocking | Action Required |
|-------|------|----------|-----------------|
| **Linting** | `ruff check src/` | ✅ Yes | Fix all linting errors before commit |
| **Type Checking** | `pyright src/playwright_proxy_mcp` | ✅ Yes | Fix all type errors - no exceptions |
| **Tests** | `pytest -v` | ✅ Yes | All tests must pass |
| **Duplication** | PMD CPD (80+ tokens) | ⚠️ No | Review and refactor if in project source |
| **Complexity** | Radon (Grade C+) | ⚠️ No | Consider refactoring high-complexity functions |
| **Proportionality** | Test/complexity ratio | ⚠️ No | Add tests to meet 80% guideline |

## Report Format

After running, produce an **Action Plan** with the following structure:

### 1. Critical Fixes (Must Address)

For each blocking failure, provide:
- **Issue**: Brief description of the failure
- **Location**: File path and line number(s)
- **Fix**: Specific action to resolve

Example:
```
**Issue**: Type error - argument type mismatch
**Location**: src/playwright_proxy_mcp/api/browser.py:45
**Fix**: Change `result: str` to `result: dict[str, Any]` to match return type of `call_tool()`
```

### 2. Recommended Improvements (Should Address)

For non-blocking warnings, provide:
- **Category**: Duplication / Complexity / Test Coverage
- **Location**: File(s) and function(s) affected
- **Recommendation**: Suggested improvement with rationale

Example:
```
**Category**: Complexity
**Location**: src/playwright_proxy_mcp/middleware.py:process_response (Grade C, complexity 12)
**Recommendation**: Extract conditional blocks into helper functions to reduce cyclomatic complexity
```

### 3. Test Coverage Gaps

For modules below 80% test proportionality:
- **Module**: Module name
- **Current**: X tests / Y complexity
- **Needed**: Z additional tests
- **Suggested Tests**: List specific test cases to add

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | All checks passed | None required |
| 1 | Linting or type checking failed | Fix errors immediately |
| 2 | Tests failed | Fix failing tests |
| 3 | Script execution error | Check prerequisites |

## Script Options

```bash
./scripts/test.sh --help              # Show all options
./scripts/test.sh --skip-lint         # Skip linting
./scripts/test.sh --skip-typecheck    # Skip type checking
./scripts/test.sh --skip-tests        # Skip pytest
./scripts/test.sh --skip-duplication  # Skip PMD CPD
./scripts/test.sh --skip-complexity   # Skip Radon analysis
./scripts/test.sh --continue-on-error # Run all checks even if some fail
```

## Important Notes

- **Type Errors**: All pyright type errors must be fixed. Do not ignore or suppress type errors without explicit user approval.
- **Linting**: All ruff errors must be resolved. Use `uv run ruff check --fix src/` for auto-fixable issues.
- **Tests**: Failing tests block the pipeline. Investigate root cause before proceeding.
- **Warnings**: Non-blocking warnings should be addressed in a follow-up session if not immediately actionable.
