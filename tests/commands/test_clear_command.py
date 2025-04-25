# tests/commands/test_clear_command.py
import unittest
from unittest.mock import MagicMock, patch

from streetrace.application import Application
from streetrace.commands.definitions.clear_command import ClearCommand


class TestClearCommand(unittest.TestCase):
    """Unit tests for the ClearCommand."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.command = ClearCommand()
        # Mock the Application instance
        self.mock_app_instance = MagicMock(spec=Application)

    def test_names_property(self) -> None:
        """Test the names property."""
        assert self.command.names == ["clear"]

    def test_description_property(self) -> None:
        """Test the description property."""
        assert "Clear conversation history" in self.command.description

    def test_execute_calls_clear_history(self) -> None:
        """Test that execute calls the _clear_history method on the app instance."""
        # Ensure _clear_history exists and returns True
        self.mock_app_instance._clear_history = MagicMock(return_value=True)

        # Execute the command
        result = self.command.execute(self.mock_app_instance)

        # Assert _clear_history was called once
        self.mock_app_instance._clear_history.assert_called_once()
        # Assert the result is True (should continue)
        assert result

    def test_execute_handles_missing_method(self) -> None:
        """Test execute handles when _clear_history is missing on the app instance."""
        # Remove the method from the mock
        del self.mock_app_instance._clear_history

        # Execute the command and check for logs (optional)
        with patch("logging.Logger.error") as mock_log_error:
            result = self.command.execute(self.mock_app_instance)

            # Assert an error was logged
            mock_log_error.assert_called_once_with(
                "Application instance is missing the _clear_history method.",
            )
            # Assert the result is still True (should continue by default)
            assert not result

    def test_execute_returns_value_from_clear_history(self) -> None:
        """Test that execute returns the boolean value from _clear_history."""
        # Configure _clear_history to return False
        self.mock_app_instance._clear_history = MagicMock(return_value=False)
        result_false = self.command.execute(self.mock_app_instance)
        assert not result_false
        self.mock_app_instance._clear_history.assert_called_once()

        # Configure _clear_history to return True
        self.mock_app_instance._clear_history = MagicMock(return_value=True)
        result_true = self.command.execute(self.mock_app_instance)
        assert result_true
        assert self.mock_app_instance._clear_history.call_count == 1  # Called again


if __name__ == "__main__":
    unittest.main()
