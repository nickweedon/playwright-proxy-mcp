"""Tests for server helper functions."""

import pytest
from playwright_proxy_mcp.server import (
    _create_navigation_error,
    _validate_navigation_params,
    _create_evaluation_error,
    _validate_evaluation_params,
    _extract_blob_id_from_response,
)


class TestCreateNavigationError:
    """Tests for _create_navigation_error helper function."""

    def test_creates_error_response_with_all_params(self):
        """Test creating error response with all parameters."""
        result = _create_navigation_error(
            url="https://example.com",
            error="Test error message",
            offset=10,
            limit=50,
            cache_key="test_key",
            output_format="json",
        )

        assert result["success"] is False
        assert result["url"] == "https://example.com"
        assert result["error"] == "Test error message"
        assert result["offset"] == 10
        assert result["limit"] == 50
        assert result["cache_key"] == "test_key"
        assert result["output_format"] == "json"
        assert result["total_items"] == 0
        assert result["has_more"] is False
        assert result["snapshot"] is None

    def test_creates_error_response_with_defaults(self):
        """Test creating error response with default parameters."""
        result = _create_navigation_error(
            url="https://example.com",
            error="Test error",
        )

        assert result["success"] is False
        assert result["url"] == "https://example.com"
        assert result["error"] == "Test error"
        assert result["offset"] == 0
        assert result["limit"] == 1000
        assert result["cache_key"] == ""
        assert result["output_format"] == "yaml"

    def test_creates_error_response_with_empty_url(self):
        """Test creating error response for snapshot (empty URL)."""
        result = _create_navigation_error(
            url="",
            error="Snapshot error",
            offset=5,
            limit=100,
        )

        assert result["success"] is False
        assert result["url"] == ""
        assert result["error"] == "Snapshot error"
        assert result["offset"] == 5
        assert result["limit"] == 100


class TestValidateNavigationParams:
    """Tests for _validate_navigation_params helper function."""

    def test_valid_params_returns_none(self):
        """Test that valid parameters return None."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=0,
            limit=100,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error is None

    def test_valid_params_with_jmespath_returns_none(self):
        """Test that valid parameters with JMESPath return None."""
        error = _validate_navigation_params(
            output_format="json",
            offset=10,
            limit=50,
            flatten=False,
            jmespath_query="[?role == 'button']",
            cache_key=None,
        )
        assert error is None

    def test_invalid_output_format(self):
        """Test that invalid output format returns error."""
        error = _validate_navigation_params(
            output_format="xml",
            offset=0,
            limit=100,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error == "output_format must be 'json' or 'yaml'"

    def test_negative_offset(self):
        """Test that negative offset returns error."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=-5,
            limit=100,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error == "offset must be non-negative"

    def test_limit_too_low(self):
        """Test that limit < 1 returns error."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=0,
            limit=0,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error == "limit must be between 1 and 10000"

    def test_limit_too_high(self):
        """Test that limit > 10000 returns error."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=0,
            limit=10001,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error == "limit must be between 1 and 10000"

    def test_pagination_without_flatten_query_or_cache(self):
        """Test that pagination without flatten/query/cache returns error."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=10,
            limit=100,
            flatten=False,
            jmespath_query=None,
            cache_key=None,
        )
        assert "Pagination (offset/limit) requires" in error

    def test_non_default_limit_without_flatten_query_or_cache(self):
        """Test that non-default limit without flatten/query/cache returns error."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=0,
            limit=500,
            flatten=False,
            jmespath_query=None,
            cache_key=None,
        )
        assert "Pagination (offset/limit) requires" in error

    def test_pagination_with_cache_key_is_valid(self):
        """Test that pagination with cache_key is valid."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=10,
            limit=100,
            flatten=False,
            jmespath_query=None,
            cache_key="nav_abc123",
        )
        assert error is None

    def test_default_params_without_pagination_is_valid(self):
        """Test that default params (offset=0, limit=1000) without flatten is valid."""
        error = _validate_navigation_params(
            output_format="yaml",
            offset=0,
            limit=1000,
            flatten=False,
            jmespath_query=None,
            cache_key=None,
        )
        assert error is None

    def test_case_insensitive_output_format(self):
        """Test that output format validation is case-insensitive."""
        error = _validate_navigation_params(
            output_format="JSON",
            offset=0,
            limit=100,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error is None

        error = _validate_navigation_params(
            output_format="YAML",
            offset=0,
            limit=100,
            flatten=True,
            jmespath_query=None,
            cache_key=None,
        )
        assert error is None


class TestCreateEvaluationError:
    """Tests for _create_evaluation_error helper function."""

    def test_creates_error_response_with_all_params(self):
        """Test creating evaluation error with all parameters."""
        result = _create_evaluation_error(
            error="Test error message",
            offset=10,
            limit=50,
            cache_key="test_key",
        )

        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert result["offset"] == 10
        assert result["limit"] == 50
        assert result["cache_key"] == "test_key"
        assert result["total_items"] == 0
        assert result["has_more"] is False
        assert result["result"] is None

    def test_creates_error_response_with_defaults(self):
        """Test creating evaluation error with default parameters."""
        result = _create_evaluation_error(error="Test error")

        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["offset"] == 0
        assert result["limit"] == 1000
        assert result["cache_key"] == ""


class TestValidateEvaluationParams:
    """Tests for _validate_evaluation_params helper function."""

    def test_valid_params_returns_none(self):
        """Test that valid parameters return None."""
        error = _validate_evaluation_params(offset=0, limit=100)
        assert error is None

    def test_negative_offset(self):
        """Test that negative offset returns error."""
        error = _validate_evaluation_params(offset=-5, limit=100)
        assert error == "offset must be non-negative"

    def test_limit_too_low(self):
        """Test that limit < 1 returns error."""
        error = _validate_evaluation_params(offset=0, limit=0)
        assert error == "limit must be between 1 and 10000"

    def test_limit_too_high(self):
        """Test that limit > 10000 returns error."""
        error = _validate_evaluation_params(offset=0, limit=10001)
        assert error == "limit must be between 1 and 10000"

    def test_limit_exactly_1(self):
        """Test that limit = 1 is valid."""
        error = _validate_evaluation_params(offset=0, limit=1)
        assert error is None

    def test_limit_exactly_10000(self):
        """Test that limit = 10000 is valid."""
        error = _validate_evaluation_params(offset=0, limit=10000)
        assert error is None


class TestExtractBlobIdFromResponse:
    """Tests for _extract_blob_id_from_response helper function."""

    def test_extracts_from_dict_response(self):
        """Test extracting blob ID from dict response."""
        result = {
            "content": [
                {"type": "text", "text": "some text"},
                {"type": "blob", "blob_id": "blob://test-123.png"},
            ]
        }
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id == "blob://test-123.png"

    def test_extracts_from_pydantic_like_object(self):
        """Test extracting blob ID from object with attributes."""

        class MockItem:
            def __init__(self, item_type, blob_id=None):
                self.type = item_type
                self.blob_id = blob_id

        class MockResult:
            def __init__(self):
                self.content = [
                    MockItem("text"),
                    MockItem("blob", "blob://object-456.pdf"),
                ]

        result = MockResult()
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id == "blob://object-456.pdf"

    def test_returns_string_directly(self):
        """Test that string results are returned directly."""
        result = "blob://direct-789.jpeg"
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id == "blob://direct-789.jpeg"

    def test_returns_none_when_no_blob(self):
        """Test that None is returned when no blob found."""
        result = {"content": [{"type": "text", "text": "only text"}]}
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id is None

    def test_returns_none_for_empty_content(self):
        """Test that None is returned for empty content."""
        result = {"content": []}
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id is None

    def test_returns_none_for_missing_content(self):
        """Test that None is returned when content is missing."""
        result = {"other_field": "value"}
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id is None

    def test_finds_blob_among_multiple_items(self):
        """Test finding blob among multiple content items."""
        result = {
            "content": [
                {"type": "text", "text": "text1"},
                {"type": "text", "text": "text2"},
                {"type": "blob", "blob_id": "blob://found-it.png"},
                {"type": "text", "text": "text3"},
            ]
        }
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id == "blob://found-it.png"

    def test_returns_first_blob_when_multiple(self):
        """Test that first blob is returned when multiple blobs present."""
        result = {
            "content": [
                {"type": "blob", "blob_id": "blob://first.png"},
                {"type": "blob", "blob_id": "blob://second.png"},
            ]
        }
        blob_id = _extract_blob_id_from_response(result)
        assert blob_id == "blob://first.png"
