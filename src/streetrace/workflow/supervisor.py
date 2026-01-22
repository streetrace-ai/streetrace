"""Runs workloads and implements the core user<->agent interaction loop."""

from typing import TYPE_CHECKING, override

from opentelemetry import trace

from streetrace.input_handler import (
    HANDLED_CONT,
    HandlerResult,
    InputContext,
    InputHandler,
)
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.adk_event_renderer import Event
from streetrace.ui.ui_bus import UiBus

if TYPE_CHECKING:
    from streetrace.session.session_manager import SessionManager
    from streetrace.workloads import WorkloadManager

logger = get_logger(__name__)


class Supervisor(InputHandler):
    """Workflow supervisor manages and executes available workloads."""

    def __init__(
        self,
        workload_manager: "WorkloadManager",
        session_manager: "SessionManager",
        ui_bus: UiBus,
    ) -> None:
        """Initialize a new instance of workflow supervisor.

        Args:
            workload_manager: Manager for discovering and creating workloads
            session_manager: Conversation sessions manager
            ui_bus: UI event bus for displaying messages to the user

        """
        self.workload_manager = workload_manager
        self.session_manager = session_manager
        self.ui_bus = ui_bus
        self.long_running = True

    @override
    async def handle(self, ctx: InputContext) -> HandlerResult:
        """Run the payload through the workload.

        Orchestrate the full user-workload interaction cycle:
        1. Prepares the user's message with any attached file contents
        2. Creates a session if needed or retrieves an existing one
        3. Creates a workload via WorkloadManager
        4. Runs the workload with the message and captures all events
        5. Extracts the final response and adds it to global history

        Args:
            ctx: User input processing context.

        Returns:
            HandlerResult indicating handing result.

        """
        from google.genai import types as genai_types

        from streetrace.tools.named_toolset import (
            ToolsetLifecycleError,
        )

        parts = [genai_types.Part.from_text(text=item) for item in ctx]

        content = genai_types.Content(role="user", parts=parts) if parts else None
        final_response_text: str | None = "Agent did not produce a final response."

        session = await self.session_manager.get_or_create_session()
        session = await self.session_manager.validate_session(session)
        # Use workload specified in args, or default if none specified
        workload_name = ctx.agent_name or "default"
        try:
            # Create parent telemetry span for the entire workload run
            # Get tracer lazily to ensure we use the configured tracer provider
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("streetrace_agent_run"):
                async with self.workload_manager.create_workload(
                    workload_name,
                ) as workload:
                    # Key Concept: run_async executes the workload logic and
                    # yields Events while it goes through ReAct loop.
                    # We iterate through events to reach the final answer.
                    async for event in workload.run_async(session, content):
                        self.ui_bus.dispatch_ui_update(Event(event=event))
                        await self.session_manager.manage_current_session()

                        # TODO(krmrn42): Handle wrong tool calls. How to
                        # detect the root cause is an attempt to store a
                        # large file? E.g.:
                        # Tool signature doesn't match
                        #   -> Parameters missing
                        #       -> tool name is "write_file"
                        #           -> missing parameter name is "content"

                        # Check if this is the final response from the workload
                        # Only capture first final response if multiple
                        if (
                            event.is_final_response()
                            and final_response_text
                            == "Agent did not produce a final response."
                        ):
                            if event.content and event.content.parts:
                                # Assuming text response in first part
                                final_response_text = event.content.parts[0].text
                            elif event.actions and event.actions.escalate:
                                # Handle potential errors/escalations
                                error_msg = (
                                    event.error_message or "No specific message."
                                )
                                final_response_text = f"Agent escalated: {error_msg}"
            # Add the workload's final message to the history
            if final_response_text:
                await self.session_manager.post_process(
                    user_input=ctx.user_input,
                    original_session=session,
                )
                ctx.final_response = final_response_text
        except* ToolsetLifecycleError as lifecycle_err_group:
            logger.exception(
                "Failed to initialize or cleanup tools for workload '%s'",
                workload_name,
            )
            err = next(
                err
                for err in lifecycle_err_group.exceptions
                if isinstance(err, ToolsetLifecycleError)
            )
            self.ui_bus.dispatch_ui_update(
                ui_events.Error(f"'{workload_name}': {err}"),
            )
            raise
        except* BaseException as err_group:
            logger.exception("Error running workload '%s'", workload_name)
            self.ui_bus.dispatch_ui_update(
                ui_events.Error(f"'{workload_name}': {err_group.exceptions[0]}"),
            )
            raise

        return HANDLED_CONT
