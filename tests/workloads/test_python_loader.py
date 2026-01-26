"""Tests for PythonDefinitionLoader class."""

from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.workloads.loader import DefinitionLoader
from streetrace.workloads.python_definition import PythonWorkloadDefinition

if TYPE_CHECKING:

    from streetrace.workloads.python_loader import PythonDefinitionLoader


# Valid agent.py content for testing
VALID_AGENT_PY = '''\
"""Test agent module."""

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from a2a.types import AgentCapabilities


class TestAgent(StreetRaceAgent):
    """Test agent implementation."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        """Provide an A2A AgentCard."""
        return StreetRaceAgentCard(
            name="test_agent",
            description="A test agent for unit testing",
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[],
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        """Create a mock agent."""
        from unittest.mock import MagicMock
        return MagicMock()
'''

# Agent with custom description
AGENT_WITH_DESCRIPTION = '''\
"""Custom agent with specific description."""

from streetrace.agents.street_race_agent import StreetRaceAgent
from streetrace.agents.street_race_agent_card import StreetRaceAgentCard
from a2a.types import AgentCapabilities


class CustomDescAgent(StreetRaceAgent):
    """Custom description agent."""

    def get_agent_card(self) -> StreetRaceAgentCard:
        return StreetRaceAgentCard(
            name="custom_agent",
            description="A custom agent with specific functionality",
            version="2.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[],
        )

    async def create_agent(self, model_factory, tool_provider, system_context):
        from unittest.mock import MagicMock
        return MagicMock()
'''

# Invalid Python (syntax error)
INVALID_PYTHON_SYNTAX = """\
def broken(
    # Missing closing parenthesis
"""

# Python without StreetRaceAgent class
PYTHON_NO_AGENT = '''\
"""Module without agent."""

class NotAnAgent:
    """Just a regular class."""
    pass
'''

# Python with agent that fails to instantiate
PYTHON_AGENT_FAILS_INIT = '''\
"""Agent that fails during init."""

from streetrace.agents.street_race_agent import StreetRaceAgent


class FailingAgent(StreetRaceAgent):
    """Agent that fails."""

    def __init__(self):
        raise RuntimeError("Intentional failure")

    def get_agent_card(self):
        pass

    async def create_agent(self, model_factory, tool_provider, system_context):
        pass
'''


def make_resolution(
    content: str,
    source: str,
    file_path: Path | None,
) -> SourceResolution:
    """Create a SourceResolution for testing."""
    return SourceResolution(
        content=content,
        source=source,
        source_type=SourceType.FILE_PATH,
        file_path=file_path,
        format="python",
    )


class TestPythonDefinitionLoaderLoad:
    """Test PythonDefinitionLoader.load() method."""

    @pytest.fixture
    def loader(self) -> "PythonDefinitionLoader":
        """Create a PythonDefinitionLoader instance."""
        from streetrace.workloads.python_loader import PythonDefinitionLoader

        return PythonDefinitionLoader()

    def test_load_imports_valid_agent_module(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load imports a valid agent module."""
        agent_dir = tmp_path / "valid_agent"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(VALID_AGENT_PY)
        resolution = make_resolution(VALID_AGENT_PY, str(agent_dir), agent_dir)

        definition = loader.load(resolution)

        assert isinstance(definition, PythonWorkloadDefinition)
        assert definition.name == "test_agent"
        assert definition.metadata.source_path == agent_dir
        assert definition.metadata.format == "python"
        assert issubclass(definition.agent_class, StreetRaceAgent)
        assert isinstance(definition.module, ModuleType)

    def test_load_extracts_metadata_from_agent_card(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load extracts metadata from the agent card."""
        agent_dir = tmp_path / "custom_agent"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(AGENT_WITH_DESCRIPTION)
        resolution = make_resolution(AGENT_WITH_DESCRIPTION, str(agent_dir), agent_dir)

        definition = loader.load(resolution)

        assert definition.name == "custom_agent"
        assert definition.metadata.name == "custom_agent"
        assert "specific functionality" in definition.metadata.description

    def test_load_raises_for_none_file_path(
        self, loader: "PythonDefinitionLoader",
    ) -> None:
        """Test load raises ValueError when file_path is None (HTTP sources)."""
        resolution = make_resolution(
            VALID_AGENT_PY,
            "https://example.com/agent",
            None,
        )

        with pytest.raises(ValueError, match="requires file_path"):
            loader.load(resolution)

    def test_load_raises_for_file_not_directory(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises ValueError when file_path is a file, not directory."""
        file_path = tmp_path / "agent.py"
        file_path.write_text(VALID_AGENT_PY)
        resolution = make_resolution(VALID_AGENT_PY, str(file_path), file_path)

        with pytest.raises(ValueError, match="must be a directory"):
            loader.load(resolution)

    def test_load_raises_for_directory_without_agent_py(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises ValueError for directory without agent.py."""
        agent_dir = tmp_path / "no_agent"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        resolution = make_resolution("", str(agent_dir), agent_dir)

        with pytest.raises(ValueError, match="Agent definition not found"):
            loader.load(resolution)

    def test_load_raises_for_invalid_python_syntax(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises ValueError for invalid Python syntax."""
        agent_dir = tmp_path / "syntax_error"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(INVALID_PYTHON_SYNTAX)
        resolution = make_resolution(INVALID_PYTHON_SYNTAX, str(agent_dir), agent_dir)

        with pytest.raises(ValueError, match="Failed to import"):
            loader.load(resolution)

    def test_load_raises_for_module_without_agent_class(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises ValueError for module without StreetRaceAgent subclass."""
        agent_dir = tmp_path / "no_agent_class"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(PYTHON_NO_AGENT)
        resolution = make_resolution(PYTHON_NO_AGENT, str(agent_dir), agent_dir)

        with pytest.raises(ValueError, match="No StreetRaceAgent"):
            loader.load(resolution)

    def test_load_raises_for_agent_that_fails_to_instantiate(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test load raises ValueError for agent that fails during instantiation."""
        agent_dir = tmp_path / "failing_agent"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(PYTHON_AGENT_FAILS_INIT)
        resolution = make_resolution(PYTHON_AGENT_FAILS_INIT, str(agent_dir), agent_dir)

        with pytest.raises(ValueError, match="Failed to"):
            loader.load(resolution)


class TestPythonDefinitionLoaderProtocolCompliance:
    """Test that PythonDefinitionLoader satisfies the DefinitionLoader protocol."""

    def test_satisfies_definition_loader_protocol(self) -> None:
        """Test PythonDefinitionLoader satisfies the DefinitionLoader protocol."""
        from streetrace.workloads.python_loader import PythonDefinitionLoader

        loader = PythonDefinitionLoader()

        assert isinstance(loader, DefinitionLoader)

    def test_has_load_method(self) -> None:
        """Test PythonDefinitionLoader has load method."""
        from streetrace.workloads.python_loader import PythonDefinitionLoader

        loader = PythonDefinitionLoader()

        assert hasattr(loader, "load")
        assert callable(loader.load)


class TestPythonDefinitionLoaderMetadataExtraction:
    """Test metadata extraction from Python agent modules."""

    @pytest.fixture
    def loader(self) -> "PythonDefinitionLoader":
        """Create a PythonDefinitionLoader instance."""
        from streetrace.workloads.python_loader import PythonDefinitionLoader

        return PythonDefinitionLoader()

    def test_metadata_has_correct_format(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loaded definition has format='python' in metadata."""
        agent_dir = tmp_path / "format_test"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(VALID_AGENT_PY)
        resolution = make_resolution(VALID_AGENT_PY, str(agent_dir), agent_dir)

        definition = loader.load(resolution)

        assert definition.metadata.format == "python"

    def test_metadata_has_source_path(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test loaded definition preserves the source path."""
        agent_dir = tmp_path / "path_test"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(VALID_AGENT_PY)
        resolution = make_resolution(VALID_AGENT_PY, str(agent_dir), agent_dir)

        definition = loader.load(resolution)

        assert definition.metadata.source_path == agent_dir

    def test_module_is_correctly_imported(
        self, loader: "PythonDefinitionLoader", tmp_path: Path,
    ) -> None:
        """Test that the module is correctly imported and accessible."""
        agent_dir = tmp_path / "module_test"
        agent_dir.mkdir()
        (agent_dir / "__init__.py").write_text("")
        (agent_dir / "agent.py").write_text(VALID_AGENT_PY)
        resolution = make_resolution(VALID_AGENT_PY, str(agent_dir), agent_dir)

        definition = loader.load(resolution)

        assert isinstance(definition.module, ModuleType)
        assert hasattr(definition.module, "TestAgent")
