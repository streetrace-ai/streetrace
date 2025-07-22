"""Tests for enhanced write_file and append_to_file functionality."""

import tempfile
from pathlib import Path

import pytest

from streetrace.tools.fs_tool import write_file, append_to_file
from streetrace.tools.definitions.result import OpResultCode


class TestWriteFileEnhanced:
    """Test enhanced write_file functionality with empty content handling."""

    def test_write_file_with_content(self, work_dir: Path) -> None:
        """Test write_file with normal content."""
        test_file = "test_normal.py"
        content = "print('Hello, World!')"
        
        result = write_file(test_file, work_dir, content)
        
        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None
        assert result.get("output") is None  # No guidance needed for normal content
        
        # Verify file was created with correct content
        file_path = work_dir / test_file
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_write_file_with_empty_content_default(self, work_dir: Path) -> None:
        """Test write_file with default empty content parameter."""
        test_file = "test_empty_default.js"
        
        result = write_file(test_file, work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None
        
        # Should provide guidance for empty content
        guidance = result.get("output", "")
        assert "Empty file created" in guidance
        assert "append_to_file" in guidance
        assert "6000 tokens" in guidance
        assert "4500 words" in guidance
        assert "multiple smaller" in guidance
        
        # Verify empty file was created
        file_path = work_dir / test_file
        assert file_path.exists()
        assert file_path.read_text() == ""

    def test_write_file_with_explicit_empty_content(self, work_dir: Path) -> None:
        """Test write_file with explicitly empty content string."""
        test_file = "test_empty_explicit.css"
        
        result = write_file(test_file, work_dir, "")
        
        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None
        
        # Should provide guidance for empty content
        guidance = result.get("output", "")
        assert "Empty file created" in guidance
        assert "append_to_file" in guidance
        
        # Verify empty file was created
        file_path = work_dir / test_file
        assert file_path.exists()
        assert file_path.read_text() == ""

    def test_write_file_creates_directories(self, work_dir: Path) -> None:
        """Test write_file creates parent directories when needed."""
        test_file = "nested/dir/test.txt"
        
        result = write_file(test_file, work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        
        # Verify nested directories and file were created
        file_path = work_dir / test_file
        assert file_path.exists()
        assert file_path.parent.exists()

    def test_write_file_python_syntax_validation(self, work_dir: Path) -> None:
        """Test write_file validates Python syntax."""
        test_file = "invalid.py"
        invalid_content = "def invalid_python(\n    missing_closing_paren"
        
        result = write_file(test_file, work_dir, invalid_content)
        
        assert result["result"] == OpResultCode.FAILURE
        assert "not a valid python script" in result["error"]

    def test_write_file_overwrites_existing(self, work_dir: Path) -> None:
        """Test write_file overwrites existing files."""
        test_file = "overwrite_test.txt"
        file_path = work_dir / test_file
        
        # Create initial file
        file_path.write_text("original content")
        
        # Overwrite with new content
        new_content = "new content"
        result = write_file(test_file, work_dir, new_content)
        
        assert result["result"] == OpResultCode.SUCCESS
        assert file_path.read_text() == new_content


class TestAppendToFile:
    """Test append_to_file functionality."""

    def test_append_to_existing_file(self, work_dir: Path) -> None:
        """Test appending content to an existing file."""
        test_file = "existing.txt"
        file_path = work_dir / test_file
        
        # Create initial file
        initial_content = "First line\n"
        file_path.write_text(initial_content)
        
        # Append new content
        append_content = "Second line\n"
        result = append_to_file(test_file, append_content, work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None
        assert result.get("output") is None
        
        # Verify content was appended
        final_content = file_path.read_text()
        assert final_content == initial_content + append_content

    def test_append_to_nonexistent_file(self, work_dir: Path) -> None:
        """Test appending to a file that doesn't exist creates it."""
        test_file = "new_file.txt"
        content = "New file content\n"
        
        result = append_to_file(test_file, content, work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None
        
        # Verify file was created with content
        file_path = work_dir / test_file
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_append_multiple_chunks(self, work_dir: Path) -> None:
        """Test appending multiple chunks to build a file incrementally."""
        test_file = "incremental.js"
        
        # Start with empty file using write_file
        write_result = write_file(test_file, work_dir)
        assert write_result["result"] == OpResultCode.SUCCESS
        
        # Append chunks one by one
        chunks = [
            "// JavaScript file header\n",
            "function hello() {\n",
            "    console.log('Hello, World!');\n",
            "}\n"
        ]
        
        for chunk in chunks:
            result = append_to_file(test_file, chunk, work_dir)
            assert result["result"] == OpResultCode.SUCCESS
        
        # Verify final content
        file_path = work_dir / test_file
        expected_content = "".join(chunks)
        assert file_path.read_text() == expected_content

    def test_append_creates_parent_directories(self, work_dir: Path) -> None:
        """Test append_to_file creates parent directories."""
        test_file = "deep/nested/path/append_test.txt"
        content = "Content in nested file\n"
        
        result = append_to_file(test_file, content, work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        
        # Verify nested directories and file were created
        file_path = work_dir / test_file
        assert file_path.exists()
        assert file_path.parent.exists()
        assert file_path.read_text() == content

    def test_append_empty_content(self, work_dir: Path) -> None:
        """Test appending empty content doesn't change file."""
        test_file = "empty_append.txt"
        initial_content = "Initial content"
        file_path = work_dir / test_file
        file_path.write_text(initial_content)
        
        result = append_to_file(test_file, "", work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        assert file_path.read_text() == initial_content

    def test_append_preserves_encoding(self, work_dir: Path) -> None:
        """Test append_to_file preserves UTF-8 encoding."""
        test_file = "unicode_test.txt"
        unicode_content = "Hello 世界! 🚗💨\n"
        
        result = append_to_file(test_file, unicode_content, work_dir)
        
        assert result["result"] == OpResultCode.SUCCESS
        
        # Verify Unicode content is preserved
        file_path = work_dir / test_file
        assert file_path.read_text(encoding="utf-8") == unicode_content


class TestWriteFileAppendFileIntegration:
    """Test integration between write_file and append_to_file."""

    def test_empty_file_then_append_workflow(self, work_dir: Path) -> None:
        """Test the complete workflow: empty file creation + chunked appending."""
        test_file = "large_project.js"
        
        # Step 1: Create empty file (simulating token limit hit)
        write_result = write_file(test_file, work_dir)
        assert write_result["result"] == OpResultCode.SUCCESS
        
        guidance = write_result.get("output", "")
        assert "append_to_file" in guidance
        
        # Step 2: Build file in chunks (simulating recovery)
        chunks = [
            "/**\n * Large JavaScript Project\n */\n\n",
            "class GameEngine {\n",
            "    constructor() {\n",
            "        this.initialized = false;\n",
            "    }\n",
            "}\n\n",
            "// Export the class\n",
            "export default GameEngine;\n"
        ]
        
        for chunk in chunks:
            append_result = append_to_file(test_file, chunk, work_dir)
            assert append_result["result"] == OpResultCode.SUCCESS
        
        # Step 3: Verify final file is complete
        file_path = work_dir / test_file
        final_content = file_path.read_text()
        expected_content = "".join(chunks)
        assert final_content == expected_content
        assert "Large JavaScript Project" in final_content
        assert "GameEngine" in final_content

    def test_guidance_message_accuracy(self, work_dir: Path) -> None:
        """Test that guidance message provides accurate information."""
        test_file = "guidance_test.css"
        
        result = write_file(test_file, work_dir)
        
        guidance = result.get("output", "")
        
        # Check all expected guidance elements
        assert f"Empty file created at '{test_file}'" in guidance
        assert "append_to_file" in guidance
        assert "manageable chunks" in guidance
        assert "6000 tokens" in guidance
        assert "4500 words" in guidance
        assert "output limits" in guidance
        assert "multiple smaller" in guidance

    def test_file_path_sanitization(self, work_dir: Path) -> None:
        """Test that file paths are properly sanitized."""
        # Test with path containing whitespace and quotes
        test_file = '  "spaced file.txt"  '
        content = "test content"
        
        result = write_file(test_file, work_dir, content)
        
        assert result["result"] == OpResultCode.SUCCESS
        
        # File should be created with sanitized name
        expected_files = list(work_dir.glob("*spaced file.txt*"))
        assert len(expected_files) >= 1


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_write_file_invalid_path(self, work_dir: Path) -> None:
        """Test write_file with invalid path characters."""
        # This test depends on the path validation implementation
        # The exact behavior may vary based on the OS and validation rules
        pass  # Placeholder for platform-specific path validation tests

    def test_append_file_permission_error(self, work_dir: Path) -> None:
        """Test append_to_file handles permission errors gracefully."""
        # This would require setting up a read-only directory
        # Implementation depends on the specific error handling in append_to_file
        pass  # Placeholder for permission-based error tests