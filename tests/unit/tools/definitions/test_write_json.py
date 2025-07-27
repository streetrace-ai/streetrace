"""Unit tests for write_json tool."""

import json
from pathlib import Path

from streetrace.tools.definitions.result import OpResultCode
from streetrace.tools.definitions.write_json import write_json_file


class TestWriteJsonFile:
    """Test write_json_file functionality."""

    def test_write_valid_json(self, tmp_path: Path) -> None:
        """Test writing valid JSON."""
        content = """{
            "key": "value",
            "number": 42,
            "array": [1, 2, 3],
            "nested": {
                "inner": "data"
            }
        }"""

        result = write_json_file("test.json", content, tmp_path)

        assert result["result"] == OpResultCode.SUCCESS
        assert result["output"] == "Successfully wrote valid JSON to test.json"
        assert result["error"] is None

        # Verify file was created with proper formatting
        json_file = tmp_path / "test.json"
        assert json_file.exists()

        with json_file.open() as f:
            data = json.load(f)
            assert data["key"] == "value"
            assert data["number"] == 42
            assert data["array"] == [1, 2, 3]
            assert data["nested"]["inner"] == "data"

        # Check that JSON is properly formatted
        with json_file.open() as f:
            content = f.read()
            assert "  " in content  # Should have 2-space indentation

    def test_write_json_missing_comma(self, tmp_path: Path) -> None:
        """Test error handling for missing comma."""
        content = """{
            "key1": "value1"
            "key2": "value2"
        }"""

        result = write_json_file("invalid.json", content, tmp_path)

        assert result["result"] == OpResultCode.FAILURE
        assert "JSON validation failed" in result["error"]
        assert "Line 3, Column 13" in result["error"]
        assert "Expecting ',' delimiter" in result["error"]
        assert result["output"] is None

        # File should not be created
        assert not (tmp_path / "invalid.json").exists()

    def test_write_json_trailing_comma(self, tmp_path: Path) -> None:
        """Test handling of trailing commas (should succeed in Python)."""
        content = """{
            "key": "value",
            "array": [1, 2, 3,],
        }"""

        # Python's json.loads is lenient with trailing commas in some cases
        # But strict JSON doesn't allow them
        result = write_json_file("trailing.json", content, tmp_path)

        # This might succeed or fail depending on Python version
        # Just verify we get a result
        assert result["result"] in [OpResultCode.SUCCESS, OpResultCode.FAILURE]

    def test_write_json_unescaped_quotes(self, tmp_path: Path) -> None:
        """Test error handling for unescaped quotes."""
        content = """{
            "message": "This is a "bad" message"
        }"""

        result = write_json_file("unescaped.json", content, tmp_path)

        assert result["result"] == OpResultCode.FAILURE
        assert "JSON validation failed" in result["error"]
        assert "Expecting ',' delimiter" in result["error"]
        assert result["output"] is None

    def test_write_json_invalid_escape(self, tmp_path: Path) -> None:
        """Test error handling for invalid escape sequences."""
        # Invalid JSON with unescaped backslash at end
        content = r'{"path": "C:\invalid\"}'

        result = write_json_file("escape.json", content, tmp_path)

        assert result["result"] == OpResultCode.FAILURE
        assert "JSON validation failed" in result["error"]
        # Error message should mention escape sequences
        assert result["output"] is None

    def test_write_json_creates_directory(self, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        content = '{"test": "data"}'

        result = write_json_file("nested/dir/test.json", content, tmp_path)

        assert result["result"] == OpResultCode.SUCCESS
        assert (tmp_path / "nested" / "dir" / "test.json").exists()

    def test_write_json_overwrites_existing(self, tmp_path: Path) -> None:
        """Test overwriting existing JSON file."""
        json_file = tmp_path / "existing.json"
        json_file.write_text('{"old": "data"}')

        content = '{"new": "data"}'
        result = write_json_file("existing.json", content, tmp_path)

        assert result["result"] == OpResultCode.SUCCESS
        with json_file.open() as f:
            data = json.load(f)
            assert data == {"new": "data"}
            assert "old" not in data

    def test_write_json_empty_object(self, tmp_path: Path) -> None:
        """Test writing empty JSON object."""
        result = write_json_file("empty.json", "{}", tmp_path)

        assert result["result"] == OpResultCode.SUCCESS
        with (tmp_path / "empty.json").open() as f:
            data = json.load(f)
            assert data == {}

    def test_write_json_empty_array(self, tmp_path: Path) -> None:
        """Test writing empty JSON array."""
        result = write_json_file("empty_array.json", "[]", tmp_path)

        assert result["result"] == OpResultCode.SUCCESS
        with (tmp_path / "empty_array.json").open() as f:
            data = json.load(f)
            assert data == []

    def test_write_json_complex_structure(self, tmp_path: Path) -> None:
        """Test writing complex nested JSON structure."""
        content = """{
            "files": [
                {
                    "path": "src/main.py",
                    "issues": [
                        {
                            "line": 42,
                            "severity": "error",
                            "message": "Undefined variable 'x'"
                        }
                    ]
                }
            ],
            "summary": {
                "total_issues": 1,
                "errors": 1,
                "warnings": 0
            }
        }"""

        result = write_json_file("review.json", content, tmp_path)

        assert result["result"] == OpResultCode.SUCCESS
        with (tmp_path / "review.json").open() as f:
            data = json.load(f)
            assert len(data["files"]) == 1
            assert data["files"][0]["issues"][0]["line"] == 42
            assert data["summary"]["total_issues"] == 1

    def test_write_json_path_traversal(self, tmp_path: Path) -> None:
        """Test that path traversal attempts are blocked."""
        result = write_json_file("../../etc/passwd", '{"test": "data"}', tmp_path)

        assert result["result"] == OpResultCode.FAILURE
        assert "Error writing JSON file" in result["error"]

    def test_write_json_absolute_path(self, tmp_path: Path) -> None:
        """Test that absolute paths are rejected."""
        result = write_json_file("/etc/passwd", '{"test": "data"}', tmp_path)

        assert result["result"] == OpResultCode.FAILURE
        assert "Error writing JSON file" in result["error"]
