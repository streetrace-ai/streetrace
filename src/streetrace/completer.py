import os
import re
from collections.abc import Iterable

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class PathCompleter(Completer):
    """A prompt_toolkit completer that suggests file and directory paths
    relative to a working directory when the user types '@'.
    Only activates if the cursor is adjacent to or within a valid @-mention path.
    """

    def __init__(self, working_dir: str) -> None:
        """Initializes the PathCompleter.

        Args:
            working_dir: The absolute path to the directory relative to which
                         paths should be suggested.

        """
        if not os.path.isdir(working_dir):
            raise ValueError(
                f"The provided working directory '{working_dir}' is not a valid directory."
            )

        self.working_dir = os.path.abspath(working_dir)

    def get_completions(
        self,
        document: Document,
        complete_event,
    ) -> Iterable[Completion]:
        """Generates completions for file/directory paths after an '@' symbol."""
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

        partial_path_typed = path_part
        base_dir = self.working_dir
        current_search_dir = base_dir
        prefix = ""

        if "/" in partial_path_typed:
            dir_part = os.path.dirname(partial_path_typed)
            prefix = os.path.basename(partial_path_typed)
            candidate_search_dir = os.path.abspath(os.path.join(base_dir, dir_part))
            if os.path.isdir(candidate_search_dir):
                current_search_dir = candidate_search_dir
            else:
                return []
        elif partial_path_typed:
            prefix = partial_path_typed

        completions = []
        try:
            if os.path.isdir(current_search_dir):
                items = sorted(os.listdir(current_search_dir))
                for item in items:
                    is_hidden = item.startswith(".")
                    show_item = not is_hidden or prefix.startswith(".")

                    if show_item:
                        matches_prefix = not prefix or item.lower().startswith(
                            prefix.lower(),
                        )
                        if matches_prefix:
                            full_item_path_in_search_dir = os.path.join(
                                current_search_dir,
                                item,
                            )
                            is_dir = os.path.isdir(full_item_path_in_search_dir)
                            relative_item_path = os.path.relpath(
                                full_item_path_in_search_dir,
                                base_dir,
                            ).replace("\\", "/")

                            completion_text = relative_item_path
                            display_text = item
                            if is_dir:
                                # completion_text should be just the name
                                # if it's a directory, the user can type '/' to trigger
                                # a new completion.
                                display_text += "/"

                            start_position = -len(partial_path_typed)

                            completions.append(
                                Completion(
                                    text=completion_text,
                                    start_position=start_position,
                                    display=display_text,
                                    display_meta="dir" if is_dir else "file",
                                ),
                            )
            return completions
        except OSError:
            return []


# --- Command Completer ---
class CommandCompleter(Completer):
    """A prompt_toolkit completer that suggests predefined commands
    when the user types '/'.
    Only activates if the entire input consists only of the command being typed
    (allowing for leading/trailing whitespace).
    """

    def __init__(self, commands: list[str]) -> None:
        """Initializes the CommandCompleter.

        Args:
            commands: A list of available commands (e.g., ['/exit', '/history']).

        """
        self.commands = sorted(
            [cmd if cmd.startswith("/") else "/" + cmd for cmd in commands],
        )

    def get_completions(
        self,
        document: Document,
        complete_event,
    ) -> Iterable[Completion]:
        """Generates completions for commands starting with '/'.
        Only completes if the command is the only content on the line (trimmed).
        """
        text = document.text
        text_trimmed = text.strip()

        # Check context: Entire trimmed text must match command pattern
        # Requires / followed by zero or more valid command characters.
        # Use a pattern that enforces the starting slash.
        command_pattern_match = re.fullmatch(r"/([\w\-_]*)?", text_trimmed)
        # Special case: if the input is exactly "/", it's a valid prefix but won't match above
        is_just_slash = text_trimmed == "/"

        if not command_pattern_match and not is_just_slash:
            return []  # Not a valid command-only context

        # --- If context is valid, proceed ---

        prefix = text_trimmed
        start_pos = -len(prefix)

        completions = []
        for cmd in self.commands:
            if cmd.startswith(prefix):
                completions.append(
                    Completion(
                        text=cmd,
                        start_position=start_pos,
                        display=cmd,
                        display_meta="command",
                    ),
                )
        return completions


# --- Main Prompt Completer (True Composition) ---
class PromptCompleter(Completer):
    """A composite completer that delegates to a list of other completers.
    Simply aggregates completions from all registered completers.
    """

    def __init__(self, completers: Iterable[Completer]) -> None:
        """Initializes the PromptCompleter.

        Args:
            completers: An iterable of Completer instances.

        """
        self.completers = list(completers)

    def get_completions(
        self,
        document: Document,
        complete_event,
    ) -> Iterable[Completion]:
        """Generates completions by yielding results from all registered completers.
        Each delegate completer is responsible for checking its own context.
        """
        for completer in self.completers:
            yield from completer.get_completions(document, complete_event)
