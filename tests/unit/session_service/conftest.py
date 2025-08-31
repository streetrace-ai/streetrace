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
from streetrace.session.json_serializer import JSONSessionSerializer
from streetrace.session.session_manager import SessionManager
from streetrace.session.session_service import JSONSessionService
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
    return system_context


@pytest.fixture
def json_serializer(session_storage_dir: Path) -> JSONSessionSerializer:
    """Create a JSON session serializer."""
    return JSONSessionSerializer(storage_path=session_storage_dir)


@pytest.fixture
def json_session_service(json_serializer: JSONSessionSerializer) -> JSONSessionService:
    """Create a JSON session service."""
    return JSONSessionService(
        serializer=json_serializer,
    )


@pytest.fixture
def session_manager(
    mock_args: Args,
    system_context: SystemContext,
    json_session_service: JSONSessionService,
    ui_bus: UiBus,
) -> SessionManager:
    """Create a session manager."""
    with patch("streetrace.session.session_manager._session_id") as mock_session_id:
        mock_session_id.return_value = "test-session-id"
        manager = SessionManager(
            args=mock_args,
            system_context=system_context,
            ui_bus=ui_bus,
        )
        manager._session_service = json_session_service  # noqa: SLF001
        return manager


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


# Session validation specific fixtures
@pytest.fixture
def function_call_event() -> Event:
    """Create an event with a function call."""
    return Event(
        author="assistant",
        content=genai_types.Content(
            role="assistant",
            parts=[
                genai_types.Part(
                    function_call=genai_types.FunctionCall(
                        name="test_function",
                        args={"param": "value"},
                    ),
                ),
            ],
        ),
    )


@pytest.fixture
def function_response_event() -> Event:
    """Create an event with a function response."""
    return Event(
        author="function",
        content=genai_types.Content(
            role="function",
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name="test_function",
                        response={"result": "success"},
                    ),
                ),
            ],
        ),
    )


@pytest.fixture
def text_only_event() -> Event:
    """Create an event with only text content."""
    return Event(
        author="assistant",
        content=genai_types.Content(
            role="assistant",
            parts=[genai_types.Part.from_text(text="This is a text response")],
        ),
    )


@pytest.fixture
def empty_content_event() -> Event:
    """Create an event with empty content."""
    return Event(
        author="assistant",
        content=None,
    )


@pytest.fixture
def empty_parts_event() -> Event:
    """Create an event with empty parts."""
    return Event(
        author="assistant",
        content=genai_types.Content(
            role="assistant",
            parts=[],
        ),
    )


@pytest.fixture
def mixed_content_event() -> Event:
    """Create an event with both text and function call."""
    return Event(
        author="assistant",
        content=genai_types.Content(
            role="assistant",
            parts=[
                genai_types.Part.from_text(text="I'll call this function:"),
                genai_types.Part(
                    function_call=genai_types.FunctionCall(
                        name="mixed_function",
                        args={},
                    ),
                ),
            ],
        ),
    )


@pytest.fixture
def valid_session_no_functions(sample_session, text_only_event, user_event) -> Session:
    """Create a valid session with no function calls."""
    session = sample_session.model_copy(deep=True)
    session.events = [user_event, text_only_event]
    return session


@pytest.fixture
def valid_session_with_functions(
    sample_session,
    user_event,
    function_call_event,
    function_response_event,
    text_only_event,
) -> Session:
    """Create a valid session with proper function call/response pairs."""
    session = sample_session.model_copy(deep=True)
    session.events = [
        user_event,
        function_call_event,
        function_response_event,
        text_only_event,
    ]
    return session
