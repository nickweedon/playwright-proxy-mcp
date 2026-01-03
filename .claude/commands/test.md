---
allowed-tools: Bash(uv:*), Bash(radon:*), Bash(pmd:*), Bash(pip:install radon)
description: Run linting, tests, and validate test coverage is proportional to code complexity.
---

## Overview

This command executes the full validation pipeline to ensure code quality and adequate test coverage relative to complexity.

## Steps

1. **Ensure Radon is Installed**
   - Check if radon is available, if not install it: `uv pip install radon`
   - Radon is used for cyclomatic complexity analysis

2. **Ensure PMD is Installed**
   - Check if PMD is available in PATH
   - If not installed, install it automatically:
     ```bash
     # Download latest PMD release
     PMD_VERSION="7.10.0"
     wget "https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip" -O /tmp/pmd.zip
     unzip -q /tmp/pmd.zip -d /tmp
     sudo mv /tmp/pmd-bin-${PMD_VERSION} /opt/pmd
     sudo ln -sf /opt/pmd/bin/pmd /usr/local/bin/pmd
     rm /tmp/pmd.zip
     ```
   - PMD is used for code duplication detection

3. **Linting**
   - Run `uv run ruff check src/` to check code style and quality
   - If linting fails, stop and report errors to the user

4. **Tests**
   - Run `uv run pytest -v` to execute the test suite
   - If tests fail, stop and report errors to the user
   - Note: Coverage reporting is not currently configured in this project

5. **Code Duplication Detection**
   - Run PMD CPD to detect duplicated code blocks:
     ```bash
     pmd cpd \
       --language python \
       --minimum-tokens 80 \
       --ignore-literals \
       --ignore-identifiers \
       --ignore-annotations \
       --skip-duplicate-files \
       --exclude "**/.venv/**,**/venv/**,**/__pycache__/**,**/.git/**,**/build/**,**/dist/**,**/.mypy_cache/**,**/.pytest_cache/**,**/.tox/**" \
       --dir "src" \
       --fail-on-violation
     ```
   - `--minimum-tokens 80`: Flag duplicated blocks of 80+ tokens (adjust if needed)
   - `--ignore-literals`: Ignore literal values when comparing code
   - `--ignore-identifiers`: Ignore identifier names when comparing code
   - If duplications are found, report them but continue (non-blocking)
   - Duplicated code should be refactored into shared functions or utilities

6. **Cyclomatic Complexity Analysis**
   - Run `uv run radon cc src/playwright_proxy_mcp -a -s` to analyze cyclomatic complexity
     - `-a` shows average complexity
     - `-s` sorts by complexity (highest first)
   - Report the results with clear headers
   - Identify any functions with high complexity (C grade or worse) that may need refactoring

7. **Test Proportionality Check**
   - Calculate total complexity of source code modules
   - Count tests in corresponding test files
   - **Guideline**: For any module with complexity >= 6 (B or less), test count should be >= 80% of complexity score
   - **Reasoning**: Complex code requires more comprehensive testing scenarios
   - Report modules with insufficient testing
     Display in a table with columns: Module, Complexity, Tests, Ratio, Additional Needed
   - Report modules rated B grade or below
   - Highlight areas that need more test coverage

8. **Report Results**
   - Use clear section headers and status indicators
   - Include duplication detection results
   - Include complexity metrics and test proportionality assessment
   - Include next steps for the user

## Output Format

Structure the output with these sections:

### Test & Verification Status
- ✅/❌ Lint passed
- ✅/❌ Tests passed (include test count and any failures)
- ✅/⚠️ Duplication check (show number of duplications found)
- ✅ Complexity analysis completed
- ✅/⚠️ Test proportionality check (show ratio and assessment)

### Code Duplication
- **Duplicate Blocks Found**: Show count and locations of duplicated code
- **Duplication Details**: List file paths and line ranges for each duplication
- **Refactoring Opportunities**: Suggest where duplicated code should be extracted

### Complexity Metrics
- **Source Code Complexity**: Show average and total complexity by module
- **Test Code Complexity**: Show average and total complexity by test file
- **High Complexity Functions**: List any functions with C grade or worse
- **Test-to-Complexity Ratio**: Show modules that meet/don't meet the 80% guideline

### Next Steps
- Refactor duplicated code into shared utilities or functions
- Review high complexity functions and consider refactoring
- Add tests for modules below the 80% test coverage threshold
- Fix any linting or test failures

### Recommendations (if applicable)
- If duplications are found, suggest specific refactoring to eliminate them
- If test proportionality is low, suggest specific modules that need more tests
- If any source functions have high complexity (C or worse), recommend refactoring or additional test coverage

## Error Handling

- If radon is not installed, install it automatically with `uv pip install radon`
- If PMD is not installed or not in PATH, install it automatically using the installation steps above
- If linting fails, report the errors and stop (blocking)
- If tests fail, report which tests failed and stop (blocking)
- If duplication check fails, show the error but continue (non-blocking)
- If complexity analysis fails, show the error but continue (non-blocking)
- Do not proceed to duplication check or complexity analysis if linting or tests fail

## Implementation Notes

To extract complexity metrics from radon output:
- Use `uv run radon cc -j src/playwright_proxy_mcp` for JSON output to programmatically parse complexity
- Use `uv run radon cc -j tests` for test complexity analysis
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
