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
from streetrace.system_context import SystemContext
from streetrace.ui.console_ui import ConsoleUI


class TestApplication(unittest.TestCase):
    """Unit tests for the Application class (interactions with HistoryManager)."""

    def setUp(self) -> None:
        """Set up test fixtures for Application tests."""
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.mock_cmd_executor = MagicMock(spec=CommandExecutor)
        self.mock_prompt_processor = MagicMock(spec=PromptProcessor)
        self.mock_system_context = MagicMock(spec=SystemContext)
        self.mock_interaction_manager = MagicMock(spec=InteractionManager)
        # Mock HistoryManager and its methods
        self.mock_history_manager = MagicMock(spec=HistoryManager)

        self.mock_history_manager.ui = self.mock_ui
        self.mock_history_manager.prompt_processor = self.mock_prompt_processor
        self.mock_history_manager.system_context = self.mock_system_context
        self.mock_history_manager.interaction_manager = self.mock_interaction_manager

        self.working_dir = Path("/fake/dir")

        # Configure build_context mock (used for mention processing)
        self.mock_prompt_context = MagicMock(spec=PromptContext)
        self.mock_prompt_context.mentioned_files = []
        self.mock_prompt_processor.build_context.return_value = self.mock_prompt_context

        # Configure system_context mocks
        self.mock_system_context.get_system_message.return_value = "SysMsg"
        self.mock_system_context.get_project_context.return_value = "ProjCtx"

        # Initialize Application with the mocked components
        self.app_config = ApplicationConfig(working_dir=self.working_dir)
        self.app = Application(
            app_config=self.app_config,
            ui=self.mock_ui,
            cmd_executor=self.mock_cmd_executor,
            prompt_processor=self.mock_prompt_processor,
            system_context=self.mock_system_context,
            interaction_manager=self.mock_interaction_manager,
            history_manager=self.mock_history_manager,
        )

        # Mock history object returned by history_manager.get_history()
        self.mock_history = MagicMock(spec=History)
        self.mock_history_manager.get_history.return_value = self.mock_history

        # Reset mocks after setup to isolate test calls
        self.mock_ui.reset_mock()
        self.mock_cmd_executor.reset_mock()
        self.mock_prompt_processor.reset_mock()
        self.mock_system_context.reset_mock()
        self.mock_interaction_manager.reset_mock()
        self.mock_history_manager.reset_mock()

        # Re-assign after reset
        self.mock_system_context.get_system_message.return_value = "SysMsg"
        self.mock_system_context.get_project_context.return_value = "ProjCtx"
        self.mock_history_manager.get_history.return_value = self.mock_history

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

    def test_run_non_interactive_prompt(self) -> None:
        """Test non-interactive run with a prompt processes it."""
        prompt = "generate code"
        mentioned_files_data = [("file.py", "content")]
        self.app.config.non_interactive_prompt = prompt
        # Command executor doesn't find a command
        self.mock_cmd_executor.execute.return_value = (False, True)
        # Mock build_context for this specific prompt
        self.mock_prompt_context.mentioned_files = mentioned_files_data
        self.mock_prompt_processor.build_context.return_value = self.mock_prompt_context

        self.app.run()

        self.mock_ui.display_user_prompt.assert_called_once_with(prompt)
        self.mock_cmd_executor.execute.assert_called_once_with(prompt, self.app)
        # Build context called for the prompt itself
        self.mock_prompt_processor.build_context.assert_called_once_with(
            prompt,
            self.working_dir,
        )
        self.mock_history_manager.initialize_history.assert_called_once_with()
        # Check interaction manager was called with the temporary history
        self.mock_interaction_manager.process_prompt.assert_called_once_with(
            self.app_config.initial_model,
            self.mock_history_manager.get_history(),
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


if __name__ == "__main__":
    unittest.main()
