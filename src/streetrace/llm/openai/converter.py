import json
from typing import Iterable, List, Optional, Union
from streetrace.llm.history_converter import (
    HistoryConverter, ChunkWrapper
)
from openai.types import chat

from streetrace.llm.wrapper import Message, ContentPart, ContentPartText, ContentPartToolCall, ContentPartToolResult, Role

_ROLES = {
    Role.SYSTEM: "system",
    Role.CONTEXT: "user",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "tool",
}

class OpenAIChunkWrapper(ChunkWrapper[chat.ChatCompletionAssistantMessageParam]):
    """The actual messages are chat.ChatCompletionAssistantMessageParam.

    ChoiceDelta is only used to render streamed content.

    Args:
        ChunkWrapper (_type_): _description_
    """
    def get_text(self) -> str:
        return self.raw.get('content', '')

    def get_tool_calls(self) -> List[ContentPartToolCall]:
        if not self.raw.get('tool_calls'):
            return []
        return [
            ContentPartToolCall(
                id=call["id"],
                name=call["function"]["name"],
                arguments=json.loads(call["function"]["arguments"])
            ) for call in self.raw.get('tool_calls')
        ]

    def get_finish_message(self) -> Optional[str]:
        return None


class OpenAIHistoryConverter(HistoryConverter[
    chat.ChatCompletionMessageParam,
    Union[chat.ChatCompletionContentPartTextParam, chat.ChatCompletionMessageToolCallParam],
    chat.ChatCompletionAssistantMessageParam,
    OpenAIChunkWrapper
]):
    def to_provider_history_items(
        self,
        turn: List[Message],
    ) -> Iterable[chat.ChatCompletionMessageParam]:
        if turn:
            for message in turn:
                tool_result_parts = [part for part in message.content if isinstance(part, ContentPartToolResult)]
                other_parts = [part for part in message.content if not isinstance(part, ContentPartToolResult)]
                if other_parts:
                    yield self._provider_message(message.role, [
                        self._common_to_request(part) for part in other_parts
                    ])
                if tool_result_parts:
                    for part in tool_result_parts:
                        yield self._tool_result_message(part)

    def _provider_message(self, role: Role, items: List[Union[chat.ChatCompletionContentPartTextParam, chat.ChatCompletionMessageToolCallParam]]) -> chat.ChatCompletionMessageParam:
        if role == Role.USER or role == Role.CONTEXT:
            return {"role": "user", "content": items}
        elif role == Role.MODEL:
            content = [item for item in items if item.get('type') == "type"]
            tool_calls = [item for item in items if item.get('type') == "function"]
            return {"role": "assistant", "content": content, "tool_calls": tool_calls}
        elif role == Role.SYSTEM:
            return {"role": "system", "content": items}
        else:
            # tools are handled in to_provider_history_items
            raise ValueError(f"Unsupported role: {role}")

    def _common_to_request(self, item: ContentPart) -> Union[chat.ChatCompletionContentPartTextParam, chat.ChatCompletionMessageToolCallParam]:
        if isinstance(item, ContentPartText):
            return {"type": "text", "text": item.text}
        elif isinstance(item, ContentPartToolCall):
            return {
                "id": item.id or "tool-call",
                "function": chat.chat_completion_message_tool_call_param.Function(name=item.name, arguments=json.dumps(item.arguments)),
                "type": "function"
            }
        # tools are handled in to_provider_history_items(self, turn) -> _tool_result_message(self, tool_result)
        raise TypeError(f"Unsupported content type for OpenAI request: {type(item)}")

    def _tool_result_message(self, tool_result: ContentPartToolResult) -> chat.ChatCompletionToolMessageParam:
        return {
            "role": "tool",
            "tool_call_id": tool_result.id or "tool-call",
            "content": [{"type": "text", "text": tool_result.content.model_dump_json(exclude_none=True)}]
        }