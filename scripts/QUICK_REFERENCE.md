# Test Script Quick Reference

## TL;DR

```bash
# Run everything
./scripts/test.sh

# Skip slow checks
./scripts/test.sh --skip-duplication --skip-complexity

# Get help
./scripts/test.sh --help
```

## Common Use Cases

### 1. Pre-Commit Check (Fast)
```bash
./scripts/test.sh --skip-duplication --skip-complexity
```
Runs: Lint + Tests only (~10-30 seconds)

### 2. Full Validation (Comprehensive)
```bash
./scripts/test.sh
```
Runs: Everything (~1-2 minutes)

### 3. Code Quality Check (No Tests)
```bash
./scripts/test.sh --skip-tests
```
Runs: Lint + Duplication + Complexity

### 4. Test Only (No Analysis)
```bash
./scripts/test.sh --skip-lint --skip-duplication --skip-complexity
```
Runs: Tests only

### 5. Get Full Report (Don't Stop on Errors)
```bash
./scripts/test.sh --continue-on-error
```
Runs: Everything, shows all issues

## Options at a Glance

| Option | Effect |
|--------|--------|
| `--skip-lint` | Skip linting (ruff) |
| `--skip-tests` | Skip pytest |
| `--skip-duplication` | Skip PMD duplication check |
| `--skip-complexity` | Skip Radon complexity analysis |
| `--continue-on-error` | Don't stop on failures |
| `-h` or `--help` | Show help |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (or warnings only) |
| 1 | Linting failed |
| 2 | Tests failed |
| 3 | Script error |

## Integration Examples

### GitHub Actions
```yaml
- name: Validate code
  run: ./scripts/test.sh
```

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
./scripts/test.sh --skip-duplication --skip-complexity
```

### Claude Command
```
/test
```

## Status Indicators

- ✅ Check passed
- ❌ Check failed (critical)
- ⚠️ Check has warnings (non-critical)
- ⏭️ Check skipped

## What Gets Checked

1. **Lint** (blocking): Code style via ruff
2. **Tests** (blocking): Test suite via pytest
3. **Duplication** (warning): Code duplicates via PMD
4. **Complexity** (warning): Cyclomatic complexity via Radon
5. **Proportionality** (warning): Test coverage vs complexity ratio

## Performance Tips

- Use `--skip-duplication` for faster runs (saves ~10-20 seconds)
- Use `--skip-complexity` for faster runs (saves ~5-10 seconds)
- Both duplication and complexity are non-blocking (warnings only)
- Linting and tests are fast and critical (always run them)
