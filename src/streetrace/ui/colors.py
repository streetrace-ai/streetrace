from prompt_toolkit.styles import Style


# ANSI color codes for terminal output
class AnsiColors:
    USER = "\x1b[1;32;40m"
    MODEL = "\x1b[1;37;40m"
    MODELERROR = "\x1b[1;37;41m"
    TOOL = "\x1b[1;34;40m"
    TOOLERROR = "\x1b[1;34;41m"
    DEBUG = "\x1b[0;35;40m"
    INFO = "\x1b[0;35;40m"
    RESET = "\x1b[0m"
    WARNING = "\x1b[1;33;40m"


_RICH_USER_INPUT = "#f4bf75"
_PT_USER_INPUT = "#f4bf75"
_RICH_MODEL_RESPONSE = "#f5f5f5"
_RICH_INFO = "#d0d0d0"
_RICH_WARNING = "#f4bf75"
_RICH_ERROR = "#ac4142"


class Styles:
    PT = Style.from_dict(
        {
            "": "",
            "prompt": _PT_USER_INPUT,
        }
    )
    RICH_PROMPT = _RICH_USER_INPUT
    RICH_MODEL = _RICH_MODEL_RESPONSE
    RICH_TOOL_CALL = "monokai"
    RICH_TOOL = _RICH_INFO
    RICH_DIFF = "monokai"

    RICH_HISTORY_SYSTEM_INSTRUCTIONS_HEADER = _RICH_INFO
    RICH_HISTORY_SYSTEM_INSTRUCTIONS = _RICH_INFO
    RICH_HISTORY_CONTEXT_HEADER = _RICH_INFO
    RICH_HISTORY_CONTEXT = _RICH_INFO
    RICH_HISTORY_ASSISTANT_HEADER = _RICH_INFO
    RICH_HISTORY_ASSISTANT = _RICH_INFO
    RICH_HISTORY_USER_HEADER = _RICH_INFO
    RICH_HISTORY_USER = _RICH_INFO

    RICH_INFO = _RICH_INFO
    RICH_WARNING = _RICH_WARNING
    RICH_ERROR = _RICH_ERROR
