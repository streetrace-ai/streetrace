"""Tests for YAML agent loader."""

import tempfile
from pathlib import Path

from streetrace.utils.file_discovery import find_files


class TestAgentFileDiscovery:
    """Test agent file discovery."""

    def test_discover_agent_files_empty_dir(self):
        """Test discovering agents in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = find_files([Path(tmpdir)], "*.yaml")
            assert files == []

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

            files = find_files([agents_dir, tmppath], "*.yaml") + find_files(
                [agents_dir, tmppath],
                "*.yml",
            )
            file_names = [f.name for f in files]
            assert "test1.yml" in file_names
            assert "test2.yaml" in file_names
            assert "custom.agent.yml" in file_names
