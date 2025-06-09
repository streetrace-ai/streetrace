"""Runs agents and implements the core user<->agent interaction loop."""

from google.adk import Runner
from google.genai import types as genai_types

from streetrace.agents.agent_manager import AgentManager
from streetrace.log import get_logger
from streetrace.prompt_processor import ProcessedPrompt
from streetrace.session_service import SessionManager
from streetrace.ui.adk_event_renderer import render_event as _  # noqa: F401
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class Supervisor:
    """Workflow supervisor manages and executes available workflows."""

    def __init__(
        self,
        agent_manager: AgentManager,
        session_manager: SessionManager,
        ui_bus: UiBus,
    ) -> None:
        """Initialize a new instance of workflow supervisor.

        Args:
            ui_bus: UI event bus for displaying messages to the user
            tool_provider: Provider of tools for the agent
            session_manager: Conversaion sessions manager
            args: Application arguments containing session information
            agent_manager: Manager for discovering and creating agents

        """
        self.ui_bus = ui_bus
        self.session_manager = session_manager
        self.agent_manager = agent_manager

    async def run_async(self, payload: ProcessedPrompt | None) -> None:
        """Run the payload through the workflow.

        Args:
            payload: Processed user prompt to be sent to the agent.

        This method orchestrates the full interaction cycle between the user and agent:
        1. Prepares the user's message with any attached file contents
        2. Creates a session if needed or retrieves an existing one
        3. Creates an agent with appropriate tools
        4. Runs the agent with the message and captures all events
        5. Extracts the final response and adds it to global history

        """
        parts = []
        if payload:
            if payload.prompt:
                parts.append(genai_types.Part.from_text(text=payload.prompt))
            if payload.mentions:
                for mention in payload.mentions:
                    mention_text = (
                        f"\nAttached file `{mention[0]!s}`:\n\n```\n{mention[1]}\n```\n"
                    )
                    parts.append(genai_types.Part.from_text(text=mention_text))

        content = genai_types.Content(role="user", parts=parts) if parts else None

        final_response_text = "Agent did not produce a final response."  # Default

        session = self.session_manager.get_or_create_session()
        async with self.agent_manager.create_agent("default") as root_agent:
            runner = Runner(
                app_name=session.app_name,
                session_service=self.session_manager.session_service,
                agent=root_agent,
            )
            # Key Concept: run_async executes the agent logic and yields Events while
            # it goes through ReAct loop. We iterate through events to reach the final
            # answer.
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=content,  # type: ignore[unused-ignore]
            ):
                self.ui_bus.dispatch_ui_update(event)

                # TODO(krmrn42): Handle wrong tool calls. How to detect the root cause
                # is an attempt to store a large file? E.g.:
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

        # Add the agent's final message to the history
        if final_response_text:
            self.session_manager.post_process(
                processed_prompt=payload,
                original_session=session,
            )
