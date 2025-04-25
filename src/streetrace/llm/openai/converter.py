import json
from collections.abc import Iterator
from typing import override

from openai.types import chat

from streetrace.llm.history_converter import HistoryConverter
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    ContentPartUsage,
    Role,
)

_ROLES = {
    Role.SYSTEM: "system",
    Role.CONTEXT: "user",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "tool",
}


class OpenAIHistoryConverter(
    HistoryConverter[chat.ChatCompletionMessageParam, chat.ChatCompletion],
):
    @override
    def create_history_messages(
        self,
        role: Role,
        items: list[ContentPart],
    ) -> Iterator[chat.ChatCompletionMessageParam]:
        if role not in _ROLES:
            msg = f"Unsupported role for Ollama: {role}"
            raise ValueError(msg)

        role_str = _ROLES[role]

        message = {"role": role_str}
        yield_message = False

        tool_results: list[chat.ChatCompletionToolMessageParam] = []

        for item in items:
            if isinstance(item, ContentPartText):
                message["content"] = item.text
                yield_message = True
            elif isinstance(item, ContentPartToolCall):
                if "tool_calls" not in message:
                    message["tool_calls"] = []
                message["tool_calls"].append(
                    chat.ChatCompletionMessageToolCallParam(
                        type="function",
                        id=item.id,
                        function={
                            "name": item.name,
                            "arguments": json.dumps(item.arguments),
                        },
                    ),
                )
                yield_message = True
            elif isinstance(item, ContentPartToolResult):
                tool_results.append(
                    chat.ChatCompletionToolMessageParam(
                        role="tool",
                        tool_call_id=item.id,
                        content=item.model_dump_json(exclude_none=True),
                    ),
                )

        if yield_message:
            yield message
        yield from tool_results

    @override
    def get_response_parts(
        self,
        response: chat.ChatCompletion,
    ) -> Iterator[ContentPart]:
        if not response.choices:
            return

        choice = response.choices[0]

        if choice.message.content:
            yield ContentPartText(text=choice.message.content)

        if choice.message.tool_calls:
            for call in choice.message.tool_calls:
                yield ContentPartToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=json.loads(call.function.arguments),
                )

        if response.usage:
            yield ContentPartUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                response_tokens=response.usage.completion_tokens or 0,
            )

        if choice.finish_reason:
            yield ContentPartFinishReason(finish_reason=choice.finish_reason)
