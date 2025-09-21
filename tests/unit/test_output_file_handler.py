"""Tests for the OutputFileHandler class."""

from pathlib import Path
from unittest.mock import patch

import pytest

from streetrace.input_handler import HANDLED_CONT, SKIP, InputContext
from streetrace.output_file_handler import OutputFileHandler


class TestOutputFileHandler:
    """Test cases for OutputFileHandler functionality."""

    def test_init_with_output_file(self, tmp_path: Path) -> None:
        """Test OutputFileHandler initialization with output file."""
        # Arrange
        output_file = tmp_path / "test_output.txt"

        # Act
        handler = OutputFileHandler(output_file)

        # Assert
        assert handler.output_file == output_file

    def test_init_with_none_output_file(self) -> None:
        """Test OutputFileHandler initialization with None output file."""
        # Act
        handler = OutputFileHandler(None)

        # Assert
        assert handler.output_file is None

    async def test_handle_skips_when_no_output_file(self) -> None:
        """Test that handler skips when no output file is configured."""
        # Arrange
        handler = OutputFileHandler(None)
        ctx = InputContext(final_response="Some response")

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == SKIP

    async def test_handle_skips_when_no_final_response(self, tmp_path: Path) -> None:
        """Test that handler skips when no final response is available."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        ctx = InputContext(final_response=None)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == SKIP
        assert not output_file.exists()

    async def test_handle_skips_when_empty_final_response(self, tmp_path: Path) -> None:
        """Test that handler skips when final response is empty."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        ctx = InputContext(final_response="")

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == SKIP
        assert not output_file.exists()

    async def test_handle_writes_final_response_to_file(self, tmp_path: Path) -> None:
        """Test that handler writes final response to output file."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        final_response = "This is the final response from the agent."
        ctx = InputContext(final_response=final_response)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == HANDLED_CONT
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == final_response

    async def test_handle_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that handler overwrites existing output file."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        output_file.write_text("Previous content", encoding="utf-8")
        handler = OutputFileHandler(output_file)
        final_response = "New response content."
        ctx = InputContext(final_response=final_response)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == HANDLED_CONT
        assert output_file.read_text(encoding="utf-8") == final_response

    async def test_handle_writes_unicode_content(self, tmp_path: Path) -> None:
        """Test that handler properly writes unicode content."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        final_response = "Unicode content: 你好 🚗💨 café"
        ctx = InputContext(final_response=final_response)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == HANDLED_CONT
        assert output_file.read_text(encoding="utf-8") == final_response

    async def test_handle_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that handler creates parent directories if they don't exist."""
        # Arrange
        nested_dir = tmp_path / "nested" / "dir"
        output_file = nested_dir / "test_output.txt"
        handler = OutputFileHandler(output_file)
        final_response = "Content in nested directory."
        ctx = InputContext(final_response=final_response)

        # Create parent directories first (PathLib write_text doesn't create them)
        nested_dir.mkdir(parents=True, exist_ok=True)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == HANDLED_CONT
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == final_response

    async def test_handle_raises_os_error_on_write_failure(
        self, tmp_path: Path,
    ) -> None:
        """Test that handler raises OSError when file write fails."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        final_response = "Some response"
        ctx = InputContext(final_response=final_response)

        # Mock Path.write_text to raise an OSError
        with patch(
            "pathlib.Path.write_text",
            side_effect=OSError("Permission denied"),
        ) as mock_write:
            # Act & Assert
            with pytest.raises(
                OSError, match="Failed to write output file: Permission denied",
            ):
                await handler.handle(ctx)

            mock_write.assert_called_once_with(final_response, encoding="utf-8")

    async def test_handle_with_multiline_response(self, tmp_path: Path) -> None:
        """Test that handler correctly writes multiline responses."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        final_response = "Line 1\nLine 2\n\nLine 4 with unicode: 🚗💨"
        ctx = InputContext(final_response=final_response)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == HANDLED_CONT
        assert output_file.read_text(encoding="utf-8") == final_response

    async def test_handle_with_large_response(self, tmp_path: Path) -> None:
        """Test that handler can write large responses."""
        # Arrange
        output_file = tmp_path / "test_output.txt"
        handler = OutputFileHandler(output_file)
        # Create a large response (1MB)
        final_response = "A" * (1024 * 1024)
        ctx = InputContext(final_response=final_response)

        # Act
        result = await handler.handle(ctx)

        # Assert
        assert result == HANDLED_CONT
        assert output_file.read_text(encoding="utf-8") == final_response
        assert len(output_file.read_text(encoding="utf-8")) == 1024 * 1024

