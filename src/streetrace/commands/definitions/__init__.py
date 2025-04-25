# src/streetrace/commands/definitions/__init__.py

# Make command classes easily importable
from .exit_command import ExitCommand
from .history_command import HistoryCommand
from .compact_command import CompactCommand
from .clear_command import ClearCommand  # Import ClearCommand

__all__ = [
    "ExitCommand",
    "HistoryCommand",
    "CompactCommand",
    "ClearCommand",  # Add ClearCommand to __all__
]
