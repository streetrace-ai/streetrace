"""Define color constants and styles for the StreetRace user interface.

This module contains ANSI color codes for terminal output and styles for
prompt_toolkit and rich library components used throughout the application.

"""

from prompt_toolkit.styles import Style

_USER_INPUT = "#f4bf75"
_MODEL_RESPONSE = "#f5f5f5"
_DIM = "#505050"
_INFO = "#d0d0d0"
_WARNING = "#f4bf75"
_ERROR = "#ac4142"
_CODE_THEME = "monokai"


class Styles:
    """Style definitions for UI components in StreetRace.

    Contains style configurations for prompt_toolkit and rich library components,
    including prompts, model responses, tool calls, history display, and various
    message types (info, warning, error).
    """

    PT = Style.from_dict(
        {
            "": "",
            "prompt": _USER_INPUT,
            "prompt-continuation": _DIM,
            "bottom-toolbar": _DIM,
        },
    )
    RICH_PROMPT = _USER_INPUT
    RICH_MODEL = _MODEL_RESPONSE
    RICH_TOOL_CALL = _CODE_THEME  # Theme for tool call syntax
    RICH_TOOL_OUTPUT_CODE_THEME = (
        _CODE_THEME  # Theme for code in tool output (json, diff)
    )
    RICH_TOOL_OUTPUT_TEXT_STYLE = _INFO  # Style for plain text tool output
    RICH_MD_CODE = _CODE_THEME  # Theme for markdown code blocks

    RICH_HISTORY_SYSTEM_INSTRUCTIONS_HEADER = _INFO
    RICH_HISTORY_SYSTEM_INSTRUCTIONS = _INFO
    RICH_HISTORY_CONTEXT_HEADER = _INFO
    RICH_HISTORY_CONTEXT = _INFO
    RICH_HISTORY_ASSISTANT_HEADER = _INFO
    RICH_HISTORY_ASSISTANT = _INFO
    RICH_HISTORY_USER_HEADER = _INFO
    RICH_HISTORY_USER = _INFO

    RICH_INFO = _INFO
    RICH_WARNING = _WARNING
    RICH_ERROR = _ERROR
