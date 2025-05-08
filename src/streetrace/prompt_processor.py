"""Process AI prompts by loading mentioned files.

This module processes user prompts with file mentions to build
context for AI requests.
"""

import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

from streetrace.args import Args
from streetrace.log import get_logger
from streetrace.ui.console_ui import ConsoleUI

logger = get_logger(__name__)


# TODO(krmrn42): Rename PromptContext -> ProcessedPrompt
# TODO(krmrn42): raw_prompt -> prompt
# TODO(krmrn42): mentioned_files -> mentions
# TODO(krmrn42): PromptProcessor.build_context -> remove working_dir arg
class ProcessedPrompt(BaseModel):
    """Holds the processed context components for the AI prompt."""

    prompt: str
    mentions: list[tuple[Path, str]] = Field(default_factory=list)


class PromptProcessor:
    """Handle processing user prompts with file mentions.

    Processes user prompts (like parsing @mentions) to build a ProcessedPrompt object.
    """

    def __init__(self, ui: ConsoleUI, args: Args) -> None:
        """Initialize the PromptProcessor.

        Args:
            ui: The ConsoleUI instance for displaying messages/errors.
            args: App args.

        """
        self.ui = ui
        self.args = args

    def build_context(self, prompt: str) -> ProcessedPrompt:
        """Build the prompt context for a given raw prompt and working directory.

        Args:
            prompt: The unprocessed input string from the user.

        Returns:
            A ProcessedPrompt object populated with parsed mentions.

        """
        mentions = (
            self.parse_and_load_mentions(
                prompt,
            )
            if prompt
            else []
        )
        return ProcessedPrompt(prompt=prompt, mentions=mentions)

    def parse_and_load_mentions(
        self,
        prompt: str,
    ) -> list[tuple[Path, str]]:
        """Parse @mentions from the prompt and load file contents.

        Args:
            prompt: The user's input prompt containing potential @file mentions.

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

        abs_working_dir = self.args.working_dir.resolve().absolute()

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
                    log_msg = f"Mention '@{mention}' points outside the working directory '{self.args.working_dir}'. Skipping."
                    self.ui.display_warning(log_msg)
                    logger.warning(
                        "Security Warning: Mention '@%s' resolved to '%s' which is outside the working directory '%s'. Skipping.",
                        mention,
                        abs_mention_path,
                        self.args.working_dir,
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
