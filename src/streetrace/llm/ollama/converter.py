from typing import Iterable, List, Optional, override
from streetrace.llm.history_converter import (
    HistoryConverter, ChunkWrapper, Role, ContentPart,
    ContentPartText, ContentPartToolCall, ContentPartToolResult
)
from ollama import Message as OllamaMessage

_ROLES = {
    Role.SYSTEM: "system",
    Role.CONTEXT: "user",
    Role.USER: "user",
    Role.MODEL: "assistant",
    Role.TOOL: "tool",
}

class OllamaChunkWrapper(ChunkWrapper[OllamaMessage]):
    def get_text(self) -> str:
        return self.raw.content or ""

    def get_tool_calls(self) -> List[ContentPartToolCall]:
        if not self.raw.tool_calls:
            return []
        return [
            ContentPartToolCall(
                id=call.function.name,  # Ollama doesn't use explicit ID; fallback to name
                name=call.function.name,
                arguments=call.function.arguments
            ) for call in self.raw.tool_calls
        ]

    def get_finish_message(self) -> Optional[str]:
        return None


class OllamaHistoryConverter(HistoryConverter[dict, dict, OllamaMessage, OllamaChunkWrapper]):
    @override
    def _provider_message(self, role: Role, items: List[dict]) -> dict:
        if role not in _ROLES:
            raise ValueError(f"Unsupported role for Ollama: {role}")

        role_str = _ROLES[role]

        message: dict = {
            "role": role_str,
        }

        if role_str == "tool":
            tool_call_id = items[0].get("id") or "tool-call"
            message.update({
                "tool_call_id": tool_call_id,
                "content": items[0].get("content") or ""
            })
        else:
            message["content"] = items[0].get("text") if items else ""
            if "tool_calls" in items[0]:
                message["tool_calls"] = items[0]["tool_calls"]

        return message

    @override
    def _common_to_request(self, item: ContentPart) -> dict:
        if isinstance(item, ContentPartText):
            return {"text": item.text}
        elif isinstance(item, ContentPartToolCall):
            return {
                "tool_calls": [{
                    "function": {
                        "name": item.name,
                        "arguments": item.arguments
                    }
                }]
            }
        elif isinstance(item, ContentPartToolResult):
            return {
                "id": item.id or "tool-call",
                "content": item.content.model_dump_json(exclude_none=True)
            }
        raise TypeError(f"Unsupported content part type for Ollama request: {type(item)}")
