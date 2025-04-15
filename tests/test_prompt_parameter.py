#!/usr/bin/env python3
"""
Unit tests for the --prompt parameter in main.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to the path to import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import streetrace.main as main


class TestPromptParameter(unittest.TestCase):
    """Test cases for the --prompt parameter in main.py"""

    @patch("builtins.input")  # Mock the input function
    @patch("argparse.ArgumentParser.parse_args")
    def test_non_interactive_mode(self, mock_parse_args, mock_input):
        """Test that the script runs in non-interactive mode with --prompt parameter"""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = "Test prompt"
        mock_parse_args.return_value = mock_args

        # Create a mock model setup
        mock_generate_tool = MagicMock()
        mock_generate_tool.return_value = []

        with patch("main.setup_model") as mock_setup:
            mock_setup.return_value = (mock_generate_tool, "test-model")

            # Call the main function
            main.main()

            # Assert the generate_with_tool was called with the prompt
            mock_generate_tool.assert_called_once()
            call_args = mock_generate_tool.call_args[0]
            self.assertEqual(call_args[0], "Test prompt")

            # Assert that input() was never called (non-interactive mode)
            mock_input.assert_not_called()

    @patch("builtins.input")  # Mock the input function
    @patch("argparse.ArgumentParser.parse_args")
    def test_interactive_mode(self, mock_parse_args, mock_input):
        """Test that the script runs in interactive mode without --prompt parameter"""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = None
        mock_parse_args.return_value = mock_args

        # Create a mock model setup
        mock_generate_tool = MagicMock()
        mock_generate_tool.return_value = []

        # Mock user input (first prompt then exit)
        mock_input.side_effect = ["Tell me about Python", "exit"]

        with patch("main.setup_model") as mock_setup:
            mock_setup.return_value = (mock_generate_tool, "test-model")

            # Call the main function
            main.main()

            # Assert that input() was called (interactive mode)
            self.assertEqual(mock_input.call_count, 2)

            # Assert generate_with_tool was called with user input
            mock_generate_tool.assert_called_once()
            call_args = mock_generate_tool.call_args[0]
            self.assertEqual(call_args[0], "Tell me about Python")


if __name__ == "__main__":
    unittest.main()
