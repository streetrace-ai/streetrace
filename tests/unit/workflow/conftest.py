from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from google.adk.events import Event

from streetrace.workflow.supervisor import Supervisor
from streetrace.workloads import Workload, WorkloadManager


@pytest.fixture
def mock_workload() -> Workload:
    """Create a mock Workload for testing."""
    mock = MagicMock(spec=Workload)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_create_workload_context_manager(mock_workload: Workload) -> AsyncMock:
    """Create a mock async context manager for create_workload."""
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_workload
    mock_context_manager.__aexit__.return_value = None
    return mock_context_manager


@pytest.fixture
def mock_workload_manager(
    mock_model_factory,
    mock_tool_provider,
    work_dir,
    mock_create_workload_context_manager,
) -> WorkloadManager:
    """Create a mock WorkloadManager for testing."""
    workload_manager = Mock(spec=WorkloadManager)
    workload_manager.model_factory = mock_model_factory
    workload_manager.tool_provider = mock_tool_provider
    workload_manager.work_dir = work_dir
    workload_manager.create_workload.return_value = mock_create_workload_context_manager
    workload_manager.discover_definitions.return_value = []
    return workload_manager


def create_mock_workload_run_async(
    events: list[Event],
) -> AsyncGenerator[Event, None]:
    """Create a mock run_async generator that yields events."""

    async def _gen(
        session: MagicMock,  # noqa: ARG001
        message: MagicMock,  # noqa: ARG001
    ) -> AsyncGenerator[Event, None]:
        for event in events:
            yield event

    return _gen


@pytest.fixture
def shallow_supervisor(
    mock_workload_manager,
    mock_session_manager,
    mock_ui_bus,
) -> Supervisor:
    """Create a Supervisor with WorkloadManager for workflow tests."""
    return Supervisor(
        workload_manager=mock_workload_manager,
        session_manager=mock_session_manager,
        ui_bus=mock_ui_bus,
    )


@pytest.fixture
def events_mocker():
    """Create a mock for events with content."""

    def _mock_event(
        content: str | list[str] | None = None,
        author: str = "user",
        is_final_response: bool | None = True,
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
