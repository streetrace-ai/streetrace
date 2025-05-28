"""Integration tests for agent_loader with filesystem fixtures."""

from pathlib import Path

from streetrace.agents.agent_loader import get_available_agents
from tests.unit.agents.agent_loader.fixtures.fixture_generator import (
    AgentFixtureGenerator,
)


def test_get_available_agents_with_real_files():
    """Test discovering agents from actual directories."""
    with AgentFixtureGenerator() as (base_dir, agent_dirs):
        # Get available agents from the temporary directory
        available_agents = get_available_agents([base_dir])

        # Should find 2 valid agents (valid_agent1 and valid_agent2)
        assert len(available_agents) == 2

        # Verify agent names
        agent_names = sorted([agent.agent_card.name for agent in available_agents])
        assert agent_names == ["ValidAgent1", "ValidAgent2"]

        # Verify agent card properties
        for agent in available_agents:
            assert agent.agent_card.description == "Test agent for agent_loader tests"
            assert agent.agent_card.version == "1.0.0"

            # Check that modules are properly loaded
            assert agent.module.__name__.startswith("agent_module_")


def test_get_available_agents_with_nonexistent_directory():
    """Test discovering agents from a nonexistent directory."""
    # This should not raise an exception but return an empty list
    nonexistent_path = Path("~/nonexistent_directory").expanduser()
    agents = get_available_agents([nonexistent_path])
    assert agents == []
