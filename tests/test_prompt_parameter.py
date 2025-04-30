#!/usr/bin/env python3
"""Unit tests for the --prompt parameter in main.py."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import main, which should now be able to import other modules
from streetrace import main

# We also need to mock the modules that main imports if they aren't available
# or if we don't want their side effects during testing main's argument parsing.
# Mock components to isolate main's logic
sys.modules["streetrace.prompt_processor"] = MagicMock()
sys.modules["streetrace.application"] = MagicMock()
sys.modules["streetrace.commands.command_executor"] = MagicMock()
sys.modules["streetrace.llm.llmapi_factory"] = MagicMock()
sys.modules["streetrace.messages"] = MagicMock()
sys.modules["streetrace.tools.tools"] = MagicMock()
sys.modules["streetrace.ui.console_ui"] = MagicMock()
sys.modules["streetrace.interaction_manager"] = MagicMock()


class TestPromptParameter(unittest.TestCase):
    """Test cases for the --prompt parameter in main.py."""

    @patch("streetrace.main.get_ai_provider")  # Patch the factory function
    @patch("pathlib.Path.is_dir")  # Mock path checks
    @patch("pathlib.Path.cwd")  # Mock getcwd
    @patch("streetrace.main.ConsoleUI")  # Mock UI
    @patch("streetrace.main.CommandExecutor")  # Mock Executor
    @patch("streetrace.main.PromptProcessor")  # Mock Processor
    @patch("streetrace.main.InteractionManager")  # Mock Interaction Manager
    @patch("streetrace.main.ToolCall")  # Mock ToolCall
    @patch("builtins.input")  # Mock input
    @patch("argparse.ArgumentParser.parse_args")  # Mock arg parsing
    @patch("streetrace.main.Application")  # Mock Application class
    def test_non_interactive_mode(
        self,
        MockApplication,
        mock_parse_args,
        mock_input,
        MockToolCall,  # Add mocks to args
        MockInteractionManager,
        MockPromptProcessor,
        MockCommandExecutor,
        MockConsoleUI,
        mock_getcwd,
        mock_isdir,
        mock_get_ai_provider,
    ) -> None:
        """Test that the script runs in non-interactive mode with --prompt parameter."""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = "Test prompt"
        mock_args.path = None  # Assume default path
        mock_args.debug = False
        mock_args.engine = None  # Assume default engine
        mock_args.model = None
        # Non-interactive mode is implicitly true if prompt is given in Application
        mock_parse_args.return_value = mock_args

        mock_isdir.return_value = True  # Assume path is valid
        mock_getcwd.return_value = Path("/fake/cwd")
        mock_get_ai_provider.return_value = MagicMock()  # Return a dummy provider

        # Mock the Application instance and its run method
        mock_app_instance = MockApplication.return_value

        # Call the main function
        main.main()

        # Assert Application was initialized (basic check)
        MockApplication.assert_called_once()

        # Assert the run method was called correctly for non-interactive
        mock_app_instance.run.assert_called_once()
        # Check the call arguments of run (Application should handle prompt)
        call_args, call_kwargs = mock_app_instance.run.call_args
        # Application's run doesn't take initial_prompt anymore directly
        # Instead, it checks args.prompt internally.

        # Assert that input() was never called (non-interactive mode)
        mock_input.assert_not_called()
        # Assert UI display for non-interactive start (optional)
        # mock_ui_instance.display_info.assert_any_call("Running with provided prompt...")

    @patch("streetrace.main.get_ai_provider")  # Patch the factory function
    @patch("pathlib.Path.cwd")  # Mock getcwd
    @patch("pathlib.Path.is_dir")  # Mock getcwd
    @patch("streetrace.main.ConsoleUI")  # Mock UI
    @patch("streetrace.main.CommandExecutor")  # Mock Executor
    @patch("streetrace.main.PromptProcessor")  # Mock Processor
    @patch("streetrace.main.InteractionManager")  # Mock Interaction Manager
    @patch("streetrace.main.ToolCall")  # Mock ToolCall
    @patch("builtins.input")  # Mock input
    @patch("argparse.ArgumentParser.parse_args")  # Mock arg parsing
    @patch("streetrace.main.Application")  # Mock Application class
    def test_interactive_mode(
        self,
        MockApplication,
        mock_parse_args,
        mock_input,
        MockToolCall,
        MockInteractionManager,
        MockPromptProcessor,
        MockCommandExecutor,
        MockConsoleUI,
        mock_is_dir,
        mock_cwd,
        mock_get_ai_provider,
    ) -> None:
        """Test that the script runs in interactive mode without --prompt parameter."""
        # Set up mocks
        mock_args = MagicMock()
        mock_args.prompt = None  # No prompt provided
        mock_args.path = None
        mock_args.debug = False
        mock_args.engine = "openai"  # Provide a valid engine name
        mock_args.model = None
        mock_parse_args.return_value = mock_args

        mock_is_dir.return_value = True
        mock_cwd.return_value = Path("/fake/cwd")
        mock_get_ai_provider.return_value = MagicMock()  # Return a dummy provider

        # Mock the Application instance and its run method
        mock_app_instance = MockApplication.return_value

        # Call the main function
        main.main()

        # Assert Application was initialized (basic check)
        MockApplication.assert_called_once()

        # Assert the run method was called correctly for interactive mode
        mock_app_instance.run.assert_called_once()
        call_args, call_kwargs = mock_app_instance.run.call_args
        # Interactive mode doesn't pass prompt to run

        # Note: We don't assert input() here as the Application's run loop is mocked
        # Assert UI display for interactive start (optional)
        # mock_ui_instance.display_info.assert_any_call("Entering interactive mode...")


if __name__ == "__main__":
    unittest.main()
