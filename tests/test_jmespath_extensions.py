"""Tests for jmespath_extensions module."""

import pytest

from playwright_proxy_mcp.utils.jmespath_extensions import (
    CustomFunctions,
    search_with_custom_functions,
)


class TestCustomFunctions:
    """Tests for CustomFunctions class"""

    @pytest.fixture
    def functions(self):
        return CustomFunctions()

    def test_nvl_with_none_returns_default(self, functions):
        result = functions._func_nvl(None, "default")
        assert result == "default"

    def test_nvl_with_value_returns_value(self, functions):
        result = functions._func_nvl("value", "default")
        assert result == "value"

    def test_nvl_with_zero_returns_zero(self, functions):
        result = functions._func_nvl(0, "default")
        assert result == 0

    def test_nvl_with_empty_string_returns_empty_string(self, functions):
        result = functions._func_nvl("", "default")
        assert result == ""

    def test_nvl_with_false_returns_false(self, functions):
        result = functions._func_nvl(False, "default")
        assert result is False

    def test_int_with_integer_string(self, functions):
        result = functions._func_int("42")
        assert result == 42

    def test_int_with_integer(self, functions):
        result = functions._func_int(42)
        assert result == 42

    def test_int_with_float_string(self, functions):
        # int() doesn't convert float strings directly, returns None
        result = functions._func_int("42.7")
        assert result is None

    def test_int_with_float(self, functions):
        result = functions._func_int(42.7)
        assert result == 42

    def test_int_with_none(self, functions):
        result = functions._func_int(None)
        assert result is None

    def test_int_with_invalid_string(self, functions):
        result = functions._func_int("not a number")
        assert result is None

    def test_int_with_empty_string(self, functions):
        result = functions._func_int("")
        assert result is None

    def test_str_with_string(self, functions):
        result = functions._func_str("hello")
        assert result == "hello"

    def test_str_with_integer(self, functions):
        result = functions._func_str(42)
        assert result == "42"

    def test_str_with_float(self, functions):
        result = functions._func_str(3.14)
        assert result == "3.14"

    def test_str_with_none(self, functions):
        result = functions._func_str(None)
        assert result is None

    def test_str_with_boolean(self, functions):
        result = functions._func_str(True)
        assert result == "True"

    def test_regex_replace_basic(self, functions):
        result = functions._func_regex_replace(r"\d+", "X", "abc123def456")
        assert result == "abcXdefX"

    def test_regex_replace_with_groups(self, functions):
        result = functions._func_regex_replace(r"(\w+)@(\w+)", r"\2:\1", "user@example")
        assert result == "example:user"

    def test_regex_replace_no_match(self, functions):
        result = functions._func_regex_replace(r"\d+", "X", "abcdef")
        assert result == "abcdef"

    def test_regex_replace_with_none_value(self, functions):
        result = functions._func_regex_replace(r"\d+", "X", None)
        assert result is None

    def test_regex_replace_with_invalid_pattern(self, functions):
        # Invalid regex pattern should return original value
        result = functions._func_regex_replace(r"[", "X", "test")
        assert result == "test"

    def test_regex_replace_empty_replacement(self, functions):
        result = functions._func_regex_replace(r"\d+", "", "abc123def")
        assert result == "abcdef"


class TestSearchWithCustomFunctions:
    """Tests for search_with_custom_functions function"""

    def test_nvl_in_filter(self):
        data = [
            {"name": "Item 1", "value": 10},
            {"name": "Item 2", "value": None},
            {"name": "Item 3", "value": 20},
        ]
        # Filter items where value (or 0 if null) > 5
        result = search_with_custom_functions("[?nvl(value, `0`) > `5`]", data)
        assert len(result) == 2
        assert result[0]["name"] == "Item 1"
        assert result[1]["name"] == "Item 3"

    def test_int_conversion_in_query(self):
        data = {"items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}
        # Convert string IDs to integers and sum them
        result = search_with_custom_functions("items[].int(id)", data)
        assert result == [1, 2, 3]

    def test_str_conversion_in_query(self):
        data = {"items": [{"count": 10}, {"count": 20}, {"count": 30}]}
        result = search_with_custom_functions("items[].str(count)", data)
        assert result == ["10", "20", "30"]

    def test_regex_replace_in_query(self):
        data = {"emails": ["user1@example.com", "user2@example.com"]}
        # Extract username part
        result = search_with_custom_functions(
            "emails[].regex_replace(`@.*$`, ``, @)", data
        )
        assert result == ["user1", "user2"]

    def test_chained_custom_functions(self):
        data = {"items": [{"price": "100"}, {"price": "200"}, {"price": None}]}
        # Convert string prices to int, with default "0" for None
        result = search_with_custom_functions("items[].int(nvl(price, `\"0\"`))", data)
        assert result == [100, 200, 0]

    def test_custom_function_in_projection(self):
        data = [
            {"name": "Product A", "code": "ABC-123"},
            {"name": "Product B", "code": "DEF-456"},
        ]
        result = search_with_custom_functions(
            "[].{name: name, numeric: regex_replace(`[A-Z-]`, ``, code)}", data
        )
        assert result[0] == {"name": "Product A", "numeric": "123"}
        assert result[1] == {"name": "Product B", "numeric": "456"}

    def test_nvl_with_complex_default(self):
        data = {"items": [{"value": None}, {"value": 10}]}
        result = search_with_custom_functions("items[].nvl(value, `999`)", data)
        assert result == [999, 10]

    def test_int_with_nested_path(self):
        data = {"outer": {"inner": {"value": "42"}}}
        result = search_with_custom_functions("int(outer.inner.value)", data)
        assert result == 42

    def test_str_with_null_path(self):
        data = {"exists": 123}
        result = search_with_custom_functions("str(nonexistent)", data)
        assert result is None

    def test_multiple_regex_replaces(self):
        data = {"text": "Hello-World"}
        # Replace hyphens with underscores
        result = search_with_custom_functions("regex_replace(`-`, `_`, text)", data)
        assert result == "Hello_World"

    def test_real_world_aria_snapshot_query(self):
        """Test with realistic ARIA snapshot-like data"""
        data = {
            "children": [
                {"role": "button", "name": "Click me", "level": "1"},
                {"role": "link", "name": None, "level": "2"},
                {"role": "button", "name": "Submit", "level": "3"},
            ]
        }
        # Get buttons with non-null names, convert level to int
        result = search_with_custom_functions(
            "children[?role == `button` && nvl(name, ``) != ``].{name: name, level: int(level)}",
            data,
        )
        assert len(result) == 2
        assert result[0] == {"name": "Click me", "level": 1}
        assert result[1] == {"name": "Submit", "level": 3}
