"""Tests for YAML agent loader helper functions.

Tests for YAML parsing, validation, and reference resolution functions
used by YamlDefinitionLoader.
"""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from streetrace.agents.base_agent_loader import (
    AgentValidationError,
)
from streetrace.workloads.yaml_loader import YamlDefinitionLoader


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
