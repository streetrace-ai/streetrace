# tests/commands/test_command_executor.py
import inspect  # Import inspect
import logging
import unittest
from typing import Any, Callable  # Import Callable and Any
from unittest.mock import MagicMock, Mock, patch

# Use absolute import from the 'src' root
from streetrace.commands.command_executor import CommandExecutor

# Get a logger for this module - use the same name as in the source file
logger = logging.getLogger("streetrace.commands.command_executor")
# Keep logging disabled unless specifically needed for a test
# logging.disable(logging.CRITICAL)


class TestCommandExecutor(unittest.TestCase):

    def setUp(self):
        """Set up a new CommandExecutor for each test."""
        self.executor = CommandExecutor()
        # Mock the logger used within CommandExecutor to check calls
        self.patcher = patch("streetrace.commands.command_executor.logger", spec=True)
        self.mock_logger = self.patcher.start()
        self.addCleanup(self.patcher.stop)  # Ensure patch is stopped even if test fails

    def test_register_command_success(self):
        """Test successful registration of a command."""

        def dummy_action():
            return True

        self.executor.register("testCmd", dummy_action, "Test description")
        self.assertIn("testcmd", self.executor._commands)
        self.assertEqual(self.executor._commands["testcmd"], dummy_action)
        self.assertEqual(
            self.executor._command_descriptions["testcmd"], "Test description"
        )
        self.mock_logger.debug.assert_called_with(
            "Command 'testcmd' registered: Test description"
        )

    def test_register_command_case_insensitivity(self):
        """Test that command names are stored lowercased."""

        def dummy_action():
            return True

        self.executor.register("UPPERCASE", dummy_action)
        self.assertIn("uppercase", self.executor._commands)
        self.assertNotIn("UPPERCASE", self.executor._commands)

    def test_register_command_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped from command names."""

        def dummy_action():
            return True

        self.executor.register("  paddedCmd  ", dummy_action)
        self.assertIn("paddedcmd", self.executor._commands)
        self.assertNotIn("  paddedCmd  ", self.executor._commands)

    def test_register_command_redefinition_warning(self):
        """Test that redefining a command logs a warning."""

        def action1():
            return True

        def action2():
            return False

        self.executor.register("testCmd", action1, "First")
        self.executor.register("testCmd", action2, "Second")  # Redefine
        self.assertIn("testcmd", self.executor._commands)
        self.assertEqual(
            self.executor._commands["testcmd"], action2
        )  # Should have the second action
        self.assertEqual(
            self.executor._command_descriptions["testcmd"], "Second"
        )  # Description updated
        self.mock_logger.warning.assert_called_once_with(
            "Command 'testcmd' is being redefined."
        )

    def test_register_command_empty_name_raises_error(self):
        """Test that registering an empty command name raises ValueError."""

        def dummy_action():
            return True

        with self.assertRaisesRegex(
            ValueError, "Command name cannot be empty or whitespace."
        ):
            self.executor.register("", dummy_action)
        with self.assertRaisesRegex(
            ValueError, "Command name cannot be empty or whitespace."
        ):
            self.executor.register("   ", dummy_action)  # Just whitespace

    def test_register_command_non_callable_action_raises_error(self):
        """Test that registering a non-callable action raises TypeError."""
        with self.assertRaisesRegex(
            TypeError, "Action for command 'testCmd' must be callable."
        ):
            self.executor.register("testCmd", "not a function")

    def test_get_commands(self):
        """Test retrieving the list of registered command names."""

        def action_a():
            return True

        def action_b():
            return True

        self.executor.register("CmdB", action_b)
        self.executor.register("cmdA", action_a)
        self.assertEqual(
            self.executor.get_commands(), ["cmda", "cmdb"]
        )  # Should be sorted

    def test_get_command_descriptions(self):
        """Test retrieving the command descriptions."""

        def action_a():
            return True

        def action_b():
            return True

        self.executor.register("CmdB", action_b, "Command B Desc")
        self.executor.register("cmdA", action_a, "Command A Desc")
        expected_descriptions = {"cmda": "Command A Desc", "cmdb": "Command B Desc"}
        self.assertEqual(
            self.executor.get_command_descriptions(), expected_descriptions
        )

    def test_execute_existing_command_continue_no_args(self):
        """Test executing a command (no args) that signals continue."""
        # Use a mock that behaves like a function for assertion tracking
        action_mock = MagicMock(spec=Callable[[], bool], return_value=True)
        # Ensure the mock has a signature inspect can read
        action_mock.__signature__ = inspect.signature(lambda: None)

        self.executor.register("continueCmd", action_mock)
        executed, should_continue = self.executor.execute("continueCmd")

        self.assertTrue(executed)
        self.assertTrue(should_continue)
        action_mock.assert_called_once_with()  # Called with no arguments
        self.mock_logger.info.assert_any_call("Executing command: 'continuecmd'")
        self.mock_logger.debug.assert_any_call(
            "Command 'continuecmd' action returned: True"
        )

    def test_execute_existing_command_exit_no_args(self):
        """Test executing a command (no args) that signals exit."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=False)
        action_mock.__signature__ = inspect.signature(lambda: None)

        self.executor.register("exitCmd", action_mock)
        executed, should_continue = self.executor.execute("exitCmd")

        self.assertTrue(executed)
        self.assertFalse(should_continue)  # Correctly check for False
        action_mock.assert_called_once_with()
        self.mock_logger.info.assert_any_call("Executing command: 'exitcmd'")
        self.mock_logger.debug.assert_any_call(
            "Command 'exitcmd' action returned: False"
        )

    def test_execute_existing_command_continue_with_arg(self):
        """Test executing a command (with arg) that signals continue."""
        # Mock action that expects one argument
        action_mock = MagicMock(spec=Callable[[Any], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(
            lambda app: None
        )  # Signature with 1 param

        app_instance = Mock()  # Dummy app instance
        self.executor.register("continueWithArgCmd", action_mock)
        executed, should_continue = self.executor.execute(
            "continueWithArgCmd", app_instance=app_instance
        )

        self.assertTrue(executed)
        self.assertTrue(should_continue)
        action_mock.assert_called_once_with(app_instance)  # Called with app_instance
        self.mock_logger.info.assert_any_call("Executing command: 'continuewithargcmd'")
        self.mock_logger.debug.assert_any_call(
            "Command 'continuewithargcmd' action returned: True"
        )

    def test_execute_existing_command_exit_with_arg(self):
        """Test executing a command (with arg) that signals exit."""
        action_mock = MagicMock(spec=Callable[[Any], bool], return_value=False)
        action_mock.__signature__ = inspect.signature(lambda app: None)

        app_instance = Mock()
        self.executor.register("exitWithArgCmd", action_mock)
        executed, should_continue = self.executor.execute(
            "exitWithArgCmd", app_instance=app_instance
        )

        self.assertTrue(executed)
        self.assertFalse(should_continue)
        action_mock.assert_called_once_with(app_instance)
        self.mock_logger.info.assert_any_call("Executing command: 'exitwithargcmd'")
        self.mock_logger.debug.assert_any_call(
            "Command 'exitwithargcmd' action returned: False"
        )

    def test_execute_command_case_insensitivity(self):
        """Test that execution matches commands case-insensitively."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("TestCmd", action_mock)

        executed, should_continue = self.executor.execute("tEsTcMd")
        self.assertTrue(executed)
        self.assertTrue(should_continue)
        action_mock.assert_called_once_with()

    def test_execute_command_strips_whitespace(self):
        """Test that execution handles input with leading/trailing whitespace."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("testCmd", action_mock)

        executed, should_continue = self.executor.execute("  testCmd  ")
        self.assertTrue(executed)
        self.assertTrue(should_continue)
        action_mock.assert_called_once_with()

    def test_execute_non_existent_command(self):
        """Test executing input that doesn't match any command."""
        executed, should_continue = self.executor.execute("unknownCmd")
        self.assertFalse(executed)
        self.assertTrue(should_continue)
        self.mock_logger.debug.assert_called_with(
            "Input 'unknownCmd' is not a registered command."
        )

    def test_execute_command_action_raises_exception(self):
        """Test execution when the command's action raises an exception."""
        test_exception = RuntimeError("Action failed")
        action_mock = MagicMock(spec=Callable[[], bool], side_effect=test_exception)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("errorCmd", action_mock)

        executed, should_continue = self.executor.execute("errorCmd")

        self.assertTrue(executed)  # Command was matched and attempted
        self.assertTrue(should_continue)  # Should continue despite error
        action_mock.assert_called_once_with()
        self.mock_logger.error.assert_called_once_with(
            "Error executing action for command 'errorcmd': Action failed",
            exc_info=True,
        )

    def test_execute_command_action_returns_non_boolean(self):
        """Test execution when the action returns something other than a boolean."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value="not a boolean")
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("badReturnCmd", action_mock)

        executed, should_continue = self.executor.execute("badReturnCmd")

        self.assertTrue(executed)  # Command was matched and executed
        self.assertTrue(should_continue)  # Should default to continue
        action_mock.assert_called_once_with()
        self.mock_logger.error.assert_called_once_with(
            "Action for command 'badreturncmd' did not return a boolean. Assuming continue."
        )

    def test_execute_command_with_unexpected_signature(self):
        """Test execution when action has more than one argument."""

        def action_too_many_args(arg1, arg2):
            pass  # pragma: no cover

        self.executor.register("badSigCmd", action_too_many_args)

        app_instance = Mock()
        executed, should_continue = self.executor.execute(
            "badSigCmd", app_instance=app_instance
        )

        self.assertTrue(executed)  # Command was matched
        self.assertTrue(should_continue)  # Default to continue on signature error
        self.mock_logger.error.assert_called_once()
        # Check that the error message contains the expected signature info
        log_call_args, _ = self.mock_logger.error.call_args
        self.assertIn(
            "Action for command 'badsigcmd' has an unexpected signature",
            log_call_args[0],
        )
        self.assertIn("(arg1, arg2)", log_call_args[0])
        self.assertIn("Cannot execute.", log_call_args[0])


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
