"""Tests for the AgentInfo class."""

from types import ModuleType
from unittest.mock import MagicMock

import pytest

from streetrace.agents.agent_loader import AgentInfo
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard


@pytest.fixture
def mock_agent_card():
    """Create a mock StreetRaceAgentCard."""
    mock_card = MagicMock(spec=StreetRaceAgentCard)
    mock_card.name = "TestAgent"
    mock_card.description = "A test agent for testing AgentInfo"
    return mock_card


@pytest.fixture
def mock_module():
    """Create a mock module."""
    mock = MagicMock(spec=ModuleType)
    mock.__name__ = "test_agent_module"
    return mock


def test_agent_info_initialization(mock_agent_card, mock_module):
    """Test initializing an AgentInfo object with required parameters."""
    # Create an AgentInfo instance
    agent_info = AgentInfo(agent_card=mock_agent_card, module=mock_module)

    # Verify properties
    assert agent_info.agent_card == mock_agent_card
    assert agent_info.module == mock_module


def test_agent_info_attribute_access(mock_agent_card, mock_module):
    """Test accessing attributes of an AgentInfo object."""
    # Create an AgentInfo instance
    agent_info = AgentInfo(agent_card=mock_agent_card, module=mock_module)

    # Verify we can access attributes through the agent_card
    assert agent_info.agent_card.name == "TestAgent"
    assert agent_info.agent_card.description == "A test agent for testing AgentInfo"
