from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from google.adk.sessions import Session
from prompt_toolkit import PromptSession
from rich.console import Console

from streetrace.agents.agent_manager import AgentManager
from streetrace.app import Application
from streetrace.app_state import AppState
from streetrace.args import Args
from streetrace.commands.command_executor import CommandExecutor
from streetrace.commands.definitions import (
    CompactCommand,
    ExitCommand,
    HelpCommand,
    HistoryCommand,
    ResetSessionCommand,
)

# Import specific command classes
from streetrace.llm.model_factory import ModelFactory
from streetrace.prompt_processor import PromptProcessor
from streetrace.session_service import (
    JSONSessionSerializer,
    JSONSessionService,
    SessionManager,
)
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.ui.completer import CommandCompleter, PathCompleter, PromptCompleter
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.ui_bus import UiBus
from streetrace.workflow.supervisor import Supervisor

FAKE_MODEL_NAME = "fake-model"


@pytest.fixture
def mock_args() -> Args:
    return Mock(spec=Args)


@pytest.fixture
def fake_model_name() -> str:
    return FAKE_MODEL_NAME


@pytest.fixture
def app_state(fake_model_name) -> Args:
    return AppState(current_model=fake_model_name)


@pytest.fixture
def work_dir(tmp_path) -> Path:
    """Fixture to provide a mock working directory."""
    return tmp_path


@pytest.fixture
def mock_ui_bus() -> UiBus:
    return Mock(spec=UiBus)


@pytest.fixture
def mock_command_executor() -> CommandExecutor:
    return Mock(spec=CommandExecutor)


@pytest.fixture
def mock_path_completer() -> PathCompleter:
    return Mock(spec=PathCompleter)


@pytest.fixture
def shallow_path_completer(work_dir) -> PathCompleter:
    return PathCompleter(work_dir)


@pytest.fixture
def mock_command_completer(mock_command_executor) -> CommandCompleter:
    command_completer = Mock(spec=CommandCompleter)
    command_completer.command_executor = mock_command_executor
    return command_completer


@pytest.fixture
def shallow_command_completer(mock_command_executor) -> CommandCompleter:
    return CommandCompleter(mock_command_executor)


@pytest.fixture
def mock_prompt_completer(
    mock_path_completer,
    mock_command_completer,
) -> PromptCompleter:
    prompt_completer = Mock(spec=PromptCompleter)
    prompt_completer.completers = [mock_path_completer, mock_command_completer]
    return prompt_completer


@pytest.fixture
def shallow_prompt_completer(
    mock_path_completer,
    mock_command_completer,
) -> PromptCompleter:
    return PromptCompleter([mock_path_completer, mock_command_completer])


@pytest.fixture
def mock_rich_console() -> Console:
    return Mock(spec=Console)


@pytest.fixture
def mock_prompt_session(mock_prompt_completer) -> PromptSession[Any]:
    prompt_session = Mock(spec=PromptSession[Any])
    prompt_session.completer = mock_prompt_completer
    return prompt_session


@pytest.fixture
def mock_console_ui(
    app_state,
    mock_prompt_completer,
    mock_ui_bus,
    mock_rich_console,
    mock_prompt_session,
) -> ConsoleUI:
    console_ui = Mock(spec=ConsoleUI)
    console_ui.app_state = app_state
    console_ui.console = mock_rich_console
    console_ui.completer = mock_prompt_completer
    console_ui.prompt_session = mock_prompt_session
    console_ui.ui_bus = mock_ui_bus
    return console_ui


@pytest.fixture
def shallow_console_ui(
    app_state,
    mock_prompt_completer,
    mock_ui_bus,
    mock_rich_console,
    mock_prompt_session,
) -> ConsoleUI:
    console_ui = ConsoleUI(
        app_state=app_state,
        completer=mock_prompt_completer,
        ui_bus=mock_ui_bus,
    )
    console_ui.console = mock_rich_console
    console_ui.prompt_session = mock_prompt_session
    return console_ui


@pytest.fixture
def context_dir(work_dir) -> Path:
    return work_dir / "context"


@pytest.fixture
def mock_system_context(context_dir, mock_ui_bus) -> SystemContext:
    system_context = Mock(spec=SystemContext)
    system_context.ui_bus = mock_ui_bus
    system_context.config_dir = context_dir
    return system_context


@pytest.fixture
def shallow_system_context(context_dir, mock_ui_bus) -> SystemContext:
    return SystemContext(ui_bus=mock_ui_bus, context_dir=context_dir)


@pytest.fixture
def mock_prompt_processor(mock_ui_bus, mock_args) -> PromptProcessor:
    prompt_processor = Mock(spec=PromptProcessor)
    prompt_processor.ui_bus = mock_ui_bus
    prompt_processor.args = mock_args
    return prompt_processor


@pytest.fixture
def shallow_prompt_processor(mock_ui_bus, mock_args) -> PromptProcessor:
    return PromptProcessor(ui_bus=mock_ui_bus, args=mock_args)


@pytest.fixture
def mock_tool_provider(work_dir) -> ToolProvider:
    tool_provider = Mock(spec=ToolProvider)
    tool_provider.work_dir = work_dir
    return tool_provider


@pytest.fixture
def shallow_tool_provider(work_dir) -> ToolProvider:
    return ToolProvider(work_dir)


@pytest.fixture
def sessions_dir(context_dir) -> Path:
    return context_dir / "sessions"


@pytest.fixture
def mock_json_serializer(sessions_dir) -> JSONSessionSerializer:
    session_serializer = Mock(spec=JSONSessionSerializer)
    session_serializer.storage_path = sessions_dir
    return session_serializer


@pytest.fixture
def fake_session_id() -> str:
    return "fake-session-id"


@pytest.fixture
def fake_user_id() -> str:
    return "fake-user-id"


@pytest.fixture
def fake_app_name() -> str:
    return "fake-app-name"


@pytest.fixture
def mock_session(fake_app_name, fake_user_id, fake_session_id) -> Session:
    session = Mock(spec=Session)
    session.app_name = fake_app_name
    session.user_id = fake_user_id
    session.id = fake_session_id
    return session


@pytest.fixture
def shallow_json_serializer(sessions_dir) -> JSONSessionSerializer:
    return JSONSessionSerializer(sessions_dir)


@pytest.fixture
def mock_json_session_service(mock_json_serializer) -> JSONSessionService:
    session_service = Mock(spec=JSONSessionService)
    session_service.serializer = mock_json_serializer
    return session_service


@pytest.fixture
def shallow_json_session_service(
    sessions_dir,
    mock_json_serializer,
) -> JSONSessionService:
    return JSONSessionService(sessions_dir, mock_json_serializer)


@pytest.fixture
def mock_session_manager(
    mock_json_session_service,
    mock_args,
    mock_system_context,
    mock_ui_bus,
    mock_session,
) -> SessionManager:
    session_manager = Mock(spec=SessionManager)
    session_manager.session_service = mock_json_session_service
    session_manager.args = mock_args
    session_manager.system_context = mock_system_context
    session_manager.ui_bus = mock_ui_bus
    session_manager.get_or_create_session.return_value = mock_session
    return session_manager


@pytest.fixture
def shallow_session_manager(
    mock_json_session_service,
    mock_args,
    mock_system_context,
    mock_ui_bus,
) -> SessionManager:
    return SessionManager(
        session_service=mock_json_session_service,
        args=mock_args,
        system_context=mock_system_context,
        ui_bus=mock_ui_bus,
    )


@pytest.fixture
def mock_model_factory(mock_ui_bus, fake_model_name) -> ModelFactory:
    model_factory = Mock(spec=ModelFactory)
    model_factory.ui_bus = mock_ui_bus
    model_factory.current_model_name = fake_model_name
    return model_factory


@pytest.fixture
def shallow_model_factory(mock_ui_bus, fake_model_name) -> ModelFactory:
    return ModelFactory(fake_model_name, mock_ui_bus)


@pytest.fixture
def mock_agent_manager(
    mock_model_factory,
    mock_tool_provider,
    work_dir,
) -> AgentManager:
    agent_manager = Mock(spec=AgentManager)
    agent_manager.model_factory = mock_model_factory
    agent_manager.tool_provider = mock_tool_provider
    agent_manager.work_dir = work_dir
    return agent_manager


@pytest.fixture
def shallow_agent_manager(
    mock_model_factory,
    mock_tool_provider,
    work_dir,
) -> AgentManager:
    return AgentManager(
        model_factory=mock_model_factory,
        tool_provider=mock_tool_provider,
        work_dir=work_dir,
    )


@pytest.fixture
def mock_supervisor(
    mock_ui_bus,
    mock_session_manager,
    mock_agent_manager,
) -> Supervisor:
    supervisor = Mock(spec=Supervisor)
    supervisor.ui_bus = mock_ui_bus
    supervisor.session_manager = mock_session_manager
    supervisor.agent_manager = mock_agent_manager
    return supervisor


@pytest.fixture
def shallow_supervisor(
    mock_ui_bus,
    mock_session_manager,
    mock_agent_manager,
) -> Supervisor:
    return Supervisor(
        ui_bus=mock_ui_bus,
        session_manager=mock_session_manager,
        agent_manager=mock_agent_manager,
    )


@pytest.fixture
def mock_compact_command(
    mock_args,
    mock_ui_bus,
    mock_session_manager,
    mock_system_context,
    mock_model_factory,
) -> CompactCommand:
    compact_command = Mock(spec=CompactCommand)
    compact_command.args = mock_args
    compact_command.ui_bus = mock_ui_bus
    compact_command.session_manager = mock_session_manager
    compact_command.system_context = mock_system_context
    compact_command.model_factory = mock_model_factory
    return compact_command


@pytest.fixture
def shallow_compact_command(
    mock_args,
    mock_ui_bus,
    mock_session_manager,
    mock_system_context,
    mock_model_factory,
) -> CompactCommand:
    return CompactCommand(
        args=mock_args,
        ui_bus=mock_ui_bus,
        session_manager=mock_session_manager,
        system_context=mock_system_context,
        model_factory=mock_model_factory,
    )


@pytest.fixture
def mock_exit_command() -> ExitCommand:
    return Mock(spec=ExitCommand)


@pytest.fixture
def mock_help_command(mock_ui_bus, mock_command_executor) -> HelpCommand:
    help_command = Mock(spec=HelpCommand)
    help_command.ui_bus = mock_ui_bus
    help_command.cmd_executor = mock_command_executor
    return help_command


@pytest.fixture
def shallow_help_command(mock_ui_bus, mock_command_executor) -> HelpCommand:
    return HelpCommand(
        ui_bus=mock_ui_bus,
        cmd_executor=mock_command_executor,
    )


@pytest.fixture
def mock_history_command(
    mock_ui_bus,
    mock_system_context,
    mock_session_manager,
) -> HistoryCommand:
    history_command = Mock(spec=HistoryCommand)
    history_command.ui_bus = mock_ui_bus
    history_command.system_context = mock_system_context
    history_command.session_manager = mock_session_manager
    return history_command


@pytest.fixture
def shallow_history_command(
    mock_ui_bus,
    mock_system_context,
    mock_session_manager,
) -> HistoryCommand:
    return HistoryCommand(
        ui_bus=mock_ui_bus,
        system_context=mock_system_context,
        session_manager=mock_session_manager,
    )


@pytest.fixture
def mock_reset_command(mock_ui_bus, mock_session_manager) -> ResetSessionCommand:
    reset_command = Mock(spec=ResetSessionCommand)
    reset_command.ui_bus = mock_ui_bus
    reset_command.session_manager = mock_session_manager
    return reset_command


@pytest.fixture
def shallow_reset_command(mock_ui_bus, mock_session_manager) -> ResetSessionCommand:
    return ResetSessionCommand(
        ui_bus=mock_ui_bus,
        session_manager=mock_session_manager,
    )


@pytest.fixture
def mock_app(  # noqa: PLR0913
    mock_args,
    mock_console_ui,
    mock_ui_bus,
    mock_command_executor,
    mock_prompt_processor,
    mock_session_manager,
    mock_supervisor,
    app_state,
) -> Application:
    app = Mock(spec=Application)
    app.args = mock_args
    app.ui = mock_console_ui
    app.ui_bus = mock_ui_bus
    app.cmd_executor = mock_command_executor
    app.prompt_processor = mock_prompt_processor
    app.session_manager = mock_session_manager
    app.workflow_supervisor = mock_supervisor
    app.state = app_state
    return app


@pytest.fixture
def shallow_app(  # noqa: PLR0913
    mock_args,
    mock_console_ui,
    mock_ui_bus,
    mock_command_executor,
    mock_prompt_processor,
    mock_session_manager,
    mock_supervisor,
    app_state,
) -> Application:
    return Application(
        args=mock_args,
        ui=mock_console_ui,
        ui_bus=mock_ui_bus,
        cmd_executor=mock_command_executor,
        prompt_processor=mock_prompt_processor,
        session_manager=mock_session_manager,
        workflow_supervisor=mock_supervisor,
        state=app_state,
    )
