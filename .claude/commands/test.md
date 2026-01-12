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
| **Complexity** | Radon | ⚠️ No | Consider refactoring high-complexity functions |
| **Proportionality** | Test/complexity ratio | ⚠️ No | Add tests to meet 80% guideline |

## Report Format

⚠️ **CRITICAL**: The test script **ALWAYS** reports warnings (exit code 0) for non-blocking issues like complexity and test proportionality. **DO NOT** state "All checks passed" or "No issues found" when warnings are present. Always distinguish between:
- **Blocking checks** (must pass): Linting, type checking, tests
- **Non-blocking warnings** (should address): Duplication, complexity, test proportionality

After running, produce an **Action Plan** with the following structure:

### 1. Executive Summary

**ALWAYS start with an honest assessment**:
- If blocking checks failed: State "Critical failures detected - must fix before commit"
- If only warnings present: State "Blocking checks passed, but X warnings require attention"
- Only if truly no issues: State "All checks passed with no warnings"

### 2. Critical Fixes (Must Address)

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

### 3. Recommended Improvements (Should Address)

⚠️ **IMPORTANT**: If the script shows `⚠️` status for Complexity or Proportionality, you **MUST** include this section with details.

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

**Complexity Grading**:
- Grade D-F (complexity 21+): High priority - refactoring strongly recommended
- Grade C (complexity 11-20): Medium priority - consider refactoring and/or add tests
- Grade A-B (complexity 1-10): Low priority - add tests if proportionality is low

### 4. Test Coverage Gaps

⚠️ **IMPORTANT**: If proportionality check shows modules below 80%, you **MUST** include this section.

For modules below 80% test proportionality:
- **Module**: Module name
- **Current**: X tests / Y complexity
- **Needed**: Z additional tests
- **Priority**: Based on complexity grade and current ratio
- **Suggested Tests**: List specific test cases to add

## Exit Codes

⚠️ **IMPORTANT**: Exit code 0 does **NOT** mean "no issues" - it means "no blocking failures". Always check the status symbols in the output.

| Code | Meaning | Action |
|------|---------|--------|
| 0 | No blocking failures (may have ⚠️ warnings) | Check status summary for warnings |
| 1 | Linting or type checking failed | Fix errors immediately |
| 2 | Tests failed | Fix failing tests |
| 3 | Script execution error | Check prerequisites |

**Status Symbol Guide**:
- ✅ = Check passed with no issues
- ⚠️ = Warning present (non-blocking but should address)
- ❌ = Check failed (blocking)
- ⏭️ = Check skipped

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

## Common Mistakes to Avoid

⚠️ **DO NOT**:
1. State "All checks passed" when status shows ⚠️ symbols
2. Ignore complexity warnings just because exit code is 0
3. Skip the "Recommended Improvements" section when warnings are present
4. Assume exit code 0 means no issues

✅ **DO**:
1. Always check the final "Status:" summary for ⚠️ symbols
2. Report ALL warnings (duplication, complexity, proportionality) in your output
3. Distinguish between "blocking checks passed" and "all checks passed with no warnings"
4. Include specific function names and complexity scores when reporting warnings

