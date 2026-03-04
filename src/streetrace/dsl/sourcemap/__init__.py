"""Source map module for Streetrace DSL.

Provide source mapping functionality to translate generated Python
line numbers back to original DSL file locations.
"""

from streetrace.dsl.sourcemap.excepthook import (
    format_exception_with_source_map,
    install_excepthook,
    uninstall_excepthook,
)
from streetrace.dsl.sourcemap.registry import SourceMapping, SourceMapRegistry

__all__ = [
    "SourceMapRegistry",
    "SourceMapping",
    "format_exception_with_source_map",
    "install_excepthook",
    "uninstall_excepthook",
]
