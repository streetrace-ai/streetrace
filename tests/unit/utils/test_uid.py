"""Tests for the user identity utility functions.

This test module verifies that the uid module correctly identifies users through
various methods including GitHub, Git, and OS username fallbacks.
"""

import subprocess
from unittest.mock import MagicMock, patch

from streetrace.utils.uid import get_user_identity


class TestGetUserIdentity:
    """Test suite for the get_user_identity function."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_github_identification(self, mock_which, mock_run):
        """Test successful user identification via GitHub CLI."""
        # Setup mocks
        mock_which.return_value = "/usr/bin/gh"  # gh is available
        mock_run.return_value = MagicMock(
            stdout="github-user\n",
            stderr="",
            returncode=0,
        )

        # Call function
        result = get_user_identity()

        # Verify GitHub CLI was used
        assert result == "github-user"
        mock_which.assert_called_with("gh")
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["gh", "api", "user", "--jq", ".login"]

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_github_fallback_to_git(self, mock_which, mock_run):
        """Test fallback to Git when GitHub CLI fails."""
        # Setup mocks - gh exists but fails, git succeeds
        mock_which.side_effect = (
            lambda cmd: "/usr/bin/" + cmd if cmd in ["gh", "git"] else None
        )

        # First call (gh) raises exception
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "gh", "Not logged in"),
            MagicMock(stdout="git-user\n", stderr="", returncode=0),
        ]

        # Call function
        result = get_user_identity()

        # Verify Git was used as fallback
        assert result == "git-user"
        assert mock_which.call_count == 2
        assert mock_run.call_count == 2
        assert mock_run.call_args[0][0] == ["git", "config", "user.name"]

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_github_fallback_to_git_empty_output(self, mock_which, mock_run):
        """Test fallback to Git when GitHub CLI returns empty output."""
        # Setup mocks - gh exists but returns empty, git succeeds
        mock_which.side_effect = (
            lambda cmd: "/usr/bin/" + cmd if cmd in ["gh", "git"] else None
        )

        # gh returns empty output, git returns valid output
        mock_run.side_effect = [
            MagicMock(stdout="\n", stderr="", returncode=0),  # Empty output
            MagicMock(stdout="git-user\n", stderr="", returncode=0),
        ]

        # Call function
        result = get_user_identity()

        # Verify Git was used as fallback
        assert result == "git-user"
        assert mock_which.call_count == 2
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("getpass.getuser")
    def test_fallback_to_os_user(self, mock_getuser, mock_which, mock_run):
        """Test fallback to OS username when both GitHub and Git fail."""
        # Setup mocks - neither gh nor git are available
        mock_which.return_value = None
        mock_getuser.return_value = "os-user"

        # Call function
        result = get_user_identity()

        # Verify OS username was used
        assert result == "os-user"
        assert mock_which.call_count == 2
        assert mock_run.call_count == 0
        mock_getuser.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("getpass.getuser")
    def test_git_failure_fallback_to_os(self, mock_getuser, mock_which, mock_run):
        """Test fallback to OS username when Git is available but fails."""
        # Setup mocks - gh doesn't exist, git exists but fails
        mock_which.side_effect = lambda cmd: "/usr/bin/git" if cmd == "git" else None
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", "git error")
        mock_getuser.return_value = "os-user"

        # Call function
        result = get_user_identity()

        # Verify OS username was used as final fallback
        assert result == "os-user"
        assert mock_which.call_count == 2
        assert mock_run.call_count == 1
        mock_getuser.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_github_returns_correct_format(self, mock_which, mock_run):
        """Test that whitespace is properly stripped from GitHub response."""
        # Setup mocks with whitespace in output
        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(
            stdout="  github-user-with-spaces  \n",
            stderr="",
            returncode=0,
        )

        # Call function
        result = get_user_identity()

        # Verify whitespace was stripped
        assert result == "github-user-with-spaces"

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_git_returns_correct_format(self, mock_which, mock_run):
        """Test that whitespace is properly stripped from Git response."""
        # Setup mocks - gh doesn't exist, git succeeds but with whitespace
        mock_which.side_effect = lambda cmd: "/usr/bin/git" if cmd == "git" else None
        mock_run.return_value = MagicMock(
            stdout="  git-user-with-spaces  \n",
            stderr="",
            returncode=0,
        )

        # Call function
        result = get_user_identity()

        # Verify whitespace was stripped
        assert result == "git-user-with-spaces"
