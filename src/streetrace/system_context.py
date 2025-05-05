"""Handle system and project context loading for StreetRace.

This module provides the SystemContext class responsible for loading and managing
system messages and project context from the configuration directory.
"""

import logging
from pathlib import Path

from streetrace import messages
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


class SystemContext:
    """Handle loading and providing system and project context for AI interactions.

    Responsible for reading the system message and project context files
    from the configuration directory.
    """

    def __init__(self, ui: ConsoleUI, config_dir: Path = Path(".streetrace")) -> None:
        """Initialize the SystemContext.

        Args:
            ui: The ConsoleUI instance for displaying messages/errors.
            config_dir: The directory containing configuration files like
                        system.md and other context files. Defaults to '.streetrace'.

        """
        self.ui = ui
        self.config_dir = config_dir
        logger.info("SystemContext initialized with config_dir: %s", config_dir)

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
                self.ui.display_error(log_msg)
        else:
            logger.debug("System message file not found, using default.")

        # Default system message
        return messages.SYSTEM

    def get_project_context(self) -> str:
        """Read and combine all context files from the config directory (excluding system.md).

        Returns:
            A string containing the combined content of all context files.

        """
        combined_context = ""
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
            self.ui.display_error(log_msg)
            return combined_context

        if not context_files:
            logger.info("No additional context files found in '%s'.", self.config_dir)
            return combined_context

        context_content_parts = []
        logger.info(
            "Reading project context files: %s",
            ", ".join(str(f) for f in context_files),
        )

        if context_files:  # Only display if files were actually found
            self.ui.display_info(
                f"[Loading context from {len(context_files)} .streetrace/ file(s)]",
            )

        for file_path in context_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                context_content_parts.append(
                    f"--- Context from: {file_path.name} ---\n\n{content}\n\n--- End Context: {file_path.name} ---\n\n\n",
                )
                logger.debug("Read context from: %s", file_path)
            except Exception as e:
                log_msg = f"Error reading context file {file_path}: {e}"
                logger.exception(log_msg)
                self.ui.display_error(log_msg)

        combined_context = "".join(context_content_parts)
        logger.info(
            "Successfully loaded project context from %d file(s).",
            len(context_content_parts),
        )
        return combined_context
