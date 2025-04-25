# tests/test_application.py
import unittest
from unittest.mock import MagicMock, patch
import argparse

from streetrace.application import Application
from streetrace.llm.wrapper import (
    History,
    Role,
    ContentPartText,
)
from streetrace.prompt_processor import PromptContext, PromptProcessor
from streetrace.ui.console_ui import ConsoleUI
from streetrace.commands.command_executor import CommandExecutor
from streetrace.interaction_manager import InteractionManager


class TestApplication(unittest.TestCase):
    """Unit tests for the Application class."""

    def setUp(self):
        """Set up test fixtures for Application tests."""
        self.mock_args = argparse.Namespace(
            prompt=None, debug=False, engine=None, model=None, path=None
        )
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.mock_cmd_executor = MagicMock(spec=CommandExecutor)
        self.mock_prompt_processor = MagicMock(spec=PromptProcessor)
        self.mock_interaction_manager = MagicMock(spec=InteractionManager)
        self.working_dir = "/fake/dir"

        # Define the context that build_context will return
        self.initial_system = "Initial System Message"
        self.initial_proj_context = "Initial Project Context"
        self.mock_initial_context_obj = MagicMock(spec=PromptContext)
        self.mock_initial_context_obj.system_message = self.initial_system
        self.mock_initial_context_obj.project_context = self.initial_proj_context
        self.mock_initial_context_obj.mentioned_files = [] # Assume no mentions for initial context

        # Configure the mock prompt_processor to return this object
        self.mock_prompt_processor.build_context.return_value = self.mock_initial_context_obj

        # Initialize Application - it will call build_context during init
        self.app = Application(
            args=self.mock_args,
            ui=self.mock_ui,
            cmd_executor=self.mock_cmd_executor,
            prompt_processor=self.mock_prompt_processor,
            interaction_manager=self.mock_interaction_manager,
            working_dir=self.working_dir,
        )

        # Reset mock call count after init to isolate test calls
        self.mock_prompt_processor.build_context.reset_mock()
        # Set up initial conversation history as Application does in _run_interactive
        self.app.conversation_history = History(
            system_message=self.initial_system,
            context=self.initial_proj_context
        )

    def test_clear_history_resets_history_using_build_context(self):
        """Test that _clear_history resets the conversation history using build_context."""
        # Add some messages to the history
        self.app.conversation_history.add_message(
            role=Role.USER, content=[ContentPartText(text="Hello there")]
        )
        self.app.conversation_history.add_message(
            role=Role.MODEL, content=[ContentPartText(text="General Kenobi")]
        )
        self.assertEqual(len(self.app.conversation_history.conversation), 2)

        # Configure mock build_context again for the call inside _clear_history
        # Use slightly different values to ensure the *new* context is used
        new_system = "New System Message After Clear"
        new_context = "New Project Context After Clear"
        new_mock_context_obj = MagicMock(spec=PromptContext)
        new_mock_context_obj.system_message = new_system
        new_mock_context_obj.project_context = new_context
        self.mock_prompt_processor.build_context.return_value = new_mock_context_obj

        # Call the method
        result = self.app._clear_history()

        # Assert the result is True (continue)
        self.assertTrue(result)

        # Assert build_context was called correctly
        self.mock_prompt_processor.build_context.assert_called_once_with("", self.working_dir)

        # Assert history is reset using the *new* context from build_context
        self.assertIsNotNone(self.app.conversation_history)
        self.assertEqual(
            self.app.conversation_history.system_message, new_system
        )
        self.assertEqual(
            self.app.conversation_history.context, new_context
        )
        self.assertEqual(len(self.app.conversation_history.conversation), 0) # No messages

        # Assert UI and logging messages
        self.mock_ui.display_info.assert_called_with("Conversation history has been cleared.")

    def test_clear_history_handles_build_context_exception(self):
        """Test _clear_history handles exceptions during build_context."""
        # Add some messages to the history (they should remain untouched)
        original_history = self.app.conversation_history
        original_history.add_message(role=Role.USER, content=[ContentPartText(text="Test")])

        # Configure build_context to raise an exception
        error_message = "Failed to read context file"
        self.mock_prompt_processor.build_context.side_effect = Exception(error_message)

        # Call the method
        with patch("logging.Logger.error") as mock_log_error:
            result = self.app._clear_history()

            # Assert the result is True (continue even on error)
            self.assertTrue(result)

            # Assert build_context was called
            self.mock_prompt_processor.build_context.assert_called_once_with("", self.working_dir)

            # Assert history was NOT changed
            self.assertIs(self.app.conversation_history, original_history)
            self.assertEqual(len(self.app.conversation_history.conversation), 1)

            # Assert UI error message and log message
            self.mock_ui.display_error.assert_called_with(
                 f"Could not clear history due to an error rebuilding context: {error_message}"
            )
            mock_log_error.assert_called_once()
            self.assertIn("Failed to rebuild context", mock_log_error.call_args[0][0])

    # Removed test_clear_history_when_initial_context_missing

if __name__ == "__main__":
    unittest.main()
