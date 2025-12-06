"""
Type Definitions

Define TypedDict classes and other type hints for your API data structures.
This provides better type safety and documentation for your MCP tools.
"""

from typing import TypedDict


class ItemData(TypedDict, total=False):
    """
    Example item data structure.

    Customize this to match your API's data model.
    """

    id: str
    name: str
    description: str | None
    created_at: str
    updated_at: str
    metadata: dict[str, str] | None


class ItemListResponse(TypedDict):
    """Response from listing items."""

    items: list[ItemData]
    total: int
    page: int
    page_size: int


class ItemCreateRequest(TypedDict, total=False):
    """Request body for creating an item."""

    name: str
    description: str | None
    metadata: dict[str, str] | None


class ItemUpdateRequest(TypedDict, total=False):
    """Request body for updating an item."""

    name: str | None
    description: str | None
    metadata: dict[str, str] | None


class ErrorResponse(TypedDict):
    """Standard error response structure."""

    error: str
    message: str
    details: dict[str, str] | None
