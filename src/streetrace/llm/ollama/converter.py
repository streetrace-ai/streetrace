from collections.abc import Iterator
from typing import override

from ollama import ChatResponse
from ollama import Message as OllamaMessage

from streetrace.llm.history_converter import HistoryConverter
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    Role,
)

_ROLES = {
    Role.SYSTEM: "system",
    Role.CONTEXT: "user",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "tool",
}


class OllamaHistoryConverter(HistoryConverter[OllamaMessage, ChatResponse]):
    @override
    def create_history_messages(
        self,
        role: Role,
        items: list[ContentPart],
    ) -> Iterator[OllamaMessage]:
        if role not in _ROLES:
            msg = f"Unsupported role for Ollama: {role}"
            raise ValueError(msg)

        role_str = _ROLES[role]

        message = OllamaMessage(role=role_str, tool_calls=[])
        yield_message = False

        tool_results: list[OllamaMessage] = []

        for item in items:
            if isinstance(item, ContentPartText):
                message.content = item.text
                yield_message = True
            elif isinstance(item, ContentPartToolCall):
                message.tool_calls.append(
                    OllamaMessage.ToolCall(
                        function=OllamaMessage.ToolCall.Function(
                            name=item.name,
                            arguments=item.arguments,
                        ),
                    ),
                )
                yield_message = True
            elif isinstance(item, ContentPartToolResult):
                tool_results.append(
                    OllamaMessage(
                        role="tool",
                        content=item.model_dump_json(exclude_none=True),
                    ),
                )

        if yield_message:
            yield message
        yield from tool_results

    @override
    def get_response_parts(self, model_response: ChatResponse) -> Iterator[ContentPart]:
        if not model_response.message:
            return

        if model_response.message.content:
            yield ContentPartText(text=model_response.message.content)

        if model_response.message.tool_calls:
            for call in model_response.message.tool_calls:
                yield ContentPartToolCall(
                    name=call.function.name,
                    arguments=call.function.arguments,
                )

        yield ContentPartFinishReason(finish_reason="done")
