# app/prompt_processor.py
import logging
import os
import re
from dataclasses import dataclass, field

from streetrace import messages
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """Holds the processed context components for the AI prompt."""

    raw_prompt: str
    working_dir: str
    system_message: str = ""
    project_context: str = ""
    # List of tuples: (relative_mention_path, file_content)
    mentioned_files: list[tuple[str, str]] = field(default_factory=list)
    # Could add more fields later: rewritten_prompt, parsed_instructions, etc.


class PromptProcessor:
    """Handles loading context (system, project) and processing user prompts
    (like parsing @mentions) to build a complete PromptContext object.
    """

    def __init__(self, ui: ConsoleUI, config_dir: str = ".streetrace") -> None:
        """Initializes the PromptProcessor.

        Args:
            ui: The ConsoleUI instance for displaying messages/errors.
            config_dir: The directory containing configuration files like
                        system.md and other context files. Defaults to '.streetrace'.

        """
        self.ui = ui
        self.config_dir = config_dir
        logger.info(f"PromptProcessor initialized with config_dir: {config_dir}")

    def build_context(self, raw_prompt: str, working_dir: str) -> PromptContext:
        """Builds the full context for a given raw prompt and working directory.

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
            context.mentioned_files = self._parse_and_load_mentions(
                raw_prompt,
                working_dir,
            )

        # Future steps could be added here, modifying the context object:
        # context = self._rewrite_prompt(context)
        # context = self._parse_instructions(context)

        return context

    def _read_system_message(self) -> str:
        """Reads the system message from the config directory."""
        system_message_path = os.path.join(self.config_dir, "system.md")
        if os.path.exists(system_message_path):
            try:
                with open(system_message_path, encoding="utf-8") as f:
                    logger.debug(f"Reading system message from: {system_message_path}")
                    return f.read()
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
        """Reads and combines all context files from the config directory (excluding system.md)."""
        combined_context = ""
        if not os.path.exists(self.config_dir) or not os.path.isdir(self.config_dir):
            logger.info(f"Context directory '{self.config_dir}' not found.")
            return combined_context

        try:
            context_files = [
                f
                for f in os.listdir(self.config_dir)
                if os.path.isfile(os.path.join(self.config_dir, f)) and f != "system.md"
            ]
        except Exception as e:
            log_msg = f"Error listing context directory '{self.config_dir}': {e}"
            logger.exception(log_msg)
            self.ui.display_error(log_msg)  # Use UI
            return combined_context

        if not context_files:
            logger.info(f"No additional context files found in '{self.config_dir}'.")
            return combined_context

        context_content_parts = []
        logger.info(f"Reading project context files: {', '.join(context_files)}")
        if context_files:  # Only display if files were actually found
            self.ui.display_info(
                f"[Loading context from {len(context_files)} .streetrace/ file(s)]",
            )

        for file_name in context_files:
            file_path = os.path.join(self.config_dir, file_name)
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                    context_content_parts.append(
                        f"--- Context from: {file_name} ---\n\n{content}\n\n--- End Context: {file_name} ---\n\n\n",
                    )
                    logger.debug(f"Read context from: {file_path}")
            except Exception as e:
                log_msg = f"Error reading context file {file_path}: {e}"
                logger.exception(log_msg)
                self.ui.display_error(log_msg)  # Use UI

        combined_context = "".join(context_content_parts)
        logger.info(
            f"Successfully loaded project context from {len(context_content_parts)} file(s).",
        )
        return combined_context

    def _parse_and_load_mentions(
        self,
        prompt: str,
        working_dir: str,
    ) -> list[tuple[str, str]]:
        """Parses @mentions from the prompt and loads file contents."""
        mention_pattern = r"@([^\s@]+)"
        raw_mentions = re.findall(mention_pattern, prompt)

        processed_mentions = set()
        trailing_punctuation = ".,!?;:)]}\"'"

        for raw_mention in raw_mentions:
            cleaned_mention = raw_mention
            while (
                len(cleaned_mention) > 1 and cleaned_mention[-1] in trailing_punctuation
            ):
                cleaned_mention = cleaned_mention[:-1]
            processed_mentions.add(cleaned_mention)

        mentions = sorted(processed_mentions)
        loaded_files = []

        if not mentions:
            return loaded_files

        logging.debug(f"Detected mentions after cleaning: {', '.join(mentions)}")

        absolute_working_dir = os.path.realpath(working_dir)

        mentions_found = 0
        mentions_loaded = []
        for mention in mentions:
            potential_rel_path = mention
            try:
                normalized_path = os.path.normpath(os.path.join(working_dir, mention))
                absolute_mention_path = os.path.realpath(normalized_path)

                common_path = os.path.commonpath(
                    [absolute_working_dir, absolute_mention_path],
                )

                if common_path != absolute_working_dir:
                    log_msg = f"Mention '@{mention}' points outside the working directory '{working_dir}'. Skipping."
                    self.ui.display_warning(log_msg)
                    logging.warning(
                        f"Security Warning: Mention '@{mention}' resolved to '{absolute_mention_path}' which is outside the working directory '{absolute_working_dir}'. Skipping.",
                    )
                    continue

                if os.path.isfile(absolute_mention_path):
                    try:
                        with open(absolute_mention_path, encoding="utf-8") as f:
                            content = f.read()
                        loaded_files.append((potential_rel_path, content))
                        mentions_found += 1
                        mentions_loaded.append(mention)
                        # self.ui.display_info(f"[Loaded context from @{mention}]") # Maybe too verbose? Logged below.
                        logging.info(
                            f"Loaded context from mentioned file: {absolute_mention_path} (Mention: @{mention})",
                        )
                    except Exception as e:
                        log_msg = f"Error reading mentioned file @{mention}: {e}"
                        self.ui.display_error(log_msg)
                        logging.exception(
                            f"Error reading mentioned file '{absolute_mention_path}' (Mention: @{mention}): {e}",
                        )
                else:
                    log_msg = f"Mentioned path @{mention} ('{absolute_mention_path}') not found or is not a file. Skipping."
                    self.ui.display_error(log_msg)
                    logging.warning(log_msg)
            except Exception as e:
                log_msg = f"Error processing mention @{mention}: {e}"
                self.ui.display_error(log_msg)
                logging.exception(log_msg)

        if mentions_found > 0:
            self.ui.display_info(
                f"[Loading content from {', '.join(['@'+m for m in mentions_loaded])}]",
            )

        return loaded_files
