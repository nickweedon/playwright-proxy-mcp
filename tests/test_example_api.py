"""
Tests for the Example API Module

This demonstrates how to write tests for your MCP tools.
"""

import pytest

from skeleton_mcp.api import example


@pytest.fixture(autouse=True)
def reset_mock_items():
    """Reset mock items before each test."""
    example.MOCK_ITEMS.clear()
    example.MOCK_ITEMS.update({
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
    })


class TestListItems:
    """Tests for list_items function."""

    @pytest.mark.asyncio
    async def test_list_items_returns_all(self):
        """Test that list_items returns all items."""
        result = await example.list_items()

        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["page"] == 1
        assert result["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_items_with_filter(self):
        """Test filtering items by name."""
        result = await example.list_items(filter_name="Item 1")

        assert result["total"] == 1
        assert result["items"][0]["name"] == "Example Item 1"

    @pytest.mark.asyncio
    async def test_list_items_pagination(self):
        """Test pagination of items."""
        result = await example.list_items(page=1, page_size=1)

        assert result["total"] == 2
        assert len(result["items"]) == 1
        assert result["page"] == 1
        assert result["page_size"] == 1


class TestGetItem:
    """Tests for get_item function."""

    @pytest.mark.asyncio
    async def test_get_item_exists(self):
        """Test getting an existing item."""
        result = await example.get_item("item-1")

        assert result["id"] == "item-1"
        assert result["name"] == "Example Item 1"

    @pytest.mark.asyncio
    async def test_get_item_not_found(self):
        """Test getting a non-existent item raises error."""
        with pytest.raises(ValueError, match="Item not found"):
            await example.get_item("nonexistent")


class TestCreateItem:
    """Tests for create_item function."""

    @pytest.mark.asyncio
    async def test_create_item(self):
        """Test creating a new item."""
        result = await example.create_item(
            name="New Item",
            description="A brand new item",
        )

        assert result["name"] == "New Item"
        assert result["description"] == "A brand new item"
        assert "id" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_create_item_minimal(self):
        """Test creating an item with only required fields."""
        result = await example.create_item(name="Minimal Item")

        assert result["name"] == "Minimal Item"
        assert result["description"] is None


class TestUpdateItem:
    """Tests for update_item function."""

    @pytest.mark.asyncio
    async def test_update_item(self):
        """Test updating an existing item."""
        result = await example.update_item(
            item_id="item-1",
            name="Updated Name",
        )

        assert result["id"] == "item-1"
        assert result["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_item_not_found(self):
        """Test updating a non-existent item raises error."""
        with pytest.raises(ValueError, match="Item not found"):
            await example.update_item("nonexistent", name="Test")


class TestDeleteItem:
    """Tests for delete_item function."""

    @pytest.mark.asyncio
    async def test_delete_item(self):
        """Test deleting an existing item."""
        result = await example.delete_item("item-1")

        assert result["status"] == "deleted"
        assert result["id"] == "item-1"
        assert "item-1" not in example.MOCK_ITEMS

    @pytest.mark.asyncio
    async def test_delete_item_not_found(self):
        """Test deleting a non-existent item raises error."""
        with pytest.raises(ValueError, match="Item not found"):
            await example.delete_item("nonexistent")
