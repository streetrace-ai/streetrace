import unittest

# Import Application for type hinting if needed, but avoid direct use
from unittest.mock import MagicMock, patch

from streetrace.commands.definitions.clear_command import ClearCommand
from streetrace.history_manager import HistoryManager


class TestClearCommand(unittest.TestCase):
    """Unit tests for the ClearCommand."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.command = ClearCommand()
        # Mock the HistoryManager
        self.mock_history_manager = MagicMock(spec=HistoryManager)
        # Mock the Application instance - remove spec=Application
        self.mock_app_instance = MagicMock()
        self.mock_app_instance.history_manager = self.mock_history_manager
        # Mock UI on app instance for error display testing
        self.mock_app_instance.ui = MagicMock()

    def test_names_property(self) -> None:
        """Test the names property."""
        assert self.command.names == ["clear"]

    def test_description_property(self) -> None:
        """Test the description property."""
        assert "Clear conversation history" in self.command.description

    def test_execute_calls_history_manager_clear_history(self) -> None:
        """Test execute calls clear_history on the HistoryManager."""
        # Ensure clear_history exists on the mock
        self.mock_history_manager.clear_history = MagicMock()

        # Execute the command
        result = self.command.execute(self.mock_app_instance)

        # Assert clear_history was called once on the history manager
        self.mock_history_manager.clear_history.assert_called_once()
        # Assert the result is True (command always signals continue)
        assert result

    def test_execute_handles_missing_history_manager(self) -> None:
        """Test execute handles when history_manager is missing on the app instance."""
        # Remove the history_manager attribute
        del self.mock_app_instance.history_manager

        with patch("logging.Logger.error") as mock_log_error:
            result = self.command.execute(self.mock_app_instance)

            # Assert an error was logged
            mock_log_error.assert_called_with(
                "Application instance is missing the history_manager.",
            )
            # Assert UI error display was called
            self.mock_app_instance.ui.display_error.assert_called_once()
            # Assert the result is True (should still continue)
            assert result

    def test_execute_handles_missing_clear_history_method(self) -> None:
        """Test execute handles when clear_history method is missing on HistoryManager."""
        # Ensure the history_manager exists but the method doesn't
        # We can achieve this by ensuring the attribute is NOT on the mock manager
        if hasattr(self.mock_history_manager, "clear_history"):
            del self.mock_history_manager.clear_history

        with patch("logging.Logger.error") as mock_log_error:
            result = self.command.execute(self.mock_app_instance)

            # Assert an error was logged
            mock_log_error.assert_called_with(
                "HistoryManager instance is missing the clear_history method.",
            )
            # Assert UI error display was called
            self.mock_app_instance.ui.display_error.assert_called_once()
            # Assert the result is True (should still continue)
            assert result

    # Removed test_execute_returns_value_from_clear_history as command always returns True now


if __name__ == "__main__":
    unittest.main()
