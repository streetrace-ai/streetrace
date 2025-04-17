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
    content: str | dict


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
    def error(output: str | ToolOutput, display_output: Optional[str | ToolOutput] = None) -> "ToolCallResult":
        if isinstance(output, str):
            output = ToolOutput(type="text", content=output)
        if isinstance(display_output, str):
            display_output = ToolOutput(type="text", content=display_output)
        return ToolCallResult(failure=True, output=output, display_output=display_output)

    @staticmethod
    def ok(output: ToolOutput | str | dict, display_output: Optional[ToolOutput | str | dict] = None) -> "ToolCallResult":
        if not isinstance(output, ToolOutput):
            output = ToolOutput(type="text", content=output)
        if not isinstance(display_output, ToolOutput):
            display_output = ToolOutput(type="text", content=display_output)
        return ToolCallResult(success=True, output=output, display_output=display_output)

    @model_validator(mode='after')
    def check_success_or_failure(self):
        if (self.success is True and self.failure is True) or (self.success is False and self.failure is False) or (self.success is None and self.failure is None):
            raise ValueError("One and only one of 'success' or 'failure' must be True, and the other should be False or unset.")
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
