"""Provide intelligent auto-completion for file paths and commands in the console.

This module implements a set of specialized prompt_toolkit completers that enhance
user experience by providing contextual suggestions:

1. PathCompleter: Suggests file and directory paths when users type '@' mentions
2. CommandCompleter: Provides command suggestions when users type '/' commands
3. PromptCompleter: Composes multiple completers into a unified interface

These completers help users efficiently navigate the file system and discover available
commands without needing to remember exact paths or command names.
"""

import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.completion import CompleteEvent, Completer, Completion

from streetrace.commands.command_executor import CommandExecutor

if TYPE_CHECKING:
    from prompt_toolkit.document import Document


class PathCompleter(Completer):
    """A prompt_toolkit @path completer.

    Suggests file and directory paths relative to a working directory when the user
    types '@'. Only activates if the cursor is adjacent to or within a valid @-mention
    path.
    """

    def __init__(self, working_dir: Path) -> None:
        """Initialize the PathCompleter.

        Args:
            working_dir: The absolute path to the directory relative to which
                         paths should be suggested. Can be a string or Path object.

        """
        if not working_dir.is_dir():
            msg = f"working_dir '{working_dir}' is not a valid directory."
            raise ValueError(
                msg,
            )

        self.working_dir = working_dir.absolute()

    def get_completions(  # noqa: C901, PLR0912
        self,
        document: "Document",
        complete_event: CompleteEvent,  # noqa: ARG002
    ) -> Iterable[Completion]:
        """Generate completions for file/directory paths after an '@' symbol."""
        text_before_cursor = document.text_before_cursor
        current_pos = document.cursor_position

        # Find the last @ before the cursor
        last_at_pos = text_before_cursor.rfind("@", 0, current_pos)

        if last_at_pos == -1:
            return []  # No @ found before cursor, not relevant for this completer

        # Extract text after the last @ up to the cursor
        path_part = text_before_cursor[last_at_pos + 1 : current_pos]

        # Check if characters between @ and cursor are valid path characters
        # Or if the path_part is empty (cursor immediately after @)
        if not re.fullmatch(r"[\w./\-_]*", path_part):
            return []  # Invalid context for this completer

        # --- If context is valid, proceed to find completions ---

        partial_path_typed = Path(path_part)
        base_dir = self.working_dir
        current_search_dir = base_dir
        prefix = ""
        # pathlib.Path does not store the trailing path separator, and
        # we need to know if there is one to understand where to look for
        # completions
        is_in_subdir = path_part and (path_part[-1] == os.sep or path_part[-2:] == "/.")
        # if the last typed path fragment == '.' then we need to interpret the
        # dot as a dot in the file name, but Path will interpret it as
        # a current directory specifier
        is_trailing_dot = path_part and (
            path_part.endswith(os.sep + ".")
            or (not partial_path_typed.name and path_part.endswith("."))
        )

        if is_in_subdir:
            prefix = "." if is_trailing_dot else ""
            candidate_search_dir = self.working_dir.joinpath(partial_path_typed)
        else:
            prefix = partial_path_typed.name if not is_trailing_dot else "."
            candidate_search_dir = self.working_dir.joinpath(partial_path_typed.parent)

        if candidate_search_dir.is_dir():
            current_search_dir = candidate_search_dir
        else:
            return []

        completions = []
        try:
            if current_search_dir.is_dir():
                items = sorted(item.name for item in current_search_dir.iterdir())
                for item in items:
                    # don't show hidden files unless requested
                    if item.startswith(".") and not prefix.startswith("."):
                        continue

                    # only show items starting with the typed prefix
                    if prefix and not item.lower().startswith(
                        prefix.lower(),
                    ):
                        continue

                    full_item_path_in_search_dir = current_search_dir / item

                    # Get relative path and ensure forward slashes

                    completion_text = str(
                        full_item_path_in_search_dir.relative_to(base_dir),
                    ).replace("\\", "/")
                    display_meta = "file"

                    display_text = item
                    if full_item_path_in_search_dir.is_dir():
                        # Add slash for display purposes on directories
                        display_text += "/"
                        display_meta = "dir"

                    start_position = -len(path_part)

                    completions.append(
                        Completion(
                            text=completion_text,
                            start_position=start_position,
                            display=display_text,
                            display_meta=display_meta,
                        ),
                    )
        except OSError:
            return []
        else:
            return completions


# --- Command Completer ---
class CommandCompleter(Completer):
    """A prompt_toolkit /command completer.

    Suggests predefined commands when the user types '/'.
    Only activates if the entire input consists only of the command being typed
    (allowing for leading/trailing whitespace).
    """

    def __init__(self, command_executor: CommandExecutor) -> None:
        """Initialize the CommandCompleter.

        Args:
            command_executor: A command executor to get commands from.

        """
        self.command_executor = command_executor

    def get_completions(
        self,
        document: "Document",
        complete_event: CompleteEvent,  # noqa: ARG002
    ) -> Iterable[Completion]:
        """Generate completions for commands starting with '/'.

        Only completes if the command is the only content on the line (trimmed).
        """
        cmd_names = [
            f"/{cmd_name}"
            for cmd in self.command_executor.commands
            for cmd_name in cmd.names
        ]
        text = document.text
        text_trimmed = text.strip()

        # Check context: Entire trimmed text must match command pattern
        # Requires / followed by zero or more valid command characters.
        # Use a pattern that enforces the starting slash.
        command_pattern_match = re.fullmatch(r"/([\w\-_]*)?", text_trimmed)
        is_just_slash = text_trimmed == "/"

        if not command_pattern_match and not is_just_slash:
            return []  # Not a valid command-only context

        prefix = text_trimmed
        start_pos = -len(prefix)

        return [
            Completion(
                text=cmd,
                start_position=start_pos,
                display=cmd,
                display_meta="command",
            )
            for cmd in cmd_names
            if cmd.startswith(prefix)
        ]


# --- Main Prompt Completer (True Composition) ---
class PromptCompleter(Completer):
    """A composite completer that combines all other completers.

    Simply aggregates completions from all registered completers.
    """

    def __init__(self, completers: Iterable[Completer]) -> None:
        """Initialize the PromptCompleter.

        Args:
            completers: An iterable of Completer instances.

        """
        self.completers = list(completers)

    def get_completions(
        self,
        document: "Document",
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        """Generate completions by yielding results from all registered completers.

        Each delegate completer is responsible for checking its own context.
        """
        for completer in self.completers:
            yield from completer.get_completions(document, complete_event)
