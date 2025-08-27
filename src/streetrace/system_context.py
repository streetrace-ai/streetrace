"""Handle system and project context loading for StreetRace.

This module provides the SystemContext class responsible for loading and managing
system messages and project context from the configuration directory.
"""

from datetime import datetime
from pathlib import Path

from tzlocal import get_localzone

from streetrace import messages
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)

_SYSTEM_MD = "SYSTEM.md"
# TODO(krmrn42): Experiment with pre-processing this file and use messages for RAG
_CONVERSATIONS_MD = "CONVERSATIONS.md"
_CONVERSATIONS_MD_TEMPLATE = """
# {date}

## User

{user}

## Assistant

{assistant}

"""
_CONVERSATION_HEADER_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"


def _find_file_case_insensitive(path: Path) -> Path | None:
    """Return the actual file path that matches the given path, ignoring case."""
    if not path.parent.exists():
        return None

    for entry in path.parent.iterdir():
        if entry.name.lower() == path.name.lower():
            return entry.resolve()

    return None


class SystemContext:
    """Handle loading and providing system and project context for AI interactions.

    Responsible for reading the system message and project context files
    from the configuration directory.
    """

    def __init__(self, ui_bus: UiBus, context_dir: Path) -> None:
        """Initialize the SystemContext.

        Args:
            ui_bus: UI event bus to exchange messages with the UI.
            context_dir: Context storage directory.

        """
        self.ui_bus = ui_bus
        self.config_dir = context_dir
        logger.info("SystemContext initialized with config_dir: %s", self.config_dir)

    def get_system_message(self) -> str:
        """Get the system message from the config directory.

        Returns:
            The loaded system message or a default message if none is found.

        """
        system_message_path = _find_file_case_insensitive(self.config_dir / _SYSTEM_MD)
        if not system_message_path or not system_message_path.exists():
            logger.debug("System message file not found, using default.")
        else:
            try:
                logger.debug("Reading system message from: %s", system_message_path)
                return system_message_path.read_text(encoding="utf-8")
            except Exception as e:
                log_msg = (
                    f"Error reading system message file '{system_message_path}': {e}"
                )
                logger.exception(log_msg)
                self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))

        # Default system message
        return messages.SYSTEM

    def add_context_from_turn(
        self,
        user_prompt: str,
        assistant_response: str,
    ) -> None:
        """Add the sequence of request-responses to project context."""
        # payload can be empty if the user just sends an empty message
        # see Application._process_input in app.py
        conv_path = self.config_dir / _CONVERSATIONS_MD
        buffer = _CONVERSATIONS_MD_TEMPLATE.format(
            date=datetime.now(tz=get_localzone()).strftime(
                _CONVERSATION_HEADER_DATE_FORMAT,
            ),
            user=user_prompt,
            assistant=assistant_response,
        )
        with conv_path.open(mode="a", encoding="utf-8") as f:
            f.write(buffer)
