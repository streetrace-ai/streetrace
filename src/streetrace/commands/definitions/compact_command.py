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
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.messages import COMPACT
from streetrace.session_service import SessionManager
from streetrace.system_context import SystemContext
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class CompactCommand(Command):
    """Command to compact/summarize the conversation history to reduce token usage."""

    def __init__(
        self,
        ui_bus: UiBus,
        args: Args,
        session_manager: SessionManager,
        system_context: SystemContext,
        model_factory: ModelFactory,
    ) -> None:
        """Initialize a new instance of ResetSessionCommand."""
        self.args = args
        self.ui_bus = ui_bus
        self.session_manager = session_manager
        self.system_context = system_context
        self.model_factory = model_factory

    @property
    def names(self) -> list[str]:
        """Command invocation names."""
        return ["compact"]

    @property
    def description(self) -> str:
        """Command description."""
        return "Summarize conversation history and replace history with the summary."

    async def _summarize_contents(
        self,
        contents: list[genai_types.Content],
    ) -> tuple[str | None, str | None]:
        contents.append(
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=COMPACT)],
            ),
        )
        llm_request = LlmRequest(
            model=self.args.model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=self.system_context.get_system_message(),
            ),
        )
        role: str | None = None
        summary_message_parts: list[str] = []
        logger.info("Requesting conversation summary from LLM")
        async for (
            response
        ) in self.model_factory.get_current_model().generate_content_async(
            llm_request=llm_request,
            stream=False,
        ):
            logger.info("receiving response %s", response)
            if response.partial:
                continue
            # Get the summary message from the response
            if response.content and response.content.parts:
                role = response.content.role
                summary_message_parts.extend(
                    [part.text for part in response.content.parts if part.text],
                )
        summary_message = (
            "".join(summary_message_parts) if summary_message_parts else None
        )
        return role, summary_message

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

        last_non_user_author: str | None = None
        compact_session_events: list[Event] = []
        # tail_events accumulates the tail non-final events
        tail_events: list[Event] = []
        for event in current_session.events:
            if event.author != "user":
                last_non_user_author = event.author
            if event.author == "user" or event.is_final_response():
                tail_events.clear()
                compact_session_events.append(event.model_copy())
            else:
                tail_events.append(event.model_copy())

        if tail_events:
            contents = [
                event.content for event in current_session.events if event.content
            ]
            if not contents:
                self.ui_bus.dispatch_ui_update(
                    ui_events.Info("Nothing to compact."),
                )
                return
            role, summary_message = await self._summarize_contents(contents)
            # TODO(krmrn42): Somewhere in this process we lose user's message
            if summary_message:
                # TODO(krmrn42): Compact result is still not displayed as markdown.
                self.ui_bus.dispatch_ui_update(ui_events.Markdown(summary_message))

                compact_session_events.append(
                    Event(
                        author=last_non_user_author or "assistant",
                        content=genai_types.Content(
                            role=role,
                            parts=[genai_types.Part.from_text(text=summary_message)],
                        ),
                    ),
                )
            else:
                self.ui_bus.dispatch_ui_update(
                    ui_events.Warn(
                        "The session could not be compacted, see logs for details. "
                        "Please report or fix in code if that's not right.",
                    ),
                )
                logger.error("LLM response was not in the expected format for summary.")
                logger.debug("History sent for compact: \n%s", contents)
                return
        else:
            self.ui_bus.dispatch_ui_update(
                ui_events.Warn("History was cleaned up, non-final responses removed."),
            )

        self.session_manager.replace_current_session_events(compact_session_events)

        self.ui_bus.dispatch_ui_update(
            ui_events.Info("Session compacted successfully."),
        )
