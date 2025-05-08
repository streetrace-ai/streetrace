"""Implement the history command for displaying conversation history.

This module defines the HistoryCommand class which allows users to view
the current conversation history in the interactive mode.
"""

from typing import override

from streetrace.commands.base_command import Command
from streetrace.history import History, HistoryManager, Role
from streetrace.log import get_logger
from streetrace.tools.tool_call_result import ToolCallResult
from streetrace.ui.console_ui import ConsoleUI

logger = get_logger(__name__)

_MAX_CONTEXT_PREVIEW_LENGTH = 200
"""Maximum length for context preview."""

class HistoryCommand(Command):
    """Command to display the conversation history."""

    def __init__(self, ui: ConsoleUI, history_manager: HistoryManager) -> None:
        """Initialize a new instance of HistoryCommand."""
        self.ui = ui
        self.history_manager = history_manager

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["history"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Display the conversation history."

    @override
    async def execute_async(self) -> None:
        """Execute the history display action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Executing history command.")
        history = self.history_manager.get_history()
        if not history:
            self.ui.display_warning("No history available yet.")
            return

        self._display_history_header(history=history)
        self._display_history_messages(history=history)

        self.ui.display_info("--- End History ---")


    def _display_history_header(self, history: History) -> None:
        """Display the header part of the history (system message, context)."""
        self.ui.display_info("\n--- Conversation History ---")
        if history.system_message:
            self.ui.display_system_message(history.system_message)
        if history.context:
            context_str = str(history.context)
            display_context = (
                context_str[:_MAX_CONTEXT_PREVIEW_LENGTH] + "..."
                if len(context_str) > _MAX_CONTEXT_PREVIEW_LENGTH
                else context_str
            )
            self.ui.display_context_message(display_context)

    def _display_history_messages(self, history: History) -> None:
        """Display the messages part of the history."""
        if not history.messages:
            self.ui.display_info("No messages in history yet.")
        else:
            for msg in history.messages:
                if msg.role == Role.USER and msg.content:
                    self.ui.display_history_user_message(msg.content)
                elif msg.role == Role.MODEL:
                    if msg.content:
                        self.ui.display_history_assistant_message(msg.content)
                    if msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            self.ui.display_tool_call(tool_call)
                elif msg.role == Role.TOOL and msg.content:
                    tool_result = ToolCallResult.model_validate_json(msg.content)
                    self.ui.display_tool_result(msg.name, tool_result)
