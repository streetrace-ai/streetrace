"""Test version functionality."""

from unittest.mock import patch

import pytest

from streetrace.version import show_version


def test_show_version_with_valid_version():
    """Test that show_version displays the correct version when package is found."""
    with patch("streetrace.version.version") as mock_version:
        mock_version.return_value = "1.2.3"

        with patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                show_version()

            mock_version.assert_called_once_with("streetrace")
            mock_print.assert_called_once_with("StreetRace🚗💨 1.2.3")
            assert exc_info.value.code == 0


def test_show_version_with_missing_package():
    """Test that show_version handles missing package gracefully."""
    with patch("streetrace.version.version") as mock_version:
        mock_version.side_effect = Exception("Package not found")

        with patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                show_version()

            mock_version.assert_called_once_with("streetrace")
            mock_print.assert_called_once_with("StreetRace🚗💨 (version unknown)")
            assert exc_info.value.code == 0


def test_show_version_exit_code():
    """Test that show_version exits with code 0."""
    with (
        patch("streetrace.version.version", return_value="1.0.0"),
        patch("builtins.print"),
    ):
        with pytest.raises(SystemExit) as exc_info:
            show_version()

        assert exc_info.value.code == 0
