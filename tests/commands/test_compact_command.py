# Avoid direct Application import, use TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import litellm  # Import litellm to create Message objects
import pytest

from streetrace.commands.definitions.compact_command import CompactCommand

# Import History and Role, but not Message
from streetrace.history import History, Role
from streetrace.history_manager import HistoryManager


# --- Tests for CompactCommand structure and execution call ---
class TestCompactCommand:
    """Tests for the CompactCommand class structure and basic execution."""

    def setup_method(self) -> None:
        """Set up test resources before each test method."""
        self.command = CompactCommand()
        # Mock the HistoryManager
        self.mock_history_manager = MagicMock(spec=HistoryManager)
        # Mock the Application instance - remove spec
        self.mock_app = MagicMock()
        self.mock_app.history_manager = self.mock_history_manager
        # Mock UI on app instance for error display testing
        self.mock_app.ui = MagicMock()

    def test_command_names(self) -> None:
        """Test that the command has the expected name(s)."""
        assert "compact" in self.command.names

    def test_command_description(self) -> None:
        """Test that the command has a non-empty description."""
        assert self.command.description
        assert isinstance(self.command.description, str)
        assert len(self.command.description) > 0

    def test_execute_calls_compact_history_on_manager(self) -> None:
        """Test that execute calls compact_history on the HistoryManager."""
        # Ensure the method exists on the mock manager for hasattr check
        self.mock_history_manager.compact_history = MagicMock()
        result = self.command.execute(self.mock_app)
        self.mock_history_manager.compact_history.assert_called_once()
        assert result is True  # Command always returns True

    def test_execute_handles_missing_history_manager(self) -> None:
        """Test execute handles when history_manager is missing on the app instance."""
        del self.mock_app.history_manager

        with patch("logging.Logger.error") as mock_log_error:
            result = self.command.execute(self.mock_app)
            mock_log_error.assert_called_with(
                "Application instance is missing the history_manager.",
            )
            self.mock_app.ui.display_error.assert_called_once()
            assert result is True  # Should still continue

    def test_execute_handles_missing_compact_history_method(self) -> None:
        """Test execute handles when compact_history method is missing on HistoryManager."""
        # Ensure history_manager exists, but the method doesn't
        if hasattr(self.mock_history_manager, "compact_history"):
            del self.mock_history_manager.compact_history

        with patch("logging.Logger.error") as mock_log_error:
            result = self.command.execute(self.mock_app)
            mock_log_error.assert_called_with(
                "HistoryManager instance is missing the compact_history method.",
            )
            self.mock_app.ui.display_error.assert_called_once()
            assert result is True  # Should still continue


# --- Tests for HistoryManager.compact_history functionality ---
class TestHistoryManagerCompactFunctionality:

    @pytest.fixture
    def mock_history_manager_components(self):
        """Fixture to create mocks for HistoryManager dependencies."""
        mock_ui = MagicMock()
        mock_interaction_manager = MagicMock()
        mock_app_config = MagicMock()
        mock_app_config.initial_model = "fake model"
        mock_app_config.tools = MagicMock()
        mock_prompt_processor = MagicMock()  # Needed for __init__ but not compact
        mock_system_context = MagicMock()
        return (
            mock_ui,
            mock_interaction_manager,
            mock_app_config,
            mock_prompt_processor,
            mock_system_context,
        )

    @pytest.fixture
    def history_manager_instance(self, mock_history_manager_components):
        """Fixture to create a HistoryManager instance with mocked dependencies."""
        ui, im, cfg, pp, sc = mock_history_manager_components
        manager = HistoryManager(
            app_config=cfg,
            ui=ui,
            prompt_processor=pp,
            system_context=sc,
            interaction_manager=im,
        )
        # Reset mocks before yielding
        ui.reset_mock()
        im.reset_mock()
        cfg.reset_mock()
        pp.reset_mock()
        return manager

    @pytest.fixture
    def sample_history_data(self):
        """Create data for initializing History, using dicts for messages."""
        messages_data = [
            {"role": Role.USER.value, "content": "User message 1"},
            {"role": Role.MODEL.value, "content": "Model response 1"},
            {"role": Role.USER.value, "content": "User message 2"},
        ]
        return {
            "system_message": "System Info",
            "context": "Project Context",
            "messages": messages_data,
        }

    def test_compact_basic_success(
        self,
        history_manager_instance,
        sample_history_data,
    ) -> None:
        """Test successful compaction: verifies history replacement and UI calls."""
        manager = history_manager_instance
        initial_history = History(**sample_history_data)
        manager.set_history(initial_history)
        summary_text = "This is the conversation summary."

        # Mock interaction_manager: it should modify the history passed to it
        def mock_process_prompt(
            _model: str,
            history_to_summarize: History,
            _tools: any,
        ) -> None:
            assert history_to_summarize.messages[-1].role == Role.USER
            assert "Please summarize" in history_to_summarize.messages[-1].content
            # Simulate LLM adding the summary AS A LITELM.MESSAGE object
            history_to_summarize.messages.append(
                litellm.Message(role=Role.MODEL, content=summary_text),
            )
            assert history_to_summarize.messages[-1].role == Role.MODEL
            assert history_to_summarize.messages[-1].content == summary_text

        manager.interaction_manager.process_prompt.side_effect = mock_process_prompt

        manager.compact_history()

        manager.ui.display_info.assert_has_calls(
            [
                call("Compacting conversation history..."),
                call("History compacted successfully."),
            ],
        )
        manager.interaction_manager.process_prompt.assert_called_once()

        final_history = manager.get_history()
        assert isinstance(final_history, History)
        assert final_history.system_message == sample_history_data["system_message"]
        assert final_history.context == sample_history_data["context"]
        assert len(final_history.messages) == 1
        assert final_history.messages[0].role == Role.MODEL
        assert final_history.messages[0].content == summary_text
        assert final_history is not initial_history

    def test_compact_no_history_to_compact(self, history_manager_instance) -> None:
        """Test compaction attempt when history is None."""
        manager = history_manager_instance

        # freshly mocked history manager will have no messages
        manager.compact_history()

        manager.ui.display_warning.assert_called_once_with(
            "No history available to compact.",
        )
        manager.ui.display_info.assert_not_called()
        manager.interaction_manager.process_prompt.assert_not_called()

    def test_compact_history_with_no_messages(self, history_manager_instance) -> None:
        """Test compaction attempt when history exists but has no messages."""
        manager = history_manager_instance
        empty_history = History(system_message="Sys", context="Ctx", messages=[])
        manager.set_history(empty_history)

        manager.compact_history()

        manager.ui.display_warning.assert_called_once_with(
            "No history available to compact.",
        )
        manager.ui.display_info.assert_not_called()
        manager.interaction_manager.process_prompt.assert_not_called()
        assert manager.get_history() is empty_history

    def test_compact_llm_failure(
        self,
        history_manager_instance,
        sample_history_data,
    ) -> None:
        """Test compaction failure when LLM doesn't return a MODEL message."""
        manager = history_manager_instance
        initial_history = History(**sample_history_data)
        manager.set_history(initial_history)
        original_messages_data = initial_history.messages[:]
        original_system = initial_history.system_message
        original_context = initial_history.context

        # Mock interaction_manager: Simulate adding a USER message
        def mock_process_prompt_failure(_model, history, _tools) -> None:
            history.messages.append(
                litellm.Message(role=Role.USER, content="LLM failed"),
            )

        manager.interaction_manager.process_prompt.side_effect = (
            mock_process_prompt_failure
        )

        manager.compact_history()

        manager.ui.display_info.assert_called_once_with(
            "Compacting conversation history...",
        )
        manager.ui.display_warning.assert_called_once_with(
            "The last message in history is not model, skipping compact. Please report or fix in code if that's not right.",
        )
        manager.interaction_manager.process_prompt.assert_called_once()

        final_history = manager.get_history()
        assert final_history is initial_history
        assert final_history.messages == original_messages_data
        assert final_history.system_message == original_system
        assert final_history.context == original_context

    def test_compact_preserves_system_and_context(
        self,
        history_manager_instance,
        sample_history_data,
    ) -> None:
        """Verify that system message and context are preserved."""
        manager = history_manager_instance
        initial_history = History(**sample_history_data)
        manager.set_history(initial_history)
        summary_text = "Summary preserving context."

        def mock_process_prompt(
            _model: str,
            history_to_summarize: History,
            _tools: any,
        ) -> None:
            history_to_summarize.messages.append(
                litellm.Message(role=Role.MODEL, content=summary_text),
            )

        manager.interaction_manager.process_prompt.side_effect = mock_process_prompt

        manager.compact_history()

        final_history = manager.get_history()
        assert final_history is not None
        assert final_history.system_message == sample_history_data["system_message"]
        assert final_history.context == sample_history_data["context"]
