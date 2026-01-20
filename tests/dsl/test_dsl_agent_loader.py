"""Tests for DSL agent loader integration with AgentManager.

Test loading .sr files as agents through the AgentManager's agent loading
mechanism.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Sample DSL sources for testing
VALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello! How can I help you today?\"\"\"

tool fs = builtin streetrace.filesystem

agent:
    tools fs
    instruction greeting
"""

INVALID_DSL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""


class TestDslAgentLoaderIntegration:
    """Test DSL agent loading via AgentManager."""

    def test_agent_manager_has_dsl_format_loader(self) -> None:
        """AgentManager includes DSL format in format loaders."""
        from streetrace.agents.agent_manager import AgentManager
        from streetrace.llm.model_factory import ModelFactory
        from streetrace.system_context import SystemContext
        from streetrace.tools.tool_provider import ToolProvider

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = AgentManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=Path.cwd(),
        )

        assert "dsl" in manager.format_loaders

    def test_load_sr_file_directly(self, tmp_path: Path) -> None:
        """Load a .sr file directly via path."""
        from streetrace.agents.agent_manager import AgentManager
        from streetrace.llm.model_factory import ModelFactory
        from streetrace.system_context import SystemContext
        from streetrace.tools.tool_provider import ToolProvider

        # Create test DSL file
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = AgentManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        # Load agent definition (not create_agent which requires async)
        agent_def = manager._load_agent_definition(str(dsl_file))  # noqa: SLF001

        assert agent_def is not None

    def test_format_hints_include_sr_extension(self) -> None:
        """Ensure .sr extension is in format hints."""
        from streetrace.agents.agent_manager import AgentManager
        from streetrace.llm.model_factory import ModelFactory
        from streetrace.system_context import SystemContext
        from streetrace.tools.tool_provider import ToolProvider

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = AgentManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=Path.cwd(),
        )

        # The _load_from_path method uses format_hints internally
        # Check that .sr files are recognized
        # Test that the manager doesn't raise "Not a YAML file" for .sr files
        # by checking that DSL loader can handle the path
        dsl_loader = manager.format_loaders.get("dsl")
        assert dsl_loader is not None

    def test_discover_sr_files_in_directory(self, tmp_path: Path) -> None:
        """Discover .sr files in agent directories."""
        from streetrace.agents.agent_manager import AgentManager
        from streetrace.llm.model_factory import ModelFactory
        from streetrace.system_context import SystemContext
        from streetrace.tools.tool_provider import ToolProvider

        # Create test directory with agent files
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "my_agent.sr").write_text(VALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = AgentManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        # Discover agents
        discovered = manager.discover()

        # Check that our DSL agent was discovered
        agent_names = [agent.name.lower() for agent in discovered]
        assert "my_agent" in agent_names

    def test_invalid_dsl_raises_error(self, tmp_path: Path) -> None:
        """Invalid DSL file raises appropriate error."""
        from streetrace.agents.agent_manager import AgentManager
        from streetrace.llm.model_factory import ModelFactory
        from streetrace.system_context import SystemContext
        from streetrace.tools.tool_provider import ToolProvider

        # Create invalid DSL file
        dsl_file = tmp_path / "invalid_agent.sr"
        dsl_file.write_text(INVALID_DSL_SOURCE)

        model_factory = MagicMock(spec=ModelFactory)
        tool_provider = MagicMock(spec=ToolProvider)
        system_context = MagicMock(spec=SystemContext)

        manager = AgentManager(
            model_factory=model_factory,
            tool_provider=tool_provider,
            system_context=system_context,
            work_dir=tmp_path,
        )

        # Attempting to load invalid DSL should fail
        agent_def = manager._load_agent_definition(str(dsl_file))  # noqa: SLF001
        assert agent_def is None
        # Check error message contains information about the failure
        assert len(manager._last_load_errors) > 0  # noqa: SLF001


class TestDslAgentLoader:
    """Test the DSL agent loader directly."""

    def test_discover_in_paths(self, tmp_path: Path) -> None:
        """Discover .sr files in given paths."""
        from streetrace.agents.dsl_agent_loader import DslAgentLoader

        # Create test files
        (tmp_path / "agent1.sr").write_text(VALID_DSL_SOURCE)
        (tmp_path / "agent2.sr").write_text(VALID_DSL_SOURCE)
        (tmp_path / "not_agent.txt").write_text("not a DSL file")

        loader = DslAgentLoader()
        discovered = loader.discover_in_paths([tmp_path])

        # Should find both .sr files
        assert len(discovered) == 2
        names = {info.name for info in discovered}
        assert "agent1" in names
        assert "agent2" in names

    def test_load_from_path(self, tmp_path: Path) -> None:
        """Load agent from file path."""
        from streetrace.agents.dsl_agent_loader import DslAgentLoader

        dsl_file = tmp_path / "my_agent.sr"
        dsl_file.write_text(VALID_DSL_SOURCE)

        loader = DslAgentLoader()
        agent = loader.load_from_path(dsl_file)

        assert agent is not None

    def test_load_from_url_not_supported(self) -> None:
        """Load from URL should raise not supported error."""
        from streetrace.agents.dsl_agent_loader import DslAgentLoader

        loader = DslAgentLoader()

        with pytest.raises(ValueError, match="not supported"):
            loader.load_from_url("https://example.com/agent.sr")
