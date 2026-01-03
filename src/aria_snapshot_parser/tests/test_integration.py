"""Integration tests for aria-snapshot-parser."""


from aria_snapshot_parser import AriaSnapshotSerializer, parse


class TestIntegration:
    """End-to-end integration tests."""

    def test_parse_and_serialize_round_trip(self, simple_yaml: str):
        """Test full pipeline: parse -> serialize."""
        # Parse
        tree, errors = parse(simple_yaml)
        assert len(errors) == 0
        assert tree is not None

        # Serialize
        serializer = AriaSnapshotSerializer()
        json_output = serializer.to_json(tree, indent=2)

        # Verify output is valid
        assert "button" in json_output
        assert "Submit" in json_output
        assert "link" in json_output
        assert "Home" in json_output

    def test_google_example_end_to_end(self, google_yaml: str):
        """Test Google example end-to-end."""
        tree, errors = parse(google_yaml)
        assert len(errors) == 0
        assert tree is not None

        serializer = AriaSnapshotSerializer()
        data = serializer.to_dict(tree)

        # Verify structure
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["role"] == "generic"

    def test_all_attribute_types(self, attributes_yaml: str):
        """Test all ARIA attribute types work correctly."""
        tree, errors = parse(attributes_yaml)
        assert len(errors) == 0

        serializer = AriaSnapshotSerializer()
        data = serializer.to_dict(tree)

        # Verify all attributes are present
        assert any("checked" in item for item in data)
        assert any("disabled" in item for item in data)
        assert any("expanded" in item for item in data)
        assert any("active" in item for item in data)
        assert any("level" in item for item in data)
        assert any("pressed" in item for item in data)
        assert any("selected" in item for item in data)
