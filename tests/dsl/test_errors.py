"""Tests for DSL error codes, diagnostics, and reporter.

Test error code definitions, diagnostic message building, and
rustc-style error formatting.
"""

import json

from streetrace.dsl.errors.codes import ErrorCode, format_error_message
from streetrace.dsl.errors.diagnostics import Diagnostic, Severity
from streetrace.dsl.errors.reporter import (
    DiagnosticReporter,
    format_success_message,
)

# =============================================================================
# ErrorCode Tests
# =============================================================================


class TestErrorCode:
    """Test ErrorCode enumeration."""

    def test_error_codes_are_strings(self) -> None:
        """Error codes are string values."""
        assert ErrorCode.E0001.value == "E0001"
        assert ErrorCode.E0010.value == "E0010"

    def test_error_codes_have_categories(self) -> None:
        """Error codes have category property."""
        assert ErrorCode.E0001.category == "reference"
        assert ErrorCode.E0002.category == "reference"
        assert ErrorCode.E0004.category == "type"
        assert ErrorCode.E0005.category == "import"
        assert ErrorCode.E0007.category == "syntax"
        assert ErrorCode.E0009.category == "semantic"

    def test_all_error_codes_defined(self) -> None:
        """All expected error codes are defined."""
        expected_codes = [
            "E0001", "E0002", "E0003", "E0004", "E0005",
            "E0006", "E0007", "E0008", "E0009", "E0010",
        ]
        for code in expected_codes:
            assert code in [e.value for e in ErrorCode]


class TestFormatErrorMessage:
    """Test error message formatting."""

    def test_format_undefined_reference(self) -> None:
        """Format undefined reference error."""
        msg = format_error_message(
            ErrorCode.E0001,
            kind="model",
            name="fast",
        )
        assert "model" in msg
        assert "fast" in msg

    def test_format_variable_before_definition(self) -> None:
        """Format variable used before definition error."""
        msg = format_error_message(
            ErrorCode.E0002,
            name="result",
        )
        assert "$result" in msg

    def test_format_missing_parameter_gracefully(self) -> None:
        """Handle missing parameters gracefully."""
        msg = format_error_message(ErrorCode.E0001)
        # Should return template even with missing params
        assert "undefined" in msg


# =============================================================================
# Diagnostic Tests
# =============================================================================


class TestDiagnostic:
    """Test Diagnostic class."""

    def test_create_error_diagnostic(self) -> None:
        """Create an error diagnostic."""
        diag = Diagnostic.error(
            message="undefined reference to model 'fast'",
            file="my_agent.sr",
            line=15,
            column=17,
            code=ErrorCode.E0001,
        )
        assert diag.severity == Severity.ERROR
        assert diag.message == "undefined reference to model 'fast'"
        assert diag.file == "my_agent.sr"
        assert diag.line == 15
        assert diag.column == 17
        assert diag.code == ErrorCode.E0001

    def test_create_warning_diagnostic(self) -> None:
        """Create a warning diagnostic."""
        diag = Diagnostic.warning(
            message="unused variable",
            file="test.sr",
            line=10,
            column=4,
        )
        assert diag.severity == Severity.WARNING

    def test_create_note_diagnostic(self) -> None:
        """Create a note diagnostic."""
        diag = Diagnostic.note(
            message="defined here",
            file="test.sr",
            line=5,
            column=0,
        )
        assert diag.severity == Severity.NOTE

    def test_add_help_text(self) -> None:
        """Add help text to diagnostic."""
        diag = Diagnostic.error(
            message="undefined reference",
            file="test.sr",
            line=1,
            column=0,
        ).with_help("defined models are: main, compact")

        assert diag.help_text == "defined models are: main, compact"

    def test_add_related_note(self) -> None:
        """Add related note to diagnostic."""
        diag = Diagnostic.error(
            message="undefined reference",
            file="test.sr",
            line=10,
            column=0,
        ).with_note(
            message="model defined here",
            file="test.sr",
            line=5,
            column=0,
        )

        assert len(diag.related) == 1
        assert diag.related[0].severity == Severity.NOTE

    def test_span_length_calculation(self) -> None:
        """Calculate span length from columns."""
        diag = Diagnostic.error(
            message="error",
            file="test.sr",
            line=1,
            column=10,
            end_line=1,
            end_column=15,
        )
        assert diag.span_length == 5

    def test_span_length_default(self) -> None:
        """Default span length is 1."""
        diag = Diagnostic.error(
            message="error",
            file="test.sr",
            line=1,
            column=0,
        )
        assert diag.span_length == 1

    def test_to_dict(self) -> None:
        """Convert diagnostic to dictionary."""
        diag = Diagnostic.error(
            message="test error",
            file="test.sr",
            line=5,
            column=10,
            code=ErrorCode.E0001,
            help_text="help text",
        )
        d = diag.to_dict()

        assert d["severity"] == "error"
        assert d["message"] == "test error"
        assert d["location"]["file"] == "test.sr"
        assert d["location"]["line"] == 5
        assert d["location"]["column"] == 10
        assert d["code"] == "E0001"
        assert d["help"] == "help text"


class TestSeverity:
    """Test Severity enumeration."""

    def test_severity_values(self) -> None:
        """Severity values are lowercase strings."""
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.NOTE.value == "note"


# =============================================================================
# DiagnosticReporter Tests
# =============================================================================


class TestDiagnosticReporter:
    """Test DiagnosticReporter class."""

    def test_format_single_error(self) -> None:
        """Format a single error diagnostic."""
        reporter = DiagnosticReporter()
        reporter.add_source("test.sr", '    using model "fast"\n')

        diag = Diagnostic.error(
            message="undefined reference to model 'fast'",
            file="test.sr",
            line=1,
            column=17,
            code=ErrorCode.E0001,
            end_column=21,
        )

        output = reporter.format_diagnostic(diag)

        # Check header
        assert "error[E0001]:" in output
        assert "undefined reference to model 'fast'" in output

        # Check location
        assert "--> test.sr:1:18" in output  # Column is 1-indexed in display

        # Check source context
        assert 'using model "fast"' in output

    def test_format_error_with_help(self) -> None:
        """Format error with help text."""
        reporter = DiagnosticReporter()
        reporter.add_source("test.sr", "code\n")

        diag = Diagnostic.error(
            message="test error",
            file="test.sr",
            line=1,
            column=0,
            help_text="try this instead",
        )

        output = reporter.format_diagnostic(diag)
        assert "= help: try this instead" in output

    def test_format_error_without_source(self) -> None:
        """Format error when source is not available."""
        reporter = DiagnosticReporter()

        diag = Diagnostic.error(
            message="test error",
            file="test.sr",
            line=1,
            column=0,
        )

        output = reporter.format_diagnostic(diag)
        assert "error:" in output
        assert "test.sr" in output

    def test_format_multiple_diagnostics(self) -> None:
        """Format multiple diagnostics with summary."""
        reporter = DiagnosticReporter()

        diagnostics = [
            Diagnostic.error(
                message="error 1",
                file="test.sr",
                line=1,
                column=0,
            ),
            Diagnostic.error(
                message="error 2",
                file="test.sr",
                line=2,
                column=0,
            ),
        ]

        output = reporter.format_diagnostics(diagnostics)

        assert "error 1" in output
        assert "error 2" in output
        assert "2 errors" in output

    def test_format_json_output(self) -> None:
        """Format diagnostics as JSON."""
        reporter = DiagnosticReporter()

        diagnostics = [
            Diagnostic.error(
                message="test error",
                file="test.sr",
                line=1,
                column=0,
                code=ErrorCode.E0001,
            ),
        ]

        output = reporter.format_json(diagnostics, "test.sr")
        data = json.loads(output)

        assert data["version"] == "1.0"
        assert data["file"] == "test.sr"
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "E0001"

    def test_format_json_valid_file(self) -> None:
        """Format JSON for valid file (no errors)."""
        reporter = DiagnosticReporter()

        output = reporter.format_json([], "test.sr")
        data = json.loads(output)

        assert data["valid"] is True
        assert len(data["errors"]) == 0

    def test_format_diagnostic_with_note(self) -> None:
        """Format diagnostic with related note."""
        reporter = DiagnosticReporter()
        reporter.add_source("test.sr", "line 1\nline 2\n")

        diag = Diagnostic.error(
            message="duplicate definition",
            file="test.sr",
            line=2,
            column=0,
        ).with_note(
            message="first defined here",
            file="test.sr",
            line=1,
            column=0,
        )

        output = reporter.format_diagnostic(diag)

        assert "duplicate definition" in output
        assert "first defined here" in output
        assert "note:" in output


class TestFormatSuccessMessage:
    """Test success message formatting."""

    def test_format_with_all_stats(self) -> None:
        """Format success message with all stats."""
        msg = format_success_message(
            "test.sr",
            models=2,
            agents=1,
            flows=3,
            handlers=1,
        )
        assert "valid" in msg
        assert "2 models" in msg
        assert "1 agent" in msg
        assert "3 flows" in msg
        assert "1 handler" in msg

    def test_format_with_no_stats(self) -> None:
        """Format success message with no stats."""
        msg = format_success_message("test.sr")
        assert msg == "valid"

    def test_format_pluralization(self) -> None:
        """Test correct pluralization."""
        msg = format_success_message("test.sr", models=1, agents=2)
        assert "1 model" in msg  # Singular
        assert "2 agents" in msg  # Plural
