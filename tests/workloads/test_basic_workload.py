"""Tests for BasicAgentWorkload."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.types import AgentCapabilities
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.sessions import Session
from google.adk.sessions.base_session_service import BaseSessionService
from google.genai.types import Content

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import AnyTool, ToolProvider
from streetrace.workloads.basic_workload import BasicAgentWorkload
from streetrace.workloads.protocol import Workload


class MockStreetRaceAgent(StreetRaceAgent):
    """Mock StreetRaceAgent implementation for testing."""

    def __init__(self, name: str = "Test Agent") -> None:
        """Initialize mock agent with given name."""
        self.agent_name = name
        self.close_called = False
        self.create_agent_called = False

    def get_agent_card(self) -> StreetRaceAgentCard:
        """Return a mock agent card."""
        return StreetRaceAgentCard(
            name=self.agent_name,
            description=f"A test agent named {self.agent_name}",
            capabilities=AgentCapabilities(streaming=False),
            skills=[],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            version="1.0.0",
        )

    async def get_required_tools(self) -> list[AnyTool]:
        """Return list of required tools."""
        return []

    async def create_agent(
        self,
        model_factory: ModelFactory,  # noqa: ARG002
        tool_provider: ToolProvider,  # noqa: ARG002
        system_context: SystemContext,  # noqa: ARG002
    ) -> BaseAgent:
        """Create a mock BaseAgent."""
        self.create_agent_called = True
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = self.agent_name
        return mock_agent

    async def close(self, agent_instance: BaseAgent) -> None:  # noqa: ARG002
        """Mark close as called."""
        self.close_called = True


@pytest.fixture
def mock_model_factory() -> ModelFactory:
    """Create a mock ModelFactory."""
    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.get_current_model.return_value = MagicMock()
    return mock_factory


@pytest.fixture
def mock_tool_provider() -> ToolProvider:
    """Create a mock ToolProvider."""
    mock_provider = MagicMock(spec=ToolProvider)
    mock_tools = [MagicMock(), MagicMock()]
    mock_provider.get_tools.return_value.__aenter__ = AsyncMock(return_value=mock_tools)
    mock_provider.get_tools.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_provider


@pytest.fixture
def mock_session_service() -> BaseSessionService:
    """Create a mock BaseSessionService."""
    return MagicMock(spec=BaseSessionService)


@pytest.fixture
def mock_session() -> Session:
    """Create a mock Session for testing."""
    session = MagicMock(spec=Session)
    session.app_name = "test-app"
    session.user_id = "test-user"
    session.id = "test-session-id"
    return session


@pytest.fixture
def mock_content() -> Content:
    """Create a mock Content for testing."""
    return MagicMock(spec=Content)


@pytest.fixture
def mock_agent_definition() -> MockStreetRaceAgent:
    """Create a mock agent definition."""
    return MockStreetRaceAgent("Test Agent")


@pytest.fixture
def basic_workload(
    mock_agent_definition: MockStreetRaceAgent,
    mock_model_factory: ModelFactory,
    mock_tool_provider: ToolProvider,
    mock_system_context: SystemContext,
    mock_session_service: BaseSessionService,
) -> BasicAgentWorkload:
    """Create a BasicAgentWorkload instance for testing."""
    return BasicAgentWorkload(
        agent_definition=mock_agent_definition,
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        session_service=mock_session_service,
    )


async def _mock_run_async_gen(
    events: list[Event],
    capture: dict[str, object] | None = None,
    **kwargs: object,
) -> AsyncGenerator[Event, None]:
    """Yield events and optionally capture kwargs for testing."""
    if capture is not None:
        capture.update(kwargs)
    for event in events:
        yield event


class TestBasicAgentWorkloadInstantiation:
    """Test cases for BasicAgentWorkload instantiation."""

    def test_init_stores_dependencies(
        self,
        mock_agent_definition: MockStreetRaceAgent,
        mock_model_factory: ModelFactory,
        mock_tool_provider: ToolProvider,
        mock_system_context: SystemContext,
        mock_session_service: BaseSessionService,
    ) -> None:
        """Test that constructor stores all dependencies."""
        workload = BasicAgentWorkload(
            agent_definition=mock_agent_definition,
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )

        assert workload._agent_def is mock_agent_definition  # noqa: SLF001
        assert workload._model_factory is mock_model_factory  # noqa: SLF001
        assert workload._tool_provider is mock_tool_provider  # noqa: SLF001
        assert workload._system_context is mock_system_context  # noqa: SLF001
        assert workload._session_service is mock_session_service  # noqa: SLF001

    def test_init_agent_is_none(
        self,
        basic_workload: BasicAgentWorkload,
    ) -> None:
        """Test that agent is None after initialization."""
        assert basic_workload._agent is None  # noqa: SLF001

    def test_satisfies_workload_protocol(
        self,
        basic_workload: BasicAgentWorkload,
    ) -> None:
        """Test that BasicAgentWorkload satisfies the Workload protocol."""
        assert isinstance(basic_workload, Workload)

    def test_has_agent_property(
        self,
        basic_workload: BasicAgentWorkload,
    ) -> None:
        """Test that BasicAgentWorkload has agent property."""
        assert hasattr(basic_workload, "agent")
        assert basic_workload.agent is None


class TestBasicAgentWorkloadRunAsync:
    """Test cases for BasicAgentWorkload.run_async method."""

    async def test_run_async_creates_agent(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
        mock_agent_definition: MockStreetRaceAgent,
    ) -> None:
        """Test that run_async creates the agent via agent_definition."""
        mock_event = MagicMock(spec=Event)
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen([mock_event])

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            events = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            assert mock_agent_definition.create_agent_called
            assert len(events) == 1
            assert events[0] is mock_event

    async def test_run_async_yields_events_from_runner(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
    ) -> None:
        """Test that run_async yields events from ADK Runner."""
        mock_event_1 = MagicMock(spec=Event)
        mock_event_2 = MagicMock(spec=Event)
        mock_event_3 = MagicMock(spec=Event)

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen(
            [mock_event_1, mock_event_2, mock_event_3],
        )

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            events = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            assert len(events) == 3
            assert events[0] is mock_event_1
            assert events[1] is mock_event_2
            assert events[2] is mock_event_3

    async def test_run_async_passes_session_to_runner(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
        mock_session_service: BaseSessionService,
    ) -> None:
        """Test that run_async passes session info to Runner."""
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen(
            [MagicMock(spec=Event)],
        )

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            mock_runner_class.assert_called_once()
            call_kwargs = mock_runner_class.call_args.kwargs
            assert call_kwargs["app_name"] == mock_session.app_name
            assert call_kwargs["session_service"] is mock_session_service

    async def test_run_async_passes_message_to_runner(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
    ) -> None:
        """Test that run_async passes message to runner.run_async."""
        mock_runner_instance = MagicMock()
        captured_kwargs: dict[str, object] = {}

        def capturing_run_async(**kw: object) -> AsyncGenerator[Event, None]:
            return _mock_run_async_gen([MagicMock(spec=Event)], captured_kwargs, **kw)

        mock_runner_instance.run_async = capturing_run_async

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            assert captured_kwargs["user_id"] == mock_session.user_id
            assert captured_kwargs["session_id"] == mock_session.id
            assert captured_kwargs["new_message"] is mock_content

    async def test_run_async_reuses_existing_agent(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
        mock_agent_definition: MockStreetRaceAgent,
    ) -> None:
        """Test that run_async reuses existing agent on subsequent calls."""
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen(
            [MagicMock(spec=Event)],
        )

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]
            assert mock_agent_definition.create_agent_called
            first_agent = basic_workload._agent  # noqa: SLF001

            mock_agent_definition.create_agent_called = False

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            assert not mock_agent_definition.create_agent_called
            assert basic_workload._agent is first_agent  # noqa: SLF001

    async def test_run_async_with_none_message(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
    ) -> None:
        """Test that run_async works with None message."""
        mock_runner_instance = MagicMock()
        captured_kwargs: dict[str, object] = {}

        def capturing_run_async(**kw: object) -> AsyncGenerator[Event, None]:
            return _mock_run_async_gen([MagicMock(spec=Event)], captured_kwargs, **kw)

        mock_runner_instance.run_async = capturing_run_async

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [event async for event in basic_workload.run_async(mock_session, None)]

            assert captured_kwargs["new_message"] is None


class TestBasicAgentWorkloadClose:
    """Test cases for BasicAgentWorkload.close method."""

    async def test_close_calls_agent_def_close(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
        mock_agent_definition: MockStreetRaceAgent,
    ) -> None:
        """Test that close calls agent_definition.close with the agent."""
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen(
            [MagicMock(spec=Event)],
        )

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            assert basic_workload._agent is not None  # noqa: SLF001

            await basic_workload.close()

            assert mock_agent_definition.close_called
            assert basic_workload._agent is None  # noqa: SLF001

    async def test_close_without_agent_does_nothing(
        self,
        basic_workload: BasicAgentWorkload,
        mock_agent_definition: MockStreetRaceAgent,
    ) -> None:
        """Test that close does nothing if agent was never created."""
        assert basic_workload._agent is None  # noqa: SLF001

        await basic_workload.close()

        assert not mock_agent_definition.close_called
        assert basic_workload._agent is None  # noqa: SLF001

    async def test_close_sets_agent_to_none(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
    ) -> None:
        """Test that close sets agent to None."""
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen(
            [MagicMock(spec=Event)],
        )

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]
            assert basic_workload._agent is not None  # noqa: SLF001

            await basic_workload.close()

            assert basic_workload._agent is None  # noqa: SLF001


class TestBasicAgentWorkloadAgentProperty:
    """Test cases for BasicAgentWorkload.agent property."""

    def test_agent_property_returns_none_initially(
        self,
        basic_workload: BasicAgentWorkload,
    ) -> None:
        """Test that agent property returns None before run_async."""
        assert basic_workload.agent is None

    async def test_agent_property_returns_agent_after_run(
        self,
        basic_workload: BasicAgentWorkload,
        mock_session: Session,
        mock_content: Content,
    ) -> None:
        """Test that agent property returns the created agent after run_async."""
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = lambda **_kw: _mock_run_async_gen(
            [MagicMock(spec=Event)],
        )

        with patch("streetrace.workloads.basic_workload.Runner") as mock_runner_class:
            mock_runner_class.return_value = mock_runner_instance

            _ = [
                event
                async for event in basic_workload.run_async(mock_session, mock_content)
            ]

            assert basic_workload.agent is not None
            assert hasattr(basic_workload.agent, "name")
