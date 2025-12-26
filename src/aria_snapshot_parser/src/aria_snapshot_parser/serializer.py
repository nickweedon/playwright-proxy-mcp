"""JSON serialization for parsed ARIA snapshot trees."""

import json
from typing import Any

from .types import AriaTemplateNode, AriaTextValue


class AriaSnapshotSerializer:
    """Serialize parsed ARIA tree to JSON."""

    def to_dict(self, node: AriaTemplateNode | str | list[Any] | None) -> dict[str, Any] | str | list[Any] | None:
        """
        Convert node to dictionary (recursive).

        Args:
            node: Node to convert

        Returns:
            Dictionary representation
        """
        if node is None:
            return None

        if isinstance(node, str):
            return node

        if isinstance(node, list):
            return [self.to_dict(item) for item in node]

        if not isinstance(node, AriaTemplateNode):
            return str(node)

        # Convert AriaTemplateNode to dict
        result: dict[str, Any] = {"role": node.role}

        # Handle name (can be AriaTextValue)
        if node.name:
            if isinstance(node.name, AriaTextValue):
                result["name"] = {
                    "value": node.name.value,
                    "is_regex": node.name.is_regex,
                }
            else:
                result["name"] = node.name

        # Add ARIA props if present
        for prop in ["checked", "disabled", "expanded", "active", "level", "pressed", "selected"]:
            val = getattr(node, prop, None)
            if val is not None:
                result[prop] = val

        # Add ref and cursor if present
        if node.ref is not None:
            result["ref"] = node.ref
        if node.cursor is not None:
            result["cursor"] = node.cursor

        # Add properties if present
        if node.props:
            result["props"] = node.props

        # Recursively convert children
        if node.children:
            result["children"] = [self.to_dict(child) for child in node.children]

        return result

    def to_json(self, node: AriaTemplateNode | str | list[Any] | None, indent: int = 2, **kwargs: Any) -> str:
        """
        Convert node to JSON string.

        Args:
            node: Node to convert
            indent: Number of spaces for indentation
            **kwargs: Additional arguments for json.dumps

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(node), indent=indent, **kwargs)

    def to_json_file(
        self, node: AriaTemplateNode | str | list[Any] | None, filepath: str, **kwargs: Any
    ) -> None:
        """
        Write node to JSON file.

        Args:
            node: Node to convert
            filepath: Path to output file
            **kwargs: Additional arguments for json.dump
        """
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(node), f, indent=2, **kwargs)
