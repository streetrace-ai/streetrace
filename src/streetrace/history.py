"""Wrapper classes for LLM API message formatting and conversation history."""

from dataclasses import field
from enum import Enum

import litellm
from pydantic import BaseModel

from streetrace.tools.tool_call_result import ToolCallResult


class Role(str, Enum):
    """Roles in a conversation between user, model and tools."""

    @staticmethod
    def _generate_next_value_(
        name: str,
        _start: int,
        _count: int,
        _last_values: list[str],
    ) -> str:
        return name

    SYSTEM = "system"
    USER = "user"
    CONTEXT = "user"  # noqa: PIE796
    MODEL = "assistant"
    TOOL = "tool"


class History(BaseModel):
    """Model for the conversation history."""

    system_message: str | None = None
    context: str | None = None
    messages: list[litellm.Message] = field(default_factory=list)

    def get_all_messages(self) -> list[litellm.Message]:
        """Create messages for the conversation history.

        Returns:
            List of litellm.Message objects

        """
        messages = []
        if self.system_message:
            messages.append(
                litellm.Message(role=Role.SYSTEM, content=self.system_message),
            )
        if self.context:
            messages.append(
                litellm.Message(role=Role.CONTEXT, content=self.context),
            )
        return messages + self.messages

    def add_assistant_message(self, message: litellm.Message) -> None:
        """Add an assistant message to the conversation history.

        Args:
            message: The content of the assistant message

        """
        self.messages.append(message)

    def add_assistant_message_test(
        self,
        content: str,
        tool_call: dict[str, any] | None = None,
    ) -> None:
        """Add an assistant message to the conversation history.

        Args:
            content: The content of the assistant message
            tool_call: Optional tool call to add to the assistant message

        """
        tool_calls_part = []
        if tool_call:
            tool_calls_part = [
                litellm.ChatCompletionMessageToolCall(
                    id=tool_call["tool_call_id"],
                    type="function",
                    function={
                        "name": tool_call["tool_name"],
                        "arguments": tool_call["arguments"],
                    },
                ),
            ]
        self.messages.append(
            litellm.Message(
                role="assistant",
                content=content,
                tool_calls=tool_calls_part,
            ),
        )

    def add_user_message(self, content: str) -> None:
        """Add user message to the conversation history.

        Args:
            content: The content of the user message

        """
        self.messages.append(
            litellm.Message(role="user", content=content),
        )

    def add_context_message(self, title: str, content: str) -> None:
        """Add user message to the conversation history.

        Args:
            title: The title of the context item
            content: The content of the context item

        """
        self.messages.append(
            litellm.Message(role="user", content=f"---\n# {title}\n\n{content}\n\n---"),
        )

    def add_tool_message(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_result: ToolCallResult,
    ) -> None:
        """Add user message to the conversation history.

        Args:
            tool_call_id: The ID of the tool call
            tool_name: The name of the tool
            tool_result: The result of the tool call

        """
        self.messages.append(
            litellm.Message(
                role="tool",
                tool_call_id=tool_call_id,
                name=tool_name,
                content=tool_result.model_dump_json(exclude_none=True),
            ),
        )
