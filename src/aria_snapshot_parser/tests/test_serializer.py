"""Tests for JSON serializer."""

import json

import pytest

from aria_snapshot_parser import AriaSnapshotSerializer, parse


class TestAriaSnapshotSerializer:
    """Test JSON serialization."""

    def test_serialize_simple(self, simple_yaml: str):
        """Test serializing simple YAML."""
        tree, errors = parse(simple_yaml)
        assert len(errors) == 0

        serializer = AriaSnapshotSerializer()
        json_str = serializer.to_json(tree)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 2

        # Check button
        assert data[0]["role"] == "button"
        assert data[0]["name"]["value"] == "Submit"
        assert data[0]["name"]["is_regex"] is False
        assert data[0]["ref"] == "e1"

    def test_serialize_regex(self, regex_yaml: str):
        """Test serializing regex patterns."""
        tree, errors = parse(regex_yaml)
        assert len(errors) == 0

        serializer = AriaSnapshotSerializer()
        data_dict = serializer.to_dict(tree)

        assert data_dict[0]["name"]["is_regex"] is True
        assert data_dict[0]["name"]["value"] == "Submit.*"

    def test_serialize_attributes(self, attributes_yaml: str):
        """Test serializing attributes."""
        tree, errors = parse(attributes_yaml)
        assert len(errors) == 0

        serializer = AriaSnapshotSerializer()
        data_dict = serializer.to_dict(tree)

        # Check mixed attribute
        assert data_dict[1]["checked"] == "mixed"

        # Check level
        assert data_dict[5]["level"] == 2

    def test_to_json_formatting(self, simple_yaml: str):
        """Test JSON formatting options."""
        tree, errors = parse(simple_yaml)
        assert len(errors) == 0

        serializer = AriaSnapshotSerializer()

        # Test with different indent
        json_str = serializer.to_json(tree, indent=4)
        assert "    " in json_str  # 4-space indent

        # Test compact
        json_str = serializer.to_json(tree, indent=None)
        assert "\n" not in json_str

    def test_json_matches_fixture(self, simple_yaml: str, simple_expected_json: str):
        """Test JSON output matches expected fixture file."""
        tree, errors = parse(simple_yaml)
        assert len(errors) == 0

        serializer = AriaSnapshotSerializer()
        json_str = serializer.to_json(tree, indent=2)

        # Parse both as JSON and compare (ignores whitespace differences)
        actual_data = json.loads(json_str)
        expected_data = json.loads(simple_expected_json)

        assert actual_data == expected_data, "JSON output should match expected fixture"

        # Also verify the string representation is close (allows for minor formatting)
        assert json_str.strip() == simple_expected_json.strip()
