# Scripts Directory

This directory contains standalone utility scripts for the Playwright Proxy MCP project.

## Available Scripts

### test.sh

Comprehensive test validation script that runs linting, tests, code duplication detection, and complexity analysis.

**Usage:**
```bash
# Run all checks
./scripts/test.sh

# Skip specific checks
./scripts/test.sh --skip-lint
./scripts/test.sh --skip-tests
./scripts/test.sh --skip-duplication
./scripts/test.sh --skip-complexity

# Continue on errors (get full report)
./scripts/test.sh --continue-on-error

# Combine options
./scripts/test.sh --skip-duplication --skip-complexity

# Get help
./scripts/test.sh --help
```

**What it does:**

1. **Prerequisites Check**: Automatically installs Radon and PMD if missing
2. **Linting**: Runs `uv run ruff check src/` (blocking)
3. **Tests**: Runs `uv run pytest -v` (blocking)
4. **Duplication Detection**: Uses PMD CPD to find duplicated code (non-blocking)
5. **Complexity Analysis**: Uses Radon to analyze cyclomatic complexity (non-blocking)
6. **Test Proportionality**: Validates that complex modules have adequate test coverage (non-blocking)

**Exit Codes:**
- `0` - All checks passed or only non-critical warnings
- `1` - Linting failed
- `2` - Tests failed
- `3` - Script execution error

**Features:**
- Colored output for easy reading
- Optional flags to skip specific checks
- Can be used in CI/CD pipelines
- Can be used in git hooks
- Self-documenting with `--help`

**Integration:**

This script is also available as a Claude command:
```
/test
```

The Claude command will invoke this script directly, making it easy to run both interactively and through automation.

## Adding New Scripts

When adding new utility scripts to this directory:

1. **Follow the pattern** from existing scripts (see `container-test.sh` and `bulk-command-test.sh` in the root directory)
2. **Use bash** with proper error handling (`set -e`)
3. **Add logging functions** for colored output (log_info, log_success, log_error, log_warn)
4. **Include help text** in comments at the top
5. **Make executable**: `chmod +x scripts/your-script.sh`
6. **Document here** in this README
7. **Consider Claude command integration** if appropriate

## Best Practices

- Keep scripts focused on a single purpose
- Use `uv run` prefix for all Python commands
- Provide clear, colored output
- Include help text with `--help` flag
- Return appropriate exit codes
- Handle errors gracefully
- Make scripts self-contained (install prerequisites automatically)
