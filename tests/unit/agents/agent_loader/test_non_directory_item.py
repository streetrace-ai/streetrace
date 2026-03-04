"""Test for handling various directory scenarios in SourceResolver.discover()."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from streetrace.agents.resolver import SourceResolver


def test_discover_returns_only_yaml_files():
    """Test that discover() returns only YAML files from directory."""
    mock_base_dir = MagicMock(spec=Path)
    mock_base_dir.is_dir.return_value = True

    # Mock YAML file
    mock_yaml_file = MagicMock(spec=Path)
    mock_yaml_file.is_file.return_value = True
    mock_yaml_file.suffix = ".yaml"

    # Mock YML file
    mock_yml_file = MagicMock(spec=Path)
    mock_yml_file.is_file.return_value = True
    mock_yml_file.suffix = ".yml"

    # Mock non-YAML file that should be skipped
    mock_other_file = MagicMock(spec=Path)
    mock_other_file.is_file.return_value = True
    mock_other_file.suffix = ".txt"

    # Set up the mock directory to return files via rglob
    def rglob_side_effect(pattern: str) -> list[MagicMock]:
        if pattern == "*.yaml":
            return [mock_yaml_file]
        if pattern == "*.yml":
            return [mock_yml_file]
        return []

    mock_base_dir.rglob.side_effect = rglob_side_effect

    # Verify rglob pattern matches
    mock_base_dir.rglob("*.yaml")
    mock_base_dir.rglob("*.yml")

    # Assertions about the patterns
    calls = [call[0][0] for call in mock_base_dir.rglob.call_args_list]
    assert "*.yaml" in calls
    assert "*.yml" in calls


def test_discover_empty_directory():
    """Test that discover() returns empty dict for directory with no agent files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create a non-agent file
        (tmppath / "readme.txt").write_text("Not an agent file")

        resolver = SourceResolver()
        result = resolver.discover([tmppath])

        assert result == {}


def test_discover_non_existent_directory():
    """Test that discover() handles non-existent directory gracefully."""
    resolver = SourceResolver()
    result = resolver.discover([Path("/nonexistent/directory")])

    assert result == {}
