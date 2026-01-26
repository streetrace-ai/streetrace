"""Tests for YAML agent loader helper functions.

Tests for YAML parsing, validation, and reference resolution functions
used by YamlDefinitionLoader.
"""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from streetrace.agents.base_agent_loader import (
    AgentCycleError,
    AgentValidationError,
)
from streetrace.agents.yaml_agent_loader import (
    InlineAgentSpec,
    _load_agent_yaml,
)
from streetrace.agents.yaml_models import ToolSpec, YamlAgentDocument
from streetrace.workloads.yaml_loader import YamlDefinitionLoader


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
                doc = _load_agent_yaml(Path(f.name))
                assert isinstance(doc, YamlAgentDocument)
                assert doc.get_name() == "test_agent"
                assert doc.get_description() == "A test agent for unit tests"
                assert doc.file_path == Path(f.name).resolve()
                assert doc.spec.prompt is None  # No prompt in minimal spec
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
                doc = _load_agent_yaml(Path(f.name))
                assert len(doc.spec.tools) == 2
                assert isinstance(doc.spec.tools[0], ToolSpec)
                assert doc.spec.tools[0].streetrace is not None
                assert isinstance(doc.spec.tools[1], ToolSpec)
                assert doc.spec.tools[1].mcp is not None
            finally:
                Path(f.name).unlink()

    def test_load_agent_with_prompt(self):
        """Test loading agent with prompt field."""
        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: prompt_agent
            description: An agent with a default prompt
            instruction: You are a helpful assistant
            prompt: Analyze the provided code for best practices
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(agent_yaml)
            f.flush()

            try:
                doc = _load_agent_yaml(Path(f.name))
                assert doc.get_name() == "prompt_agent"
                assert doc.spec.instruction == "You are a helpful assistant"
                assert doc.spec.prompt == "Analyze the provided code for best practices"
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
                    _load_agent_yaml(Path(f.name))
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
                    _load_agent_yaml(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_load_agent_file_not_found(self):
        """Test loading non-existent agent file."""
        with pytest.raises(AgentValidationError, match="not found"):
            _load_agent_yaml(Path("/nonexistent/agent.yml"))


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
            doc = _load_agent_yaml(main_file)

            assert len(doc.spec.sub_agents) == 1
            assert isinstance(doc.spec.sub_agents[0], InlineAgentSpec)
            sub_agent_spec = doc.spec.sub_agents[0].agent
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
                with pytest.raises(
                    AgentValidationError,
                    match="Could not resolve identifier",
                ):
                    _load_agent_yaml(Path(f.name))
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
                _load_agent_yaml(agent1_file)

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
                _load_agent_yaml(tmppath / "agent0.yml")


class TestYamlDefinitionLoaderWithSourceResolution:
    """Test YAML definition loader with SourceResolution API.

    Note: Discovery is handled by SourceResolver, not by loaders.
    These tests verify the loader's load(resolution) method.
    """

    def test_load_yaml_from_resolution(self):
        """Test loading from SourceResolution."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: agent1
            description: First agent
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file_path = tmppath / "agent1.yml"
            file_path.write_text(agent_yaml)

            resolution = SourceResolution(
                content=agent_yaml,
                source=str(file_path),
                source_type=SourceType.FILE_PATH,
                file_path=file_path,
                format="yaml",
            )

            loader = YamlDefinitionLoader()
            definition = loader.load(resolution)

            assert definition.metadata.name == "agent1"
            assert definition.metadata.description == "First agent"

    def test_load_multiple_agents_from_resolutions(self):
        """Test loading multiple agents via SourceResolver discovery."""
        from streetrace.agents.resolver import SourceResolver

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

            # Use SourceResolver for discovery
            resolver = SourceResolver()
            discovered = resolver.discover([tmppath])
            assert len(discovered) == 2

            # Load the discovered resolutions
            loader = YamlDefinitionLoader()
            definitions = [loader.load(r) for r in discovered.values()]
            names = {d.metadata.name for d in definitions}
            assert names == {"agent1", "agent2"}


class TestYamlDefinitionLoaderLoading:
    """Test YAML definition loader loading functionality."""

    def test_load_agent_from_resolution(self):
        """Test loading existing agent via SourceResolution."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        agent_yaml = dedent("""
            version: 1
            kind: agent
            name: findable_agent
            description: An agent that can be found
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file_path = tmppath / "agent.yml"
            file_path.write_text(agent_yaml)

            resolution = SourceResolution(
                content=agent_yaml,
                source=str(file_path),
                source_type=SourceType.FILE_PATH,
                file_path=file_path,
                format="yaml",
            )

            loader = YamlDefinitionLoader()
            definition = loader.load(resolution)

            assert definition is not None
            assert definition.metadata.name == "findable_agent"

    def test_load_agent_invalid_yaml_in_resolution(self):
        """Test loading invalid YAML content via SourceResolution."""
        from streetrace.agents.resolver import SourceResolution, SourceType

        resolution = SourceResolution(
            content="invalid: yaml: [",
            source="/test/path.yaml",
            source_type=SourceType.FILE_PATH,
            file_path=None,
            format="yaml",
        )

        loader = YamlDefinitionLoader()
        with pytest.raises(AgentValidationError, match="Invalid YAML"):
            loader.load(resolution)
