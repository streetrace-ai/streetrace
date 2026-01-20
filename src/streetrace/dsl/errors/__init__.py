"""Error handling and diagnostics for Streetrace DSL compiler.

Provide error codes, diagnostic messages, and rustc-style error formatting
for reporting compiler errors with source context and helpful suggestions.
"""

from streetrace.dsl.errors.codes import ErrorCode
from streetrace.dsl.errors.diagnostics import Diagnostic, Severity
from streetrace.dsl.errors.reporter import DiagnosticReporter

__all__ = [
    "Diagnostic",
    "DiagnosticReporter",
    "ErrorCode",
    "Severity",
]
