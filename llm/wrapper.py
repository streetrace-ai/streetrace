
import abc
from dataclasses import dataclass, field
from typing import Any, Generic, Dict, List, Optional, TypeVar
from enum import Enum

from pydantic import BaseModel

# class syntax
class ContentType(Enum):
    TEXT = 1
    TOOL_CALL = 2
    UNKNOWN = 3
    TOOL_RESULT = 4

class ContentPartText(BaseModel):
    text: str

class ContentPartToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]

class ContentPartToolResult(BaseModel):
    id: str
    name: str
    content: Dict[str, Any]

ContentPart = ContentPartText | ContentPartToolCall | ContentPartToolResult

class ToolResult(BaseModel):
    tool_call: ContentPartToolCall
    tool_result: ContentPartToolResult

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
        self.conversation.append(Message(role = role, content = content))