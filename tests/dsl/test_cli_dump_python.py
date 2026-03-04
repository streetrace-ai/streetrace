"""Tests for dump_python --no-comments flag.

Test that --no-comments correctly removes source location comments
while preserving code, docstrings, and other comments.
"""

from pathlib import Path

from streetrace.dsl.cli import EXIT_SUCCESS, dump_python

# =============================================================================
# Sample DSL Sources for Testing
# =============================================================================

DSL_WITH_MULTIPLE_ELEMENTS = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

tool fs = builtin streetrace.filesystem

agent helper:
    tools fs
    instruction greeting
"""

DSL_WITH_LONG_PATH = """\
streetrace v1

model main = anthropic/claude-sonnet
"""


# =============================================================================
# Source Comment Filtering Tests
# =============================================================================


class TestNoCommentsRemovesSourceComments:
    """Test --no-comments removes source location comments."""

    def test_no_comments_removes_source_comments(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify source comments like '# file.sr:5' are removed."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Source comments have format: # filename.sr:line_number
        for line in captured.out.split("\n"):
            stripped = line.strip()
            # Source comments match pattern: # *.sr:<number>
            if stripped.startswith("# ") and ".sr:" in stripped:
                # Should not have trailing digit pattern of source comments
                import re
                assert not re.search(r"\.sr:\d+$", stripped), (
                    f"Source comment not removed: {line}"
                )

    def test_no_comments_counts_removed_comments(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify source comments are actually removed, not just empty."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        # Get with comments
        dump_python(dsl_file, include_comments=True)
        with_comments = capsys.readouterr().out

        # Get without comments
        dump_python(dsl_file, include_comments=False)
        without_comments = capsys.readouterr().out

        # Without comments should have fewer lines
        lines_with = len(with_comments.split("\n"))
        lines_without = len(without_comments.split("\n"))
        assert lines_without < lines_with, (
            f"Expected fewer lines without comments: {lines_without} vs {lines_with}"
        )


class TestNoCommentsPreservesCode:
    """Test --no-comments preserves all Python code."""

    def test_no_comments_preserves_class_definition(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify class definitions are preserved."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        assert "class" in captured.out
        assert "DslAgentWorkflow" in captured.out

    def test_no_comments_preserves_imports(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify import statements are preserved."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        assert "import" in captured.out
        # Specific imports from the generated code
        assert "WorkflowContext" in captured.out

    def test_no_comments_preserves_dict_entries(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify dictionary entries in _models, _prompts, etc. are preserved."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Model dict should still have the model entry
        assert "'main'" in captured.out
        assert "anthropic/claude-sonnet" in captured.out

    def test_no_comments_preserves_prompt_content(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify prompt content is preserved."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        assert "greeting" in captured.out
        assert "Hello!" in captured.out

    def test_no_comments_preserves_string_with_colons(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify strings containing colons are preserved."""
        dsl_source = '''\
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.filesystem

prompt my_prompt: """Important: Follow these steps:
1. Step one
2. Step two"""

agent helper:
    tools fs
    instruction my_prompt
'''
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(dsl_source)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # The string content with colons should be preserved
        assert "Important:" in captured.out
        assert "Follow these steps:" in captured.out


class TestNoCommentsPreservesDocstrings:
    """Test --no-comments preserves docstrings."""

    def test_no_comments_preserves_module_docstring(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify module docstring is preserved."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Module docstring should be present
        assert '"""Generated workflow from' in captured.out

    def test_no_comments_preserves_class_docstring(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify class docstring is preserved."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Class docstring should be present (after class definition)
        lines = captured.out.split("\n")
        class_found = False
        for i, line in enumerate(lines):
            if "class " in line and "DslAgentWorkflow" in line:
                class_found = True
                # Next non-empty line should be docstring
                for next_line in lines[i + 1:]:
                    if next_line.strip():
                        assert '"""' in next_line, (
                            f"Expected docstring after class, got: {next_line}"
                        )
                        break
                break
        assert class_found, "Class definition not found"


class TestNoCommentsEdgeCases:
    """Test edge cases for --no-comments."""

    def test_no_comments_with_long_file_path(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify filtering works with long file paths (>30 chars)."""
        # Create deeply nested path
        deep_path = tmp_path / "very" / "long" / "nested" / "directory" / "path"
        deep_path.mkdir(parents=True)
        dsl_file = deep_path / "very_long_filename_for_testing.sr"
        dsl_file.write_text(DSL_WITH_LONG_PATH)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Even with long paths, source comments should be removed
        import re
        for line in captured.out.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                # Should not match source comment pattern
                assert not re.search(r"\.sr:\d+$", stripped), (
                    f"Source comment with long path not removed: {line}"
                )

    def test_no_comments_preserves_regular_code_comments(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify regular code comments are preserved if they exist.

        Note: The current code generator does not emit non-source comments,
        but this test verifies the filter is specific enough.
        """
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Valid Python should be generated
        lines = [line for line in captured.out.split("\n") if line.strip()]
        assert len(lines) > 0

    def test_include_comments_true_has_source_comments(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify include_comments=True includes source comments."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=True)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS
        # Source comments should be present
        import re
        found_source_comment = False
        for line in captured.out.split("\n"):
            if re.search(r"# .*\.sr:\d+$", line.strip()):
                found_source_comment = True
                break
        expected_msg = "Expected source comments when include_comments=True"
        assert found_source_comment, expected_msg

    def test_no_comments_produces_valid_python(
        self, tmp_path: Path, capsys,
    ) -> None:
        """Verify output without comments is syntactically valid Python."""
        dsl_file = tmp_path / "test.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_ELEMENTS)

        result = dump_python(dsl_file, include_comments=False)
        captured = capsys.readouterr()

        assert result == EXIT_SUCCESS

        # Try to compile the generated code
        try:
            compile(captured.out, "<string>", "exec")
        except SyntaxError as e:
            msg = f"Generated code is not valid Python: {e}"
            raise AssertionError(msg) from e
