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


_USER_INPUT = "#f4bf75"
_MODEL_RESPONSE = "#f5f5f5"
_DIM = "#505050"
_INFO = "#d0d0d0"
_WARNING = "#f4bf75"
_ERROR = "#ac4142"
_CODE_THEME = "monokai"


class Styles:
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
    RICH_TOOL_CALL = _CODE_THEME
    RICH_TOOL = _INFO
    RICH_DIFF = _CODE_THEME
    RICH_MD_CODE = _CODE_THEME

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
