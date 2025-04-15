# tests/test_command_executor.py
import logging
import unittest
from unittest.mock import Mock, patch  # Use patch for logger checks if needed

# Assume CommandExecutor is importable (adjust path if necessary)
# If 'app' is not automatically in pythonpath, we might need to adjust sys.path
# For now, assume it works or we adjust later.
try:
    from app.command_executor import CommandExecutor
except ImportError:
    # If running tests from root, might need to add 'app' to path
    import os
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from app.command_executor import CommandExecutor

# Disable logging during tests unless specifically testing logging output
logging.disable(logging.CRITICAL)


class TestCommandExecutor(unittest.TestCase):

    def setUp(self):
        """Set up a new CommandExecutor for each test."""
        self.executor = CommandExecutor()

    def test_register_command_success(self):
        """Test successful registration of a command."""
        mock_action = Mock(return_value=True)
        self.executor.register("testCmd", mock_action)
        self.assertIn("testcmd", self.executor._commands)
        self.assertEqual(self.executor._commands["testcmd"], mock_action)

    def test_register_command_case_insensitivity(self):
        """Test that command names are stored lowercased."""
        mock_action = Mock(return_value=True)
        self.executor.register("UPPERCASE", mock_action)
        self.assertIn("uppercase", self.executor._commands)
        self.assertNotIn("UPPERCASE", self.executor._commands)

    def test_register_command_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped from command names."""
        mock_action = Mock(return_value=True)
        self.executor.register("  paddedCmd  ", mock_action)
        self.assertIn("paddedcmd", self.executor._commands)
        self.assertNotIn("  paddedCmd  ", self.executor._commands)

    def test_register_command_empty_name_raises_error(self):
        """Test that registering an empty command name raises ValueError."""
        mock_action = Mock(return_value=True)
        with self.assertRaises(ValueError):
            self.executor.register("", mock_action)
        with self.assertRaises(ValueError):
            self.executor.register("   ", mock_action)  # Just whitespace

    def test_register_command_non_callable_action_raises_error(self):
        """Test that registering a non-callable action raises TypeError."""
        with self.assertRaises(TypeError):
            self.executor.register("testCmd", "not a function")

    def test_get_commands(self):
        """Test retrieving the list of registered command names."""
        mock_action1 = Mock(return_value=True)
        mock_action2 = Mock(return_value=True)
        self.executor.register("CmdB", mock_action1)
        self.executor.register("cmdA", mock_action2)
        self.assertEqual(self.executor.get_commands(), ["cmda", "cmdb"])

    def test_execute_existing_command_continue(self):
        """Test executing a command that signals continue."""
        mock_action = Mock(return_value=True)
        self.executor.register("continueCmd", mock_action)
        executed, should_continue = self.executor.execute("continueCmd")
        self.assertTrue(executed)
        self.assertTrue(should_continue)
        mock_action.assert_called_once()

    def test_execute_existing_command_exit(self):
        """Test executing a command that signals exit."""
        mock_action = Mock(return_value=False)
        self.executor.register("exitCmd", mock_action)
        executed, should_continue = self.executor.execute("exitCmd")
        self.assertTrue(executed)
        self.assertFalse(should_continue)
        mock_action.assert_called_once()

    def test_execute_command_case_insensitivity(self):
        """Test that execution matches commands case-insensitively."""
        mock_action = Mock(return_value=True)
        self.executor.register("TestCmd", mock_action)
        executed, should_continue = self.executor.execute("tEsTcMd")
        self.assertTrue(executed)
        self.assertTrue(should_continue)
        mock_action.assert_called_once()

    def test_execute_command_strips_whitespace(self):
        """Test that execution handles input with leading/trailing whitespace."""
        mock_action = Mock(return_value=True)
        self.executor.register("testCmd", mock_action)
        executed, should_continue = self.executor.execute("  testCmd  ")
        self.assertTrue(executed)
        self.assertTrue(should_continue)
        mock_action.assert_called_once()

    def test_execute_non_existent_command(self):
        """Test executing input that doesn't match any command."""
        executed, should_continue = self.executor.execute("unknownCmd")
        self.assertFalse(executed)
        self.assertTrue(should_continue)

    def test_execute_command_action_raises_exception(self):
        """Test execution when the command's action raises an exception."""
        mock_action = Mock(side_effect=RuntimeError("Action failed"))
        self.executor.register("errorCmd", mock_action)

        # Use patch to check if logger.error was called
        with patch("app.command_executor.logger") as mock_logger:
            executed, should_continue = self.executor.execute("errorCmd")

        self.assertTrue(executed)
        self.assertTrue(should_continue)  # Should continue despite error
        mock_action.assert_called_once()
        mock_logger.error.assert_called_once()  # Verify error was logged

    def test_execute_command_action_returns_non_boolean(self):
        """Test execution when the action returns something other than a boolean."""
        mock_action = Mock(return_value="not a boolean")
        self.executor.register("badReturnCmd", mock_action)

        with patch("app.command_executor.logger") as mock_logger:
            executed, should_continue = self.executor.execute("badReturnCmd")

        self.assertTrue(executed)
        self.assertTrue(should_continue)  # Should default to continue
        mock_action.assert_called_once()
        mock_logger.error.assert_called_once()  # Verify error was logged


if __name__ == "__main__":
    unittest.main()
