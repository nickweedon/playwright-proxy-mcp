"""ARIA Snapshot parser combining YAML and ANTLR."""

from typing import Any

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from ruamel.yaml import YAML

from .exceptions import ParseError as ParseErrorException
from .exceptions import ValidationError
from .generated.AriaKeyLexer import AriaKeyLexer
from .generated.AriaKeyParser import AriaKeyParser
from .generated.AriaKeyVisitor import AriaKeyVisitor
from .types import AriaTemplateNode, AriaTextValue, ParseError
from .utils import (
    normalize_text,
    parse_boolean,
    parse_mixed_boolean,
    unescape_string,
    validate_level,
)


class AriaSnapshotErrorListener(ErrorListener):
    """Custom error listener for ANTLR parser."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[ParseError] = []

    def syntaxError(
        self, recognizer: Any, offendingSymbol: Any, line: int, column: int, msg: str, e: Any
    ) -> None:
        """Called when a syntax error is encountered."""
        error_msg = msg
        if offendingSymbol:
            error_msg = f"{msg} near '{offendingSymbol.text}'"

        self.errors.append(
            ParseError(
                message=error_msg,
                line=line,
                column=column,
            )
        )


class AriaKeyNodeBuilder(AriaKeyVisitor):
    """Visitor to build AriaTemplateNode from ANTLR parse tree."""

    def __init__(self) -> None:
        self.errors: list[ParseError] = []

    def visitKey(self, ctx: Any) -> dict[str, Any]:
        """Visit key rule: role name? attributes?"""
        result: dict[str, Any] = {}

        # Get role (required)
        if ctx.role():
            result["role"] = self.visit(ctx.role())

        # Get name (optional)
        if ctx.name():
            result["name"] = self.visit(ctx.name())

        # Get attributes (optional)
        if ctx.attributes():
            attrs = self.visit(ctx.attributes())
            result.update(attrs)

        return result

    def visitRole(self, ctx: Any) -> str:
        """Visit role rule: IDENTIFIER"""
        return ctx.IDENTIFIER().getText()

    def visitName(self, ctx: Any) -> AriaTextValue:
        """Visit name rule: STRING | REGEX"""
        if ctx.STRING():
            # String literal
            text = ctx.STRING().getText()
            # Remove quotes and unescape
            unescaped = unescape_string(text)
            return AriaTextValue(value=unescaped, is_regex=False)
        elif ctx.REGEX():
            # Regex pattern
            text = ctx.REGEX().getText()
            # Remove surrounding slashes
            if text.startswith("/") and text.endswith("/"):
                pattern = text[1:-1]
            else:
                pattern = text
            return AriaTextValue(value=pattern, is_regex=True)
        else:
            return AriaTextValue(value="", is_regex=False)

    def visitAttributes(self, ctx: Any) -> dict[str, Any]:
        """Visit attributes rule: attribute+"""
        result: dict[str, Any] = {}

        for attr_ctx in ctx.attribute():
            attr_dict = self.visit(attr_ctx)
            result.update(attr_dict)

        return result

    def visitAttribute(self, ctx: Any) -> dict[str, Any]:
        """Visit attribute rule: '[' attrName ']' | '[' attrName '=' attrValue ']'"""
        attr_name = ctx.attrName().getText()

        # Get value (may be None for boolean attributes)
        attr_value = None
        if ctx.attrValue():
            attr_value_ctx = ctx.attrValue()
            if attr_value_ctx.STRING():
                attr_value = unescape_string(attr_value_ctx.STRING().getText())
            elif attr_value_ctx.NUMBER():
                attr_value = attr_value_ctx.NUMBER().getText()
            elif attr_value_ctx.IDENTIFIER():
                attr_value = attr_value_ctx.IDENTIFIER().getText()
            elif attr_value_ctx.getText() == "mixed":
                attr_value = "mixed"

        # Validate and convert attribute
        try:
            return self._process_attribute(attr_name, attr_value)
        except (ValueError, ValidationError) as e:
            self.errors.append(ParseError(message=str(e)))
            return {}

    def _process_attribute(self, name: str, value: str | None) -> dict[str, Any]:
        """Process and validate attribute."""
        result: dict[str, Any] = {}

        # For boolean attributes, None value means True
        if value is None:
            value = "true"

        if name == "checked":
            result["checked"] = parse_mixed_boolean(value)
        elif name == "disabled":
            result["disabled"] = parse_boolean(value)
        elif name == "expanded":
            result["expanded"] = parse_boolean(value)
        elif name == "active":
            result["active"] = parse_boolean(value)
        elif name == "level":
            result["level"] = validate_level(value)
        elif name == "pressed":
            result["pressed"] = parse_mixed_boolean(value)
        elif name == "selected":
            result["selected"] = parse_boolean(value)
        elif name == "ref":
            result["ref"] = value
        elif name == "cursor":
            result["cursor"] = value
        else:
            raise ValidationError(f"Unknown attribute: {name}")

        return result


class AriaSnapshotParser:
    """Parser for ARIA snapshot YAML format."""

    def __init__(self) -> None:
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.errors: list[ParseError] = []

    def parse(self, text: str) -> tuple[list[AriaTemplateNode] | None, list[ParseError]]:
        """
        Parse ARIA snapshot YAML into template tree.

        Args:
            text: YAML text to parse

        Returns:
            Tuple of (parsed nodes, errors)
        """
        self.errors = []

        try:
            # Parse YAML structure
            yaml_data = self.yaml.load(text)

            if yaml_data is None:
                return None, self.errors

            # Process YAML nodes
            result = self._process_yaml_node(yaml_data, "root")

            return result, self.errors

        except Exception as e:
            self.errors.append(ParseError(message=f"YAML parsing error: {e}"))
            return None, self.errors

    def _process_yaml_node(
        self, node: Any, yaml_path: str
    ) -> list[AriaTemplateNode] | AriaTemplateNode | str | None:
        """Process YAML node recursively."""
        if node is None:
            return None

        if isinstance(node, list):
            # Process list of nodes
            result = []
            for i, item in enumerate(node):
                processed = self._process_yaml_node(item, f"{yaml_path}[{i}]")
                if processed is not None:
                    if isinstance(processed, list):
                        result.extend(processed)
                    else:
                        result.append(processed)
            return result

        elif isinstance(node, dict):
            # Check if this is a single-key property dict like {'/url': 'https://...'}
            if len(node) == 1:
                only_key = list(node.keys())[0]
                if only_key.startswith("/"):
                    # This is a property dict, return it as-is for parent to extract
                    return node
                elif only_key == "text":
                    # Text node
                    return str(node[only_key])

            # Otherwise process as full dict node
            return self._process_dict(node, yaml_path)

        elif isinstance(node, str):
            # Plain string might be an ARIA key like: button "Submit" [ref=e1]
            # Try to parse it as a key first
            aria_node = self._parse_key_with_antlr(node, yaml_path)
            if aria_node:
                return aria_node
            # Otherwise, return as plain text
            return node

        else:
            # Other types (numbers, booleans, etc.)
            return str(node)

    def _process_dict(self, node_dict: dict[str, Any], yaml_path: str) -> AriaTemplateNode | None:
        """Process dictionary node."""
        # A dict can have:
        # 1. A key with ARIA syntax: "button 'Submit' [ref=e1]"
        # 2. Special keys: "text:" or "/property:"

        properties: dict[str, str] = {}
        children: list[Any] = []
        aria_node: AriaTemplateNode | None = None

        for key, value in node_dict.items():
            if key.startswith("/"):
                # Property like /url: or /placeholder:
                prop_name = key[1:]  # Remove leading /
                properties[prop_name] = str(value) if value is not None else ""

            elif key == "text":
                # Text node
                return str(value) if value is not None else ""  # type: ignore

            else:
                # Parse key with ANTLR
                aria_node = self._parse_key_with_antlr(key, yaml_path)

                if aria_node and value is not None:
                    # Process children (value is usually a list)
                    processed_children = self._process_yaml_node(value, f"{yaml_path}.{key}")
                    if processed_children is not None:
                        if isinstance(processed_children, list):
                            # Extract properties from children
                            actual_children = []
                            for child in processed_children:
                                if isinstance(child, dict) and len(child) == 1:
                                    # Check if this is a property dict
                                    only_key = list(child.keys())[0]
                                    if only_key.startswith("/"):
                                        prop_name = only_key[1:]
                                        properties[prop_name] = str(child[only_key])
                                        continue
                                actual_children.append(child)
                            children.extend(actual_children)
                        else:
                            children.append(processed_children)

        if aria_node:
            # Update node with children and properties
            return AriaTemplateNode(
                role=aria_node.role,
                name=aria_node.name,
                children=tuple(children),
                props={**aria_node.props, **properties},
                checked=aria_node.checked,
                disabled=aria_node.disabled,
                expanded=aria_node.expanded,
                active=aria_node.active,
                level=aria_node.level,
                pressed=aria_node.pressed,
                selected=aria_node.selected,
                ref=aria_node.ref,
                cursor=aria_node.cursor,
            )

        return None

    def _parse_key_with_antlr(self, key_text: str, yaml_path: str) -> AriaTemplateNode | None:
        """Parse key using ANTLR grammar."""
        try:
            # Create ANTLR input stream
            input_stream = InputStream(key_text)

            # Create lexer
            lexer = AriaKeyLexer(input_stream)

            # Create token stream
            tokens = CommonTokenStream(lexer)

            # Create parser
            parser = AriaKeyParser(tokens)

            # Add custom error listener
            error_listener = AriaSnapshotErrorListener()
            parser.removeErrorListeners()
            parser.addErrorListener(error_listener)

            # Parse
            tree = parser.key()

            # Visit parse tree to build node data
            visitor = AriaKeyNodeBuilder()
            node_data = visitor.visit(tree)

            # Collect errors
            self.errors.extend(error_listener.errors)
            self.errors.extend(visitor.errors)

            if not node_data or "role" not in node_data:
                return None

            # Build AriaTemplateNode
            return AriaTemplateNode(
                role=node_data.get("role", ""),
                name=node_data.get("name"),
                checked=node_data.get("checked"),
                disabled=node_data.get("disabled"),
                expanded=node_data.get("expanded"),
                active=node_data.get("active"),
                level=node_data.get("level"),
                pressed=node_data.get("pressed"),
                selected=node_data.get("selected"),
                ref=node_data.get("ref"),
                cursor=node_data.get("cursor"),
            )

        except Exception as e:
            self.errors.append(
                ParseError(message=f"Error parsing key '{key_text}': {e}", yaml_path=yaml_path)
            )
            return None
