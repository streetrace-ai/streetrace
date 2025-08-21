"""Tests for YAML agent loader."""

import os
import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from streetrace.agents.yaml_loader import (
    AgentCycleError,
    AgentDuplicateNameError,
    AgentValidationError,
    _discover_agent_files,
    _expand_path,
    _get_agent_search_paths,
    discover_agents,
    find_agent_by_name,
    load_agent_from_file,
    validate_agent_file,
)
from streetrace.agents.yaml_models import AgentDocument


class TestPathUtilities:
    """Test path utility functions."""

    def test_expand_path_absolute(self):
        """Test expanding absolute paths."""
        path = _expand_path("/tmp/test")  # noqa: S108
        assert path == Path("/tmp/test")  # noqa: S108

    def test_expand_path_home(self):
        """Test expanding home directory paths."""
        path = _expand_path("~/test")
        assert path == Path.home() / "test"

    def test_expand_path_relative(self):
        """Test expanding relative paths."""
        path = _expand_path("./test")
        assert path.is_absolute()
        assert path.name == "test"


class TestAgentSearchPaths:
    """Test agent search path discovery."""

    def test_get_agent_search_paths_default(self):
        """Test getting default agent search paths."""
        # Clear environment variable to test defaults
        old_paths = os.environ.get("STREETRACE_AGENT_PATHS")
        if old_paths:
            del os.environ["STREETRACE_AGENT_PATHS"]

        try:
            paths = _get_agent_search_paths()
            assert len(paths) >= 0  # May be empty if default dirs don't exist
        finally:
            if old_paths:
                os.environ["STREETRACE_AGENT_PATHS"] = old_paths

    def test_get_agent_search_paths_env(self):
        """Test getting search paths from environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir)
            os.environ["STREETRACE_AGENT_PATHS"] = str(test_path)

            try:
                paths = _get_agent_search_paths()
                assert test_path in paths
            finally:
                if "STREETRACE_AGENT_PATHS" in os.environ:
                    del os.environ["STREETRACE_AGENT_PATHS"]

    def test_get_agent_search_paths_invalid_env(self):
        """Test handling invalid paths in environment variable."""
        os.environ["STREETRACE_AGENT_PATHS"] = "/nonexistent/path:/another/bad/path"

        try:
            paths = _get_agent_search_paths()
            # Should not include invalid paths
            assert all(p.exists() for p in paths)
        finally:
            if "STREETRACE_AGENT_PATHS" in os.environ:
                del os.environ["STREETRACE_AGENT_PATHS"]


class TestAgentFileDiscovery:
    """Test agent file discovery."""

    def test_discover_agent_files_empty_dir(self):
        """Test discovering agents in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Override search paths to only include our temp directory
            old_get_paths = _get_agent_search_paths

            def mock_get_paths():
                return [Path(tmpdir)]

            import streetrace.agents.yaml_loader

            streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

            try:
                files = _discover_agent_files()
                assert files == []
            finally:
                streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001

    def test_discover_agent_files_with_agents(self):
        """Test discovering agents with YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create agents directory
            agents_dir = tmppath / "agents"
            agents_dir.mkdir()

            # Create agent files
            (agents_dir / "test1.yml").write_text("test: content")
            (agents_dir / "test2.yaml").write_text("test: content")
            (tmppath / "custom.agent.yml").write_text("test: content")

            # Override search paths
            old_get_paths = _get_agent_search_paths

            def mock_get_paths():
                return [agents_dir, tmppath]

            import streetrace.agents.yaml_loader

            streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

            try:
                files = _discover_agent_files()
                file_names = [f.name for f in files]
                assert "test1.yml" in file_names
                assert "test2.yaml" in file_names
                assert "custom.agent.yml" in file_names
            finally:
                streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001


class TestAgentLoading:
    """Test agent loading functionality."""

    def test_load_agent_minimal(self):
        """Test loading minimal valid agent."""
        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: test_agent
            description: A test agent for unit tests
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(agent_yaml)
            f.flush()

            try:
                doc = load_agent_from_file(Path(f.name))
                assert isinstance(doc, AgentDocument)
                assert doc.get_name() == "test_agent"
                assert doc.get_description() == "A test agent for unit tests"
                assert doc.file_path == Path(f.name).resolve()
            finally:
                Path(f.name).unlink()

    def test_load_agent_with_tools(self):
        """Test loading agent with tools."""
        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: tool_agent
            description: An agent with tools
            tools:
              - streetrace:
                  module: fs_tool
                  function: read_file
              - mcp:
                  name: filesystem
                  server:
                    type: stdio
                    command: npx
                    args: ["-y", "@mcp/filesystem"]
                  tools: ["read_file", "write_file"]
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(agent_yaml)
            f.flush()

            try:
                doc = load_agent_from_file(Path(f.name))
                assert len(doc.spec.tools) == 2
                assert doc.spec.tools[0].streetrace is not None
                assert doc.spec.tools[1].mcp is not None
            finally:
                Path(f.name).unlink()

    def test_load_agent_invalid_yaml(self):
        """Test loading agent with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(invalid_yaml)
            f.flush()

            try:
                with pytest.raises(AgentValidationError, match="Invalid YAML"):
                    load_agent_from_file(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_load_agent_invalid_spec(self):
        """Test loading agent with invalid specification."""
        invalid_spec = dedent("""
            version: 1
            kind: agent
            name: 123invalid
            description: Invalid agent name
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(invalid_spec)
            f.flush()

            try:
                with pytest.raises(AgentValidationError, match="validation failed"):
                    load_agent_from_file(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_load_agent_file_not_found(self):
        """Test loading non-existent agent file."""
        with pytest.raises(AgentValidationError, match="not found"):
            load_agent_from_file(Path("/nonexistent/agent.yml"))


class TestReferenceResolution:
    """Test $ref reference resolution."""

    def test_load_agent_with_ref(self):
        """Test loading agent with $ref to another agent."""
        # Create sub-agent
        sub_agent_yaml = dedent("""
            version: 1
            kind: agent
            name: sub_agent
            description: A sub agent
        """)

        # Create main agent with reference
        main_agent_yaml = dedent("""
            version: 1
            kind: agent
            name: main_agent
            description: Main agent with sub-agent
            sub_agents:
              - $ref: ./sub_agent.yml
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write files
            sub_file = tmppath / "sub_agent.yml"
            main_file = tmppath / "main_agent.yml"

            sub_file.write_text(sub_agent_yaml)
            main_file.write_text(main_agent_yaml)

            # Load main agent
            doc = load_agent_from_file(main_file)

            assert len(doc.spec.sub_agents) == 1
            sub_agent_spec = doc.spec.sub_agents[0].inline
            assert sub_agent_spec.name == "sub_agent"

    def test_load_agent_ref_not_found(self):
        """Test loading agent with $ref to non-existent file."""
        main_agent_yaml = dedent("""
            version: 1
            kind: agent
            name: main_agent
            description: Main agent with missing reference
            sub_agents:
              - $ref: ./nonexistent.yml
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(main_agent_yaml)
            f.flush()

            try:
                with pytest.raises(AgentValidationError, match="not found"):
                    load_agent_from_file(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_load_agent_circular_ref(self):
        """Test loading agent with circular references."""
        # Create two agents that reference each other
        agent1_yaml = dedent("""
            version: 1
            kind: agent
            name: agent1
            description: Agent 1
            sub_agents:
              - $ref: ./agent2.yml
        """)

        agent2_yaml = dedent("""
            version: 1
            kind: agent
            name: agent2
            description: Agent 2
            sub_agents:
              - $ref: ./agent1.yml
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            agent1_file = tmppath / "agent1.yml"
            agent2_file = tmppath / "agent2.yml"

            agent1_file.write_text(agent1_yaml)
            agent2_file.write_text(agent2_yaml)

            with pytest.raises(AgentCycleError, match="Circular reference"):
                load_agent_from_file(agent1_file)

    def test_load_agent_max_depth(self):
        """Test maximum reference depth limit."""
        # Create a chain of agents longer than MAX_REF_DEPTH
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a deep chain of references
            for i in range(10):  # Assuming MAX_REF_DEPTH is 5
                if i == 9:
                    # Final agent with no references
                    agent_yaml = dedent(f"""
                        version: 1
                        kind: agent
                        name: agent{i}
                        description: Agent {i}
                    """)
                else:
                    # Agent with reference to next
                    agent_yaml = dedent(f"""
                        version: 1
                        kind: agent
                        name: agent{i}
                        description: Agent {i}
                        sub_agents:
                          - $ref: ./agent{i + 1}.yml
                    """)

                (tmppath / f"agent{i}.yml").write_text(agent_yaml)

            with pytest.raises(AgentValidationError, match="Maximum reference depth"):
                load_agent_from_file(tmppath / "agent0.yml")


class TestAgentDiscovery:
    """Test agent discovery functionality."""

    def test_discover_agents_empty(self):
        """Test discovering agents in empty environment."""
        # Override search paths to return empty list
        old_get_paths = _get_agent_search_paths

        def mock_get_paths():
            return []

        import streetrace.agents.yaml_loader

        streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

        try:
            agents = discover_agents()
            assert agents == []
        finally:
            streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001

    def test_discover_agents_with_valid_agents(self):
        """Test discovering valid agents."""
        agent1_yaml = dedent("""
            version: 1
            kind: agent
            name: agent1
            description: First agent
        """)

        agent2_yaml = dedent("""
            version: 1
            kind: agent
            name: agent2
            description: Second agent
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "agent1.yml").write_text(agent1_yaml)
            (tmppath / "agent2.yml").write_text(agent2_yaml)

            # Override search paths
            old_get_paths = _get_agent_search_paths

            def mock_get_paths():
                return [tmppath]

            import streetrace.agents.yaml_loader

            streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

            try:
                agents = discover_agents()
                assert len(agents) == 2
                names = {agent.get_name() for agent in agents}
                assert names == {"agent1", "agent2"}
            finally:
                streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001

    def test_discover_agents_duplicate_names(self):
        """Test discovering agents with duplicate names raises error."""
        # Create two agents with the same name in different files
        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: duplicate_agent
            description: Duplicate agent
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "agent1.yml").write_text(agent_yaml)
            (tmppath / "agent2.yml").write_text(agent_yaml)

            # Override search paths
            old_get_paths = _get_agent_search_paths

            def mock_get_paths():
                return [tmppath]

            import streetrace.agents.yaml_loader

            streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

            try:
                with pytest.raises(
                    AgentDuplicateNameError,
                    match="Duplicate agent names",
                ):
                    discover_agents()
            finally:
                streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001


class TestAgentFinding:
    """Test agent finding by name."""

    def test_find_agent_by_name_exists(self):
        """Test finding existing agent by name."""
        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: findable_agent
            description: An agent that can be found
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "agent.yml").write_text(agent_yaml)

            # Override search paths
            old_get_paths = _get_agent_search_paths

            def mock_get_paths():
                return [tmppath]

            import streetrace.agents.yaml_loader

            streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

            try:
                agent = find_agent_by_name("findable_agent")
                assert agent is not None
                assert agent.get_name() == "findable_agent"
            finally:
                streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001

    def test_find_agent_by_name_not_exists(self):
        """Test finding non-existent agent by name."""
        # Override search paths to return empty
        old_get_paths = _get_agent_search_paths

        def mock_get_paths():
            return []

        import streetrace.agents.yaml_loader

        streetrace.agents.yaml_loader._get_agent_search_paths = mock_get_paths  # noqa: SLF001

        try:
            agent = find_agent_by_name("nonexistent_agent")
            assert agent is None
        finally:
            streetrace.agents.yaml_loader._get_agent_search_paths = old_get_paths  # noqa: SLF001


class TestAgentValidation:
    """Test agent validation functionality."""

    def test_validate_agent_file_valid(self):
        """Test validating a valid agent file."""
        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: valid_agent
            description: A valid agent
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(agent_yaml)
            f.flush()

            try:
                # Should not raise any exception
                validate_agent_file(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_validate_agent_file_invalid(self):
        """Test validating an invalid agent file."""
        invalid_yaml = dedent("""
            version: 1
            kind: agent
            name: 123invalid
            description: Invalid agent
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(invalid_yaml)
            f.flush()

            try:
                with pytest.raises(AgentValidationError):
                    validate_agent_file(Path(f.name))
            finally:
                Path(f.name).unlink()
