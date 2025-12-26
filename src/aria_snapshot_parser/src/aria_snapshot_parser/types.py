"""Data models for ARIA snapshot parser."""

from dataclasses import dataclass, field
from typing import Literal, Union


@dataclass(frozen=True)
class AriaProps:
    """ARIA properties/attributes."""

    checked: bool | Literal["mixed"] | None = None
    disabled: bool | None = None
    expanded: bool | None = None
    active: bool | None = None
    level: int | None = None
    pressed: bool | Literal["mixed"] | None = None
    selected: bool | None = None


@dataclass(frozen=True)
class AriaTextValue:
    """Text value that can be literal string or regex pattern."""

    value: str
    is_regex: bool = False

    def __str__(self) -> str:
        if self.is_regex:
            return f"/{self.value}/"
        return f'"{self.value}"'


@dataclass(frozen=True)
class AriaTemplateNode:
    """
    Parsed ARIA node from YAML template.

    This represents a node in the accessibility tree with its role,
    accessible name, attributes, and children.
    """

    role: str  # ARIA role (button, link, navigation, etc.)
    name: AriaTextValue | None = None  # Accessible name (can be regex)
    children: tuple[Union["AriaTemplateNode", str], ...] = field(default_factory=tuple)
    props: dict[str, str] = field(default_factory=dict)  # Properties like /url, /placeholder

    # ARIA attributes
    checked: bool | Literal["mixed"] | None = None
    disabled: bool | None = None
    expanded: bool | None = None
    active: bool | None = None
    level: int | None = None
    pressed: bool | Literal["mixed"] | None = None
    selected: bool | None = None

    # Element reference and cursor
    ref: str | None = None
    cursor: str | None = None


@dataclass(frozen=True)
class ParseError:
    """Error encountered during parsing with position tracking."""

    message: str
    line: int | None = None
    column: int | None = None
    yaml_path: str | None = None  # YAML path like "root[0].children[2]"

    def __str__(self) -> str:
        location_parts = []
        if self.line is not None:
            location_parts.append(f"line {self.line}")
        if self.column is not None:
            location_parts.append(f"column {self.column}")
        if self.yaml_path:
            location_parts.append(f"path {self.yaml_path}")

        location_str = ", ".join(location_parts)
        return f"{self.message} ({location_str})" if location_str else self.message
