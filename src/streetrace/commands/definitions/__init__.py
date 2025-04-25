# src/streetrace/commands/definitions/__init__.py

# Make command classes easily importable
from .clear_command import ClearCommand  # Import ClearCommand
from .compact_command import CompactCommand
from .exit_command import ExitCommand
from .history_command import HistoryCommand

__all__ = [
    "ClearCommand",  # Add ClearCommand to __all__
    "CompactCommand",
    "ExitCommand",
    "HistoryCommand",
]
