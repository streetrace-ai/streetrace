"""Process AI prompts by loading context and mentioned files.

This module handles the loading of system and project context, and processes user prompts
with file mentions to build a complete context for AI requests.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from streetrace import messages
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """Holds the processed context components for the AI prompt."""

    raw_prompt: str
    working_dir: Path
    system_message: str = ""
    project_context: str = ""
    mentioned_files: list[tuple[Path, str]] = field(default_factory=list)


class PromptProcessor:
    """Handle loading context (system, project) and processing user prompts.

    Processes user prompts (like parsing @mentions) to build a complete PromptContext object.
    """

    def __init__(self, ui: ConsoleUI, config_dir: Path = Path(".streetrace")) -> None:
        """Initialize the PromptProcessor.

        Args:
            ui: The ConsoleUI instance for displaying messages/errors.
            config_dir: The directory containing configuration files like
                        system.md and other context files. Defaults to '.streetrace'.

        """
        self.ui = ui
        self.config_dir = config_dir
        logger.info("PromptProcessor initialized with config_dir: %s", config_dir)

    def build_context(self, raw_prompt: str, working_dir: Path) -> PromptContext:
        """Build the full context for a given raw prompt and working directory.

        Args:
            raw_prompt: The unprocessed input string from the user.
            working_dir: The effective working directory for the operation.

        Returns:
            A PromptContext object populated with loaded context and parsed mentions.

        """
        context = PromptContext(raw_prompt=raw_prompt, working_dir=working_dir)

        context.system_message = self._read_system_message()
        context.project_context = self._read_project_context()
        if raw_prompt:
            context.mentioned_files = self.parse_and_load_mentions(
                raw_prompt,
                working_dir,
            )

        # Future steps could be added here, modifying the context object

        return context

    def _read_system_message(self) -> str:
        """Read the system message from the config directory."""
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
                self.ui.display_error(log_msg)  # Use UI to display error
        else:
            logger.debug("System message file not found, using default.")

        # Default system message
        return messages.SYSTEM  # Use imported or fallback SYSTEM constant

    def _read_project_context(self) -> str:
        """Read and combine all context files from the config directory (excluding system.md)."""
        combined_context = ""
        if not self.config_dir.exists() or not self.config_dir.is_dir():
            logger.info("Context directory '%s' not found.", self.config_dir)
            return combined_context

        try:
            context_files = [
                f
                for f in self.config_dir.iterdir()
                if (self.config_dir / f).is_file() and f.name != "system.md"
            ]
        except Exception as e:
            log_msg = f"Error listing context directory '{self.config_dir}': {e}"
            logger.exception(log_msg)
            self.ui.display_error(log_msg)  # Use UI
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
                self.ui.display_error(log_msg)  # Use UI

        combined_context = "".join(context_content_parts)
        logger.info(
            "Successfully loaded project context from %d file(s).",
            len(context_content_parts),
        )
        return combined_context

    def parse_and_load_mentions(
        self,
        prompt: str,
        working_dir: Path,
    ) -> list[tuple[Path, str]]:
        """Parse @mentions from the prompt and load file contents."""
        mention_pattern = r"@([^\s@]+)"
        raw_mentions = re.findall(mention_pattern, prompt)

        processed_mentions: set[str] = set()
        trailing_punctuation = ".,!?;:)]}\"'"

        for raw_mention in raw_mentions:
            cleaned_mention = str(raw_mention)
            while (
                len(cleaned_mention) > 1 and cleaned_mention[-1] in trailing_punctuation
            ):
                cleaned_mention = cleaned_mention[:-1]
            processed_mentions.add(cleaned_mention)

        mentions = sorted(processed_mentions)
        loaded_files = []

        if not mentions:
            return loaded_files

        logger.debug("Detected mentions after cleaning: %s", ", ".join(mentions))

        abs_working_dir = working_dir.resolve().absolute()

        mentions_found = 0
        mentions_loaded = []
        for mention in mentions:
            potential_rel_path = Path(mention)
            try:
                abs_mention_path = (abs_working_dir / mention).resolve().absolute()
                common_path = Path(
                    os.path.commonpath(
                        [abs_working_dir, abs_mention_path],
                    ),
                )

                if common_path != abs_working_dir:
                    log_msg = f"Mention '@{mention}' points outside the working directory '{working_dir}'. Skipping."
                    self.ui.display_warning(log_msg)
                    logger.warning(
                        "Security Warning: Mention '@%s' resolved to '%s' which is outside the working directory '%s'. Skipping.",
                        mention,
                        abs_mention_path,
                        working_dir,
                    )
                    continue

                if abs_mention_path.is_file():
                    try:
                        content = abs_mention_path.read_text(encoding="utf-8")
                        loaded_files.append((potential_rel_path, content))
                        mentions_found += 1
                        mentions_loaded.append(mention)
                        logger.info(
                            "Loaded context from mentioned file: %s",
                            mention,
                        )
                    except Exception as e:
                        log_msg = f"Error reading mentioned file @{mention}: {e}"
                        self.ui.display_error(log_msg)
                        logger.exception("Error reading mentioned file '%s'", mention)
                else:
                    log_msg = f"Mentioned path @{mention} not found or is not a file. Skipping."
                    self.ui.display_error(log_msg)
                    logger.warning(log_msg)
            except Exception as e:
                log_msg = f"Error processing mention @{mention}: {e}"
                self.ui.display_error(log_msg)
                logger.exception(log_msg)

        if mentions_found > 0:
            self.ui.display_info(
                f"[Loading content from {', '.join(['@'+m for m in mentions_loaded])}]",
            )

        return loaded_files
