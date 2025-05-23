"""Unit tests for the --prompt parameter in main.py."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import main, which should now be able to import other modules
from streetrace import main


class TestPromptParameter(unittest.TestCase):
    """Test cases for the --prompt parameter in main.py."""

    @patch("pathlib.Path.is_dir")  # Mock path checks
    @patch("pathlib.Path.cwd")  # Mock getcwd
    @patch("builtins.input")  # Mock input
    @patch("argparse.ArgumentParser.parse_args")  # Mock arg parsing
    @patch("streetrace.main.Application")  # Mock Application class
    def test_non_interactive_mode(
        self,
        mock_application,
        mock_parse_args,
        mock_input,
        mock_getcwd,
        mock_isdir,
    ) -> None:
        """Test that the script runs in non-interactive mode with --prompt parameter."""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = "Test prompt"
        mock_args.path = None  # Assume default path
        mock_args.debug = False
        mock_args.provider = None  # Assume default provider
        mock_args.model = None
        # Non-interactive mode is implicitly true if prompt is given in Application
        mock_parse_args.return_value = mock_args

        mock_isdir.return_value = True  # Assume path is valid
        mock_getcwd.return_value = Path("/fake/cwd")

        # Mock the Application instance and its run method
        mock_app_instance = mock_application.return_value

        # Call the main function
        main.main()

        # Assert Application was initialized (basic check)
        mock_application.assert_called_once()

        # Assert the run method was called correctly for non-interactive
        mock_app_instance.run.assert_called_once()
        # Check the call arguments of run (Application should handle prompt)
        call_args, call_kwargs = mock_app_instance.run.call_args
        # Application's run doesn't take initial_prompt anymore directly
        # Instead, it checks args.prompt internally.

        # Assert that input() was never called (non-interactive mode)
        mock_input.assert_not_called()

    @patch("pathlib.Path.cwd")  # Mock getcwd
    @patch("pathlib.Path.is_dir")  # Mock getcwd
    @patch("argparse.ArgumentParser.parse_args")  # Mock arg parsing
    @patch("streetrace.main.Application")  # Mock Application class
    def test_interactive_mode(
        self,
        mock_application,
        mock_parse_args,
        mock_is_dir,
        mock_cwd,
    ) -> None:
        """Test that the script runs in interactive mode without --prompt parameter."""
        # Arrange
        mock_args = MagicMock()
        mock_args.prompt = None  # No prompt provided
        mock_args.path = None
        mock_args.debug = False
        mock_args.provider = "openai"  # Provide a valid provider name
        mock_args.model = None
        mock_parse_args.return_value = mock_args

        mock_is_dir.return_value = True
        mock_cwd.return_value = Path("/fake/cwd")

        # Mock the Application instance and its run method
        mock_app_instance = mock_application.return_value

        # Act
        main.main()

        # Assert Application was initialized (basic check)
        mock_application.assert_called_once()

        # Assert the run method was called correctly for interactive mode
        mock_app_instance.run.assert_called_once()
        call_args, call_kwargs = mock_app_instance.run.call_args
        # Interactive mode doesn't pass prompt to run
