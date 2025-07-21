"""Subcommand infrastructure for streetrace.

This package contains subcommands execution infrastructure
e.g. configure
"""

from .base_subcommand import BaseSubcommand
from .configure import ConfigureSubcommand
from .parser import SubcommandParser
from .registry import SubcommandRegistry

__all__ = [
    "BaseSubcommand",
    "ConfigureSubcommand",
    "SubcommandParser",
    "SubcommandRegistry",
]
