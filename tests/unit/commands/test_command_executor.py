# tests/commands/test_command_executor.py

import pytest

# Use absolute import from the 'src' root
from streetrace.commands.base_command import Command
from streetrace.commands.command_executor import CommandExecutor
from streetrace.input_handler import InputContext

# Define the target logger name
TARGET_LOGGER_NAME = "streetrace.commands.command_executor"
_TEST_CMD_NAME = "testcmd"
_TEST_CMD_DESC = "A simple test command."


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
        raise_exception: bool = False,
    ) -> None:
        super().__init__()
        self._name = name
        self._description = description
        self._raise_exception = raise_exception

    @property
    def names(self) -> list[str]:
        return [self._name]  # Define the command name

    @property
    def description(self) -> str:
        return self._description

    async def execute_async(self) -> None:
        if self._raise_exception:
            raise DummyCommandError


@pytest.fixture
def command_executor():
    return CommandExecutor()


def test_register_command_success(command_executor) -> None:
    """Test successful registration of a command."""
    command_executor.register(DummyCommand())
    assert command_executor.get_command(_TEST_CMD_NAME)
    assert command_executor.get_command(_TEST_CMD_NAME).description == _TEST_CMD_DESC


def test_register_command_case_insensitivity(command_executor) -> None:
    """Test that command names are stored lowercased."""
    with pytest.raises(ValueError, match="Command name"):
        command_executor.register(DummyCommand(name=_TEST_CMD_NAME.upper()))


def test_register_command_strips_whitespace(command_executor) -> None:
    """Test that leading/trailing whitespace is stripped from command names."""
    with pytest.raises(ValueError, match="Command name"):
        command_executor.register(DummyCommand(name=f"  {_TEST_CMD_NAME}  "))


def test_register_command_redefinition_warning(command_executor) -> None:
    """Test that redefining a command logs a warning."""
    """Test successful registration of a command."""
    command_executor.register(DummyCommand())
    with pytest.raises(ValueError, match="Attempt to redefine command"):
        command_executor.register(DummyCommand())


def test_register_command_empty_name_raises_error(command_executor) -> None:
    """Test that registering an empty command name raises ValueError."""
    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        command_executor.register(DummyCommand(name=""))


def test_register_command_whitespace_name_raises_error(command_executor) -> None:
    """Test that registering an empty command name raises ValueError."""
    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        command_executor.register(DummyCommand(name="   "))


def test_get_commands(command_executor) -> None:
    """Test retrieving the list of registered command names."""
    command_executor.register(DummyCommand(name="cmdb"))
    command_executor.register(DummyCommand(name="cmda"))
    registered_names = [name for cmd in command_executor.commands for name in cmd.names]
    assert registered_names == ["cmdb", "cmda"]


async def test_execute_existing_command_continue(command_executor) -> None:
    """Test executing a command (no args) that signals continue."""
    command_executor.register(DummyCommand())
    input_context = InputContext(user_input=f"/{_TEST_CMD_NAME}")
    command_result = await command_executor.handle(input_context)
    assert command_result.handled
    assert not command_result.continue_


async def test_execute_non_existent_command(command_executor) -> None:
    """Test executing a command (no args) that signals exit."""
    command_executor.register(DummyCommand())
    input_context = InputContext(user_input=f"/{_TEST_CMD_NAME}1")
    command_result = await command_executor.handle(input_context)
    assert not command_result.handled
    assert command_result.continue_


async def test_execute_command_case_insensitivity(command_executor) -> None:
    """Test that execution matches commands case-insensitively."""
    command_executor.register(DummyCommand())
    input_context = InputContext(user_input=f"/{_TEST_CMD_NAME.upper()}")
    command_result = await command_executor.handle(input_context)
    assert command_result.handled
    assert not command_result.continue_


async def test_execute_command_strips_whitespace(command_executor) -> None:
    """Test that execution handles input with leading/trailing whitespace."""
    command_executor.register(DummyCommand())
    input_context = InputContext(user_input=f"/{_TEST_CMD_NAME}  ")
    command_result = await command_executor.handle(input_context)
    assert command_result.handled
    assert not command_result.continue_


async def test_execute_command_action_raises_exception(command_executor) -> None:
    """Test execution when the command's action raises an exception."""
    command_executor.register(DummyCommand(raise_exception=True))
    input_context = InputContext(user_input=f"/{_TEST_CMD_NAME}")
    command_result = await command_executor.handle(input_context)
    assert command_result.handled
    assert not command_result.continue_
    assert input_context.error
    assert f"Error executing command '/{_TEST_CMD_NAME}'" in input_context.error
