"""Handle system and project context loading for StreetRace.

This module provides the SystemContext class responsible for loading and managing
system messages and project context from the configuration directory.
"""

from collections.abc import Sequence
from pathlib import Path

from streetrace import messages
from streetrace.log import get_logger
from streetrace.session_service import Session
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


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
        system_message_path = self.config_dir / "system.md"
        if system_message_path.exists():
            try:
                logger.debug("Reading system message from: %s", system_message_path)
                return system_message_path.read_text(encoding="utf-8")
            except Exception as e:
                log_msg = (
                    f"Error reading system message file '{system_message_path}': {e}"
                )
                logger.exception(log_msg)
                self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))
        else:
            logger.debug("System message file not found, using default.")

        # Default system message
        return messages.SYSTEM

    def get_project_context(self) -> Sequence[str]:
        """Read and combine all context files (excluding system.md).

        Returns:
            A string containing the combined content of all context files.

        """
        combined_context = []
        if not self.config_dir.exists() or not self.config_dir.is_dir():
            logger.info("Context directory '%s' not found.", self.config_dir)
            return combined_context

        try:
            context_files = [
                f
                for f in self.config_dir.iterdir()
                if f.is_file() and f.name != "system.md"
            ]
        except Exception as e:
            log_msg = f"Error listing context directory '{self.config_dir}': {e}"
            logger.exception(log_msg)
            self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))
            return combined_context

        if not context_files:
            logger.info("No additional context files found in '%s'.", self.config_dir)
            return combined_context

        logger.info(
            "Reading project context files: %s",
            ", ".join(str(f) for f in context_files),
        )

        if context_files:  # Only display if files were actually found
            self.ui_bus.dispatch_ui_update(
                ui_events.Info(
                    f"[Loading context from {len(context_files)} .streetrace/ file(s)]",
                ),
            )

        for file_path in context_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                combined_context.append(content)
                logger.debug("Read context from: %s", file_path)
            except Exception as e:
                log_msg = f"Error reading context file {file_path}: {e}"
                logger.exception(log_msg)
                self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))

        logger.info(
            "Successfully loaded project context from %d file(s).",
            len(combined_context),
        )
        return combined_context

    def add_context_from(self, session: Session) -> None:
        """Add user's request and assistant's final response to project context."""
        # TODO(krmrn42): Implement
