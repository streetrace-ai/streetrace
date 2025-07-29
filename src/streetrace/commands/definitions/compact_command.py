"""Implement the compact command for summarizing conversation history.

This module defines the CompactCommand class which allows users to compact
the current conversation history to reduce token usage while maintaining context.
"""

# Import Application for type hint only
from typing import TYPE_CHECKING, override

from streetrace.args import Args
from streetrace.commands.base_command import Command
from streetrace.llm.model_factory import ModelFactory
from streetrace.log import get_logger
from streetrace.messages import COMPACT

if TYPE_CHECKING:
    from google.genai import types as genai_types

    from streetrace.session.session_manager import SessionManager

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
        session_manager: "SessionManager",
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
        contents: "list[genai_types.Content]",
    ) -> tuple[str | None, str | None]:
        from google.adk.models.llm_request import LlmRequest
        from google.genai import types as genai_types

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
        """Execute the history compaction action using the HistoryManager."""
        # allow ADK to feed a fake tool to model in case it needs one
        import litellm
        from google.adk.events import Event
        from google.genai import types as genai_types

        litellm.modify_params = True

        current_session = await self.session_manager.get_current_session()
        compacted_session_events: list[Event] = []
        contents_to_compact: list[genai_types.Content] = []
        assistant_author_name: str | None = None
        if current_session and current_session.events:
            for event in current_session.events:
                if not event.content or not event.content.parts:
                    continue
                contents_to_compact.append(event.content)
                if assistant_author_name is None:
                    if event.author == "user":
                        compacted_session_events.append(event.model_copy())
                    else:
                        assistant_author_name = event.author

        if not contents_to_compact:
            self.ui_bus.dispatch_ui_update(
                ui_events.Info("No history available to compact."),
            )
            return

        self.ui_bus.dispatch_ui_update(
            ui_events.Info("Compacting conversation history..."),
        )

        role, summary_message = await self._summarize_contents(contents_to_compact)
        if summary_message:
            self.ui_bus.dispatch_ui_update(ui_events.Markdown(summary_message))

            compacted_session_events.append(
                Event(
                    author=assistant_author_name or "assistant",
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
            logger.debug("History sent for compact: \n%s", contents_to_compact)
            return

        await self.session_manager.replace_current_session_events(
            compacted_session_events,
        )

        self.ui_bus.dispatch_ui_update(
            ui_events.Info("Session compacted successfully."),
        )
