"""Test for handling non-directory items in get_available_agents."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from streetrace.agents.agent_loader import get_available_agents


def test_get_available_agents_with_non_directory_items():
    """Test that non-directory items are skipped in get_available_agents."""
    mock_base_dir = MagicMock(spec=Path)
    mock_base_dir.exists.return_value = True
    mock_base_dir.is_dir.return_value = True

    # Mock directory items
    mock_agent_dir = MagicMock(spec=Path)
    mock_agent_dir.is_dir.return_value = True

    # Mock file (non-directory item)
    mock_file = MagicMock(spec=Path)
    mock_file.is_dir.return_value = False

    # Set up the mock directory to return both a file and a directory
    mock_base_dir.iterdir.return_value = [mock_agent_dir, mock_file]

    # Mock _validate_impl to return a mock agent
    with patch(
        "streetrace.agents.agent_loader._validate_impl",
        return_value=MagicMock(),
    ) as mock_validate:
        result = get_available_agents([mock_base_dir])

        # Verify _validate_impl was called only once (for the directory)
        assert mock_validate.call_count == 1
        mock_validate.assert_called_once_with(mock_agent_dir)

        # We expect one agent since the file is skipped but the directory is processed
        assert len(result) == 1
