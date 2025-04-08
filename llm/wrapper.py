
import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List
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

class ChunkWrapper(abc.ABC):
    raw: Any

    def type(self) -> ContentType:
        pass

    def get_text(self) -> str:
        pass

    def get_tool_calls(self) -> List[ContentPartToolCall]:
        pass

@dataclass
class ToolResult:
    chunk: ChunkWrapper
    tool_call: ContentPartToolCall
    tool_result: ContentPartToolResult

@dataclass
class Message():
    role: str
    content: List[ContentPart]

@dataclass
class History():
    system_message: str
    context: str
    conversation: List[Message] = field(default_factory=list)

    def add_message(self, role: str, content: List[ContentPart]):
        self.conversation.append(Message(role, content))