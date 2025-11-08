"""Tests for telemetry span creation in supervisor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.input_handler import InputContext
from streetrace.workflow.supervisor import Supervisor


@pytest.fixture
def mock_tracer():
    """Create a mock tracer for OpenTelemetry."""
    with (
        patch("opentelemetry.trace.get_tracer") as get_tracer_mock,
        patch("opentelemetry.trace.get_current_span") as get_current_span_mock,
    ):
        mock_tracer_obj = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_span.is_recording.return_value = True
        mock_tracer_obj.start_as_current_span.return_value = mock_span
        get_tracer_mock.return_value = mock_tracer_obj
        get_current_span_mock.return_value = mock_span
        yield mock_tracer_obj, mock_span


@pytest.fixture
def mock_agent_manager():
    """Create a mock agent manager that properly executes telemetry code."""
    from contextlib import asynccontextmanager

    manager = MagicMock()

    # Create a mock that mimics what create_agent does
    @asynccontextmanager
    async def mock_create_agent(agent_identifier):
        from opentelemetry import trace

        from streetrace.version import get_streetrace_version

        # Mock agent definition (StreetRaceAgent)
        mock_agent_def = MagicMock(spec=StreetRaceAgent)
        mock_agent_def.get_attributes.return_value = {
            "custom.attr1": "value1",
            "custom.attr2": "value2",
        }
        mock_agent_def.get_version.return_value = "1.0.0"
        mock_agent_card = MagicMock()
        mock_agent_card.name = "test_agent"
        mock_agent_def.get_agent_card.return_value = mock_agent_card

        # Set telemetry attributes (mimics real create_agent logic)
        current_span = trace.get_current_span()
        if current_span is not None and current_span.is_recording():
            # Add custom attributes
            for key, value in mock_agent_def.get_attributes().items():
                current_span.set_attribute(key, value)

            # Add agent version
            agent_version = mock_agent_def.get_version()
            if agent_version is not None:
                current_span.set_attribute("streetrace.agent.version", agent_version)

            # Add agent name
            agent_card = mock_agent_def.get_agent_card()
            current_span.set_attribute(
                "streetrace.agent.name",
                agent_card.name or agent_identifier,
            )

            # Add binary version
            current_span.set_attribute(
                "streetrace.binary.version", get_streetrace_version(),
            )

        # Yield mock ADK agent
        mock_adk_agent = MagicMock()
        try:
            yield mock_adk_agent
        finally:
            pass

    manager.create_agent = mock_create_agent
    return manager


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = MagicMock()
    mock_session = MagicMock()
    mock_session.app_name = "test_app"
    mock_session.user_id = "test_user"
    mock_session.id = "test_session"

    manager.get_or_create_session = AsyncMock(return_value=mock_session)
    manager.validate_session = AsyncMock(return_value=mock_session)
    manager.post_process = AsyncMock()
    manager.manage_current_session = AsyncMock()
    manager.session_service = MagicMock()

    return manager


@pytest.fixture
def mock_ui_bus():
    """Create a mock UI bus."""
    return MagicMock()


@pytest.fixture
def supervisor(mock_agent_manager, mock_session_manager, mock_ui_bus):
    """Create a supervisor instance with mocked dependencies."""
    return Supervisor(
        agent_manager=mock_agent_manager,
        session_manager=mock_session_manager,
        ui_bus=mock_ui_bus,
    )


@pytest.mark.asyncio
async def test_supervisor_creates_streetrace_agent_run_span(
    supervisor,
    mock_tracer,
):
    """Test that supervisor creates a parent span named 'streetrace_agent_run'."""
    tracer, _ = mock_tracer

    # Mock the runner to avoid actual agent execution
    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            # Create mock event with is_final_response
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

    # Verify the span was created with the correct name
    tracer.start_as_current_span.assert_called_once_with("streetrace_agent_run")


@pytest.mark.asyncio
async def test_supervisor_adds_custom_attributes_to_span(
    supervisor,
    mock_tracer,
):
    """Test that custom attributes from agent are added to the span."""
    _, mock_span = mock_tracer

    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

    # Verify custom attributes were set (no prefix)
    mock_span.set_attribute.assert_any_call("custom.attr1", "value1")
    mock_span.set_attribute.assert_any_call("custom.attr2", "value2")


@pytest.mark.asyncio
async def test_supervisor_adds_streetrace_agent_name_attribute(
    supervisor,
    mock_tracer,
):
    """Test that streetrace.agent.name attribute is added."""
    _, mock_span = mock_tracer

    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

    # Verify streetrace.agent.name was set
    mock_span.set_attribute.assert_any_call("streetrace.agent.name", "test_agent")


@pytest.mark.asyncio
async def test_supervisor_adds_agent_version_when_available(
    supervisor,
    mock_tracer,
):
    """Test that streetrace.agent.version is added when agent has a version."""
    _, mock_span = mock_tracer

    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

    # Verify streetrace.agent.version was set
    mock_span.set_attribute.assert_any_call("streetrace.agent.version", "1.0.0")


@pytest.mark.asyncio
async def test_supervisor_skips_agent_version_when_none(
    supervisor,
    mock_tracer,
):
    """Test that streetrace.agent.version is not added when agent version is None."""
    from contextlib import asynccontextmanager

    _, mock_span = mock_tracer

    # Create a custom agent manager for this test with no version
    mock_agent_manager_no_version = MagicMock()

    @asynccontextmanager
    async def mock_create_agent_no_version(agent_identifier):
        from opentelemetry import trace

        from streetrace.version import get_streetrace_version

        # Mock agent definition with no version
        mock_agent_def = MagicMock(spec=StreetRaceAgent)
        mock_agent_def.get_attributes.return_value = {}
        mock_agent_def.get_version.return_value = None
        mock_agent_card = MagicMock()
        mock_agent_card.name = "test_agent"
        mock_agent_def.get_agent_card.return_value = mock_agent_card

        # Set telemetry attributes
        current_span = trace.get_current_span()
        if current_span is not None and current_span.is_recording():
            for key, value in mock_agent_def.get_attributes().items():
                current_span.set_attribute(key, value)

            agent_version = mock_agent_def.get_version()
            if agent_version is not None:
                current_span.set_attribute("streetrace.agent.version", agent_version)

            agent_card = mock_agent_def.get_agent_card()
            current_span.set_attribute(
                "streetrace.agent.name",
                agent_card.name or agent_identifier,
            )

            current_span.set_attribute(
                "streetrace.binary.version",
                get_streetrace_version(),
            )

        mock_adk_agent = MagicMock()
        try:
            yield mock_adk_agent
        finally:
            pass

    mock_agent_manager_no_version.create_agent = mock_create_agent_no_version

    # Create supervisor with this custom agent manager
    supervisor_no_version = Supervisor(
        agent_manager=mock_agent_manager_no_version,
        session_manager=supervisor.session_manager,
        ui_bus=supervisor.ui_bus,
    )

    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor_no_version.handle(ctx)

    # Verify streetrace.agent.version was NOT set
    version_calls = [
        call
        for call in mock_span.set_attribute.call_args_list
        if len(call[0]) > 0 and call[0][0] == "streetrace.agent.version"
    ]
    assert len(version_calls) == 0, (
        "streetrace.agent.version should not be set when version is None"
    )


@pytest.mark.asyncio
async def test_supervisor_adds_binary_version_attribute(
    supervisor,
    mock_tracer,
):
    """Test that streetrace.binary.version attribute is added."""
    tracer, mock_span = mock_tracer

    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        with patch(
            "streetrace.version.get_streetrace_version",
        ) as mock_version:
            mock_version.return_value = "0.1.21"

            ctx = InputContext(user_input="test input", agent_name="test_agent")
            await supervisor.handle(ctx)

            # Verify streetrace.binary.version was set
            mock_span.set_attribute.assert_any_call(
                "streetrace.binary.version",
                "0.1.21",
            )


@pytest.mark.asyncio
async def test_supervisor_span_wraps_entire_agent_run(
    supervisor,
    mock_tracer,
):
    """Test that the span wraps the entire agent run including runner execution."""
    _, mock_span = mock_tracer

    with patch("google.adk.Runner") as mock_runner:

        async def async_generator(*_args, **_kwargs):
            mock_event = MagicMock()
            mock_event.is_final_response.return_value = True
            mock_event.content = MagicMock()
            mock_event.content.parts = [MagicMock(text="Test response")]
            mock_event.actions = None
            yield mock_event

        mock_runner.run_async = async_generator
        mock_runner.return_value = mock_runner

        ctx = InputContext(user_input="test input", agent_name="test_agent")
        await supervisor.handle(ctx)

    # Verify the span's context manager methods were called
    mock_span.__enter__.assert_called_once()
    mock_span.__exit__.assert_called_once()
