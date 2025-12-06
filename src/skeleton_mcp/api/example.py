"""
Example API Module

This module demonstrates how to structure API functions that will be
registered as MCP tools. Replace this with your actual API implementation.

Each function should:
1. Have a clear docstring explaining what it does
2. Use type hints for parameters and return values
3. Handle errors gracefully
4. Return structured data (dicts, lists, etc.)
"""

from typing import Any

# In a real implementation, you would import and use the API client:
# from ..client import get_client
# from ..types import ItemData, ItemListResponse

# For the skeleton, we use mock data
MOCK_ITEMS: dict[str, dict[str, Any]] = {
    "item-1": {
        "id": "item-1",
        "name": "Example Item 1",
        "description": "This is a sample item",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    },
    "item-2": {
        "id": "item-2",
        "name": "Example Item 2",
        "description": "Another sample item",
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    },
}


async def list_items(
    page: int = 1,
    page_size: int = 10,
    filter_name: str | None = None,
) -> dict[str, Any]:
    """
    List all items with optional filtering and pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        filter_name: Optional filter by name (case-insensitive contains)

    Returns:
        A dictionary containing:
        - items: List of item objects
        - total: Total number of items matching the filter
        - page: Current page number
        - page_size: Number of items per page
    """
    # In a real implementation:
    # client = get_client()
    # return client.get("items", params={"page": page, "page_size": page_size})

    items = list(MOCK_ITEMS.values())

    if filter_name:
        items = [i for i in items if filter_name.lower() in i["name"].lower()]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    items = items[start:end]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_item(item_id: str) -> dict[str, Any]:
    """
    Get a specific item by ID.

    Args:
        item_id: The unique identifier of the item

    Returns:
        The item data if found

    Raises:
        ValueError: If the item is not found
    """
    # In a real implementation:
    # client = get_client()
    # return client.get(f"items/{item_id}")

    if item_id not in MOCK_ITEMS:
        raise ValueError(f"Item not found: {item_id}")

    return MOCK_ITEMS[item_id]


async def create_item(
    name: str,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Create a new item.

    Args:
        name: The name of the item (required)
        description: Optional description
        metadata: Optional key-value metadata

    Returns:
        The created item data including the generated ID
    """
    # In a real implementation:
    # client = get_client()
    # return client.post("items", data={"name": name, "description": description, "metadata": metadata})

    import uuid
    from datetime import datetime, timezone

    item_id = f"item-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    item = {
        "id": item_id,
        "name": name,
        "description": description,
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
    }

    MOCK_ITEMS[item_id] = item
    return item


async def update_item(
    item_id: str,
    name: str | None = None,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Update an existing item.

    Args:
        item_id: The unique identifier of the item to update
        name: New name (optional)
        description: New description (optional)
        metadata: New metadata (optional, replaces existing)

    Returns:
        The updated item data

    Raises:
        ValueError: If the item is not found
    """
    # In a real implementation:
    # client = get_client()
    # return client.put(f"items/{item_id}", data={"name": name, "description": description, "metadata": metadata})

    if item_id not in MOCK_ITEMS:
        raise ValueError(f"Item not found: {item_id}")

    from datetime import datetime, timezone

    item = MOCK_ITEMS[item_id].copy()

    if name is not None:
        item["name"] = name
    if description is not None:
        item["description"] = description
    if metadata is not None:
        item["metadata"] = metadata

    item["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    MOCK_ITEMS[item_id] = item
    return item


async def delete_item(item_id: str) -> dict[str, Any]:
    """
    Delete an item.

    Args:
        item_id: The unique identifier of the item to delete

    Returns:
        A confirmation message

    Raises:
        ValueError: If the item is not found
    """
    # In a real implementation:
    # client = get_client()
    # return client.delete(f"items/{item_id}")

    if item_id not in MOCK_ITEMS:
        raise ValueError(f"Item not found: {item_id}")

    del MOCK_ITEMS[item_id]
    return {"status": "deleted", "id": item_id}
