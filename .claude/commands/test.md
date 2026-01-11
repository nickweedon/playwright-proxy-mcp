---
allowed-tools: Bash(./scripts/test.sh:*), Bash(uv:*), Bash(radon:*), Bash(pmd:*)
description: Run linting, tests, and validate test coverage is proportional to code complexity.
---

## Overview

This command runs the comprehensive test validation pipeline including linting, tests, code duplication detection, and complexity analysis with test coverage proportionality validation.

## Usage

The test suite is implemented as a standalone script for easy execution:

```bash
# Run all checks
./scripts/test.sh

# Skip specific checks
./scripts/test.sh --skip-duplication
./scripts/test.sh --skip-complexity

# Continue on errors (run all checks even if some fail)
./scripts/test.sh --continue-on-error

# Get help
./scripts/test.sh --help
```

## Execution

When run via this Claude command, all checks are executed with default settings (exit on critical failures).

The script will be invoked directly: `./scripts/test.sh`

## Output

The script provides a comprehensive report including:

### Test & Verification Status
- ✅/❌ Lint passed/failed
- ✅/❌ Tests passed/failed (with count)
- ✅/⚠️ Duplication check (non-blocking warnings)
- ✅/⚠️ Complexity analysis (non-blocking warnings)
- ✅/⚠️ Test proportionality check (80% guideline)

### Detailed Results
- Code duplication blocks (if found)
- High complexity functions (Grade C or worse)
- Modules needing additional test coverage
- Test-to-complexity ratios

## Implementation Details

The script performs these steps:

1. **Prerequisites**: Installs Radon and PMD if missing
2. **Linting**: `uv run ruff check src/` (blocking)
3. **Tests**: `uv run pytest -v` (blocking)
4. **Duplication**: PMD CPD with 80+ token threshold (non-blocking)
5. **Complexity**: Radon cyclomatic complexity analysis (non-blocking)
6. **Proportionality**: Validates 80% test coverage guideline for complex modules (non-blocking)

## Exit Codes

- **0**: All checks passed or non-critical warnings only
- **1**: Linting failed
- **2**: Tests failed
- **3**: Script execution error

## Manual Execution

The script can be run directly outside of Claude:

```bash
cd /workspace
./scripts/test.sh
```

This makes it easy to integrate into CI/CD pipelines, git hooks, or manual testing workflows.

## Advanced Options

```bash
# Skip linting (useful if already linted)
./scripts/test.sh --skip-lint

# Skip tests (useful for quick complexity check)
./scripts/test.sh --skip-tests

# Skip duplication detection (faster execution)
./scripts/test.sh --skip-duplication

# Skip complexity analysis
./scripts/test.sh --skip-complexity

# Run everything even if some checks fail
./scripts/test.sh --continue-on-error

# Combine options
./scripts/test.sh --skip-duplication --skip-complexity
```
