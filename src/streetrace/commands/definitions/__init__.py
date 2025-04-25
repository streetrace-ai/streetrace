# src/streetrace/commands/definitions/__init__.py

# Make command classes easily importable
from .exit_command import ExitCommand
from .history_command import HistoryCommand
from .compact_command import CompactCommand

__all__ = ["ExitCommand", "HistoryCommand", "CompactCommand"]
