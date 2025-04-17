from dataclasses import field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator


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
    name: str
    arguments: Dict[str, Any]


class ToolOutput(BaseModel):
    type: str
    content: list | dict | str

    @staticmethod
    def from_any(input_value: any) -> "ToolOutput":
        if input_value is None:
            return None
        elif isinstance(input_value, ToolOutput):
            return input_value
        else:
            assert isinstance(input_value, str) or isinstance(input_value, list) or isinstance(input_value, dict), f"Invalid input for ToolOutput: {type(input_value)}"
            return ToolOutput(type="text", content=input_value)


class ToolCallResult(BaseModel):
    success: Optional[bool] = None
    failure: Optional[bool] = None
    output: ToolOutput
    display_output: Optional[ToolOutput] = None

    def get_display_output(self) -> ToolOutput:
        if self.display_output:
            return self.display_output
        return self.output

    @staticmethod
    def error(
        output: list | dict | str | ToolOutput, display_output: Optional[list | dict | str | ToolOutput] = None
    ) -> "ToolCallResult":
        return ToolCallResult(
            failure=True,
            output=ToolOutput.from_any(output),
            display_output=ToolOutput.from_any(display_output)
        )

    @staticmethod
    def ok(
        output: list | dict | str | ToolOutput, display_output: Optional[list | dict | str | ToolOutput] = None,
    ) -> "ToolCallResult":
        return ToolCallResult(
            success=True,
            output=ToolOutput.from_any(output),
            display_output=ToolOutput.from_any(display_output)
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
    name: str
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
