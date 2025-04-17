from dataclasses import field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# class syntax
class ContentType(Enum):
    TEXT = 1
    TOOL_CALL = 2
    UNKNOWN = 3
    TOOL_RESULT = 4


class ContentPartText(BaseModel):
    text: str


class ContentPartToolCall(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    arguments: Optional[Dict[str, Any]] = None


class ToolOutput(BaseModel):
    type: str = Field(..., min_length=1)
    content: list | dict | str

    @classmethod
    def from_any(cls, input_value: Any) -> Optional["ToolOutput"]:
        if input_value is None:
            return None
        elif isinstance(input_value, cls):
            return input_value
        elif isinstance(input_value, (str, list, dict)):
            # Default type to text if it's a simple string, list, or dict
            return cls(type="text", content=input_value)
        else:
            # For other types, convert to string and use text type
            # Or raise an error if strictness is needed
            # For now, convert to string
            return cls(type="text", content=str(input_value))


class ToolCallResult(BaseModel):
    success: Optional[bool] = None
    failure: Optional[bool] = None
    output: ToolOutput
    display_output: Optional[ToolOutput] = None

    def get_display_output(self) -> ToolOutput:
        if self.display_output:
            return self.display_output
        return self.output

    @classmethod
    def error(
        cls,
        output: Any,  # Allow any type for flexibility
        display_output: Optional[Any] = None,
    ) -> "ToolCallResult":
        return cls(
            failure=True,
            output=ToolOutput.from_any(output),
            display_output=ToolOutput.from_any(display_output),
        )

    @classmethod
    def ok(
        cls,
        output: Any,  # Allow any type for flexibility
        display_output: Optional[Any] = None,
    ) -> "ToolCallResult":
        return cls(
            success=True,
            output=ToolOutput.from_any(output),
            display_output=ToolOutput.from_any(display_output),
        )

    @model_validator(mode="after")
    def check_success_or_failure(self):
        if (
            (self.success is True and self.failure is True)
            or (self.success is False and self.failure is False)
            or (self.success is None and self.failure is None)
        ):
            raise ValueError(
                "One and only one of 'success' or 'failure' must be True, and the other should be False or unset."
            )
        return self


class ContentPartToolResult(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    content: ToolCallResult


ContentPart = ContentPartText | ContentPartToolCall | ContentPartToolResult


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    MODEL = "model"
    TOOL = "tool"


class Message(BaseModel):
    role: Role
    content: List[ContentPart]


class History(BaseModel):
    system_message: Optional[str] = None
    context: Optional[str] = None
    conversation: List[Message] = field(default_factory=list)

    def add_message(self, role: Role, content: List[ContentPart]):
        if not isinstance(role, Role):
            raise ValueError(f"Invalid role: {role}")
        self.conversation.append(Message(role=role, content=content))
