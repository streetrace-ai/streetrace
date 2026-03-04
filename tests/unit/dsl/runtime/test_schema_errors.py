"""Unit tests for schema-related error classes.

Test JSONParseError and SchemaValidationError exceptions.
"""

import pytest

from streetrace.dsl.runtime.errors import (
    DslRuntimeError,
    JSONParseError,
    SchemaValidationError,
)


class TestJSONParseError:
    """Test the JSONParseError exception class."""

    def test_inherits_from_dsl_runtime_error(self):
        """Test that JSONParseError inherits from DslRuntimeError."""
        error = JSONParseError(raw_response="invalid", parse_error="Not JSON")
        assert isinstance(error, DslRuntimeError)
        assert isinstance(error, Exception)

    def test_stores_raw_response(self):
        """Test that raw_response is stored on the exception."""
        raw = '{"incomplete": '
        error = JSONParseError(raw_response=raw, parse_error="Unexpected end")
        assert error.raw_response == raw

    def test_stores_parse_error(self):
        """Test that parse_error is stored on the exception."""
        error = JSONParseError(
            raw_response="not json", parse_error="Expecting value at position 0",
        )
        assert error.parse_error == "Expecting value at position 0"

    def test_message_includes_parse_error(self):
        """Test that exception message includes the parse error."""
        error = JSONParseError(
            raw_response="invalid", parse_error="Invalid syntax at line 1",
        )
        assert "Invalid syntax at line 1" in str(error)
        assert "Failed to parse JSON" in str(error)

    def test_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(JSONParseError) as exc_info:
            raise JSONParseError(raw_response="bad", parse_error="error")

        assert exc_info.value.raw_response == "bad"
        assert exc_info.value.parse_error == "error"


class TestSchemaValidationError:
    """Test the SchemaValidationError exception class."""

    def test_inherits_from_dsl_runtime_error(self):
        """Test that SchemaValidationError inherits from DslRuntimeError."""
        error = SchemaValidationError(
            schema_name="TestSchema", errors=["error"], raw_response="{}",
        )
        assert isinstance(error, DslRuntimeError)
        assert isinstance(error, Exception)

    def test_stores_schema_name(self):
        """Test that schema_name is stored on the exception."""
        error = SchemaValidationError(
            schema_name="CodeReviewResult", errors=["missing field"], raw_response="{}",
        )
        assert error.schema_name == "CodeReviewResult"

    def test_stores_errors_list(self):
        """Test that errors list is stored on the exception."""
        errors = ["missing field 'name'", "wrong type for 'count'"]
        error = SchemaValidationError(
            schema_name="TestSchema", errors=errors, raw_response="{}",
        )
        assert error.errors == errors
        assert len(error.errors) == 2

    def test_stores_raw_response(self):
        """Test that raw_response is stored on the exception."""
        raw = '{"partial": "data"}'
        error = SchemaValidationError(
            schema_name="TestSchema", errors=["error"], raw_response=raw,
        )
        assert error.raw_response == raw

    def test_message_includes_schema_name(self):
        """Test that exception message includes schema name."""
        error = SchemaValidationError(
            schema_name="MySchema", errors=["some error"], raw_response="{}",
        )
        assert "MySchema" in str(error)
        assert "Schema validation failed" in str(error)

    def test_message_joins_multiple_errors(self):
        """Test that multiple errors are joined with semicolons."""
        errors = ["missing 'name'", "invalid 'age'", "wrong type"]
        error = SchemaValidationError(
            schema_name="TestSchema", errors=errors, raw_response="{}",
        )
        message = str(error)
        assert "missing 'name'" in message
        assert "invalid 'age'" in message
        assert "wrong type" in message
        assert "; " in message  # Errors joined with semicolon

    def test_message_with_single_error(self):
        """Test message format with a single error."""
        error = SchemaValidationError(
            schema_name="TestSchema", errors=["one error"], raw_response="{}",
        )
        assert "one error" in str(error)
        assert "TestSchema" in str(error)

    def test_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(SchemaValidationError) as exc_info:
            raise SchemaValidationError(
                schema_name="TestSchema", errors=["test error"], raw_response="{}",
            )

        assert exc_info.value.schema_name == "TestSchema"
        assert exc_info.value.errors == ["test error"]

    def test_empty_errors_list(self):
        """Test behavior with empty errors list."""
        error = SchemaValidationError(
            schema_name="TestSchema", errors=[], raw_response="{}",
        )
        assert error.errors == []
        # Message should still work, just with empty errors part
        assert "TestSchema" in str(error)
