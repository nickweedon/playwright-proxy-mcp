"""
Type Definitions

Define TypedDict classes for playwright proxy and blob storage data structures.
"""

from typing import Any, TypedDict


class BlobReference(TypedDict, total=False):
    """
    Reference to a blob stored in blob storage.

    Used when large binary data (screenshots, PDFs) is stored as a blob
    instead of being returned inline.
    """

    blob_id: str
    size_kb: int
    mime_type: str
    blob_retrieval_tool: str
    expires_at: str


class BlobMetadata(TypedDict, total=False):
    """Metadata about a stored blob."""

    blob_id: str
    mime_type: str
    size_bytes: int
    created_at: str
    expires_at: str
    tags: list[str]


class PlaywrightToolResponse(TypedDict, total=False):
    """
    Generic response from a playwright tool.

    May contain blob references instead of inline binary data.
    All browser tools include browser_instance to identify which instance was used.
    """

    success: bool
    message: str | None
    data: dict[str, str] | None
    blob_id: str | None
    browser_instance: str  # The browser instance ID that was used


class NavigationResponse(TypedDict, total=False):
    """
    Response for browser_navigate and browser_snapshot with pagination support.

    Used when navigating to URLs or capturing snapshots with advanced filtering,
    pagination, and output formatting.
    """

    success: bool
    url: str
    cache_key: str
    total_items: int
    offset: int
    limit: int
    has_more: bool
    snapshot: str | dict[str, Any] | list[dict[str, Any]] | None
    error: str | None
    output_format: str
    browser_instance: str  # The browser instance ID that was used


class EvaluationResponse(TypedDict, total=False):
    """
    Response for browser_evaluate with pagination support.

    Used when evaluating JavaScript in browser context with optional pagination
    for array results.
    """

    success: bool
    cache_key: str
    total_items: int
    offset: int
    limit: int
    has_more: bool
    result: Any
    error: str | None
    browser_instance: str  # The browser instance ID that was used


class BlobResultResponse(TypedDict):
    """
    Response for tools that return blob URIs (screenshots, PDFs).

    These tools store binary data as blobs and return a URI reference.
    """

    blob_uri: str  # URI to the stored blob (e.g., "blob://...")
    browser_instance: str  # The browser instance ID that was used


class BulkCommand(TypedDict, total=False):
    """Single command in a bulk execution."""

    tool: str  # Required: tool name (e.g., "browser_navigate")
    args: dict[str, str]  # Required: tool arguments
    return_result: bool  # Optional: include result in response (default: False)


class BulkExecutionResponse(TypedDict):
    """Response from bulk command execution."""

    success: bool  # Overall success (all commands succeeded)
    executed_count: int  # Number of commands executed
    total_count: int  # Total commands in request
    results: list  # Results array (None for non-returned results)
    errors: list  # Errors array (None for successful commands)
    stopped_at: int | None  # Index where execution stopped (if stop_on_error)
