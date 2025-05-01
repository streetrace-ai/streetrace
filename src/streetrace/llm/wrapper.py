"""Wrapper classes for LLM API message formatting and conversation history."""

from dataclasses import field
from enum import Enum
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator


class ContentType(Enum):
    """Types of content in LLM messages."""

    TEXT = 1
    TOOL_CALL = 2
    UNKNOWN = 3
    TOOL_RESULT = 4


class ContentPartText(BaseModel):
    """Model for text content parts in messages."""

    text: str


class ContentPartToolCall(BaseModel):
    """Model for tool call content parts in messages."""

    tool_id: str | None = None
    name: str = Field(..., min_length=1)
    arguments: dict[str, Any] | None = None


class ContentPartUsage(BaseModel):
    """Model for tracking token usage in LLM calls."""

    prompt_tokens: int
    response_tokens: int


class ContentPartFinishReason(BaseModel):
    """Model for tracking completion reasons from LLM responses."""

    finish_reason: str
    finish_message: str | None = None


T = TypeVar("T")


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
            return None
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
        if self.display_output:
            return self.display_output
        return self.output

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
            display_output=ToolOutput.from_any(display_output),
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
            display_output=ToolOutput.from_any(display_output),
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


class ContentPartToolResult(BaseModel):
    """Model for tool result content parts in messages."""

    tool_id: str | None = None
    name: str = Field(..., min_length=1)
    content: ToolCallResult


ContentPart = (
    ContentPartText
    | ContentPartToolCall
    | ContentPartToolResult
    | ContentPartUsage
    | ContentPartFinishReason
)


class Role(Enum):
    """Roles in a conversation between user, model and tools."""

    SYSTEM = "system"
    USER = "user"
    CONTEXT = "context"
    MODEL = "model"
    TOOL = "tool"


class Message(BaseModel):
    """Model for a message in a conversation."""

    role: Role
    content: list[ContentPart]


class History(BaseModel):
    """Model for the conversation history."""

    system_message: str | None = None
    context: str | None = None
    conversation: list[Message] = field(default_factory=list)

    def add_message(self, role: Role, content: list[ContentPart]) -> Message | None:
        """Add a message to the conversation history.

        Args:
            role: The role of the message sender
            content: The content parts of the message

        Returns:
            The created Message object or None if content was empty

        Raises:
            TypeError: If role is not a valid Role enum

        """
        if not isinstance(role, Role):
            msg = f"Invalid role: {role}"
            raise TypeError(msg)
        if not content:
            return None
        message = Message(role=role, content=content)
        self.conversation.append(message)
        return message
