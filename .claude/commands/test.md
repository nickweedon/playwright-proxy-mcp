---
allowed-tools: Bash(uv:*), Bash(radon:*), Bash(pip:install radon)
description: Run linting, tests, and validate test coverage is proportional to code complexity.
---

## Overview

This command executes the full validation pipeline to ensure code quality and adequate test coverage relative to complexity.

## Steps

1. **Ensure Radon is Installed**
   - Check if radon is available, if not install it: `pip install radon`
   - Radon is used for cyclomatic complexity analysis

2. **Linting**
   - Run `uv run ruff check src/` to check code style and quality
   - If linting fails, stop and report errors to the user

3. **Tests**
   - Run `uv run pytest -v` to execute the test suite
   - If tests fail, stop and report errors to the user
   - Note: Coverage reporting is not currently configured in this project

4. **Cyclomatic Complexity Analysis**
   - Run `radon cc src/playwright_proxy_mcp -a -s` to analyze cyclomatic complexity
     - `-a` shows average complexity
     - `-s` sorts by complexity (highest first)
   - Report the results with clear headers
   - Identify any functions with high complexity (C grade or worse) that may need refactoring

5. **Test Proportionality Check**
   - Calculate total complexity of source code modules
   - Count tests in corresponding test files
   - **Guideline**: For any module with complexity >= 6 (B or less), test count should be >= 80% of complexity score
   - **Reasoning**: Complex code requires more comprehensive testing scenarios
   - Report modules with insufficient testing
     Display in a table with columns: Module, Complexity, Tests, Ratio, Additional Needed
   - Report modules rated B grade or below
   - Highlight areas that need more test coverage

6. **Report Results**
   - Use clear section headers and status indicators
   - Include complexity metrics and test proportionality assessment
   - Include next steps for the user

## Output Format

Structure the output with these sections:

### Test & Verification Status
- ✅/❌ Lint passed
- ✅/❌ Tests passed (include test count and any failures)
- ✅ Complexity analysis completed
- ✅/⚠️ Test proportionality check (show ratio and assessment)

### Complexity Metrics
- **Source Code Complexity**: Show average and total complexity by module
- **Test Code Complexity**: Show average and total complexity by test file
- **High Complexity Functions**: List any functions with C grade or worse
- **Test-to-Complexity Ratio**: Show modules that meet/don't meet the 80% guideline

### Next Steps
- Review high complexity functions and consider refactoring
- Add tests for modules below the 80% test coverage threshold
- Fix any linting or test failures

### Recommendations (if applicable)
- If test proportionality is low, suggest specific modules that need more tests
- If any source functions have high complexity (C or worse), recommend refactoring or additional test coverage

## Error Handling

- If radon is not installed, install it automatically with `pip install radon`
- If linting fails, report the errors and stop (blocking)
- If tests fail, report which tests failed and stop (blocking)
- If complexity analysis fails, show the error but continue (non-blocking)
- Do not proceed to complexity analysis if linting or tests fail

## Implementation Notes

To extract complexity metrics from radon output:
- Use `radon cc -j src/playwright_proxy_mcp` for JSON output to programmatically parse complexity
- Use `radon cc -j tests` for test complexity analysis
- Sum up all complexity values to get total complexity per module
- Count the number of functions/methods to calculate averages
- Match test files to source files (e.g., `test_server.py` → `server.py`)
- Calculate test count per test file and compare to source module complexity

Test proportionality calculation:
- For each source module, find corresponding test file(s)
- Count number of test functions in test file(s)
- Compare test count to module complexity score
- Flag modules where test_count < (complexity * 0.8) and complexity >= 6

Execute these steps and provide clear status reporting.
