"""Command definitions for the Streetrace application.

This package contains specific command implementations that can be registered
with the command executor and invoked via slash commands in the interactive UI.
"""

from streetrace.commands.definitions.clear_command import ClearCommand
from streetrace.commands.definitions.compact_command import CompactCommand
from streetrace.commands.definitions.exit_command import ExitCommand
from streetrace.commands.definitions.history_command import HistoryCommand

__all__ = [
    "ClearCommand",
    "CompactCommand",
    "ExitCommand",
    "HistoryCommand",
]
