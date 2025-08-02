"""Define color constants and styles for the StreetRace user interface.

This module contains ANSI color codes for terminal output and styles for
prompt_toolkit and rich library components used throughout the application.

"""

from typing import ClassVar

_USER_INPUT = "#f4bf75"
_MODEL_RESPONSE = "#f5f5f5"
_DIM = "#505050"
_INFO = "#d0d0d0"
_WARNING = "#f4bf75"
_ERROR = "#ac4142"
_CODE_THEME = "solarized-dark"


class Styles:
    """Style definitions for UI components in StreetRace.

    Contains style configurations for prompt_toolkit and rich library components,
    including prompts, model responses, tool calls, history display, and various
    message types (info, warning, error).
    """

    PT_ANSI: ClassVar[dict[str, str]] = {
        # Default input area
        "": "",
        "prompt": "fg:ansiyellow bold",
        "placeholder": "fg:#808080",  # Dimmed gray for placeholder
        # Bottom toolbar (reverse=True, so fg/bg are inverted)
        "bottom-toolbar": "bg:ansiwhite fg:ansiblue",
        "highlight": "bg:ansibrightyellow",
    }
    RICH_PROMPT = _USER_INPUT
    RICH_MODEL = _MODEL_RESPONSE
    RICH_TOOL_CALL = _CODE_THEME  # Theme for tool call syntax
    RICH_MD_CODE = _CODE_THEME  # Theme for markdown code blocks

    RICH_HISTORY_ROLE = _INFO
    RICH_HISTORY_MESSAGE = _INFO

    RICH_INFO = _INFO
    RICH_WARNING = _WARNING
    RICH_ERROR = _ERROR
