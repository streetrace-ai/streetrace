from unittest.mock import MagicMock, call, patch

import pytest

from streetrace.history import Role
from streetrace.history_manager import _MAX_CONTEXT_PREVIEW_LENGTH, HistoryManager
from streetrace.tools.tool_call_result import ToolCallResult, ToolOutput

# Mock dependencies
MockAppConfig = MagicMock()
MockUI = MagicMock()
MockPromptProcessor = MagicMock()
MockInteractionManager = MagicMock()


@pytest.fixture
def history_manager_instance():
    """Provide a HistoryManager instance with fresh mocks for each test."""
    mock_ui = MagicMock()
    mock_pp = MagicMock()
    mock_im = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.working_dir = "/fake/dir"
    mock_cfg.initial_model = "test-model"
    mock_cfg.tools = []

    # Mock build_context on the PromptProcessor mock
    mock_initial_context = MagicMock()
    mock_initial_context.system_message = "Test System Message"
    mock_initial_context.project_context = "Test Project Context"
    mock_pp.build_context.return_value = mock_initial_context

    manager = HistoryManager(
        app_config=mock_cfg,
        ui=mock_ui,
        prompt_processor=mock_pp,
        interaction_manager=mock_im,
    )
    # Reset mocks before yielding
    mock_ui.reset_mock()
    mock_pp.reset_mock()
    mock_im.reset_mock()
    mock_cfg.reset_mock()
    mock_pp.build_context.return_value = mock_initial_context  # Re-assign after reset

    return manager


# --- Initialization Tests --- #


def test_initialize_history_interactive(history_manager_instance: HistoryManager):
    """Test initializing history for an interactive session."""
    manager = history_manager_instance
    manager.initialize_history()

    # Check that build_context was called
    manager.prompt_processor.build_context.assert_called_once_with(
        "",
        manager.app_config.working_dir,
    )

    history = manager.get_history()
    assert history is not None
    assert history.system_message == "Test System Message"
    assert history.context == "Test Project Context"
    assert len(history.messages) == 0


# --- Message Adding Tests --- #


def test_add_user_message(history_manager_instance: HistoryManager):
    """Test adding a user message."""
    manager = history_manager_instance
    manager.initialize_history()  # Need an initialized history
    manager.add_user_message("Hello there!")

    history = manager.get_history()
    assert len(history.messages) == 1
    assert history.messages[0].role == Role.USER
    assert history.messages[0].content == "Hello there!"


def test_add_user_message_no_history(history_manager_instance: HistoryManager):
    """Test adding user message when history is not initialized."""
    manager = history_manager_instance
    # History is None by default
    with patch("logging.Logger.error") as mock_log_error:
        manager.add_user_message("Test")
        mock_log_error.assert_called_with(
            "Cannot add user message, history not initialized.",
        )
    assert manager.get_history() is None


def test_add_mentions_to_history(history_manager_instance: HistoryManager):
    """Test adding mentions to history."""
    manager = history_manager_instance
    manager.initialize_history()
    mentions = [
        ("file1.py", "content1"),
        ("file2.txt", "content2"),
    ]
    manager.add_mentions_to_history(mentions)

    history = manager.get_history()
    # Mentions are added as context messages
    assert len(history.messages) == 2
    assert "file1.py" in history.messages[0].content
    assert "content1" in history.messages[0].content
    assert "file2.txt" in history.messages[1].content
    assert "content2" in history.messages[1].content


def test_add_mentions_truncation(history_manager_instance: HistoryManager):
    """Test adding mentions truncates long content."""
    manager = history_manager_instance
    manager.initialize_history()
    long_content = "a" * 30000
    mentions = [
        ("long_file.py", long_content),
    ]

    with patch("logging.Logger.warning") as mock_log_warning:
        manager.add_mentions_to_history(mentions)
        mock_log_warning.assert_called_once()

    history = manager.get_history()
    assert len(history.messages) == 1
    assert "long_file.py (truncated)" in history.messages[0].content
    assert len(history.messages[0].content) < len(long_content)
    assert "aaaaaaaa" in history.messages[0].content


def test_add_mentions_no_history(history_manager_instance: HistoryManager):
    """Test adding mentions when history is not initialized."""
    manager = history_manager_instance
    # History is None
    with patch("logging.Logger.error") as mock_log_error:
        manager.add_mentions_to_history([("file.txt", "content")])
        mock_log_error.assert_called_with(
            "Cannot add mentions, history is not initialized.",
        )
    assert manager.get_history() is None


# --- Display History Tests --- #


def test_display_history_empty(history_manager_instance: HistoryManager):
    """Test displaying history when it's None or empty."""
    manager = history_manager_instance
    # Case 1: History is None
    manager.display_history()
    manager.ui.display_warning.assert_called_once_with("No history available yet.")
    manager.ui.reset_mock()

    # Case 2: History is initialized but empty
    manager.initialize_history()
    manager.get_history().messages = []  # Ensure messages are empty
    manager.display_history()
    manager.ui.display_info.assert_any_call("No messages in history yet.")
    manager.ui.display_system_message.assert_called_once_with("Test System Message")
    manager.ui.display_context_message.assert_called_once_with("Test Project Context")


def test_display_history_with_content(history_manager_instance: HistoryManager):
    """Test displaying history with various message types."""
    manager = history_manager_instance
    manager.initialize_history()
    history = manager.get_history()

    # Add messages
    history.add_user_message("User prompt")
    # Simulate adding a model message with tool calls
    tool_call_mock = {
        "tool_call_id": "tool123",
        "tool_name": "read_file",
        "arguments": '{"path": "a.txt"}',
    }
    history.add_assistant_message_test(content="Thinking...", tool_call=tool_call_mock)
    # Simulate adding a tool result message
    tool_result = ToolCallResult(
        success=True,
        output=ToolOutput(type="text", content="File content here"),
    )
    history.add_tool_message(
        tool_call_id="tool123",
        tool_result=tool_result,
        tool_name="read_file",
    )
    history.add_assistant_message_test(content="Final answer")

    manager.display_history()

    # Check calls to UI display methods
    manager.ui.display_system_message.assert_called_once_with("Test System Message")
    manager.ui.display_context_message.assert_called_once_with("Test Project Context")
    manager.ui.display_history_user_message.assert_called_once_with("User prompt")
    manager.ui.display_history_assistant_message.assert_has_calls(
        [
            call("Thinking..."),  # First assistant message content
            call("Final answer"),  # Second assistant message content
        ],
    )
    manager.ui.display_tool_call.assert_called_once()
    # Need to validate the arguments passed to display_tool_result
    manager.ui.display_tool_result.assert_called_once()
    args, _ = manager.ui.display_tool_result.call_args
    assert args[0] == "read_file"
    assert isinstance(args[1], ToolCallResult)
    assert args[1].output.content == "File content here"


def test_display_history_long_context_preview(history_manager_instance: HistoryManager):
    """Test that long context is truncated in display."""
    manager = history_manager_instance
    long_context_str = "a" * (_MAX_CONTEXT_PREVIEW_LENGTH + 100)
    mock_ctx = MagicMock()
    mock_ctx.system_message = "System"
    mock_ctx.project_context = long_context_str
    manager.prompt_processor.build_context.return_value = mock_ctx

    manager.initialize_history()
    manager.display_history()

    expected_preview = long_context_str[:_MAX_CONTEXT_PREVIEW_LENGTH] + "..."
    manager.ui.display_context_message.assert_called_once_with(expected_preview)


# --- Clear History Tests --- #


def test_clear_history(history_manager_instance: HistoryManager):
    """Test clearing the history."""
    manager = history_manager_instance
    # Initialize and add something
    manager.initialize_history()
    manager.add_user_message("some message")
    assert len(manager.get_history().messages) == 1

    # Clear
    manager.clear_history()

    # Verify it re-initialized
    manager.prompt_processor.build_context.assert_called_with(
        "",
        manager.app_config.working_dir,
    )
    manager.ui.display_info.assert_called_once_with(
        "Conversation history has been cleared.",
    )
    history = manager.get_history()
    assert history is not None
    assert history.system_message == "Test System Message"  # From mock build_context
    assert history.context == "Test Project Context"
    assert len(history.messages) == 0


def test_clear_history_handles_exception(history_manager_instance: HistoryManager):
    """Test that clearing history handles exceptions during context rebuild."""
    manager = history_manager_instance
    manager.initialize_history()

    # Make build_context raise an error
    error_message = "Failed to build context"
    manager.prompt_processor.build_context.side_effect = Exception(error_message)

    with patch("logging.Logger.exception") as mock_log_exception:
        manager.clear_history()

        # Check that error was logged and UI message displayed
        mock_log_exception.assert_called_once()
        manager.ui.display_error.assert_called_once_with(
            f"Could not clear history due to an error: {error_message}",
        )

    # History should ideally still exist, maybe in its old state or None
    # Depending on exact error handling, let's just check it didn't crash
    assert manager.get_history() is not None  # Remains the old history in this case
