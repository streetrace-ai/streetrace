# tests/commands/test_command_executor.py
import inspect
import unittest
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

# Use absolute import from the 'src' root
from streetrace.commands.command_executor import CommandExecutor

# Define the target logger name
TARGET_LOGGER_NAME = "streetrace.commands.command_executor"


class TestCommandExecutor(unittest.TestCase):

    def setUp(self) -> None:
        """Set up a new CommandExecutor for each test."""
        # Revert to patching the logger instance directly within the module
        self.patcher = patch(f"{TARGET_LOGGER_NAME}.logger")
        self.mock_logger = self.patcher.start()
        self.addCleanup(self.patcher.stop)

        # Instantiate the executor AFTER the logger is patched
        self.executor = CommandExecutor()

    def test_register_command_success(self) -> None:
        """Test successful registration of a command."""

        def dummy_action() -> bool:
            return True

        self.executor.register("testCmd", dummy_action, "Test description")
        assert "testcmd" in self.executor._commands
        assert self.executor._commands["testcmd"] == dummy_action
        assert self.executor._command_descriptions["testcmd"] == "Test description"
        # After registration, the last log should be the DEBUG message
        self.mock_logger.debug.assert_called_with(
            "Command 'testcmd' registered: Test description",
        )

    def test_register_command_case_insensitivity(self) -> None:
        """Test that command names are stored lowercased."""

        def dummy_action() -> bool:
            return True

        self.executor.register("UPPERCASE", dummy_action)
        assert "uppercase" in self.executor._commands
        assert "UPPERCASE" not in self.executor._commands
        # Check the log
        self.mock_logger.debug.assert_called_with(
            "Command 'uppercase' registered: ",  # Default desc is empty string
        )

    def test_register_command_strips_whitespace(self) -> None:
        """Test that leading/trailing whitespace is stripped from command names."""

        def dummy_action() -> bool:
            return True

        self.executor.register("  paddedCmd  ", dummy_action)
        assert "paddedcmd" in self.executor._commands
        assert "  paddedCmd  " not in self.executor._commands
        # Check the log
        self.mock_logger.debug.assert_called_with(
            "Command 'paddedcmd' registered: ",  # Default desc is empty string
        )

    def test_register_command_redefinition_warning(self) -> None:
        """Test that redefining a command logs a warning."""

        def action1() -> bool:
            return True

        def action2() -> bool:
            return False

        self.executor.register("testCmd", action1, "First")
        # DEBUG log: "...registered: First"
        self.executor.register("testCmd", action2, "Second")  # Redefine
        # WARNING log: "...redefined."
        # DEBUG log: "...registered: Second"
        assert "testcmd" in self.executor._commands
        assert self.executor._commands["testcmd"] == action2
        assert self.executor._command_descriptions["testcmd"] == "Second"
        # Check warning was logged exactly once
        self.mock_logger.warning.assert_called_once_with(
            "Command 'testcmd' is being redefined.",
        )
        # Check the last debug log
        self.mock_logger.debug.assert_called_with(
            "Command 'testcmd' registered: Second",
        )
        # Check the first debug log was also called
        self.mock_logger.debug.assert_any_call("Command 'testcmd' registered: First")

    def test_register_command_empty_name_raises_error(self) -> None:
        """Test that registering an empty command name raises ValueError."""

        def dummy_action() -> bool:
            return True

        with pytest.raises(
            ValueError,
            match="Command name cannot be empty or whitespace.",
        ):
            self.executor.register("", dummy_action)
        with pytest.raises(
            ValueError,
            match="Command name cannot be empty or whitespace.",
        ):
            self.executor.register("   ", dummy_action)

    def test_register_command_non_callable_action_raises_error(self) -> None:
        """Test that registering a non-callable action raises TypeError."""
        with pytest.raises(
            TypeError,
            match="Action for command 'testCmd' must be callable.",
        ):
            self.executor.register("testCmd", "not a function")

    def test_get_commands(self) -> None:
        """Test retrieving the list of registered command names."""

        def action_a() -> bool:
            return True

        def action_b() -> bool:
            return True

        self.executor.register("CmdB", action_b)
        self.executor.register("cmdA", action_a)
        assert self.executor.get_commands() == ["cmda", "cmdb"]  # Sorted

    def test_get_command_descriptions(self) -> None:
        """Test retrieving the command descriptions."""

        def action_a() -> bool:
            return True

        def action_b() -> bool:
            return True

        self.executor.register("CmdB", action_b, "Command B Desc")
        self.executor.register("cmdA", action_a, "Command A Desc")
        expected_descriptions = {"cmda": "Command A Desc", "cmdb": "Command B Desc"}
        assert self.executor.get_command_descriptions() == expected_descriptions

    def test_execute_existing_command_continue_no_args(self) -> None:
        """Test executing a command (no args) that signals continue."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("continueCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute("continueCmd")
        # INFO log: "Executing..."
        # DEBUG log: "...returned: True"
        assert executed
        assert should_continue
        action_mock.assert_called_once_with()
        # Use assert_any_call for the info log because it's not the last one
        self.mock_logger.info.assert_any_call("Executing command: 'continuecmd'")
        # Check the last log call (debug)
        self.mock_logger.debug.assert_called_with(
            "Command 'continuecmd' action returned: True",
        )

    def test_execute_existing_command_exit_no_args(self) -> None:
        """Test executing a command (no args) that signals exit."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=False)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("exitCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute("exitCmd")
        # INFO log: "Executing..."
        # DEBUG log: "...returned: False"
        assert executed
        assert not should_continue
        action_mock.assert_called_once_with()
        self.mock_logger.info.assert_any_call("Executing command: 'exitcmd'")
        self.mock_logger.debug.assert_called_with(
            "Command 'exitcmd' action returned: False",
        )

    def test_execute_existing_command_continue_with_arg(self) -> None:
        """Test executing a command (with arg) that signals continue."""
        action_mock = MagicMock(spec=Callable[[Any], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(lambda app: None)
        app_instance = Mock()
        self.executor.register("continueWithArgCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute(
            "continueWithArgCmd",
            app_instance=app_instance,
        )
        # INFO log: "Executing..."
        # DEBUG log: "...returned: True"
        assert executed
        assert should_continue
        action_mock.assert_called_once_with(app_instance)
        self.mock_logger.info.assert_any_call("Executing command: 'continuewithargcmd'")
        self.mock_logger.debug.assert_called_with(
            "Command 'continuewithargcmd' action returned: True",
        )

    def test_execute_existing_command_exit_with_arg(self) -> None:
        """Test executing a command (with arg) that signals exit."""
        action_mock = MagicMock(spec=Callable[[Any], bool], return_value=False)
        action_mock.__signature__ = inspect.signature(lambda app: None)
        app_instance = Mock()
        self.executor.register("exitWithArgCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute(
            "exitWithArgCmd",
            app_instance=app_instance,
        )
        # INFO log: "Executing..."
        # DEBUG log: "...returned: False"
        assert executed
        assert not should_continue
        action_mock.assert_called_once_with(app_instance)
        self.mock_logger.info.assert_any_call("Executing command: 'exitwithargcmd'")
        self.mock_logger.debug.assert_called_with(
            "Command 'exitwithargcmd' action returned: False",
        )

    def test_execute_command_case_insensitivity(self) -> None:
        """Test that execution matches commands case-insensitively."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("TestCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute("tEsTcMd")
        # INFO log: "Executing..."
        # DEBUG log: "...returned: True"
        assert executed
        assert should_continue
        action_mock.assert_called_once_with()
        self.mock_logger.info.assert_any_call("Executing command: 'testcmd'")
        self.mock_logger.debug.assert_called_with(
            "Command 'testcmd' action returned: True",
        )

    def test_execute_command_strips_whitespace(self) -> None:
        """Test that execution handles input with leading/trailing whitespace."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value=True)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("testCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute("  testCmd  ")
        # INFO log: "Executing..."
        # DEBUG log: "...returned: True"
        assert executed
        assert should_continue
        action_mock.assert_called_once_with()
        self.mock_logger.info.assert_any_call("Executing command: 'testcmd'")
        self.mock_logger.debug.assert_called_with(
            "Command 'testcmd' action returned: True",
        )

    def test_execute_non_existent_command(self) -> None:
        """Test executing input that doesn't match any command."""
        executed, should_continue = self.executor.execute("unknownCmd")
        # DEBUG log: "Input 'unknown...' not registered"
        assert not executed
        assert should_continue
        # Only one log call (DEBUG) expected here. Check it was called once.
        self.mock_logger.debug.assert_called_once_with(
            "Input 'unknownCmd' is not a registered command.",
        )

    def test_execute_command_action_raises_exception(self) -> None:
        """Test execution when the command's action raises an exception."""
        test_exception = RuntimeError("Action failed")
        action_mock = MagicMock(spec=Callable[[], bool], side_effect=test_exception)
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("errorCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute("errorCmd")
        # INFO log: "Executing..."
        # ERROR log: "Error executing..."
        assert executed
        assert should_continue
        action_mock.assert_called_once_with()
        self.mock_logger.info.assert_any_call("Executing command: 'errorcmd'")
        self.mock_logger.error.assert_called_once_with(
            "Error executing action for command 'errorcmd': Action failed",
            exc_info=True,
        )

    def test_execute_command_action_returns_non_boolean(self) -> None:
        """Test execution when the action returns something other than a boolean."""
        action_mock = MagicMock(spec=Callable[[], bool], return_value="not a boolean")
        action_mock.__signature__ = inspect.signature(lambda: None)
        self.executor.register("badReturnCmd", action_mock)
        # DEBUG log: "...registered: "
        executed, should_continue = self.executor.execute("badReturnCmd")
        # INFO log: "Executing..."
        # ERROR log: "Action...did not return boolean..."
        assert executed
        assert should_continue
        action_mock.assert_called_once_with()
        self.mock_logger.info.assert_any_call("Executing command: 'badreturncmd'")
        self.mock_logger.error.assert_called_once_with(
            "Action for command 'badreturncmd' did not return a boolean. Assuming continue.",
        )

    def test_execute_command_with_unexpected_signature(self) -> None:
        """Test execution when action has more than one argument."""

        def action_too_many_args(arg1, arg2) -> None:
            pass  # pragma: no cover

        self.executor.register("badSigCmd", action_too_many_args)
        # DEBUG log: "...registered: "
        app_instance = Mock()
        executed, should_continue = self.executor.execute(
            "badSigCmd",
            app_instance=app_instance,
        )
        # INFO log: "Executing..."
        # ERROR log: "Action...unexpected signature..."
        assert executed
        assert should_continue
        self.mock_logger.info.assert_any_call("Executing command: 'badsigcmd'")
        self.mock_logger.error.assert_called_once_with(
            "Action for command 'badsigcmd' has an unexpected signature: (arg1, arg2). Cannot execute.",
        )


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
