from unittest.mock import MagicMock, call

import pytest

# Assuming Application is importable and contains the compact_history method
from streetrace.application import Application
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.history import History, Role


# --- Tests for CompactCommand structure and execution call ---
class TestCompactCommand:
    """Tests for the CompactCommand class structure and basic execution."""

    def setup_method(self) -> None:
        """Set up test resources before each test method."""
        self.command = CompactCommand()
        # Use a MagicMock for Application but without mocking compact_history itself initially
        self.mock_app = MagicMock(spec=Application)
        # Define compact_history on the mock spec so it's recognized
        self.mock_app.compact_history = MagicMock(return_value=True)

    def test_command_names(self) -> None:
        """Test that the command has the expected name(s)."""
        assert "compact" in self.command.names

    def test_command_description(self) -> None:
        """Test that the command has a non-empty description."""
        assert self.command.description
        assert isinstance(self.command.description, str)
        assert len(self.command.description) > 0

    def test_execute_calls_compact_history(self) -> None:
        """Test that execute calls the compact_history method on the application."""
        # We pass the *instance* of the command, not the class
        CompactCommand().execute(self.mock_app)
        self.mock_app.compact_history.assert_called_once()

    def test_execute_returns_continue_signal_from_compact(self) -> None:
        """Test that execute returns the boolean signal from compact_history."""
        self.mock_app.compact_history.return_value = True
        result = CompactCommand().execute(self.mock_app)
        assert result is True

        self.mock_app.compact_history.return_value = (
            False  # Though compact currently always returns True
        )
        result = CompactCommand().execute(self.mock_app)
        assert result is False


# --- Tests for the compact_history method functionality ---
class TestCompactFunctionality:
    @pytest.fixture
    def mock_app(self):
        """Create a mock application with mocked UI and InteractionManager."""
        app = MagicMock(spec=Application)
        app.ui = MagicMock()
        app.interaction_manager = MagicMock()
        app.config = MagicMock()
        app.config.initial_model = "fake model"
        app.config.tools = MagicMock()
        # We will call the *real* Application.compact_history method,
        # passing this mock_app instance as 'self'.
        return app

    @pytest.fixture
    def sample_history(self):
        """Create a sample conversation history."""
        history = History(system_message="System Info", context="Project Context")
        history.add_user_message(
            "User message 1",
        )
        history.add_assistant_message_test(
            "Model response 1",
        )
        history.add_user_message(
            "User message 2",
        )
        return history

    def test_compact_basic_success(self, mock_app, sample_history) -> None:
        """Test successful compaction: verifies history replacement and UI calls."""
        mock_app.conversation_history = sample_history
        summary_text = "This is the conversation summary."

        # Mock interaction_manager: it should add a MODEL response to the history passed to it
        def mock_process_prompt(
            _model: str,
            history_to_summarize: History,
            _tools: any,
        ) -> None:
            assert (
                history_to_summarize.messages[-1].role == "user"
            )  # check summary prompt is added
            assert (
                "Please summarize our conversation"
                in history_to_summarize.messages[-1].content
            )
            # Simulate LLM adding the summary
            history_to_summarize.add_assistant_message_test(
                summary_text,
            )

        mock_app.interaction_manager.process_prompt.side_effect = mock_process_prompt

        # Execute the actual compact_history method on the mock_app instance
        result = Application.compact_history(mock_app)

        # Assertions
        assert result is True  # Should signal to continue
        mock_app.ui.display_info.assert_has_calls(
            [
                call("Compacting conversation history..."),
                call("History compacted successfully."),
            ],
        )
        mock_app.interaction_manager.process_prompt.assert_called_once()

        # Verify the history was replaced
        final_history = mock_app.conversation_history
        assert isinstance(final_history, History)
        assert final_history.system_message == sample_history.system_message
        assert final_history.context == sample_history.context
        assert len(final_history.messages) == 1  # Only the summary message remains
        assert final_history.messages[0].role == "assistant"
        assert final_history.messages[0].content == summary_text
        # Verify original history object is not the same object anymore
        assert final_history is not sample_history

    def test_compact_no_history_to_compact(self, mock_app) -> None:
        """Test compaction attempt when history is None."""
        mock_app.conversation_history = None

        # Execute
        result = Application.compact_history(mock_app)

        # Assertions
        assert result is True
        mock_app.ui.display_warning.assert_called_once_with(
            "No history available to compact.",
        )
        mock_app.ui.display_info.assert_not_called()  # No "Compacting..." message
        mock_app.interaction_manager.process_prompt.assert_not_called()

    def test_compact_history_with_no_messages(self, mock_app) -> None:
        """Test compaction attempt when history exists but has no conversation messages."""
        mock_app.conversation_history = History(
            system_message="Sys",
            context="Ctx",
            messages=[],  # Empty conversation list
        )

        # Execute
        result = Application.compact_history(mock_app)

        # Assertions
        assert result is True
        mock_app.ui.display_warning.assert_called_once_with(
            "No history available to compact.",
        )
        mock_app.ui.display_info.assert_not_called()  # No "Compacting..." message
        mock_app.interaction_manager.process_prompt.assert_not_called()
        # Ensure history object itself wasn't replaced
        assert mock_app.conversation_history.messages == []

    def test_compact_llm_failure(self, mock_app, sample_history) -> None:
        """Test compaction failure when the LLM doesn't return a MODEL message."""
        mock_app.conversation_history = sample_history
        original_history_conversation = sample_history.messages[:]  # Keep a copy

        # Mock interaction_manager: Simulate it *not* adding a MODEL response
        def mock_process_prompt_failure(_model, _history, _tools) -> None:
            # LLM simulation does nothing here
            pass

        mock_app.interaction_manager.process_prompt.side_effect = (
            mock_process_prompt_failure
        )

        # Execute
        result = Application.compact_history(mock_app)

        # Assertions
        assert result is True  # Still returns True to continue loop
        mock_app.ui.display_info.assert_called_once_with(
            "Compacting conversation history...",
        )
        mock_app.ui.display_error.assert_called_once_with(
            "Failed to generate summary. History remains unchanged.",
        )
        mock_app.interaction_manager.process_prompt.assert_called_once()

        # Verify the history was NOT replaced
        assert mock_app.conversation_history is sample_history
        assert mock_app.conversation_history.messages == original_history_conversation

    def test_compact_preserves_system_and_context(
        self,
        mock_app,
        sample_history,
    ) -> None:
        """Verify that system message and context are preserved after compaction."""
        mock_app.conversation_history = sample_history
        summary_text = "Summary preserving context."

        def mock_process_prompt(
            _model: str,
            history_to_summarize: History,
            _tools: any,
        ) -> None:
            history_to_summarize.add_assistant_message_test(
                summary_text,
            )

        mock_app.interaction_manager.process_prompt.side_effect = mock_process_prompt

        Application.compact_history(mock_app)

        final_history = mock_app.conversation_history
        assert final_history.system_message == "System Info"
        assert final_history.context == "Project Context"

    def test_compact_post_compaction_continuity(self, mock_app, sample_history) -> None:
        """Verify conversation can continue after a successful compaction."""
        mock_app.conversation_history = sample_history
        summary_text = "Compacted history."

        # Mock the summarization process
        def mock_process_prompt(
            _model: str,
            history_to_summarize: History,
            _tools: any,
        ) -> None:
            history_to_summarize.add_assistant_message_test(
                summary_text,
            )

        mock_app.interaction_manager.process_prompt.side_effect = mock_process_prompt

        # Perform compaction
        Application.compact_history(mock_app)

        # Verify compaction happened
        assert len(mock_app.conversation_history.messages) == 1
        assert mock_app.conversation_history.messages[0].content == summary_text

        # Add a new message after compaction
        new_user_message = "What's the next step?"
        mock_app.conversation_history.add_user_message(
            new_user_message,
        )

        # Verify the new message is appended correctly
        assert len(mock_app.conversation_history.messages) == 2
        assert mock_app.conversation_history.messages[0].role == Role.MODEL  # Summary
        assert (
            mock_app.conversation_history.messages[1].role == Role.USER
        )  # New message
        assert mock_app.conversation_history.messages[1].content == new_user_message
