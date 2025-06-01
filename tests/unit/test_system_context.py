"""Tests for the SystemContext class."""

import pathlib
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from streetrace.system_context import SystemContext
from streetrace.ui.ui_bus import UiBus


@pytest.fixture(scope="class")
def temp_dirs(request):
    """Set up temporary directories once for all tests in the class."""
    base_temp_dir = Path(
        tempfile.mkdtemp(prefix="streetrace_test_system_context_"),
    )
    config_dir = base_temp_dir / ".streetrace"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Set attributes on the test class
    request.cls.base_temp_dir = base_temp_dir
    request.cls.config_dir = config_dir

    yield

    # Clean up after all tests
    if base_temp_dir.exists():
        shutil.rmtree(base_temp_dir)


@pytest.mark.usefixtures("temp_dirs")
class TestSystemContext:
    """Test the SystemContext class."""

    @pytest.fixture(autouse=True)
    def setup_system_context(self):
        """Instantiate SystemContext for each test."""
        # Mock the UI to avoid console output during tests
        self.mock_ui = MagicMock(spec=UiBus)
        self.system_context = SystemContext(
            ui_bus=self.mock_ui,
            context_dir=self.config_dir,
        )

    def test_get_system_message_default(self):
        """Test that default system message is returned when no system.md exists."""
        with patch("streetrace.messages.SYSTEM", "Default System Message"):
            system_message = self.system_context.get_system_message()
            assert system_message == "Default System Message"

    def test_get_system_message_custom(self):
        """Test that custom system message is read from file."""
        system_file = self.config_dir / "system.md"
        custom_message = "Custom System Message"
        with system_file.open("w") as f:
            f.write(custom_message)

        try:
            system_message = self.system_context.get_system_message()
            assert system_message == custom_message
        finally:
            if system_file.exists():
                system_file.unlink()

    def test_get_system_message_error(self):
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
                    self.mock_ui.dispatch_ui_update.assert_called_once()
        finally:
            if system_file.exists():
                system_file.unlink()

    def test_get_project_context_no_files(self):
        """Test that empty string is returned when no context files exist."""
        context = self.system_context.get_project_context()
        assert context == []

    def test_get_project_context_with_files(self):
        """Test that context is combined from multiple files."""
        context_file1 = self.config_dir / "context1.md"
        context_file2 = self.config_dir / "context2.md"

        with context_file1.open("w") as f:
            f.write("Content of context file 1")
        with context_file2.open("w") as f:
            f.write("Content of context file 2")

        try:
            context = self.system_context.get_project_context()
            assert len(context) == 2
            assert "Content of context file 1" in context
            assert "Content of context file 2" in context
        finally:
            if context_file1.exists():
                context_file1.unlink()
            if context_file2.exists():
                context_file2.unlink()

    def test_get_project_context_error_reading_file(self):
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
                assert len(context) == 1
                assert "Content of context file 1" in context[0]
                self.mock_ui.dispatch_ui_update.assert_called()
        finally:
            if context_file1.exists():
                context_file1.unlink()
            if context_file2.exists():
                context_file2.unlink()

    def test_get_project_context_no_dir(self):
        """Test when config directory doesn't exist."""
        nonexistent_dir = Path("/nonexistent/dir")
        system_context = SystemContext(
            ui_bus=self.mock_ui,
            context_dir=nonexistent_dir,
        )

        context = system_context.get_project_context()
        assert context == []

    def test_get_project_context_error_listing_dir(self):
        """Test that errors listing directory are handled."""
        with patch("pathlib.Path.iterdir") as mock_iterdir:
            mock_iterdir.side_effect = PermissionError("Cannot list directory")

            context = self.system_context.get_project_context()
            assert context == []
            self.mock_ui.dispatch_ui_update.assert_called_once()
