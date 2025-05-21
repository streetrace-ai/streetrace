"""Implement the compact command for summarizing conversation history.

This module defines the CompactCommand class which allows users to compact
the current conversation history to reduce token usage while maintaining context.
"""

# Import Application for type hint only
from typing import override

from google.adk.events import Event
from google.adk.models.llm_request import LlmRequest
from google.genai import types as genai_types

from streetrace.args import Args
from streetrace.commands.base_command import Command
from streetrace.llm_interface import LlmInterface
from streetrace.log import get_logger
from streetrace.messages import COMPACT
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus
from streetrace.workflow.supervisor import SessionManager

logger = get_logger(__name__)


def _dont_use_tools() -> None:
    """Address litellm.UnsupportedParamsError.

    Anthropic doesn't support tool calling without `tools=` param specified.

    Never call this tool.
    """
    return


class CompactCommand(Command):
    """Command to compact/summarize the conversation history to reduce token usage."""

    def __init__(
        self,
        ui_bus: UiBus,
        args: Args,
        session_manager: SessionManager,
        system_context: SystemContext,
        llm_interface: LlmInterface,
    ) -> None:
        """Initialize a new instance of ResetSessionCommand."""
        self.args = args
        self.ui_bus = ui_bus
        self.session_manager = session_manager
        self.system_context = system_context
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
        import litellm

        # allow ADK to feed a fake tool to model in case it needs one
        # TODO(krmrn42): Find a workaround as importing litellm directly takes time.
        litellm.modify_params = True

        logger.info("Executing compact command.")
        current_session = self.session_manager.get_current_session()
        if not current_session or not current_session.events:
            self.ui_bus.dispatch_ui_update(
                ui_events.Info("No history available to compact."),
            )
            return

        self.ui_bus.dispatch_ui_update(
            ui_events.Info("Compacting conversation history..."),
        )

        contents = [
            event.content for event in current_session.events if event.content
        ] + [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=COMPACT)],
            ),
        ]

        logger.info("Requesting conversation summary from LLM")

        summary_message_parts: list[str] = []
        llm_request = LlmRequest(
            model=self.args.model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=self.system_context.get_system_message(),
            ),
        )
        async for response in self.llm_interface.get_adk_llm().generate_content_async(
            llm_request=llm_request,
            stream=False,
        ):
            # Get the summary message from the response
            if response.content and response.content.parts:
                summary_message_parts.extend(
                    [part.text for part in response.content.parts if part.text],
                )
            if response.partial:
                continue

        summary_message = "".join(summary_message_parts)
        if summary_message:
            self.ui_bus.dispatch_ui_update(ui_events.Info(summary_message))
            new_events = [
                Event(
                    author="user",
                    content=genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text=summary_message)],
                    ),
                ),
            ]
            self.session_manager.replace_current_session_events(new_events)
            self.ui_bus.dispatch_ui_update(
                ui_events.Info("Session compacted successfully."),
            )
        else:
            self.ui_bus.dispatch_ui_update(
                ui_events.Warn(
                    "The last message did not respond, skipping compact. "
                    "Please report or fix in code if that's not right.",
                ),
            )
            logger.error("LLM response was not in the expected format for summary.")
