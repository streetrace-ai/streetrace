from collections.abc import Iterator
from typing import override

from google.genai import types

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


class GeminiHistoryConverter(HistoryConverter[types.Content, types.Content]):
    @override
    def create_history_messages(
        self,
        role: Role,
        items: list[ContentPart],
    ) -> Iterator[types.Content]:
        if role == Role.CONTEXT:
            role = Role.USER
        if role != Role.SYSTEM:
            history_item_parts: list[types.Part] = []
            for item in items:
                if isinstance(item, ContentPartText):
                    history_item_parts.append(types.Part.from_text(text=item.text))
                elif isinstance(item, ContentPartToolCall):
                    history_item_parts.append(
                        types.Part.from_function_call(
                            name=item.name,
                            args=item.arguments,
                        ),
                    )
                elif isinstance(item, ContentPartToolResult):
                    history_item_parts.append(
                        types.Part.from_function_response(
                            name=item.name,
                            response=item.content.model_dump(exclude_none=True),
                        ),
                    )
            yield types.Content(role=role.value, parts=history_item_parts)

    @override
    def get_response_parts(
        self,
        model_response: types.GenerateContentResponse,
    ) -> Iterator[ContentPart]:
        if not model_response.candidates:
            return

        if model_response.text:
            yield ContentPartText(text=model_response.text)

        candidate = model_response.candidates[0]

        for part in candidate.content.parts:
            if part.function_call:
                yield ContentPartToolCall(
                    id=part.function_call.id or "tool-call",
                    name=part.function_call.name,
                    arguments=part.function_call.args or {},
                )

        if model_response.usage_metadata:
            prompt_tokens = model_response.usage_metadata.prompt_token_count or 0
            candidates_token_count = (
                model_response.usage_metadata.candidates_token_count or 0
            )
            tool_use_prompt_token_count = (
                model_response.usage_metadata.tool_use_prompt_token_count or 0
            )
            response_tokens = candidates_token_count + tool_use_prompt_token_count
            yield ContentPartUsage(
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
            )

        if candidate.finish_reason is not None:
            msg = candidate.finish_message
            if len(model_response.candidates) > 1:
                msg += f" (there were {len(model_response.candidates)} candidates in the response: "
                msg += (
                    ", ".join(
                        [f"'{c.finish_reason}'" for c in model_response.candidates[1:]],
                    )
                    + ")"
                )
            yield ContentPartFinishReason(
                finish_reason=str(candidate.finish_reason),
                finish_message=msg,
            )
