"""Integration tests for PythonDefinitionLoader with filesystem fixtures."""

from pathlib import Path

from streetrace.agents.resolver import SourceResolver
from streetrace.workloads.python_loader import PythonDefinitionLoader
from tests.unit.agents.agent_loader.fixtures.fixture_generator import (
    AgentFixtureGenerator,
)


def test_get_available_agents_with_real_files():
    """Test discovering agents from actual directories."""
    with AgentFixtureGenerator() as (base_dir, agent_dirs):
        # Use SourceResolver for discovery (loaders no longer have discover())
        resolver = SourceResolver()
        discovered = resolver.discover([base_dir])

        # Filter for Python agents only (format = "python")
        python_resolutions = {
            name: res
            for name, res in discovered.items()
            if res.format == "python"
        }

        # Should find 2 valid agents (valid_agent1 and valid_agent2)
        assert len(python_resolutions) == 2

        # Load definitions from discovered resolutions
        loader = PythonDefinitionLoader()
        definitions = [loader.load(res) for res in python_resolutions.values()]

        # Verify agent names
        agent_names = sorted([d.metadata.name for d in definitions])
        assert agent_names == ["ValidAgent1", "ValidAgent2"]

        # Verify description
        expected_description = "Test agent for agent_loader tests"
        for definition in definitions:
            assert definition.metadata.description == expected_description

            # Check that agent_class is properly loaded
            assert definition.agent_class is not None
            assert definition.module is not None


def test_discover_agents_with_nonexistent_directory():
    """Test discovering agents from a nonexistent directory."""
    # SourceResolver.discover() handles non-existent paths gracefully
    nonexistent_path = Path("~/nonexistent_directory").expanduser()
    resolver = SourceResolver()
    discovered = resolver.discover([nonexistent_path])
    assert discovered == {}
