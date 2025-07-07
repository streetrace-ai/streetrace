"""Process AI prompts by loading mentioned files.

This module processes user prompts with file mentions to build
context for AI requests.
"""

import os
import re
from pathlib import Path

from streetrace.args import Args
from streetrace.input_handler import (
    HANDLED_CONT,
    SKIP,
    HandlerResult,
    InputContext,
    InputHandler,
)
from streetrace.log import get_logger
from streetrace.ui import ui_events
from streetrace.ui.ui_bus import UiBus

logger = get_logger(__name__)


class PromptProcessor(InputHandler):
    """Enrich user's prompt if necessary."""

    def __init__(self, ui_bus: UiBus, args: Args) -> None:
        """Initialize the PromptProcessor.

        Args:
            ui_bus: UI event bus to exchange messages with the UI.
            args: App args.

        """
        self.ui_bus = ui_bus
        self.args = args

    async def handle(
        self,
        ctx: InputContext,
    ) -> HandlerResult:
        """Build the prompt context for a given raw prompt and working directory.

        Args:
            ctx: User input processing context.

        Returns:
            HandlerResult indicating handing result.

        """
        if not ctx.user_input:
            return SKIP

        mentions = self.parse_and_load_mentions(ctx.user_input)
        ctx.enrich_input = {str(path): content for path, content in mentions}

        return HANDLED_CONT

    def parse_and_load_mentions(
        self,
        prompt: str,
    ) -> list[tuple[Path, str]]:
        """Parse @mentions from the prompt and load file contents.

        Args:
            prompt: The user's input prompt containing potential @file mentions.

        Returns:
            A list of (file_path, file_content) tuples for each valid mention.

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
        loaded_files: list[tuple[Path, str]] = []

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
                    log_msg = (
                        f"'Skipping @{mention}' (points outside the working directory "
                        f"'{self.args.working_dir}')."
                    )
                    self.ui_bus.dispatch_ui_update(ui_events.Warn(log_msg))
                    logger.warning(
                        log_msg,
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
                        self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))
                        logger.exception("Error reading mentioned file '%s'", mention)
                else:
                    log_msg = f"Skipping @{mention} (path not found or is not a file)."
                    self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))
                    logger.warning(log_msg)
            except Exception as e:
                log_msg = f"Error processing mention @{mention}: {e}"
                self.ui_bus.dispatch_ui_update(ui_events.Error(log_msg))
                logger.exception(log_msg)

        if mentions_found > 0:
            valid_mentions = ", ".join(["@" + m for m in mentions_loaded])
            self.ui_bus.dispatch_ui_update(
                ui_events.Info(f"[Loading content from {valid_mentions}]"),
            )

        return loaded_files
