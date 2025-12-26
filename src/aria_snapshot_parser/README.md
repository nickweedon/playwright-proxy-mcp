# ARIA Snapshot Parser

Python parser for Playwright's ARIA Snapshot YAML format using ANTLR4.

## Overview

This package parses Playwright's ARIA Snapshot format (the accessibility tree representation) into Python data structures and provides JSON serialization capabilities.

## Installation

```bash
# From within the aria_snapshot_parser directory
pip install -e .

# With dev dependencies
pip install -e ".[dev]"
```

## Usage

```python
from aria_snapshot_parser import parse, AriaSnapshotSerializer

# Parse ARIA snapshot YAML
yaml_text = """
- button "Submit" [ref=e1] [cursor=pointer]
- link "Home" [ref=e2]:
  - /url: https://example.com
"""

# Parse the YAML
tree, errors = parse(yaml_text)

if errors:
    for error in errors:
        print(f"Error: {error}")
else:
    # Serialize to JSON
    serializer = AriaSnapshotSerializer()
    json_output = serializer.to_json(tree, indent=2)
    print(json_output)
```

## Architecture

This parser uses a hybrid approach combining:

1. **ruamel.yaml** - For parsing the base YAML structure (handles indentation, lists, dicts)
2. **ANTLR4** - For parsing the custom key syntax: `role "name" [attr1] [attr2=value]`

This mirrors Playwright's own architecture (yaml + KeyParser).

## ARIA Snapshot Format

The ARIA Snapshot format represents the accessibility tree of a web page:

```yaml
- navigation [ref=e1]:
  - link "About" [ref=e2] [cursor=pointer]:
    - /url: https://example.com/about
  - link "Contact" [ref=e3] [cursor=pointer]:
    - /url: https://example.com/contact
- main [ref=e4]:
  - heading "Welcome" [level=1]
  - button "Sign Up" [ref=e5] [cursor=pointer]
```

### Syntax Elements

- **Role**: ARIA role (button, link, heading, etc.)
- **Name**: Accessible name in quotes or as regex `/pattern/`
- **Attributes**: Square bracket notation
  - `[ref=e1]` - Element reference
  - `[cursor=pointer]` - Has pointer cursor
  - `[checked]` - Boolean attribute
  - `[level=2]` - Heading level
  - `[disabled]`, `[expanded]`, `[active]`, `[selected]`, `[pressed]`
- **Properties**: Lines starting with `/`
  - `/url: https://...`
  - `/placeholder: Enter text...`
- **Children**: Nested YAML structure

## Development

### Generate ANTLR Parser

```bash
# Install ANTLR tools
pip install antlr4-tools

# Generate Python parser from grammar
antlr4 -Dlanguage=Python3 -visitor -o src/aria_snapshot_parser/generated grammar/AriaKey.g4
```

### Run Tests

```bash
pytest -v
pytest --cov  # With coverage
```

### Linting and Type Checking

```bash
ruff check src/ tests/
mypy src/
```

## License

MIT
