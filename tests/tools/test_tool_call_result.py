import pytest
from pydantic import ValidationError

from streetrace.tools.tool_call_result import ToolCallResult, ToolOutput


class TestToolOutput:
    """Tests for the ToolOutput model."""

    def test_from_any_with_none(self) -> None:
        """Test that from_any returns None for None input."""
        tool_output_none = ToolOutput(type="none", content="")
        assert ToolOutput.from_any(None) == tool_output_none

    def test_from_any_with_tool_output_instance(self) -> None:
        """Test that from_any returns the same instance if input is ToolOutput."""
        instance = ToolOutput(type="test", content="data")
        assert ToolOutput.from_any(instance) is instance

    def test_from_any_with_string(self) -> None:
        """Test that from_any creates a text ToolOutput for string input."""
        result = ToolOutput.from_any("hello world")
        assert isinstance(result, ToolOutput)
        assert result.type == "text"
        assert result.content == "hello world"

    def test_from_any_with_list(self) -> None:
        """Test that from_any creates a text ToolOutput for list input."""
        data = [1, 2, 3]
        result = ToolOutput.from_any(data)
        assert isinstance(result, ToolOutput)
        assert result.type == "text"
        assert result.content == data

    def test_from_any_with_dict(self) -> None:
        """Test that from_any creates a text ToolOutput for dict input."""
        data = {"a": 1, "b": 2}
        result = ToolOutput.from_any(data)
        assert isinstance(result, ToolOutput)
        assert result.type == "text"
        assert result.content == data

    def test_from_any_with_other_object(self) -> None:
        """Test that from_any creates a text ToolOutput for other object types."""

        class Dummy:
            def __str__(self) -> str:
                return "dummy object"

        data = Dummy()
        result = ToolOutput.from_any(data)
        assert isinstance(result, ToolOutput)
        assert result.type == "text"
        assert result.content == "dummy object"


class TestToolCallResult:
    """Tests for the ToolCallResult model."""

    def test_ok_factory(self) -> None:
        """Test the ToolCallResult.ok factory method."""
        result = ToolCallResult.ok("Success Output", display_output="Display Output")
        assert result.success is True
        assert result.failure is None  # Should be unset
        assert result.output == ToolOutput(type="text", content="Success Output")
        assert result.display_output == ToolOutput(
            type="text",
            content="Display Output",
        )

    def test_error_factory(self) -> None:
        """Test the ToolCallResult.error factory method."""
        result = ToolCallResult.error("Error Output", display_output="Display Error")
        assert result.success is None  # Should be unset
        assert result.failure is True
        assert result.output == ToolOutput(type="text", content="Error Output")
        assert result.display_output == ToolOutput(type="text", content="Display Error")

    def test_get_display_output_fallback(self) -> None:
        """Test get_display_output falls back to output when display_output is None."""
        result = ToolCallResult.ok("Main Output")
        assert result.get_display_output() == result.output

    def test_get_display_output_preference(self) -> None:
        """Test get_display_output prefers display_output when set."""
        result = ToolCallResult.ok("Main Output", display_output="Display Output")
        assert result.get_display_output() == result.display_output

    def test_validation_success_only(self) -> None:
        """Test validation passes when only success=True."""
        try:
            ToolCallResult(
                success=True,
                output=ToolOutput(type="text", content="ok"),
            )
        except ValidationError:
            pytest.fail("Validation should pass when only success is True")

    def test_validation_failure_only(self) -> None:
        """Test validation passes when only failure=True."""
        try:
            ToolCallResult(
                failure=True,
                output=ToolOutput(type="text", content="err"),
            )
        except ValidationError:
            pytest.fail("Validation should pass when only failure is True")

    def test_validation_fails_both_true(self) -> None:
        """Test validation fails when both success and failure are True."""
        with pytest.raises(ValidationError) as excinfo:
            ToolCallResult(
                success=True,
                failure=True,
                output=ToolOutput(type="text", content="mix"),
            )
        assert "One and only one of 'success' or 'failure' must be True" in str(
            excinfo.value,
        )

    def test_validation_fails_both_false(self) -> None:
        """Test validation fails when both success and failure are False."""
        with pytest.raises(ValidationError) as excinfo:
            ToolCallResult(
                success=False,
                failure=False,
                output=ToolOutput(type="text", content="neither"),
            )
        assert "One and only one of 'success' or 'failure' must be True" in str(
            excinfo.value,
        )

    def test_validation_fails_both_none(self) -> None:
        """Test validation fails when both success and failure are None."""
        # This requires bypassing the ok/error factories
        with pytest.raises(ValidationError) as excinfo:
            ToolCallResult(
                success=None,
                failure=None,
                output=ToolOutput(type="text", content="none state"),
            )
        assert "One and only one of 'success' or 'failure' must be True" in str(
            excinfo.value,
        )
