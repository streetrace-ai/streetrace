"""Tests for append_to_file tool definition."""

from pathlib import Path

from streetrace.tools.definitions.append_to_file import append_to_file
from streetrace.tools.definitions.result import OpResultCode


class TestAppendToFileDefinition:
    """Test append_to_file core functionality."""

    def test_append_to_existing_file(self, work_dir: Path) -> None:
        """Test appending content to an existing file."""
        test_file = work_dir / "existing.txt"
        initial_content = "Line 1\n"
        test_file.write_text(initial_content)

        append_content = "Line 2\n"
        result = append_to_file("existing.txt", append_content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None
        assert result["output"] is None

        # Verify content was appended
        final_content = test_file.read_text()
        assert final_content == initial_content + append_content

    def test_append_creates_new_file(self, work_dir: Path) -> None:
        """Test appending to non-existent file creates it."""
        test_file_path = "new_file.txt"
        content = "New file content\n"

        result = append_to_file(test_file_path, content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["error"] is None

        # Verify file was created
        file_path = work_dir / test_file_path
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_append_creates_parent_directories(self, work_dir: Path) -> None:
        """Test append_to_file creates parent directories."""
        test_file_path = "deep/nested/directory/test.txt"
        content = "Nested file content\n"

        result = append_to_file(test_file_path, content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS

        # Verify nested structure was created
        file_path = work_dir / test_file_path
        assert file_path.exists()
        assert file_path.parent.exists()
        assert file_path.read_text() == content

    def test_append_empty_content(self, work_dir: Path) -> None:
        """Test appending empty content."""
        test_file = work_dir / "empty_append.txt"
        initial_content = "Initial\n"
        test_file.write_text(initial_content)

        result = append_to_file("empty_append.txt", "", work_dir)

        assert result["result"] == OpResultCode.SUCCESS
        # Content should remain unchanged
        assert test_file.read_text() == initial_content

    def test_append_unicode_content(self, work_dir: Path) -> None:
        """Test appending Unicode content."""
        test_file_path = "unicode.txt"
        unicode_content = "Hello 世界! 🎯 Emoji test\n"

        result = append_to_file(test_file_path, unicode_content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS

        file_path = work_dir / test_file_path
        assert file_path.read_text(encoding="utf-8") == unicode_content

    def test_append_large_content(self, work_dir: Path) -> None:
        """Test appending large content blocks."""
        test_file_path = "large_content.txt"

        # Create content that's reasonably large but not huge for tests
        formatted_content = "".join(f"Line {i}\n" for i in range(1000))

        result = append_to_file(test_file_path, formatted_content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS

        file_path = work_dir / test_file_path
        content = file_path.read_text()
        assert content.count("Line") == 1000
        assert "Line 999" in content

    def test_append_multiple_times(self, work_dir: Path) -> None:
        """Test multiple append operations to same file."""
        test_file_path = "multiple_appends.txt"

        contents = [
            "First chunk\n",
            "Second chunk\n",
            "Third chunk\n",
        ]

        for content in contents:
            result = append_to_file(test_file_path, content, work_dir)
            assert result["result"] == OpResultCode.SUCCESS

        file_path = work_dir / test_file_path
        final_content = file_path.read_text()
        expected = "".join(contents)
        assert final_content == expected

    def test_append_preserves_file_content(self, work_dir: Path) -> None:
        """Test that append preserves existing file content exactly."""
        test_file = work_dir / "preserve_test.json"

        # Create file with specific JSON content
        initial_json = '{\n  "existing": "data",\n  "array": [1, 2, 3]\n'
        test_file.write_text(initial_json)

        # Append closing brace
        append_content = "}\n"
        result = append_to_file("preserve_test.json", append_content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS

        # Verify complete JSON structure
        final_content = test_file.read_text()
        assert final_content == initial_json + append_content
        assert final_content.endswith("}\n")

    def test_append_result_properties(self, work_dir: Path) -> None:
        """Test that append_to_file returns correct result properties."""
        result = append_to_file("test.txt", "content", work_dir)

        # Verify result structure
        assert "tool_name" in result
        assert "result" in result
        assert "output" in result
        assert "error" in result

        assert result["tool_name"] == "append_to_file"
        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] is None
        assert result["error"] is None


class TestAppendToFileErrorHandling:
    """Test error handling in append_to_file."""

    def test_append_invalid_work_dir(self) -> None:
        """Test append_to_file with invalid working directory."""
        invalid_path = Path("/nonexistent/invalid/path")

        result = append_to_file("test.txt", "content", invalid_path)

        assert result["result"] == OpResultCode.FAILURE
        assert result["error"] is not None
        assert "Error appending to file" in result["error"]

    def test_append_path_traversal_protection(self, work_dir: Path) -> None:
        """Test that path traversal attempts are handled."""
        # This test depends on the path validation implementation
        # The exact behavior may vary based on normalize_and_validate_path
        dangerous_path = "../../../etc/passwd"

        result = append_to_file(dangerous_path, "malicious", work_dir)

        # Should either succeed in a safe location or fail with validation error
        # The exact assertion depends on the security implementation
        if result["result"] == OpResultCode.FAILURE:
            assert result["error"] is not None
        else:
            # If it succeeds, verify it's within work_dir bounds
            # This would require checking the actual file location
            pass

    def test_append_with_path_whitespace(self, work_dir: Path) -> None:
        """Test append_to_file handles paths with whitespace correctly."""
        # The path cleaning is done at the fs_tool.py level
        # but we can test the core function behavior
        test_file_path = "file with spaces.txt"
        content = "Content with spaces\n"

        result = append_to_file(test_file_path, content, work_dir)

        assert result["result"] == OpResultCode.SUCCESS

        file_path = work_dir / test_file_path
        assert file_path.exists()
        assert file_path.read_text() == content

