from collections.abc import Iterator
from typing import override

from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    TextBlockParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)
from anthropic.types import (
    Message as AnthropicMessage,
)

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

_CLAUD_ROLES = {
    Role.SYSTEM: "system",
    Role.CONTEXT: "user",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "user",  # Tool results are sent in a user message in Anthropic
}


class AnthropicHistoryConverter(HistoryConverter[MessageParam, AnthropicMessage]):
    @override
    def create_history_messages(
        self,
        role: Role,
        items: list[ContentPart],
    ) -> Iterator[MessageParam]:
        if role != Role.SYSTEM:
            history_item_parts: list[ContentBlockParam] = []
            for item in items:
                if isinstance(item, ContentPartText):
                    history_item_parts.append(
                        TextBlockParam(type="text", text=item.text),
                    )
                elif isinstance(item, ContentPartToolCall):
                    history_item_parts.append(
                        ToolUseBlockParam(
                            id=item.id or "tool-call",
                            name=item.name,
                            input=item.arguments,
                            type="tool_use",
                        ),
                    )
                elif isinstance(item, ContentPartToolResult):
                    history_item_parts.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=item.id or "tool-call",
                            content=item.content.output.model_dump_json(
                                exclude_none=True,
                            ),
                            is_error=item.content.failure == True,  # noqa: E712
                        ),
                    )
            yield MessageParam(role=_CLAUD_ROLES[role], content=history_item_parts)

    @override
    def get_response_parts(
        self,
        model_response: AnthropicMessage,
    ) -> Iterator[ContentPart]:
        if not model_response.content:
            return

        for part in model_response.content:
            if part.type == "text":
                yield ContentPartText(text=part.text)
            elif part.type == "tool_use":
                yield ContentPartToolCall(
                    id=part.id,
                    name=part.name,
                    arguments=part.input or {},
                )

        if model_response.usage:
            yield ContentPartUsage(
                prompt_tokens=model_response.usage.input_tokens or 0,
                response_tokens=model_response.usage.output_tokens or 0,
            )

        if model_response.stop_reason is not None:
            yield ContentPartFinishReason(finish_reason=model_response.stop_reason)
