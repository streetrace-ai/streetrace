from typing import Iterable, List, Optional
from streetrace.llm.history_converter import (
    HistoryConverter, ChunkWrapper, Role, ContentPart,
    ContentPartText, ContentPartToolCall, ContentPartToolResult
)
from google.genai import types

from streetrace.llm.wrapper import ToolCallResult


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
    def create_chunk_wrapper(self, chunk: types.Part) -> GeminiChunkWrapper:
        return super().create_chunk_wrapper(chunk)

    def create_provider_history(self, history):
        return super().create_provider_history(history)

    def to_provider_history_items(self, turn):
        return super().to_provider_history_items(turn)

    def to_common_history_items(self, turn):
        return super().to_common_history_items(turn)

    def _provider_message(self, role: Role, items: List[types.Part]) -> types.Content:
        return types.Content(role=role.value, parts=items)

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

    def _response_to_request(self, item: types.Part) -> Optional[types.Part]:
        return item

    def _response_to_common(self, item: types.Part) -> Iterable[ContentPart]:
        results = []
        if item.text:
            results.append(ContentPartText(text=item.text))
        if item.function_call:
            results.append(ContentPartToolCall(
                id=item.function_call.id,
                name=item.function_call.name,
                arguments=item.function_call.args
            ))
        if item.function_response:
            results.append(ContentPartToolResult(
                id=item.function_response.id,
                name=item.function_response.name,
                content=ToolCallResult.model_validate(item.function_response.response)
            ))
        return results
