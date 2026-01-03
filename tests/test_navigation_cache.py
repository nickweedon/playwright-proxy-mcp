"""Tests for navigation_cache module."""

import time
from unittest.mock import patch

import pytest

from playwright_proxy_mcp.utils.navigation_cache import CacheEntry, NavigationCache


class TestCacheEntry:
    """Tests for CacheEntry dataclass"""

    def test_init_default(self):
        entry = CacheEntry(url="https://example.com", snapshot_json={"data": "test"})
        assert entry.url == "https://example.com"
        assert entry.snapshot_json == {"data": "test"}
        assert entry.ttl == 300
        assert entry.created_at > 0
        assert entry.last_accessed > 0

    def test_init_custom_ttl(self):
        entry = CacheEntry(url="https://example.com", snapshot_json={"data": "test"}, ttl=600)
        assert entry.ttl == 600

    def test_is_expired_false(self):
        entry = CacheEntry(url="https://example.com", snapshot_json={"data": "test"})
        assert not entry.is_expired

    def test_is_expired_true(self):
        entry = CacheEntry(url="https://example.com", snapshot_json={"data": "test"}, ttl=0)
        time.sleep(0.01)
        assert entry.is_expired

    def test_touch(self):
        entry = CacheEntry(url="https://example.com", snapshot_json={"data": "test"})
        original_time = entry.last_accessed
        time.sleep(0.01)
        entry.touch()
        assert entry.last_accessed > original_time


class TestNavigationCache:
    """Tests for NavigationCache class"""

    @pytest.fixture
    def cache(self):
        return NavigationCache()

    @pytest.fixture
    def custom_ttl_cache(self):
        return NavigationCache(default_ttl=60)

    def test_init_default_ttl(self, cache):
        assert cache._default_ttl == 300
        assert len(cache._cache) == 0

    def test_init_custom_ttl(self, custom_ttl_cache):
        assert custom_ttl_cache._default_ttl == 60

    def test_create_returns_key(self, cache):
        key = cache.create("https://example.com", {"data": "test"})
        assert isinstance(key, str)
        assert key.startswith("nav_")
        assert len(key) == 12  # nav_ + 8 hex chars

    def test_create_stores_entry(self, cache):
        key = cache.create("https://example.com", {"data": "test"})
        assert key in cache._cache
        entry = cache._cache[key]
        assert entry.url == "https://example.com"
        assert entry.snapshot_json == {"data": "test"}
        assert entry.ttl == 300

    def test_create_with_custom_ttl(self, cache):
        key = cache.create("https://example.com", {"data": "test"}, ttl=600)
        entry = cache._cache[key]
        assert entry.ttl == 600

    def test_create_uses_default_ttl_from_cache(self, custom_ttl_cache):
        key = custom_ttl_cache.create("https://example.com", {"data": "test"})
        entry = custom_ttl_cache._cache[key]
        assert entry.ttl == 60

    def test_create_multiple_entries(self, cache):
        key1 = cache.create("https://example.com", {"data": "test1"})
        key2 = cache.create("https://example.org", {"data": "test2"})
        assert key1 != key2
        assert len(cache) == 2

    def test_get_existing_entry(self, cache):
        key = cache.create("https://example.com", {"data": "test"})
        entry = cache.get(key)
        assert entry is not None
        assert entry.url == "https://example.com"
        assert entry.snapshot_json == {"data": "test"}

    def test_get_nonexistent_entry(self, cache):
        entry = cache.get("nonexistent_key")
        assert entry is None

    def test_get_updates_last_accessed(self, cache):
        key = cache.create("https://example.com", {"data": "test"})
        original_time = cache._cache[key].last_accessed
        time.sleep(0.01)
        entry = cache.get(key)
        assert entry.last_accessed > original_time

    def test_get_expired_entry_returns_none(self, cache):
        key = cache.create("https://example.com", {"data": "test"}, ttl=0)
        time.sleep(0.01)
        entry = cache.get(key)
        assert entry is None

    def test_get_expired_entry_removes_from_cache(self, cache):
        key = cache.create("https://example.com", {"data": "test"}, ttl=0)
        time.sleep(0.01)
        cache.get(key)
        assert key not in cache._cache

    def test_delete_existing_entry(self, cache):
        key = cache.create("https://example.com", {"data": "test"})
        result = cache.delete(key)
        assert result is True
        assert key not in cache._cache

    def test_delete_nonexistent_entry(self, cache):
        result = cache.delete("nonexistent_key")
        assert result is False

    def test_clear(self, cache):
        cache.create("https://example.com", {"data": "test1"})
        cache.create("https://example.org", {"data": "test2"})
        assert len(cache) == 2
        cache.clear()
        assert len(cache) == 0

    def test_lazy_cleanup_removes_expired(self, cache):
        # Create one expired and one valid entry
        key1 = cache.create("https://example.com", {"data": "test1"}, ttl=0)
        time.sleep(0.01)
        key2 = cache.create("https://example.org", {"data": "test2"}, ttl=300)

        # Trigger lazy cleanup
        cache._lazy_cleanup()

        assert key1 not in cache._cache
        assert key2 in cache._cache

    def test_lazy_cleanup_on_create(self, cache):
        # Create expired entry
        cache.create("https://example.com", {"data": "test1"}, ttl=0)
        time.sleep(0.01)
        assert len(cache) == 1

        # Create new entry should trigger cleanup
        cache.create("https://example.org", {"data": "test2"})
        assert len(cache) == 1  # Only new entry remains

    def test_lazy_cleanup_on_get(self, cache):
        # Create two entries, one expired
        key1 = cache.create("https://example.com", {"data": "test1"}, ttl=0)
        time.sleep(0.01)
        key2 = cache.create("https://example.org", {"data": "test2"}, ttl=300)

        # Get should trigger cleanup
        cache.get(key2)
        assert key1 not in cache._cache
        assert key2 in cache._cache

    def test_len(self, cache):
        assert len(cache) == 0
        cache.create("https://example.com", {"data": "test1"})
        assert len(cache) == 1
        cache.create("https://example.org", {"data": "test2"})
        assert len(cache) == 2

    def test_cache_with_list_snapshot(self, cache):
        snapshot = [{"role": "button", "name": "Click me"}]
        key = cache.create("https://example.com", snapshot)
        entry = cache.get(key)
        assert entry.snapshot_json == snapshot

    def test_cache_with_nested_dict_snapshot(self, cache):
        snapshot = {
            "children": [{"role": "button", "children": [{"text": "Click"}]}]
        }
        key = cache.create("https://example.com", snapshot)
        entry = cache.get(key)
        assert entry.snapshot_json == snapshot

    def test_multiple_gets_same_entry(self, cache):
        key = cache.create("https://example.com", {"data": "test"})
        entry1 = cache.get(key)
        entry2 = cache.get(key)
        assert entry1 is entry2  # Same object
        assert entry1.url == "https://example.com"
