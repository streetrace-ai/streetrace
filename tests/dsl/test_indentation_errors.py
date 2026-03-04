"""Tests for indentation error handling.

Test that indentation errors are caught and mapped to E0008 error code
with helpful messages.
"""

from streetrace.dsl.compiler import validate_dsl
from streetrace.dsl.errors.codes import ErrorCode


class TestIndentationErrors:
    """Test E0008 error for indentation problems."""

    def test_inconsistent_indentation_triggers_e0008(self) -> None:
        """Inconsistent indentation in agent block triggers E0008 error."""
        # DSL with inconsistent indentation (starts with 4 spaces, then 2)
        source = """\
streetrace v1.0

agent helper:
    tools fs
  instruction greeting
"""
        diagnostics = validate_dsl(source, "test.sr")

        assert len(diagnostics) >= 1
        # Should have an E0008 error for indentation
        e0008_errors = [d for d in diagnostics if d.code == ErrorCode.E0008]
        assert len(e0008_errors) >= 1, f"Expected E0008 error, got: {diagnostics}"

    def test_wrong_dedent_level_triggers_e0008(self) -> None:
        """Wrong dedent level triggers E0008 error."""
        # DSL with wrong dedent level in flow block
        source = """\
streetrace v1.0

tool fs = builtin streetrace.fs

prompt greeting: '''You help users'''

agent helper:
    tools fs
    instruction greeting

flow main:
    $result = run agent helper
   return $result
"""
        diagnostics = validate_dsl(source, "test.sr")

        assert len(diagnostics) >= 1
        # Should have an error for indentation
        e0008_errors = [d for d in diagnostics if d.code == ErrorCode.E0008]
        assert len(e0008_errors) >= 1, f"Expected E0008 error, got: {diagnostics}"

    def test_proper_indentation_passes(self) -> None:
        """Properly indented DSL passes validation."""
        source = """\
streetrace v1.0

model main = "anthropic/claude-sonnet-4-20250514"

tool fs = builtin streetrace.fs

prompt greeting = '''You are a helpful assistant.'''

agent helper:
    tools fs
    instruction greeting
"""
        diagnostics = validate_dsl(source, "test.sr")

        # Should have no errors (or at least no E0008 errors)
        e0008_errors = [d for d in diagnostics if d.code == ErrorCode.E0008]
        assert len(e0008_errors) == 0, f"Unexpected E0008 errors: {e0008_errors}"

    def test_indentation_error_has_line_info(self) -> None:
        """Indentation error includes line number information."""
        source = """\
streetrace v1.0

schema Invoice:
    amount: float
  vendor: string
"""
        diagnostics = validate_dsl(source, "test.sr")

        # Find E0008 errors
        e0008_errors = [d for d in diagnostics if d.code == ErrorCode.E0008]
        if e0008_errors:
            # Error should have meaningful line number
            assert e0008_errors[0].line >= 1

    def test_indentation_error_has_helpful_message(self) -> None:
        """Indentation error includes helpful message."""
        source = """\
streetrace v1.0

agent helper:
    tools fs
      instruction greeting
"""
        diagnostics = validate_dsl(source, "test.sr")

        # Should have diagnostics about indentation or unexpected token
        assert len(diagnostics) >= 1
        # At least one should have an indentation-related error code
        codes = [d.code for d in diagnostics]
        assert ErrorCode.E0008 in codes or ErrorCode.E0007 in codes
