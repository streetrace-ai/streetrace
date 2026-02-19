"""Runs workloads and implements the core user<->agent interaction loop."""

from typing import TYPE_CHECKING, override

from opentelemetry import trace

from streetrace.dsl.runtime.events import FlowEvent, FlowResultEvent, LlmResponseEvent
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
    from google.adk.events import Event as AdkEvent

    from streetrace.session.session_manager import SessionManager
    from streetrace.workloads import WorkloadManager

logger = get_logger(__name__)


def _log_dsl_exception(workload_name: str, exc: BaseException) -> None:
    """Log a workload exception with source-map-translated line numbers.

    If the traceback passes through generated DSL code, translate the
    generated Python line numbers back to ``.sr`` source lines so the
    log is actionable.  Fall back to the raw traceback when no source
    map is available.

    Args:
        workload_name: Name of the workload that failed.
        exc: The inner exception to log.

    """
    try:
        from streetrace.dsl.compiler import get_source_map_registry
        from streetrace.dsl.sourcemap.excepthook import (
            format_exception_with_source_map,
        )

        registry = get_source_map_registry()
        translated = format_exception_with_source_map(
            type(exc), exc, exc.__traceback__, registry,
        )
        logger.error(
            "Error running workload '%s'\n%s", workload_name, translated,
        )
    except ImportError:
        logger.exception("Error running workload '%s'", workload_name)


def _format_exception_message(exc: BaseException) -> str:
    """Format an exception for user-friendly display.

    Provide meaningful context for common exception types that have
    terse default string representations.

    Args:
        exc: The exception to format.

    Returns:
        A user-friendly error message.

    """
    if isinstance(exc, KeyError):
        # KeyError str() is just the key name, which is cryptic
        return f"undefined variable '{exc.args[0]}'"
    if isinstance(exc, AttributeError):
        return f"attribute error: {exc}"
    if isinstance(exc, TypeError):
        return f"type error: {exc}"
    # Default: use the exception's string representation
    return str(exc)


DEFAULT_NO_RESPONSE_MSG = "Agent did not produce a final response."
"""Default message when no final response is captured."""


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

    def _capture_flow_event_response(
        self,
        event: FlowEvent,
        current_response: str | None,
    ) -> str | None:
        """Capture final response from FlowEvent if applicable.

        Args:
            event: The FlowEvent to check.
            current_response: Current captured response.

        Returns:
            Updated response text if this event provides a final response.

        """
        import json

        # FlowResultEvent takes precedence - it's the explicit return value
        if isinstance(event, FlowResultEvent):
            result = event.result
            if isinstance(result, str):
                return result
            # Serialize non-string results to JSON
            return json.dumps(result, indent=2, default=str)

        if (
            isinstance(event, LlmResponseEvent)
            and event.is_final
            and current_response == DEFAULT_NO_RESPONSE_MSG
        ):
            return event.content
        return current_response

    def _capture_adk_event_response(
        self,
        event: "AdkEvent",
        current_response: str | None,
    ) -> str | None:
        """Capture final response from ADK Event if applicable.

        Args:
            event: The ADK Event to check.
            current_response: Current captured response.

        Returns:
            Updated response text if this event provides a final response.

        """
        if not event.is_final_response():
            return current_response
        if current_response != DEFAULT_NO_RESPONSE_MSG:
            return current_response

        if event.content and event.content.parts:
            return event.content.parts[0].text
        if event.actions and event.actions.escalate:
            error_msg = event.error_message or "No specific message."
            return f"Agent escalated: {error_msg}"
        return current_response

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
        logger.debug(
            "Supervisor.handle: created %d parts from ctx (user_input=%r)",
            len(parts),
            ctx.user_input[:100] if ctx.user_input else None,
        )

        content = genai_types.Content(role="user", parts=parts) if parts else None
        if content is None:
            logger.warning("Supervisor.handle: content is None (no parts created)")
        final_response_text: str | None = DEFAULT_NO_RESPONSE_MSG

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
                        if isinstance(event, FlowEvent):
                            # Custom flow event - dispatch directly
                            self.ui_bus.dispatch_ui_update(event)
                            final_response_text = self._capture_flow_event_response(
                                event,
                                final_response_text,
                            )
                        else:
                            # ADK Event - wrap and dispatch
                            self.ui_bus.dispatch_ui_update(Event(event=event))
                            await self.session_manager.manage_current_session()
                            final_response_text = self._capture_adk_event_response(
                                event,
                                final_response_text,
                            )
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
            inner = err_group.exceptions[0]
            _log_dsl_exception(workload_name, inner)
            error_msg = _format_exception_message(inner)
            self.ui_bus.dispatch_ui_update(
                ui_events.Error(f"'{workload_name}': {error_msg}"),
            )
            raise

        return HANDLED_CONT
