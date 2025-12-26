"""Basic usage example for aria-snapshot-parser."""

from aria_snapshot_parser import AriaSnapshotSerializer, parse

# Example ARIA snapshot YAML
yaml_text = """
- navigation:
  - link "Home" [ref=e1] [cursor=pointer]:
    - /url: https://example.com
  - link "About" [ref=e2] [cursor=pointer]:
    - /url: https://example.com/about
- main:
  - heading "Welcome" [level=1]
  - button "Sign Up" [ref=e3] [cursor=pointer]
  - textbox "Email" [ref=e4]
"""

# Parse the YAML
tree, errors = parse(yaml_text)

if errors:
    print("Parsing errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Parsing successful!")
    print(f"Found {len(tree)} root nodes")

    # Serialize to JSON
    serializer = AriaSnapshotSerializer()
    json_output = serializer.to_json(tree, indent=2)

    print("\nJSON output:")
    print(json_output)
