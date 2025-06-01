"""Test fixtures for session_service module tests."""

import tempfile
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from google.adk.events import Event
from google.adk.sessions import Session
from google.genai import types as genai_types

from streetrace.args import Args
from streetrace.prompt_processor import ProcessedPrompt
from streetrace.session_service import (
    JSONSessionSerializer,
    JSONSessionService,
    SessionManager,
)
from streetrace.system_context import SystemContext
from streetrace.ui.ui_bus import UiBus


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir_path:
        yield Path(temp_dir_path)


@pytest.fixture
def session_storage_dir(temp_dir: Path) -> Path:
    """Create a session storage directory."""
    storage_dir = temp_dir / "sessions"
    storage_dir.mkdir(exist_ok=True)
    return storage_dir


@pytest.fixture
def context_dir(temp_dir: Path) -> Path:
    """Create a context directory."""
    context_dir = temp_dir / ".streetrace"
    context_dir.mkdir(exist_ok=True)
    return context_dir


@pytest.fixture
def ui_bus() -> UiBus:
    """Create a mock UI bus."""
    return Mock(spec=UiBus)


@pytest.fixture
def mock_args() -> Args:
    """Create mock Args with necessary properties."""
    args = Mock(spec=Args)
    args.effective_app_name = "test-app"
    args.effective_user_id = "test-user"
    args.session_id = None
    return args


@pytest.fixture
def system_context(ui_bus: UiBus, context_dir: Path) -> SystemContext:
    """Create a mock system context."""
    system_context = Mock(spec=SystemContext)
    system_context.ui_bus = ui_bus
    system_context.config_dir = context_dir
    system_context.get_project_context.return_value = ["Test project context"]
    return system_context


@pytest.fixture
def json_serializer(session_storage_dir: Path) -> JSONSessionSerializer:
    """Create a JSON session serializer."""
    return JSONSessionSerializer(storage_path=session_storage_dir)


@pytest.fixture
def json_session_service(json_serializer: JSONSessionSerializer) -> JSONSessionService:
    """Create a JSON session service."""
    return JSONSessionService(
        storage_path=json_serializer.storage_path,
        serializer=json_serializer,
    )


@pytest.fixture
def session_manager(
    mock_args: Args,
    json_session_service: JSONSessionService,
    system_context: SystemContext,
    ui_bus: UiBus,
) -> SessionManager:
    """Create a session manager."""
    with patch("streetrace.session_service._session_id") as mock_session_id:
        mock_session_id.return_value = "test-session-id"
        return SessionManager(
            args=mock_args,
            session_service=json_session_service,
            system_context=system_context,
            ui_bus=ui_bus,
        )


@pytest.fixture
def sample_session() -> Session:
    """Create a sample session for testing."""
    return Session(
        id="test-session-id",
        app_name="test-app",
        user_id="test-user",
        events=[],
        state={},
    )


@pytest.fixture
def context_event() -> Event:
    """Create a sample context event."""
    return Event(
        author="user",
        content=genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="Test project context")],
        ),
    )


@pytest.fixture
def user_event() -> Event:
    """Create a sample user event."""
    return Event(
        author="user",
        content=genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="User prompt")],
        ),
    )


@pytest.fixture
def assistant_event() -> Event:
    """Create a sample assistant event."""
    return Event(
        author="assistant",
        content=genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="Assistant response")],
        ),
    )


@pytest.fixture
def tool_event() -> Event:
    """Create a sample event with tool calls."""
    return Event(
        author="assistant",
        content=genai_types.Content(
            role="assistant",
            parts=[
                genai_types.Part(
                    text=None,
                    function_call=genai_types.FunctionCall(name="test_function"),
                ),
            ],
        ),
    )


@pytest.fixture
def sample_processed_prompt() -> ProcessedPrompt:
    """Create a sample processed prompt."""
    return ProcessedPrompt(prompt="Test prompt")
