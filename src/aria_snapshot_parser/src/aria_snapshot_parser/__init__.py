"""
ARIA Snapshot Parser

A Python library for parsing Playwright's ARIA Snapshot YAML format using ANTLR4.
"""

__version__ = "0.1.0"

from .exceptions import AriaSnapshotError, LexerError, ValidationError
from .exceptions import ParseError as ParseException
from .parser import AriaSnapshotParser
from .serializer import AriaSnapshotSerializer
from .types import AriaProps, AriaTemplateNode, AriaTextValue, ParseError

__all__ = [
    # Main classes
    "AriaSnapshotParser",
    "AriaSnapshotSerializer",
    # Data types
    "AriaTemplateNode",
    "AriaTextValue",
    "AriaProps",
    "ParseError",
    # Exceptions
    "AriaSnapshotError",
    "ParseException",
    "LexerError",
    "ValidationError",
    # Convenience function
    "parse",
]


def parse(yaml_text: str) -> tuple[list[AriaTemplateNode] | None, list[ParseError]]:
    """
    Parse ARIA snapshot YAML.

    This is a convenience function that creates a parser instance and parses the input.

    Args:
        yaml_text: YAML string to parse

    Returns:
        Tuple of (tree, errors) where tree is the parsed node list and errors is a list
        of any parsing errors encountered

    Example:
        >>> tree, errors = parse(yaml_text)
        >>> if errors:
        ...     for error in errors:
        ...         print(error)
        >>> else:
        ...     serializer = AriaSnapshotSerializer()
        ...     json_output = serializer.to_json(tree)
    """
    parser = AriaSnapshotParser()
    return parser.parse(yaml_text)
