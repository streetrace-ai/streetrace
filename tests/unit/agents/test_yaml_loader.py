"""Tests for YAML agent loader."""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from streetrace.agents.yaml_agent_loader import (
    AgentCycleError,
    AgentValidationError,
    InlineAgentSpec,
    YamlAgentLoader,
    _load_agent_yaml,
)
from streetrace.agents.yaml_models import ToolSpec, YamlAgentDocument


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
                with pytest.raises(AgentValidationError, match="not found"):
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


class TestAgentDiscovery:
    """Test agent discovery functionality."""

    def test_discover_agents_empty(self):
        """Test discovering agents in empty environment."""
        # Override search paths to return empty list
        loader = YamlAgentLoader([])
        agents = loader.discover()
        assert agents == []

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

            loader = YamlAgentLoader([tmppath])
            agents = loader.discover()
            assert len(agents) == 2
            names = {agent.name for agent in agents}
            assert names == {"agent1", "agent2"}


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

            agents = YamlAgentLoader([tmppath]).discover()
            assert len(agents) == 1
            assert agents[0].name == "findable_agent"

            agent = YamlAgentLoader([tmppath]).load_agent("findable_agent")
            assert agent is not None
            assert agent.get_agent_card().name == "findable_agent"

    def test_find_agent_by_name_not_exists(self):
        """Test finding non-existent agent by name."""
        # Override search paths to return empty

        agents = YamlAgentLoader([]).discover()
        assert len(agents) == 0

        with pytest.raises(ValueError, match="Yaml agent not found"):
            YamlAgentLoader([]).load_agent("nonexistent_agent")
