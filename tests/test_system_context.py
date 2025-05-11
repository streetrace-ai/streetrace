"""Tests for the SystemContext class."""

import pathlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from streetrace.system_context import SystemContext
from streetrace.ui.console_ui import ConsoleUI


class TestSystemContext(unittest.TestCase):
    """Test the SystemContext class."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up temporary directories once for the class."""
        cls.base_temp_dir = Path(
            tempfile.mkdtemp(prefix="streetrace_test_system_context_"),
        )
        cls.config_dir = cls.base_temp_dir / ".streetrace"
        cls.config_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up the temporary directories once after all tests."""
        if hasattr(cls, "base_temp_dir") and cls.base_temp_dir.exists():
            shutil.rmtree(cls.base_temp_dir)

    def setUp(self) -> None:
        """Instantiate SystemContext for each test."""
        # Mock the UI to avoid console output during tests
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.system_context = SystemContext(
            ui=self.mock_ui,
            config_dir=self.config_dir,
        )

    def test_get_system_message_default(self) -> None:
        """Test that default system message is returned when no system.md exists."""
        with patch("streetrace.messages.SYSTEM", "Default System Message"):
            system_message = self.system_context.get_system_message()
            assert system_message == "Default System Message"

    def test_get_system_message_custom(self) -> None:
        """Test that custom system message is read from file."""
        system_file = self.config_dir / "system.md"
        custom_message = "Custom System Message"
        with system_file.open("w") as f:
            f.write(custom_message)

        try:
            system_message = self.system_context.get_system_message()
            assert system_message == custom_message
        finally:
            system_file.unlink()

    def test_get_system_message_error(self) -> None:
        """Test that error is handled when system.md exists but can't be read."""
        system_file = self.config_dir / "system.md"

        # Create the file but make it unreadable
        with system_file.open("w") as f:
            f.write("Some content")

        try:
            with patch("pathlib.Path.read_text") as mock_read_text:
                mock_read_text.side_effect = PermissionError("Access denied")

                with patch("streetrace.messages.SYSTEM", "Default System Message"):
                    # Should return default message and log error
                    system_message = self.system_context.get_system_message()
                    assert system_message == "Default System Message"
                    self.mock_ui.display_error.assert_called_once()
        finally:
            system_file.unlink()

    def test_get_project_context_no_files(self) -> None:
        """Test that empty string is returned when no context files exist."""
        context = self.system_context.get_project_context()
        assert context == ""

    def test_get_project_context_with_files(self) -> None:
        """Test that context is combined from multiple files."""
        context_file1 = self.config_dir / "context1.md"
        context_file2 = self.config_dir / "context2.md"

        with context_file1.open("w") as f:
            f.write("Content of context file 1")
        with context_file2.open("w") as f:
            f.write("Content of context file 2")

        try:
            context = self.system_context.get_project_context()
            assert "Context from: context1.md" in context
            assert "Content of context file 1" in context
            assert "Context from: context2.md" in context
            assert "Content of context file 2" in context
            assert "End Context: context1.md" in context
            assert "End Context: context2.md" in context
        finally:
            context_file1.unlink()
            context_file2.unlink()

    def test_get_project_context_error_reading_file(self) -> None:
        """Test that errors reading individual context files are handled."""
        context_file1 = self.config_dir / "context1.md"
        context_file2 = self.config_dir / "context2.md"

        with context_file1.open("w") as f:
            f.write("Content of context file 1")
        with context_file2.open("w") as f:
            f.write("Content of context file 2")

        try:
            # Create a patched version of read_text that raises an error for context2.md
            # but not for context1.md
            original_read_text = Path.read_text

            def side_effect_function(
                self: pathlib.Path,
                *args,
                **kwargs,
            ):
                if str(self) == str(context_file2):
                    msg = "Cannot read context2.md"
                    raise PermissionError(msg)
                return original_read_text(self, *args, **kwargs)

            with patch(
                "pathlib.Path.read_text",
                autospec=True,
                side_effect=side_effect_function,
            ):
                context = self.system_context.get_project_context()
                assert "Context from: context1.md" in context
                assert "Content of context file 1" in context
                # context2.md content should be missing
                assert "Context from: context2.md" not in context
                self.mock_ui.display_error.assert_called_once()
        finally:
            context_file1.unlink()
            context_file2.unlink()

    def test_get_project_context_no_dir(self) -> None:
        """Test when config directory doesn't exist."""
        nonexistent_dir = Path("/nonexistent/dir")
        system_context = SystemContext(
            ui=self.mock_ui,
            config_dir=nonexistent_dir,
        )

        context = system_context.get_project_context()
        assert context == ""

    def test_get_project_context_error_listing_dir(self) -> None:
        """Test that errors listing directory are handled."""
        with patch("pathlib.Path.iterdir") as mock_iterdir:
            mock_iterdir.side_effect = PermissionError("Cannot list directory")

            context = self.system_context.get_project_context()
            assert context == ""
            self.mock_ui.display_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
