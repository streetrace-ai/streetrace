
import abc
from dataclasses import dataclass, field
from typing import Any, Generic, Dict, List, TypeVar
from enum import Enum

# class syntax
class ContentType(Enum):
    TEXT = 1
    TOOL_CALL = 2
    UNKNOWN = 3
    TOOL_RESULT = 4

@dataclass
class ContentPartText():
    text: str

@dataclass
class ContentPartToolCall():
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class ContentPartToolResult():
    id: str
    name: str
    content: Dict[str, Any]

ContentPart = ContentPartText | ContentPartToolCall | ContentPartToolResult

@dataclass
class ToolResult:
    tool_call: ContentPartToolCall
    tool_result: ContentPartToolResult

class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    MODEL = "model"
    TOOL = "tool"

@dataclass
class Message():
    role: Role
    content: List[ContentPart]

@dataclass
class History():
    system_message: str
    context: str
    conversation: List[Message] = field(default_factory=list)

    def add_message(self, role: Role, content: List[ContentPart]):
        self.conversation.append(Message(role, content))