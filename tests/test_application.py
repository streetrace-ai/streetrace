import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import Application and dependencies for testing
from streetrace.application import Application, ApplicationConfig
from streetrace.commands.command_executor import CommandExecutor
from streetrace.history import History
from streetrace.history_manager import HistoryManager  # Import HistoryManager
from streetrace.interaction_manager import InteractionManager
from streetrace.prompt_processor import PromptContext, PromptProcessor
from streetrace.ui.console_ui import ConsoleUI


class TestApplication(unittest.TestCase):
    """Unit tests for the Application class (interactions with HistoryManager)."""

    def setUp(self) -> None:
        """Set up test fixtures for Application tests."""
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.mock_cmd_executor = MagicMock(spec=CommandExecutor)
        self.mock_prompt_processor = MagicMock(spec=PromptProcessor)
        self.mock_interaction_manager = MagicMock(spec=InteractionManager)
        # Mock HistoryManager and its methods
        self.mock_history_manager = MagicMock(spec=HistoryManager)
        self.working_dir = Path("/fake/dir")

        # Configure build_context mock (used for mention processing and potentially history reset)
        self.mock_prompt_context = MagicMock(spec=PromptContext)
        self.mock_prompt_context.system_message = "SysMsg"
        self.mock_prompt_context.project_context = "ProjCtx"
        self.mock_prompt_context.mentioned_files = []
        self.mock_prompt_processor.build_context.return_value = self.mock_prompt_context

        # Initialize Application with the mocked HistoryManager
        self.app_config = ApplicationConfig(working_dir=self.working_dir)
        self.app = Application(
            app_config=self.app_config,
            ui=self.mock_ui,
            cmd_executor=self.mock_cmd_executor,
            prompt_processor=self.mock_prompt_processor,
            interaction_manager=self.mock_interaction_manager,
            history_manager=self.mock_history_manager,  # Pass the mock
        )

        # Mock history object returned by history_manager.get_history()
        self.mock_history = MagicMock(spec=History)
        self.mock_history_manager.get_history.return_value = self.mock_history

        # Reset mocks after setup to isolate test calls
        self.mock_ui.reset_mock()
        self.mock_cmd_executor.reset_mock()
        self.mock_prompt_processor.reset_mock()
        self.mock_interaction_manager.reset_mock()
        self.mock_history_manager.reset_mock()
        self.mock_history_manager.get_history.return_value = (
            self.mock_history
        )  # Re-assign after reset

    @patch("streetrace.application.sys.exit")
    def test_run_non_interactive_command(self, mock_sys_exit) -> None:
        """Test non-interactive run with a command executes command and exits."""
        prompt = "/exit"
        self.app.config.non_interactive_prompt = prompt
        # Simulate command executor finding and executing the command
        self.mock_cmd_executor.execute.return_value = (
            True,
            False,
        )  # Command executed, don't continue

        self.app.run()

        self.mock_ui.display_user_prompt.assert_called_once_with(prompt)
        self.mock_cmd_executor.execute.assert_called_once_with(prompt, self.app)
        self.mock_interaction_manager.process_prompt.assert_not_called()
        mock_sys_exit.assert_called_once_with(0)

    @patch(
        "streetrace.application.History",
    )  # Patch History class used in non-interactive
    def test_run_non_interactive_prompt(self, mock_history) -> None:
        """Test non-interactive run with a prompt processes it."""
        prompt = "generate code"
        mentioned_files_data = [("file.py", "content")]
        self.app.config.non_interactive_prompt = prompt
        # Command executor doesn't find a command
        self.mock_cmd_executor.execute.return_value = (False, True)
        # Mock build_context for this specific prompt
        self.mock_prompt_context.mentioned_files = mentioned_files_data
        self.mock_prompt_processor.build_context.return_value = self.mock_prompt_context
        # Mock the temporary History instance created
        mock_temp_history_instance = MagicMock()
        mock_history.return_value = mock_temp_history_instance

        self.app.run()

        self.mock_ui.display_user_prompt.assert_called_once_with(prompt)
        self.mock_cmd_executor.execute.assert_called_once_with(prompt, self.app)
        # Build context called for the prompt itself
        self.mock_prompt_processor.build_context.assert_called_once_with(
            prompt,
            self.working_dir,
        )
        # Check History constructor was called with context from build_context
        mock_history.assert_called_once_with(system_message="SysMsg", context="ProjCtx")
        # Check mentions and user message were added to the temporary history
        # Note: _add_mentions_to_temporary_history is internal, we check its effect
        # Check that add_context_message was called by _add_mentions_to_temporary_history
        mock_temp_history_instance.add_context_message.assert_called_once_with(
            "file.py",
            "content",
        )
        # Check user message added
        mock_temp_history_instance.add_user_message.assert_called_once_with(prompt)
        # Check interaction manager was called with the temporary history
        self.mock_interaction_manager.process_prompt.assert_called_once_with(
            self.app_config.initial_model,
            mock_temp_history_instance,
            self.app_config.tools,
        )

    # Note: No need to patch builtins.input here, as Application uses self.ui.prompt()
    def test_run_interactive_exit_command(self) -> None:
        """Test interactive run exits correctly on /exit command."""
        exit_command = "/exit"
        # Configure the UI mock to return the exit command
        self.mock_ui.prompt.return_value = exit_command
        # Simulate /exit command execution returns (True, False) -> executed, don't continue
        self.mock_cmd_executor.execute.return_value = (True, False)

        self.app.run()

        # Check initialization happened *before* the loop
        self.mock_history_manager.initialize_history.assert_called_once_with()
        # Check prompt was called once
        self.mock_ui.prompt.assert_called_once()
        # Check command execution was attempted with the correct input
        self.mock_cmd_executor.execute.assert_called_once_with(exit_command, self.app)
        # Check final message and no prompt processing
        self.mock_ui.display_info.assert_any_call("Leaving...")
        self.mock_interaction_manager.process_prompt.assert_not_called()

    # Note: No need to patch builtins.input here
    def test_run_interactive_prompt_processing(self) -> None:
        """Test interactive run processes a user prompt."""
        user_prompt = "hello"
        mentioned_files_data = [("mention.txt", "mention content")]

        # Configure the UI mock to return the prompt, then raise EOFError
        self.mock_ui.prompt.side_effect = [user_prompt, EOFError]
        # Command executor doesn't find command, should continue
        self.mock_cmd_executor.execute.return_value = (False, True)
        # Mock build_context for the user prompt
        self.mock_prompt_context.mentioned_files = mentioned_files_data
        self.mock_prompt_processor.build_context.return_value = self.mock_prompt_context

        self.app.run()

        # Initialization
        self.mock_history_manager.initialize_history.assert_called_once_with()
        # Prompt called twice (once for 'hello', once resulting in EOFError)
        assert self.mock_ui.prompt.call_count == 2
        # Command execution attempt for 'hello'
        self.mock_cmd_executor.execute.assert_called_once_with(user_prompt, self.app)
        # History check (get_history is called before processing input)
        self.mock_history_manager.get_history.assert_called()
        # Context build for the specific prompt 'hello'
        self.mock_prompt_processor.build_context.assert_called_once_with(
            user_prompt,
            self.working_dir,
        )
        # History updates via manager
        self.mock_history_manager.add_mentions_to_history.assert_called_once_with(
            mentioned_files_data,
        )
        self.mock_history_manager.add_user_message.assert_called_once_with(user_prompt)
        # Interaction manager call
        self.mock_interaction_manager.process_prompt.assert_called_once_with(
            self.app_config.initial_model,
            self.mock_history,  # The history object returned by get_history
            self.app_config.tools,
        )
        # Check for exit message due to EOFError
        self.mock_ui.display_info.assert_any_call("\nExiting.")

    # Note: No need to patch builtins.input here
    def test_run_interactive_handles_missing_history(self) -> None:
        """Test interactive run attempts to clear history if it's missing."""
        user_prompt = "some prompt"
        # Configure UI mock for input -> EOF
        self.mock_ui.prompt.side_effect = [user_prompt, EOFError]
        # Simulate history_manager.get_history() returning None initially, then the mock history object
        # 1. First check in _process_interactive_input -> None
        # 2. Check after clear_history -> self.mock_history (success)
        self.mock_history_manager.get_history.side_effect = [None, self.mock_history]
        # Command executor doesn't find command
        self.mock_cmd_executor.execute.return_value = (False, True)
        # Mock build_context (it won't be called in this path because _process_interactive_input returns early)
        self.mock_prompt_processor.build_context.return_value = self.mock_prompt_context

        with patch("logging.Logger.error") as mock_log_error:
            self.app.run()

            # Check history was initialized *before* the loop
            self.mock_history_manager.initialize_history.assert_called_once_with()
            # Check prompt was called twice (once for prompt, once for EOF)
            assert self.mock_ui.prompt.call_count == 2
            # Check command executor called for the prompt
            self.mock_cmd_executor.execute.assert_called_once_with(
                user_prompt,
                self.app,
            )
            # Check history was fetched twice (once failed, once succeeded after clear)
            assert self.mock_history_manager.get_history.call_count == 2
            # Check error was logged when history was missing
            mock_log_error.assert_called_once_with(
                "Conversation history is missing. Attempting to reset.",
            )
            # Check clear_history was called on the manager
            self.mock_history_manager.clear_history.assert_called_once()
            # Check build_context was NOT called because the loop returned early after reset
            self.mock_prompt_processor.build_context.assert_not_called()
            # Check prompt processing was NOT called because the loop returned early after reset
            self.mock_interaction_manager.process_prompt.assert_not_called()
            # Check exit message
            self.mock_ui.display_info.assert_any_call("\nExiting.")

    # Remove tests specifically for app.clear_history, app.compact_history, app.display_history
    # These are now tested via the commands calling the history_manager or
    # directly in test_history_manager.py


if __name__ == "__main__":
    unittest.main()
