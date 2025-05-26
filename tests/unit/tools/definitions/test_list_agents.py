"""Unit tests for the list_agents tool."""

from pathlib import Path
from unittest import mock

import pytest

from streetrace.tools.definitions.list_agents import (
    AgentInfo,
    discover_agents,
    import_agent_module,
    list_agents,
)
from streetrace.tools.definitions.result import OpResultCode


class MockModule:
    """Mock module for testing."""

    def __init__(self, metadata=None, has_run_agent=True):
        """Initialize mock module.

        Args:
            metadata: Optional metadata to return from get_agent_metadata
            has_run_agent: Whether the module has a run_agent function

        """
        self.metadata = metadata or {
            "name": "Test Agent",
            "description": "Test description",
        }
        self.has_run_agent = has_run_agent
        self.__name__ = "mock_module"

    def get_agent_metadata(self):
        """Return mock metadata."""
        return self.metadata

    def run_agent(self, input_text):
        """Mock run_agent function."""
        return {"response": f"Processed: {input_text}"}


@pytest.fixture
def mock_agent_dir(tmp_path):
    """Create a mock agent directory for testing."""
    agent_dir = tmp_path / "test_agent"
    agent_dir.mkdir()

    # Create agent.py file
    with open(agent_dir / "agent.py", "w") as f:
        f.write("""
def get_agent_metadata():
    return {"name": "Test Agent", "description": "Test description"}

def run_agent(input_text):
    return {"response": f"Processed: {input_text}"}
""")

    # Create README.md
    with open(agent_dir / "README.md", "w") as f:
        f.write("# Test Agent\n\nThis is a test agent for unit testing.")

    return agent_dir


@pytest.fixture
def mock_invalid_agent_dir(tmp_path):
    """Create a mock invalid agent directory (missing run_agent)."""
    agent_dir = tmp_path / "invalid_agent"
    agent_dir.mkdir()

    # Create agent.py without run_agent
    with open(agent_dir / "agent.py", "w") as f:
        f.write("""
def get_agent_metadata():
    return {"name": "Invalid Agent", "description": "Missing run_agent"}
""")

    return agent_dir


def test_import_agent_module(mock_agent_dir):
    """Test importing an agent module."""
    module = import_agent_module(mock_agent_dir)
    assert module is not None
    assert hasattr(module, "get_agent_metadata")
    assert hasattr(module, "run_agent")

    # Test with non-existent file
    with pytest.raises(FileNotFoundError, match="Agent definition not found"):
        import_agent_module(Path("/nonexistent"))


def test_discover_agents(mock_agent_dir, mock_invalid_agent_dir, tmp_path):
    """Test discovering agents."""
    base_dir = tmp_path

    # Test with valid and invalid agents
    agents = discover_agents([base_dir])
    assert len(agents) == 1
    assert agents[0]["name"] == "Test Agent"
    assert agents[0]["description"] == "Test description"

    # Test with empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    agents = discover_agents([empty_dir])
    assert len(agents) == 0

    # Test with non-existent directory
    agents = discover_agents([Path("/nonexistent")])
    assert len(agents) == 0


def test_list_agents():
    """Test the list_agents function."""
    # Test successful case
    mock_agents = [
        AgentInfo(
            name="Test Agent",
            path="agents/test",
            description="Test description",
        ),
    ]

    with mock.patch(
        "streetrace.tools.definitions.list_agents.discover_agents",
        return_value=mock_agents,
    ):
        result = list_agents(Path("/fake/work_dir"))
        assert result["result"] == OpResultCode.SUCCESS
        assert len(result["output"]) == 1
        assert result["output"][0]["name"] == "Test Agent"

    # Test failure case
    with mock.patch(
        "streetrace.tools.definitions.list_agents.discover_agents",
        side_effect=OSError("Test error"),
    ):
        result = list_agents(Path("/fake/work_dir"))
        assert result["result"] == OpResultCode.FAILURE
        assert "Failed to list agents" in result["error"]
