"""Runs agents and implements the core user<->agent interaction loop."""

from typing import TYPE_CHECKING, override

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
    from streetrace.agents.agent_manager import AgentManager
    from streetrace.session.session_manager import SessionManager

logger = get_logger(__name__)


class Supervisor(InputHandler):
    """Workflow supervisor manages and executes available workflows."""

    def __init__(
        self,
        agent_manager: "AgentManager",
        session_manager: "SessionManager",
        ui_bus: UiBus,
    ) -> None:
        """Initialize a new instance of workflow supervisor.

        Args:
            agent_manager: Manager for discovering and creating agents
            session_manager: Conversaion sessions manager
            ui_bus: UI event bus for displaying messages to the user

        """
        self.agent_manager = agent_manager
        self.session_manager = session_manager
        self.ui_bus = ui_bus
        self.long_running = True

    @override
    async def handle(self, ctx: InputContext) -> HandlerResult:
        """Run the payload through the workflow.

        This method orchestrates the full interaction cycle between the user and agent:
        1. Prepares the user's message with any attached file contents
        2. Creates a session if needed or retrieves an existing one
        3. Creates an agent with appropriate tools
        4. Runs the agent with the message and captures all events
        5. Extracts the final response and adds it to global history

        Args:
            ctx: User input processing context.

        Returns:
            HandlerResult indicating handing result.

        """
        from google.genai import types as genai_types

        parts = [genai_types.Part.from_text(text=item) for item in ctx]

        content = genai_types.Content(role="user", parts=parts) if parts else None
        final_response_text: str | None = "Agent did not produce a final response."

        session = await self.session_manager.get_or_create_session()
        session = await self.session_manager.validate_session(session)
        # Use agent specified in args, or default if none specified
        agent_name = ctx.agent_name or "default"
        try:
            async with self.agent_manager.create_agent(agent_name) as root_agent:
                # Type cast needed because JSONSessionService uses duck typing at
                # runtime but inherits from BaseSessionService only during TYPE_CHECKING
                from google.adk import Runner

                runner = Runner(
                    app_name=session.app_name,
                    session_service=self.session_manager.session_service,
                    agent=root_agent,
                )
                # Key Concept: run_async executes the agent logic and yields Events
                # while it goes through ReAct loop. We iterate through events to reach
                # the final answer.
                async for event in runner.run_async(
                    user_id=session.user_id,
                    session_id=session.id,
                    new_message=content,  # type: ignore[arg-type] # base lacks precision
                ):
                    self.ui_bus.dispatch_ui_update(Event(event=event))
                    await self.session_manager.manage_current_session()

                    # TODO(krmrn42): Handle wrong tool calls. How to detect the root
                    # cause is an attempt to store a large file? E.g.:
                    # Tool signature doesn't match
                    #   -> Parameters missing
                    #       -> tool name is "write_file"
                    #           -> missing parameter name is "content"

                    # Check if this is the final response from the agent
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            # Assuming text response in the first part
                            final_response_text = event.content.parts[0].text
                        elif (
                            event.actions and event.actions.escalate
                        ):  # Handle potential errors/escalations
                            error_msg = event.error_message or "No specific message."
                            final_response_text = f"Agent escalated: {error_msg}"
                        # Add more checks here if needed (e.g., specific error codes)
                        break  # Stop processing events once the final response is found
        except:
            self.ui_bus.dispatch_ui_update(
                ui_events.Error(
                    f"Error running agent '{agent_name}', see log for errors",
                ),
            )
            logger.exception("Error running agent")
            raise

        # Add the agent's final message to the history
        if final_response_text:
            await self.session_manager.post_process(
                user_input=ctx.user_input,
                original_session=session,
            )
        return HANDLED_CONT
