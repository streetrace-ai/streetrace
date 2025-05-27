"""Tests for the run_agent tool."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.tools.definitions.result import OpResultCode
from streetrace.tools.definitions.run_agent import (
    RunAgentContext,
    run_agent,
)


@pytest.fixture
def mock_agent_manager():
    """Create a mock AgentManager."""
    mock = MagicMock()

    # Mock the context manager
    async_cm = AsyncMock()
    mock_agent = MagicMock()
    async_cm.__aenter__.return_value = mock_agent
    async_cm.__aexit__.return_value = None

    mock.create_agent.return_value = async_cm
    return mock


@pytest.fixture
def mock_model_factory():
    """Create a mock ModelFactory."""
    mock = MagicMock()
    mock.get_model.return_value = "mock_model"
    return mock


@pytest.fixture
def initialized_context(mock_agent_manager, mock_model_factory):
    """Create and initialize a RunAgentContext."""
    context = RunAgentContext.get_instance()
    context.initialize(mock_agent_manager, mock_model_factory)
    return context


@pytest.fixture
def reset_singleton():
    """Reset the RunAgentContext singleton between tests."""
    yield
    RunAgentContext._instance = None


@patch("streetrace.tools.definitions.run_agent.Runner")
async def test_run_agent_success(
    mock_runner_class, initialized_context, mock_agent_manager, reset_singleton,
):
    """Test successfully running an agent."""
    # Arrange
    mock_runner = MagicMock()
    mock_runner_class.return_value = mock_runner

    # Create a mock event with final response
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content = MagicMock()
    mock_event.content.parts = [MagicMock()]
    mock_event.content.parts[0].text = "Final response from agent"

    # Setup the runner to yield the mock event
    mock_runner.run_async = AsyncMock()
    mock_runner.run_async.return_value.__aiter__.return_value = [mock_event]

    # Act
    result = await run_agent(
        Path("/fake/work/dir"),
        "test_agent",
        "Test input",
        "default",
    )

    # Assert
    assert result.result == OpResultCode.SUCCESS
    assert result.output == "Final response from agent"
    assert result.error is None

    # Verify correct calls
    mock_agent_manager.create_agent.assert_called_once_with("test_agent", "default")
    mock_runner_class.assert_called_once()
    mock_runner.run_async.assert_called_once()

    # Check that content was created correctly
    content_arg = mock_runner.run_async.call_args[1]["new_message"]
    assert content_arg.role == "user"
    assert len(content_arg.parts) == 1
    assert content_arg.parts[0].text == "Test input"


@patch("streetrace.tools.definitions.run_agent.Runner")
async def test_run_agent_escalation(
    mock_runner_class, initialized_context, mock_agent_manager, reset_singleton,
):
    """Test running an agent that escalates."""
    # Arrange
    mock_runner = MagicMock()
    mock_runner_class.return_value = mock_runner

    # Create a mock event with escalation
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content = None
    mock_event.actions = MagicMock()
    mock_event.actions.escalate = True
    mock_event.error_message = "Error in agent execution"

    # Setup the runner to yield the mock event
    mock_runner.run_async = AsyncMock()
    mock_runner.run_async.return_value.__aiter__.return_value = [mock_event]

    # Act
    result = await run_agent(
        Path("/fake/work/dir"),
        "test_agent",
        "Test input",
    )

    # Assert
    assert result.result == OpResultCode.SUCCESS
    assert result.output == "Agent escalated: Error in agent execution"
    assert result.error is None


async def test_run_agent_uninitialized_context():
    """Test running an agent with an uninitialized context."""
    # Arrange - ensure context is reset
    RunAgentContext._instance = None

    # Act
    result = await run_agent(
        Path("/fake/work/dir"),
        "test_agent",
        "Test input",
    )

    # Assert
    assert result.result == OpResultCode.FAILURE
    assert result.output is None
    assert "not properly initialized" in result.error


@patch("streetrace.tools.definitions.run_agent.Runner")
async def test_run_agent_exception(
    mock_runner_class, initialized_context, mock_agent_manager, reset_singleton,
):
    """Test handling an exception during agent execution."""
    # Arrange
    mock_agent_manager.create_agent.side_effect = ValueError("Agent creation failed")

    # Act
    result = await run_agent(
        Path("/fake/work/dir"),
        "test_agent",
        "Test input",
    )

    # Assert
    assert result.result == OpResultCode.FAILURE
    assert result.output is None
    assert "Failed to run agent" in result.error


def test_run_agent_context_singleton():
    """Test that RunAgentContext behaves as a singleton."""
    # Act
    context1 = RunAgentContext.get_instance()
    context2 = RunAgentContext.get_instance()

    # Assert
    assert context1 is context2  # Same instance
