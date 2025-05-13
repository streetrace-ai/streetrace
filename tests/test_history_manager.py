from unittest.mock import MagicMock, patch

import pytest

from streetrace.history import HistoryManager, Role

# Mock dependencies
MockAppConfig = MagicMock()
MockUI = MagicMock()
MockPromptProcessor = MagicMock()
MockSystemContext = MagicMock()
MockInteractionManager = MagicMock()


@pytest.fixture
def history_manager_instance():
    """Provide a HistoryManager instance with fresh mocks for each test."""
    mock_ui = MagicMock()
    mock_pp = MagicMock()
    mock_sc = MagicMock()
    mock_im = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.working_dir = "/fake/dir"
    mock_cfg.initial_model = "test-model"
    mock_cfg.tools = []

    # Mock system_context for get_system_message and get_project_context
    mock_sc.get_system_message.return_value = "Test System Message"
    mock_sc.get_project_context.return_value = "Test Project Context"

    # Mock build_context on the PromptProcessor mock
    mock_initial_context = MagicMock()
    mock_initial_context.mentioned_files = []
    mock_pp.build_context.return_value = mock_initial_context

    manager = HistoryManager(
        app_config=mock_cfg,
        ui=mock_ui,
        prompt_processor=mock_pp,
        system_context=mock_sc,
        interaction_manager=mock_im,
    )
    # Reset mocks before yielding
    mock_ui.reset_mock()
    mock_pp.reset_mock()
    mock_sc.reset_mock()
    mock_im.reset_mock()
    mock_cfg.reset_mock()

    # Re-assign after reset
    mock_sc.get_system_message.return_value = "Test System Message"
    mock_sc.get_project_context.return_value = "Test Project Context"
    mock_pp.build_context.return_value = mock_initial_context

    return manager


# --- Initialization Tests --- #


def test_initialize_history_interactive(history_manager_instance: HistoryManager):
    """Test initializing history for an interactive session."""
    manager = history_manager_instance
    manager.initialize_history()

    # Check that system_context methods were called
    manager.system_context.get_system_message.assert_called_once()
    manager.system_context.get_project_context.assert_called_once()

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
