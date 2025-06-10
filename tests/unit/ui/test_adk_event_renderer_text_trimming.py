"""Test text trimming functionality in ADK event renderer.

This module tests the _trim_text helper function which is responsible for
truncating long text content to fit display constraints while preserving
readability and providing clear indicators when content has been trimmed.
"""

from streetrace.ui.adk_event_renderer import _trim_text


class TestTextTrimming:
    """Test the _trim_text utility function."""

    def test_trim_text_with_short_text(self):
        """Test that short text is returned unchanged."""
        text = "Short text"
        result = _trim_text(text)
        assert result == "Short text"

    def test_trim_text_with_empty_string(self):
        """Test that empty string is handled correctly."""
        result = _trim_text("")
        assert result == ""

    def test_trim_text_with_none_like_empty(self):
        """Test that falsy text values are handled correctly."""
        result = _trim_text("   ")  # Whitespace only, becomes empty after strip
        assert result == ""

    def test_trim_text_with_long_single_line(self):
        """Test that long single lines are truncated with ellipsis."""
        long_text = "a" * 250  # Exceeds default max_length of 200
        result = _trim_text(long_text)

        assert len(result) == 200  # max_length - 3 + 3 (for "...")
        assert result.endswith("...")
        assert result.startswith("a" * 197)  # 200 - 3 characters + ...

    def test_trim_text_with_custom_max_length(self):
        """Test text trimming with custom maximum length."""
        text = "a" * 100
        result = _trim_text(text, max_length=50)

        assert len(result) == 50
        assert result.endswith("...")
        assert result == "a" * 47 + "..."

    def test_trim_text_with_multiple_lines_within_limit(self):
        """Test that multiple lines within limit are preserved."""
        text = "Line 1\nLine 2\nLine 3"
        result = _trim_text(text, max_lines=5)

        assert result == "Line 1\nLine 2\nLine 3"

    def test_trim_text_with_multiple_lines_exceeding_limit(self):
        """Test that excess lines are trimmed with indicator."""
        lines = [f"Line {i}" for i in range(1, 6)]  # 5 lines
        text = "\n".join(lines)
        result = _trim_text(text, max_lines=3)

        expected_lines = [
            "Line 1",
            "Line 2",
            "(3 lines trimmed)...",
        ]
        assert result == "\n".join(expected_lines)

    def test_trim_text_with_single_line_limit(self):
        """Test default behavior with single line limit."""
        text = "Line 1\nLine 2\nLine 3\nLine 4"
        result = _trim_text(text, max_lines=1)

        # With 4 lines and max_lines=1, we keep 0 lines and trim 4
        assert result == "(4 lines trimmed)..."

    def test_trim_text_with_long_lines_and_multiple_lines(self):
        """Test combination of line and length trimming."""
        long_line_1 = "a" * 250
        long_line_2 = "b" * 250
        text = f"{long_line_1}\n{long_line_2}\nLine 3"

        result = _trim_text(text, max_length=100, max_lines=2)

        lines = result.split("\n")
        # Should have first line (trimmed for length) + trimming message
        # The trimming message includes a newline prefix, so split creates empty string
        assert len(lines) == 2  # First line, empty line from \n prefix, trim message
        assert lines[0] == "a" * 97 + "..."  # First line trimmed for length
        assert lines[1] == "(2 lines trimmed)..."

    def test_trim_text_preserves_whitespace_structure(self):
        """Test that internal whitespace structure is preserved."""
        text = "  Indented line\n    More indented"
        result = _trim_text(text, max_lines=3)

        # Text is stripped first, so leading spaces in first line are removed
        assert result == "Indented line\n    More indented"

    def test_trim_text_strips_leading_trailing_whitespace(self):
        """Test that leading and trailing whitespace is stripped."""
        text = "  \n  Content line  \n  "
        result = _trim_text(text, max_lines=3)

        # After stripping, we get just the content line with its internal spaces
        assert result == "Content line"

    def test_trim_text_with_zero_max_lines(self):
        """Test edge case with zero max lines."""
        text = "Line 1\nLine 2"
        result = _trim_text(text, max_lines=0)

        assert result == ""

    def test_trim_text_with_exact_length_match(self):
        """Test text that exactly matches the maximum length."""
        text = "a" * 197  # Exactly max_length - 3
        result = _trim_text(text, max_length=200)

        assert result == text  # Should not be trimmed since it fits

    def test_trim_text_with_newline_only_lines(self):
        """Test handling of lines that contain only newlines."""
        text = "Line 1\n\n\nLine 4"
        result = _trim_text(text, max_lines=5)

        assert result == "Line 1\n\n\nLine 4"  # Empty lines preserved

    def test_trim_text_with_unicode_characters(self):
        """Test trimming with unicode characters."""
        unicode_text = "🚗💨" * 100  # Unicode characters
        result = _trim_text(unicode_text, max_length=50)

        assert len(result) == 50
        assert result.endswith("...")

    def test_trim_text_with_mixed_line_lengths(self):
        """Test trimming with lines of varying lengths."""
        lines = [
            "Short line",
            "a" * 250,  # Very long line
            "Another short line",
        ]
        text = "\n".join(lines)
        result = _trim_text(text, max_length=100, max_lines=5)

        result_lines = result.split("\n")
        assert result_lines[0] == "Short line"
        assert result_lines[1].endswith("...")  # Long line trimmed
        assert len(result_lines[1]) == 100
        assert result_lines[2] == "Another short line"
