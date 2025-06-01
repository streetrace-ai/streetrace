from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.agents import Agent
from google.adk.events import Event

from streetrace.agents.agent_manager import AgentManager
from streetrace.workflow.supervisor import Supervisor


@pytest.fixture
def mock_agent() -> Agent:
    return Mock(spec=Agent)


@pytest.fixture
def mock_create_agent_context_manager(mock_agent) -> AsyncMock:
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_agent
    return mock_context_manager


@pytest.fixture
def mock_agent_manager(
    mock_create_agent_context_manager,
    mock_agent_manager: Mock,
) -> AgentManager:
    """Override the base mock_agent_manager with workflow-specific setup."""
    mock_agent_manager.create_agent.return_value = mock_create_agent_context_manager
    return mock_agent_manager


@pytest.fixture
def shallow_supervisor(
    mock_agent_manager,
    mock_session_manager,
    mock_ui_bus,
) -> Supervisor:
    """Create a Supervisor with properly mocked agent manager for workflow tests."""
    return Supervisor(
        agent_manager=mock_agent_manager,
        session_manager=mock_session_manager,
        ui_bus=mock_ui_bus,
    )


@pytest.fixture
def events_mocker():
    """Create a mock for events with content."""

    def _mock_event(
        content: str | list[str] | None = None,
        author: str = "user",
        is_final_response: bool | None = True,  # noqa: FBT002
        escalate: bool | None = None,
    ) -> Event:
        event = Mock(spec=Event)
        if is_final_response is not None:
            event.is_final_response.return_value = is_final_response
        event.author = author
        if content is not None:
            event.content = Mock()
            event.content.role = author
            if isinstance(content, str):
                event.content.parts = [Mock(text=content)]
            elif isinstance(content, list):
                event.content.parts = [Mock(text=part) for part in content]
        if escalate:
            event.actions = Mock(escalate=True)
            event.error_message = "Test Escalation."
        else:
            event.actions = None
        return event

    return _mock_event


@pytest.fixture
def mock_final_response_event(events_mocker) -> Event:
    return events_mocker("Final response.")


@pytest.fixture
def mock_adk_runner(mock_final_response_event):
    def do_patch(events: list | None = None):
        async def _async_iter_events(events: list[Mock]):
            """Create an async iterator from a list of events."""
            for event in events:
                yield event

        mock_runner = Mock()
        mock_runner.run_async.return_value = _async_iter_events(
            events if events else [mock_final_response_event],
        )
        return mock_runner

    return do_patch


@pytest.fixture
def mock_events_iterator():
    """Create helper function for async event iteration."""

    async def _async_iter_events(events: list):
        """Create an async iterator from a list of events."""
        for event in events:
            yield event

    return _async_iter_events
