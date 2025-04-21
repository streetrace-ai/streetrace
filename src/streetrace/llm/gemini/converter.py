from typing import List, Optional, override
from streetrace.llm.history_converter import (
    HistoryConverter, ChunkWrapper, Role, ContentPart,
    ContentPartText, ContentPartToolCall, ContentPartToolResult
)
from google.genai import types


class GeminiChunkWrapper(ChunkWrapper[types.Part]):
    def get_text(self) -> str:
        return self.raw.text if self.raw.text else ""

    def get_tool_calls(self) -> List[ContentPartToolCall]:
        if self.raw.function_call:
            return [ContentPartToolCall(
                id=self.raw.function_call.id or "tool-call",
                name=self.raw.function_call.name,
                arguments=self.raw.function_call.args or {}
            )]
        return []

    def get_finish_message(self) -> Optional[str]:
        return None


class GeminiHistoryConverter(HistoryConverter[types.Content, types.Part, types.Part, GeminiChunkWrapper]):
    @override
    def _provider_message(self, role: Role, items: List[types.Part]) -> types.Content:
        if role == Role.CONTEXT:
            role = Role.USER
        if role != Role.SYSTEM:
            return types.Content(role=role.value, parts=items)

    @override
    def _common_to_request(self, item: ContentPart) -> types.Part:
        if isinstance(item, ContentPartText):
            return types.Part.from_text(text=item.text)
        elif isinstance(item, ContentPartToolCall):
            return types.Part.from_function_call(
                name=item.name,
                args=item.arguments)
        elif isinstance(item, ContentPartToolResult):
            return types.Part.from_function_response(
                name=item.name,
                response=item.content.model_dump(exclude_none=True)
            )
        raise TypeError(f"Unsupported content type for Gemini request: {type(item)}")
