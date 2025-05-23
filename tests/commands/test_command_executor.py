# tests/commands/test_command_executor.py
import unittest
from typing import Any
from unittest.mock import patch

import pytest

# Use absolute import from the 'src' root
from streetrace.commands.base_command import Command
from streetrace.commands.command_executor import CommandExecutor

# Define the target logger name
TARGET_LOGGER_NAME = "streetrace.commands.command_executor"
_TEST_CMD_NAME = "testcmd"
_TEST_CMD_DESC = "A simple test command."


# Mock Application class for type hinting
class Application:
    def clear_history(self) -> bool:
        pass  # pragma: no cover


_FAKE_EXCEPTION_MESSAGE = "Simulated exception"


class DummyCommandError(Exception):
    """Custom exception for DummyCommand errors."""

    def __init__(self):
        super().__init__(_FAKE_EXCEPTION_MESSAGE)


class DummyCommand(Command):
    def __init__(
        self,
        name: str = _TEST_CMD_NAME,
        description: str = _TEST_CMD_DESC,
        execute_returns: int | Any = 0,  # noqa: ANN401 matching Popen.returncode
        raise_exception: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        super().__init__()
        self._name = name
        self._description = description
        self._execute_returns = execute_returns
        self._raise_exception = raise_exception

    @property
    def names(self) -> list[str]:
        return [self._name]  # Define the command name

    @property
    def description(self) -> str:
        return self._description

    def execute(self, _: Application) -> bool:
        if self._raise_exception:
            raise DummyCommandError
        return self._execute_returns


class TestCommandExecutor(unittest.TestCase):
    def setUp(self) -> None:
        """Set up a new CommandExecutor for each test."""
        # Revert to patching the logger instance directly within the module
        self.patcher = patch(f"{TARGET_LOGGER_NAME}.logger")
        self.mock_logger = self.patcher.start()
        self.addCleanup(self.patcher.stop)

        # Instantiate the executor AFTER the logger is patched
        self.executor = CommandExecutor()
        self.fake_app = Application()

    def test_register_command_success(self) -> None:
        """Test successful registration of a command."""
        self.executor.register(DummyCommand())
        assert self.executor.get_command(_TEST_CMD_NAME)
        assert self.executor.get_command(_TEST_CMD_NAME).description == _TEST_CMD_DESC

    def test_register_command_case_insensitivity(self) -> None:
        """Test that command names are stored lowercased."""
        with pytest.raises(ValueError, match="Command name"):
            self.executor.register(DummyCommand(name=_TEST_CMD_NAME.upper()))

    def test_register_command_strips_whitespace(self) -> None:
        """Test that leading/trailing whitespace is stripped from command names."""
        with pytest.raises(ValueError, match="Command name"):
            self.executor.register(DummyCommand(name=f"  {_TEST_CMD_NAME}  "))

    def test_register_command_redefinition_warning(self) -> None:
        """Test that redefining a command logs a warning."""
        """Test successful registration of a command."""
        self.executor.register(DummyCommand())
        with pytest.raises(ValueError, match="Attempt to redefine command"):
            self.executor.register(DummyCommand())

    def test_register_command_empty_name_raises_error(self) -> None:
        """Test that registering an empty command name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty or whitespace"):
            self.executor.register(DummyCommand(name=""))

    def test_register_command_whitespace_name_raises_error(self) -> None:
        """Test that registering an empty command name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty or whitespace"):
            self.executor.register(DummyCommand(name="   "))

    def test_register_command_non_callable_action_raises_error(self) -> None:
        """Test that registering a non-callable action raises TypeError."""
        with pytest.raises(TypeError, match="is not an instance of Command"):
            self.executor.register("")

    def test_get_commands(self) -> None:
        """Test retrieving the list of registered command names."""
        self.executor.register(DummyCommand(name="cmdb"))
        self.executor.register(DummyCommand(name="cmda"))
        registered_names = [c.name for c in self.executor.commands]
        assert registered_names == ["cmda", "cmdb"]

    def test_execute_existing_command_continue(self) -> None:
        """Test executing a command (no args) that signals continue."""
        self.executor.register(DummyCommand(execute_returns=True))
        executed, should_continue = self.executor.execute(
            f"/{_TEST_CMD_NAME}",
            self.fake_app,
        )
        assert executed
        assert should_continue

    def test_execute_existing_command_exit(self) -> None:
        """Test executing a command (no args) that signals exit."""
        self.executor.register(DummyCommand(execute_returns=False))
        executed, should_continue = self.executor.execute(
            f"/{_TEST_CMD_NAME}",
            self.fake_app,
        )
        assert executed
        assert not should_continue

    def test_execute_non_existent_command(self) -> None:
        """Test executing a command (no args) that signals exit."""
        self.executor.register(DummyCommand(execute_returns=False))
        executed, should_continue = self.executor.execute(
            f"/{_TEST_CMD_NAME}1",
            self.fake_app,
        )
        assert not executed
        assert should_continue

    def test_execute_command_case_insensitivity(self) -> None:
        """Test that execution matches commands case-insensitively."""
        self.executor.register(DummyCommand(execute_returns=True))
        executed, should_continue = self.executor.execute(
            f"/{_TEST_CMD_NAME.upper()}",
            self.fake_app,
        )
        assert executed
        assert should_continue

    def test_execute_command_strips_whitespace(self) -> None:
        """Test that execution handles input with leading/trailing whitespace."""
        self.executor.register(DummyCommand(execute_returns=True))
        executed, should_continue = self.executor.execute(
            f"/{_TEST_CMD_NAME}  ",
            self.fake_app,
        )
        assert executed
        assert should_continue

    @unittest.skip("Not implemented yet")
    def test_execute_command_action_raises_exception(self) -> None:
        """Test execution when the command's action raises an exception."""
        self.executor.register(DummyCommand(raise_exception=True))
        executed, should_continue = self.executor.execute(
            f"/{_TEST_CMD_NAME}",
            self.fake_app,
        )
        assert executed
        assert should_continue
        pytest.fail("Not implemented yet, should allow rendering the error to the user")

    def test_execute_command_action_returns_non_boolean(self) -> None:
        """Test execution when the action returns something other than a boolean."""
        self.executor.register(DummyCommand(execute_returns="not a boolean"))
        with pytest.raises(
            TypeError,
            match="Command execute method should return a boolean",
        ):
            self.executor.execute(f"/{_TEST_CMD_NAME}", self.fake_app)


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
