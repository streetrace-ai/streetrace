"""Tool call result."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ToolOutput(BaseModel):
    """Model for tool execution outputs."""

    type: str = Field(..., min_length=1)
    content: list | dict | str

    @classmethod
    def from_any(cls, input_value: object) -> Optional["ToolOutput"]:
        """Create a ToolOutput from any input value type.

        Args:
            input_value: Any object to convert to ToolOutput

        Returns:
            A ToolOutput instance or None if input is None

        """
        if input_value is None:
            return cls(type="none", content="")
        if isinstance(input_value, cls):
            return input_value
        if isinstance(input_value, (str, list, dict)):
            # Default type to text if it's a simple string, list, or dict
            return cls(type="text", content=input_value)
        # For other types, convert to string and use text type
        # Or raise an error if strictness is needed
        # For now, convert to string
        return cls(type="text", content=str(input_value))


class ToolCallResult(BaseModel):
    """Model for results of tool call executions."""

    success: bool | None = None
    failure: bool | None = None
    output: ToolOutput
    display_output: ToolOutput | None = None

    def get_display_output(self) -> ToolOutput:
        """Get the display output or fall back to regular output.

        Returns:
            ToolOutput to display to the user

        """
        return self.display_output or self.output

    @classmethod
    def error(
        cls,
        output: object,  # Allow any type for flexibility
        display_output: object | None = None,
    ) -> "ToolCallResult":
        """Create a failed tool call result.

        Args:
            output: The error output
            display_output: Optional user-friendly display output

        Returns:
            A ToolCallResult with failure status

        """
        return cls(
            failure=True,
            output=ToolOutput.from_any(output),
            display_output=(
                ToolOutput.from_any(display_output) if display_output else None
            ),
        )

    @classmethod
    def ok(
        cls,
        output: object,  # Allow any type for flexibility
        display_output: object | None = None,
    ) -> "ToolCallResult":
        """Create a successful tool call result.

        Args:
            output: The successful output
            display_output: Optional user-friendly display output

        Returns:
            A ToolCallResult with success status

        """
        return cls(
            success=True,
            output=ToolOutput.from_any(output),
            display_output=(
                ToolOutput.from_any(display_output) if display_output else None
            ),
        )

    @model_validator(mode="after")
    def check_success_or_failure(self) -> "ToolCallResult":
        """Validate that exactly one of success or failure is set.

        Returns:
            Self if validation passes

        Raises:
            ValueError: If both success and failure are True or both are False/None

        """
        if (
            (self.success is True and self.failure is True)
            or (self.success is False and self.failure is False)
            or (self.success is None and self.failure is None)
        ):
            msg = "One and only one of 'success' or 'failure' must be True, and the other should be False or unset."
            raise ValueError(
                msg,
            )
        return self
