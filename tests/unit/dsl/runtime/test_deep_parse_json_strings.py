"""Tests for deep_parse_json_strings utility function.

Verify that nested JSON strings in LLM responses are recursively parsed
before schema validation.
"""


from streetrace.dsl.runtime.context import deep_parse_json_strings


class TestDeepParseJsonStrings:
    """Test recursive JSON string parsing."""

    def test_returns_non_dict_list_unchanged(self):
        """Non-container types pass through unchanged."""
        assert deep_parse_json_strings(42) == 42
        assert deep_parse_json_strings("hello") == "hello"
        assert deep_parse_json_strings(3.14) == 3.14
        bool_val = True
        assert deep_parse_json_strings(bool_val) is True
        assert deep_parse_json_strings(None) is None

    def test_parses_json_array_string(self):
        """JSON array strings are parsed into lists."""
        result = deep_parse_json_strings('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_parses_json_object_string(self):
        """JSON object strings are parsed into dicts."""
        result = deep_parse_json_strings('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_nested_json_in_dict(self):
        """Nested JSON strings in dict values are parsed."""
        data = {
            "name": "test",
            "items": '["item1", "item2"]',
        }
        result = deep_parse_json_strings(data)
        assert result == {
            "name": "test",
            "items": ["item1", "item2"],
        }

    def test_parses_nested_json_in_list(self):
        """Nested JSON strings in list elements are parsed."""
        data = ["first", '{"nested": true}', "third"]
        result = deep_parse_json_strings(data)
        assert result == ["first", {"nested": True}, "third"]

    def test_handles_deeply_nested_structures(self):
        """Multi-level nesting is handled correctly."""
        data = {
            "level1": {
                "level2_array": '["a", "b"]',
                "level2_object": '{"key": "val"}',
            },
        }
        result = deep_parse_json_strings(data)
        assert result == {
            "level1": {
                "level2_array": ["a", "b"],
                "level2_object": {"key": "val"},
            },
        }

    def test_handles_json_with_nested_json_string_values(self):
        """Nested JSON inside parsed arrays is recursively parsed."""
        # After first parse we get a list containing a JSON string
        data = {"items": ['{"nested": true}', "plain"]}
        result = deep_parse_json_strings(data)
        assert result == {"items": [{"nested": True}, "plain"]}

    def test_preserves_non_json_strings(self):
        """Regular strings that aren't JSON pass through unchanged."""
        data = {
            "message": "Hello, world!",
            "code": "def foo(): pass",
        }
        result = deep_parse_json_strings(data)
        assert result == data

    def test_handles_malformed_json_gracefully(self):
        """Strings that look like JSON but are malformed pass through."""
        data = {
            "bad_array": "[not valid json",
            "bad_object": "{also broken",
        }
        result = deep_parse_json_strings(data)
        assert result == data

    def test_real_world_validation_result_example(self):
        """Simulate the ValidationResult schema issue from v2-parallel.sr."""
        # This is what the LLM might return - verification_steps as JSON string
        llm_response = {
            "valid": True,
            "reason": "Code looks good",
            "verification_steps": '["Step 1: Check syntax", "Step 2: Run tests"]',
        }
        result = deep_parse_json_strings(llm_response)
        assert result == {
            "valid": True,
            "reason": "Code looks good",
            "verification_steps": ["Step 1: Check syntax", "Step 2: Run tests"],
        }

    def test_empty_containers(self):
        """Empty containers are handled correctly."""
        assert deep_parse_json_strings({}) == {}
        assert deep_parse_json_strings([]) == []
        assert deep_parse_json_strings("[]") == []
        assert deep_parse_json_strings("{}") == {}
