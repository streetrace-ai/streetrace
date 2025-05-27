"""Tests for the AgentManager class."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.agents.agent_manager import AgentManager
from streetrace.llm.model_factory import ModelFactory
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.ui_bus import UiBus


@pytest.fixture
def mock_model_factory():
    """Create a mock ModelFactory."""
    mock = MagicMock(spec=ModelFactory)
    mock.get_current_model.return_value = "mock_model"
    mock.get_model.return_value = "mock_model"
    return mock


@pytest.fixture
def mock_tool_provider():
    """Create a mock ToolProvider with context manager behavior."""
    mock = MagicMock(spec=ToolProvider)

    # Mock the context manager
    async_cm = MagicMock()
    async_cm.__aenter__.return_value = ["mock_tool1", "mock_tool2"]
    async_cm.__aexit__.return_value = None

    mock.get_tools.return_value = async_cm
    return mock


@pytest.fixture
def mock_ui_bus():
    """Create a mock UiBus."""
    return MagicMock(spec=UiBus)


@pytest.fixture
def agent_manager(mock_model_factory, mock_tool_provider, mock_ui_bus):
    """Create an AgentManager with mock dependencies."""
    return AgentManager(
        mock_model_factory,
        mock_tool_provider,
        mock_ui_bus,
        Path("/fake/work/dir"),
    )


@patch("streetrace.agents.agent_manager.discover_agents")
def test_list_available_agents(mock_discover_agents, agent_manager):
    """Test listing available agents."""
    # Arrange
    mock_agents = [
        {"name": "Agent1", "path": "agents/agent1", "description": "Description1"},
        {"name": "Agent2", "path": "agents/agent2", "description": "Description2"},
    ]
    mock_discover_agents.return_value = mock_agents

    # Act
    result = agent_manager.list_available_agents()

    # Assert
    assert result == mock_agents
    mock_discover_agents.assert_called_once()
    # Verify paths are checked correctly
    paths = mock_discover_agents.call_args[0][0]
    assert len(paths) == 2
    assert paths[0] == Path("/fake/work/dir/agents")


@patch("streetrace.agents.agent_manager.importlib.util")
def test_import_agent_module_file_not_found(mock_importlib_util, agent_manager):
    """Test importing an agent module when the file is not found."""
    # Arrange
    with patch("pathlib.Path.exists", return_value=False):
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            agent_manager._import_agent_module(Path("/fake/agents/missing"))


@patch("streetrace.agents.agent_manager.importlib.util")
def test_import_agent_module_success(mock_importlib_util, agent_manager):
    """Test successfully importing an agent module."""
    # Arrange
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        # Mock the spec and module creation
        mock_spec = MagicMock()
        mock_loader = MagicMock()
        mock_spec.loader = mock_loader
        mock_importlib_util.spec_from_file_location.return_value = mock_spec

        mock_module = MagicMock()
        mock_importlib_util.module_from_spec.return_value = mock_module

        # Act
        result = agent_manager._import_agent_module(Path("/fake/agents/valid"))

        # Assert
        assert result == mock_module
        mock_importlib_util.spec_from_file_location.assert_called_once()
        mock_importlib_util.module_from_spec.assert_called_once_with(mock_spec)
        mock_loader.exec_module.assert_called_once_with(mock_module)


def test_get_agent_class(agent_manager):
    """Test getting an agent class from a module."""
    # Arrange
    mock_module = MagicMock()

    # Create a mock for StreetRaceAgent
    mock_streetrace_agent = MagicMock()
    mock_streetrace_agent.__name__ = "StreetRaceAgent"

    # Create a mock for a subclass
    mock_agent_class = MagicMock()
    mock_agent_class.__module__ = mock_module.__name__
    mock_agent_class.__mro__ = (mock_agent_class, mock_streetrace_agent, object)

    # Add the class to the module's attributes
    mock_module.MyAgent = mock_agent_class
    mock_module.MyAgent = mock_agent_class

    # Mock dir() to return the class name
    with patch("streetrace.agents.agent_manager.dir", return_value=["MyAgent"]):
        # Mock isinstance to return True for our agent class
        with patch("streetrace.agents.agent_manager.isinstance", return_value=True):
            with patch("streetrace.agents.agent_manager.issubclass", return_value=True):
                # Act
                result = agent_manager._get_agent_class(mock_module)

                # Assert
                assert result == mock_agent_class


@patch("streetrace.agents.agent_manager.AgentManager._import_agent_module")
@patch("streetrace.agents.agent_manager.AgentManager._get_agent_class")
@patch("streetrace.agents.agent_manager.AgentManager.list_available_agents")
def test_get_agent_details(
    mock_list_agents,
    mock_get_agent_class,
    mock_import_module,
    agent_manager,
):
    """Test getting agent details."""
    # Arrange
    mock_list_agents.return_value = [
        {
            "name": "TestAgent",
            "path": "agents/test_agent",
            "description": "A test agent",
        },
    ]

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module

    mock_agent_class = MagicMock()
    mock_get_agent_class.return_value = mock_agent_class

    # Act
    result = agent_manager._get_agent_details("TestAgent")

    # Assert
    assert result["info"]["name"] == "TestAgent"
    assert result["module"] == mock_module
    assert result["agent_class"] == mock_agent_class
    mock_list_agents.assert_called_once()
    mock_import_module.assert_called_once()
    mock_get_agent_class.assert_called_once_with(mock_module)


@patch("streetrace.agents.agent_manager.AgentManager._get_agent_details")
async def test_get_required_tools_with_streetrace_agent(
    mock_get_agent_details,
    agent_manager,
):
    """Test getting required tools from a StreetRaceAgent implementation."""
    # Arrange
    mock_agent_instance = AsyncMock()
    mock_agent_instance.get_required_tools.return_value = [
        "tool1",
        "tool2",
    ]

    mock_agent_class = MagicMock()
    mock_agent_class.return_value = mock_agent_instance

    mock_get_agent_details.return_value = {
        "info": {"name": "TestAgent"},
        "module": MagicMock(),
        "agent_class": mock_agent_class,
    }

    # Act
    result = await agent_manager._get_required_tools(
        mock_get_agent_details.return_value,
    )

    # Assert
    assert result == ["tool1", "tool2"]
    mock_agent_instance.get_required_tools.assert_called_once()


@patch("streetrace.agents.agent_manager.AgentManager._get_agent_details")
@patch("streetrace.agents.agent_manager.AgentManager._get_required_tools")
async def test_create_agent_with_streetrace_agent(
    mock_get_required_tools,
    mock_get_agent_details,
    agent_manager,
    mock_tool_provider,
):
    """Test creating an agent with StreetRaceAgent implementation."""
    # Arrange
    mock_agent_instance = AsyncMock()
    mock_agent = MagicMock()
    mock_agent_instance.create_agent.return_value = mock_agent

    mock_agent_class = MagicMock()
    mock_agent_class.return_value = mock_agent_instance

    mock_get_agent_details.return_value = {
        "info": {"name": "TestAgent", "description": "A test agent"},
        "module": MagicMock(),
        "agent_class": mock_agent_class,
    }

    mock_get_required_tools.return_value = ["tool1", "tool2"]

    # Act
    async with agent_manager.create_agent("TestAgent") as agent:
        # Assert
        assert agent == mock_agent
        mock_agent_instance.create_agent.assert_called_once()
        mock_tool_provider.get_tools.assert_called_once_with(
            mock_get_required_tools.return_value,
        )


@patch("streetrace.agents.agent_manager.AgentManager._get_agent_details")
@patch("streetrace.agents.agent_manager.AgentManager._get_required_tools")
@patch("streetrace.agents.agent_manager.Agent")
async def test_create_agent_with_legacy_agent(
    mock_agent_class,
    mock_get_required_tools,
    mock_get_agent_details,
    agent_manager,
    mock_tool_provider,
    mock_model_factory,
):
    """Test creating a legacy agent using run_agent function."""
    # Arrange
    mock_run_agent = MagicMock()

    mock_module = MagicMock()
    mock_module.run_agent = mock_run_agent

    mock_get_agent_details.return_value = {
        "info": {"name": "LegacyAgent", "description": "A legacy agent"},
        "module": mock_module,
        "agent_class": None,  # No StreetRaceAgent class
    }

    mock_get_required_tools.return_value = ["tool1", "tool2"]

    mock_agent = MagicMock()
    mock_agent_class.return_value = mock_agent

    # Act
    async with agent_manager.create_agent("LegacyAgent") as agent:
        # Assert
        assert agent == mock_agent
        mock_agent_class.assert_called_once_with(
            name="LegacyAgent",
            model=mock_model_factory.get_model.return_value,
            description="A legacy agent",
            tools=["mock_tool1", "mock_tool2"],
        )


@patch("streetrace.agents.agent_manager.Agent")
async def test_create_default_agent(
    mock_agent_class,
    agent_manager,
    mock_tool_provider,
    mock_model_factory,
):
    """Test creating a default agent."""
    # Arrange
    mock_agent = MagicMock()
    mock_agent_class.return_value = mock_agent

    system_message = "You are a helpful assistant."

    # Act
    async with agent_manager.create_default_agent(system_message) as agent:
        # Assert
        assert agent == mock_agent
        mock_agent_class.assert_called_once_with(
            name="StreetRace",
            model=mock_model_factory.get_model.return_value,
            description="StreetRace Default Agent",
            instruction=system_message,
            tools=["mock_tool1", "mock_tool2"],
        )
