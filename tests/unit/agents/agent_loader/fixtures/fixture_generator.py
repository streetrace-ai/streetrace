"""Utilities for generating agent loader test fixtures."""

import tempfile
from pathlib import Path


class AgentFixtureGenerator:
    """Generate fixture agent files for testing agent_loader."""

    def __init__(self):
        """Initialize the fixture generator."""
        self.temp_dir = None
        self.agent_dirs = []

    def __enter__(self) -> tuple[Path, list[Path]]:
        """Create temporary directory structure for agent tests.

        Returns:
            Tuple containing:
                - Base directory path
                - List of agent directory paths

        """
        self.temp_dir = tempfile.TemporaryDirectory()
        base_dir = Path(self.temp_dir.name)

        # Create valid agent directories
        valid_agent1_dir = base_dir / "valid_agent1"
        valid_agent1_dir.mkdir()

        valid_agent2_dir = base_dir / "valid_agent2"
        valid_agent2_dir.mkdir()

        # Create an invalid agent directory (no agent.py)
        invalid_agent_dir = base_dir / "invalid_agent"
        invalid_agent_dir.mkdir()

        # Create a non-directory entry to test filtering
        (base_dir / "not_a_directory.txt").touch()

        # Create agent.py files
        with open(valid_agent1_dir / "agent.py", "w") as f:
            f.write(self._get_valid_agent_content("ValidAgent1"))

        with open(valid_agent2_dir / "agent.py", "w") as f:
            f.write(self._get_valid_agent_content("ValidAgent2"))

        # Create a malformed agent.py
        with open(base_dir / "malformed_agent", "w") as f:
            f.write("This is not a valid Python file [")

        self.agent_dirs = [valid_agent1_dir, valid_agent2_dir, invalid_agent_dir]
        return base_dir, self.agent_dirs

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary directories."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    def _get_valid_agent_content(self, agent_name: str) -> str:
        """Generate content for a valid agent implementation.

        Args:
            agent_name: Name to use for the agent class

        Returns:
            String containing the agent implementation

        """
        return f'''
from a2a.types import AgentCapabilities, AgentSkill
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard

class {agent_name}(StreetRaceAgent):
    """A test agent implementation."""

    def get_agent_card(self):
        """Provide an agent card for testing."""
        return StreetRaceAgentCard(
            capabilities=AgentCapabilities(
                streaming=True,
            ),
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"],
            description="Test agent for agent_loader tests",
            name="{agent_name}",
            skills=[
                AgentSkill(
                    id="test",
                    name="test",
                    description="Test skill",
                    tags=["test_tag"],
                )
            ],
            version="1.0.0",
        )

    async def create_agent(self, model_factory, tools):
        """Create the agent."""
        return None
'''
