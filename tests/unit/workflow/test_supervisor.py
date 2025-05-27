"""Test cases for Supervisor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from streetrace.workflow.supervisor import Supervisor


@pytest.fixture
def mock_ui_bus():
    """Create a mock UI bus."""
    return MagicMock()


@pytest.fixture
def mock_llm_interface():
    """Create a mock LLM interface."""
    return MagicMock()


@pytest.fixture
def mock_tool_provider():
    """Create a mock tool provider."""
    return MagicMock()


@pytest.fixture
def mock_system_context():
    """Create a mock system context."""
    context = MagicMock()
    context.get_system_message.return_value = "System message"
    return context


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = MagicMock()
    manager.get_or_create_session.return_value = MagicMock()
    return manager


@pytest.fixture
def mock_args():
    """Create mock arguments."""
    args = MagicMock()
    args.effective_app_name = "test_app"
    args.effective_user_id = "test_user"
    args.effective_session_id = "test_session"
    args.work_dir = MagicMock()
    return args


@pytest.fixture
def mock_model_factory():
    """Create a mock model factory."""
    factory = MagicMock()
    factory.get_model.return_value = "model"
    return factory


@pytest.fixture
def mock_agent_manager():
    """Create a mock agent manager."""
    manager = MagicMock()
    # Mock the async context manager
    async_context = AsyncMock()
    async_context.__aenter__.return_value = MagicMock()
    manager.create_agent.return_value = async_context
    manager.create_default_agent.return_value = async_context
    return manager


@pytest.fixture
def supervisor(
    mock_ui_bus,
    mock_llm_interface,
    mock_tool_provider,
    mock_system_context,
    mock_session_manager,
    mock_args,
    mock_model_factory,
    mock_agent_manager,
):
    """Create a supervisor instance with mocked dependencies."""
    return Supervisor(
        ui_bus=mock_ui_bus,
        llm_interface=mock_llm_interface,
        tool_provider=mock_tool_provider,
        system_context=mock_system_context,
        session_manager=mock_session_manager,
        args=mock_args,
        model_factory=mock_model_factory,
        agent_manager=mock_agent_manager,
    )


def test_supervisor_initialization(
    supervisor,
    mock_ui_bus,
    mock_llm_interface,
    mock_tool_provider,
    mock_system_context,
    mock_session_manager,
    mock_args,
    mock_model_factory,
    mock_agent_manager,
):
    """Test that Supervisor initializes with the correct dependencies."""
    assert supervisor.ui_bus == mock_ui_bus
    assert supervisor.llm_interface == mock_llm_interface
    assert supervisor.tool_provider == mock_tool_provider
    assert supervisor.system_context == mock_system_context
    assert supervisor.session_manager == mock_session_manager
    assert supervisor.app_name == mock_args.effective_app_name
    assert supervisor.session_user_id == mock_args.effective_user_id
    assert supervisor.session_id == mock_args.effective_session_id
    assert supervisor.model_factory == mock_model_factory
    assert supervisor.agent_manager == mock_agent_manager


@pytest.mark.asyncio
async def test_create_agent_default(supervisor):
    """Test that _create_agent creates a default agent when agent_type is 'default'."""
    async with supervisor._create_agent("default") as agent:
        assert agent is not None
    
    # Verify create_default_agent was called
    supervisor.agent_manager.create_default_agent.assert_called_once_with(
        supervisor.system_context.get_system_message(),
    )
    supervisor.agent_manager.create_agent.assert_not_called()


@pytest.mark.asyncio
async def test_create_agent_non_default(supervisor):
    """Test that _create_agent attempts to create a specific agent for non-default types."""
    async with supervisor._create_agent("custom_agent") as agent:
        assert agent is not None
    
    # Verify create_agent was called with the correct agent type
    supervisor.agent_manager.create_agent.assert_called_once_with("custom_agent")


@pytest.mark.asyncio
async def test_create_agent_fallback(supervisor):
    """Test that _create_agent falls back to default agent if creation fails."""
    # Make create_agent raise an exception
    supervisor.agent_manager.create_agent.side_effect = ValueError("Agent not found")
    
    async with supervisor._create_agent("non_existent") as agent:
        assert agent is not None
    
    # Verify create_agent was called with the non-existent agent
    supervisor.agent_manager.create_agent.assert_called_once_with("non_existent")
    
    # Verify create_default_agent was called as a fallback
    supervisor.agent_manager.create_default_agent.assert_called_once_with(
        supervisor.system_context.get_system_message(),
    )


@pytest.mark.asyncio
async def test_run_async(supervisor):
    """Test that run_async properly processes a prompt and runs the agent."""
    # Create a mock processed prompt
    mock_prompt = MagicMock()
    mock_prompt.prompt = "Test prompt"
    mock_prompt.mentions = []
    
    # Mock the runner
    mock_runner = MagicMock()
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content.parts = [MagicMock()]
    mock_event.content.parts[0].text = "Agent response"
    
    # Mock the async iterable
    async def mock_run_async(*args, **kwargs):
        yield mock_event
    
    mock_runner.run_async = mock_run_async
    
    # Patch Runner constructor
    with patch("streetrace.workflow.supervisor.Runner", return_value=mock_runner):
        await supervisor.run_async(mock_prompt)
    
    # Verify session_manager methods were called
    supervisor.session_manager.get_or_create_session.assert_called_once()
    supervisor.session_manager.post_process.assert_called_once()