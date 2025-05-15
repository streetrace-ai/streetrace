"""Implement the compact command for summarizing conversation history.

This module defines the CompactCommand class which allows users to compact
the current conversation history to reduce token usage while maintaining context.
"""

# Import Application for type hint only
from typing import override

from streetrace.commands.base_command import Command
from streetrace.history import History, HistoryManager
from streetrace.llm_interface import LlmInterface
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class CompactCommand(Command):
    """Command to compact/summarize the conversation history to reduce token usage."""

    def __init__(
        self,
        ui_bus: UiBus,
        history_manager: HistoryManager,
        llm_interface: LlmInterface,
    ) -> None:
        """Initialize a new instance of ClearCommand."""
        self.ui_bus = ui_bus
        self.history_manager = history_manager
        self.llm_interface = llm_interface

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["compact"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Summarize conversation history to reduce token count while maintaining context."

    @override
    async def execute_async(self) -> None:
        """Execute the history compaction action using the HistoryManager.

        Args:
            app_instance: The main Application instance.

        """
        logger.info("Executing compact command.")
        current_history = self.history_manager.get_history()
        if not current_history or not current_history.messages:
            self.ui_bus.dispatch(ui_events.Warn("No history available to compact."))
            return

        self.ui_bus.dispatch(ui_events.Info("Compacting conversation history..."))

        # Create a temporary history for the summarization request
        system_message = current_history.system_message
        context = current_history.context
        messages_as_dicts = [msg.model_dump() for msg in current_history.messages]

        summary_request_history = History(
            system_message=system_message,
            context=context,
            messages=messages_as_dicts,
        )

        summary_prompt = """Please summarize our conversation so far, describing the
goal of the conversation, detailed plan we developed, all the key points and decisions.
Mark which points of the plan are already completed and mention all relevant artifacts.

Your summary should:
1. Preserve all important information, file paths, and code changes
2. Include any important decisions or conclusions we've reached
3. Keep any critical context needed for continuing the conversation
4. Format the summary as a concise narrative

Return ONLY the summary without explaining what you're doing."""

        summary_request_history.add_user_message(summary_prompt)

        logger.info("Requesting conversation summary from LLM")

        messages = await self.llm_interface.generate_async(
            self.app_args.model,
            summary_request_history,
        )
        # Get the summary message from the response
        last_message = None
        if hasattr(messages, "choices") and messages.choices:
            last_message = messages.choices[0].message

        if last_message:
            # Create a new history with just the summary
            new_history = History(system_message=system_message, context=context)

            # Pass the whole Message object to add_assistant_message
            new_history.add_assistant_message(last_message)
            # Replace the current history
            self.history_manager.set_history(new_history)
            self.ui_bus.dispatch(ui_events.Info("History compacted successfully."))
        else:
            self.ui_bus.dispatch(ui_events.Warn(
                "The last message in history is not model, skipping compact. Please report or fix in code if that's not right.",
            ))
            logger.error("LLM response was not in the expected format for summary.")
