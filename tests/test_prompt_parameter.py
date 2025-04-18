#!/usr/bin/env python3
"""
Unit tests for the --prompt parameter in main.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Import main, which should now be able to import other modules
import streetrace.main as main

# We also need to mock the modules that main imports if they aren't available
# or if we don't want their side effects during testing main's argument parsing.
# Mock PromptProcessor before it's used in main
sys.modules["streetrace.prompt_processor"] = MagicMock()
sys.modules["streetrace.application"] = MagicMock()
sys.modules["streetrace.commands.command_executor"] = MagicMock()
sys.modules["streetrace.llm.llmapi_factory"] = MagicMock()
sys.modules["streetrace.messages"] = MagicMock()
sys.modules["streetrace.tools.tools"] = MagicMock()
sys.modules["streetrace.ui.console_ui"] = MagicMock()


class TestPromptParameter(unittest.TestCase):
    """Test cases for the --prompt parameter in main.py"""

    @patch("builtins.input")  # Mock the input function
    @patch("argparse.ArgumentParser.parse_args")
    @patch("streetrace.main.Application")  # Mock the Application class used in main
    def test_non_interactive_mode(self, MockApplication, mock_parse_args, mock_input):
        """Test that the script runs in non-interactive mode with --prompt parameter"""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = "Test prompt"
        mock_args.non_interactive = (
            True  # Assume prompt implies non-interactive if not specified
        )
        mock_parse_args.return_value = mock_args

        # Mock the Application instance and its run method
        mock_app_instance = MockApplication.return_value

        # Call the main function
        main.main()

        # Assert Application was initialized with the correct arguments
        MockApplication.assert_called_once()
        init_args, init_kwargs = MockApplication.call_args
        self.assertTrue(init_kwargs["non_interactive"])

        # Assert the run method was called with the prompt
        mock_app_instance.run.assert_called_once_with(initial_prompt="Test prompt")

        # Assert that input() was never called (non-interactive mode)
        mock_input.assert_not_called()

    @patch("builtins.input")  # Mock the input function
    @patch("argparse.ArgumentParser.parse_args")
    @patch("streetrace.main.Application")  # Mock the Application class used in main
    def test_interactive_mode(self, MockApplication, mock_parse_args, mock_input):
        """Test that the script runs in interactive mode without --prompt parameter"""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = None
        mock_args.non_interactive = (
            False  # Explicitly set to False or ensure default is False
        )
        mock_parse_args.return_value = mock_args

        # Mock the Application instance and its run method
        mock_app_instance = MockApplication.return_value

        # Call the main function
        main.main()

        # Assert Application was initialized correctly
        MockApplication.assert_called_once()
        init_args, init_kwargs = MockApplication.call_args
        self.assertFalse(init_kwargs.get("non_interactive", False))

        # Assert the run method was called without an initial prompt
        mock_app_instance.run.assert_called_once_with(initial_prompt=None)

        # Note: We don't assert input() here as the Application's run loop is mocked


if __name__ == "__main__":
    unittest.main()
