"""Custom exceptions for aria-snapshot-parser."""


class AriaSnapshotError(Exception):
    """Base exception for aria-snapshot-parser."""

    pass


class ParseError(AriaSnapshotError):
    """Error during parsing."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        yaml_path: str | None = None,
    ):
        self.message = message
        self.line = line
        self.column = column
        self.yaml_path = yaml_path

        location = []
        if line is not None:
            location.append(f"line {line}")
        if column is not None:
            location.append(f"column {column}")
        if yaml_path:
            location.append(f"path {yaml_path}")

        loc_str = ", ".join(location)
        super().__init__(f"{message} ({loc_str})" if loc_str else message)


class LexerError(ParseError):
    """Error during tokenization."""

    pass


class ValidationError(ParseError):
    """Error validating attribute or value."""

    pass
