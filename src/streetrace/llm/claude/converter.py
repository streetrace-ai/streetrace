from typing import Iterable, List, Optional, override
from streetrace.llm.history_converter import (
    HistoryConverter, ChunkWrapper, Role, ContentPart, ContentPartText,
    ContentPartToolCall, ContentPartToolResult
)
from anthropic.types import (
    MessageParam, TextBlockParam, ToolUseBlockParam,
    ToolResultBlockParam, ContentBlock, ContentBlockParam
)

_CLAUD_ROLES = {
    Role.SYSTEM: "system",
    Role.CONTEXT: "user",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "user",  # Tool results are sent in a user message in Claude
}

class AnthropicChunkWrapper(ChunkWrapper[ContentBlock]):
    def get_text(self) -> str:
        if self.raw.type == "text":
            return self.raw.text
        return ""

    def get_tool_calls(self) -> List[ContentPartToolCall]:
        if self.raw.type == "tool_use":
            return [ContentPartToolCall(
                id=self.raw.id,
                name=self.raw.name,
                arguments=self.raw.input
            )]
        return []

    def get_finish_message(self) -> Optional[str]:
        return None


class AnthropicHistoryConverter(HistoryConverter[MessageParam, ContentBlockParam, ContentBlock, AnthropicChunkWrapper]):
    @override
    def _provider_message(self, role: Role, items: List[ContentBlockParam]) -> MessageParam:
        if role != Role.SYSTEM:
            return MessageParam(role=_CLAUD_ROLES[role], content=items)

    @override
    def _common_to_request(self, item: ContentPart) -> ContentBlockParam:
        if isinstance(item, ContentPartText):
            return TextBlockParam(type="text", text=item.text)
        elif isinstance(item, ContentPartToolCall):
            return ToolUseBlockParam(id=item.id or "tool-call", name=item.name, input=item.arguments, type="tool_use")
        elif isinstance(item, ContentPartToolResult):
            return ToolResultBlockParam(
                type="tool_result",
                tool_use_id=item.id or "tool-call",
                content=item.content.output.model_dump_json(exclude_none=True),
                is_error=item.content.failure == True  # noqa: E712
            )
        raise TypeError(f"Unsupported content type for request conversion: {type(item)}")
