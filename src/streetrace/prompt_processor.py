"""Process AI prompts by loading mentioned files.

This module processes user prompts with file mentions to build
context for AI requests.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """Holds the processed context components for the AI prompt."""

    raw_prompt: str
    working_dir: Path
    mentioned_files: list[tuple[Path, str]] = field(default_factory=list)


class PromptProcessor:
    """Handle processing user prompts with file mentions.

    Processes user prompts (like parsing @mentions) to build a PromptContext object.
    """

    def __init__(self, ui: ConsoleUI) -> None:
        """Initialize the PromptProcessor.

        Args:
            ui: The ConsoleUI instance for displaying messages/errors.

        """
        self.ui = ui
        logger.info("PromptProcessor initialized")

    def build_context(self, raw_prompt: str, working_dir: Path) -> PromptContext:
        """Build the prompt context for a given raw prompt and working directory.

        Args:
            raw_prompt: The unprocessed input string from the user.
            working_dir: The effective working directory for the operation.

        Returns:
            A PromptContext object populated with parsed mentions.

        """
        context = PromptContext(raw_prompt=raw_prompt, working_dir=working_dir)

        if raw_prompt:
            context.mentioned_files = self.parse_and_load_mentions(
                raw_prompt,
                working_dir,
            )

        return context

    def parse_and_load_mentions(
        self,
        prompt: str,
        working_dir: Path,
    ) -> list[tuple[Path, str]]:
        """Parse @mentions from the prompt and load file contents.

        Args:
            prompt: The user's input prompt containing potential @file mentions.
            working_dir: The working directory to resolve file paths against.

        Returns:
            A list of tuples containing (file_path, file_content) for each valid mention.

        """
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
