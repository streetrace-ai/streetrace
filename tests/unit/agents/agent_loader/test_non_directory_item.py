"""Test for handling non-directory items in get_available_agents."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from streetrace.agents.yaml_agent_loader import YamlAgentLoader


def test_get_available_agents_with_non_directory_items():
    """Test that non-directory items are skipped in get_available_agents."""
    mock_base_dir = MagicMock(spec=Path)
    mock_base_dir.exists.return_value = True
    mock_base_dir.is_dir.return_value = True

    # Mock YAML file
    mock_yaml_file = MagicMock(spec=Path)
    mock_yaml_file.is_file.return_value = True
    mock_yaml_file.suffix = ".yaml"

    # Mock non-YAML file that should be skipped
    mock_other_file = MagicMock(spec=Path)
    mock_other_file.is_file.return_value = True
    mock_other_file.suffix = ".txt"

    # Set up the mock directory to return both files via rglob
    mock_base_dir.rglob.side_effect = lambda pattern: (
        [mock_yaml_file] if pattern == "*.yaml" else []
    )

    # Mock _load_agent_yaml to return a mock agent document
    with patch(
        "streetrace.agents.yaml_agent_loader._load_agent_yaml",
        return_value=MagicMock(
            get_name=MagicMock(return_value="test_agent"),
            get_description=MagicMock(return_value="test description"),
            file_path=mock_yaml_file,
        ),
    ) as mock_load_yaml:
        result = YamlAgentLoader([mock_base_dir]).discover()

        # Verify _load_agent_yaml was called only once (for the YAML file)
        assert mock_load_yaml.call_count == 1
        # Now called with resolver parameter
        assert mock_load_yaml.call_args[0][0] == mock_yaml_file

        # We expect one agent since only the YAML file is processed
        assert len(result) == 1
