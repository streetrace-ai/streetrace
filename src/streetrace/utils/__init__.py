"""Utility functions and helpers for the StreetRace application.

This package contains various utilities that support the StreetRace application:
- hide_args: A decorator for modifying function signatures to hide specific parameters
- uid: Functions for determining user identity through various methods
"""

from streetrace.utils.hide_args import hide_args

__all__ = ["hide_args"]
