"""Utility functions for ARIA snapshot parser."""

import re
from typing import Literal


def normalize_text(text: str) -> str:
    """
    Normalize text following Playwright's rules:
    1. Remove zero-width characters and soft hyphens
    2. Collapse whitespace (multiple spaces -> single space)
    3. Trim leading/trailing whitespace

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    # Remove zero-width space (\u200b) and soft hyphen (\u00ad)
    text = text.replace("\u200b", "").replace("\u00ad", "")

    # Collapse all whitespace runs to single space
    text = re.sub(r"\s+", " ", text)

    # Trim leading/trailing whitespace
    return text.strip()


def unescape_string(text: str) -> str:
    r"""
    Unescape string literals from ANTLR/YAML.
    Handles: \\, \", \n, \t, \r, \b, \f, \/

    Args:
        text: Escaped string (may include quotes)

    Returns:
        Unescaped string
    """
    # Remove surrounding quotes if present
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    elif text.startswith("'") and text.endswith("'"):
        text = text[1:-1]

    # Unescape common sequences
    replacements = {
        r"\\": "\\",  # Backslash (must be first)
        r'\"': '"',  # Double quote
        r"\'": "'",  # Single quote
        r"\n": "\n",  # Newline
        r"\t": "\t",  # Tab
        r"\r": "\r",  # Carriage return
        r"\b": "\b",  # Backspace
        r"\f": "\f",  # Form feed
        r"\/": "/",  # Forward slash
    }

    # Replace escape sequences (in order)
    for escaped, unescaped in replacements.items():
        text = text.replace(escaped, unescaped)

    return text


def validate_level(level: str | int) -> int:
    """
    Validate and convert level attribute to integer.

    Args:
        level: Level value as string or int

    Returns:
        Level as integer

    Raises:
        ValueError: If level is invalid
    """
    try:
        level_int = int(level)
        if level_int < 1 or level_int > 6:
            raise ValueError(f"Level must be between 1 and 6, got {level_int}")
        return level_int
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid level value: {level}") from e


def is_valid_boolean_attr(value: str) -> bool:
    """
    Check if value is valid for boolean attributes.

    Args:
        value: Value to check

    Returns:
        True if valid ('true', 'false', or empty string)
    """
    return value.lower() in ("true", "false", "")


def is_valid_mixed_attr(value: str) -> bool:
    """
    Check if value is valid for mixed attributes (checked, pressed).

    Args:
        value: Value to check

    Returns:
        True if valid ('true', 'false', 'mixed', or empty string)
    """
    return value.lower() in ("true", "false", "mixed", "")


def parse_boolean(value: str | bool) -> bool:
    """
    Parse boolean value from string or bool.

    Args:
        value: Boolean value as string or bool

    Returns:
        Boolean value

    Raises:
        ValueError: If value cannot be parsed as boolean
    """
    if isinstance(value, bool):
        return value

    value_lower = str(value).lower()
    if value_lower in ("true", "1", "yes"):
        return True
    elif value_lower in ("false", "0", "no", ""):
        return False
    else:
        raise ValueError(f"Cannot parse '{value}' as boolean")


def parse_mixed_boolean(value: str | bool) -> bool | Literal["mixed"]:
    """
    Parse boolean or 'mixed' value (for checked/pressed attributes).

    Args:
        value: Value as string or bool

    Returns:
        Boolean value or 'mixed'

    Raises:
        ValueError: If value cannot be parsed
    """
    if isinstance(value, bool):
        return value

    value_lower = str(value).lower()
    if value_lower == "mixed":
        return "mixed"  # type: ignore
    else:
        return parse_boolean(value)
