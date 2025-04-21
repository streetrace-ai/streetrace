
import os
import re

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

class PathCompleter(Completer):
    """
    A prompt_toolkit completer that suggests file and directory paths
    relative to a working directory when the user types '@'.
    """

    def __init__(self, working_dir: str):
        """
        Initializes the PathCompleter.

        Args:
            working_dir: The absolute path to the directory relative to which
                         paths should be suggested.
        """
        if not os.path.isdir(working_dir):
            # Fallback or raise error if working_dir is invalid
            # For now, let's log and use current dir, though it should be valid from main.py
            print(f"Warning: Invalid working_dir '{working_dir}' for PathCompleter. Using '.'")
            self.working_dir = os.path.abspath(".")
        else:
            self.working_dir = os.path.abspath(working_dir)
        # Debug print to confirm working directory during init
        # print(f"PathCompleter initialized with working_dir: {self.working_dir}")


    def get_completions(self, document: Document, complete_event):
        """
        Generates completions for file/directory paths after an '@' symbol.
        """
        text_before_cursor = document.text_before_cursor

        # Find the latest '@' possibly followed by path characters
        # This regex finds the start of the '@' mention potentially ending at the cursor
        match = None
        # Allows alphanumeric, dots, slashes, underscores, hyphens in the path part
        for m in re.finditer(r"@([\w./\-_]*)", text_before_cursor):
             # Check if the cursor is within or just after this match's path part
             if m.end() >= document.cursor_position - (len(text_before_cursor) - m.start(1)) :
                 if m.end() == len(text_before_cursor): # Cursor at the end of the match
                     match = m
                 # Consider if cursor is inside the path as well (less common for path completion)
                 # elif m.start(1) <= document.cursor_position <= m.end():
                 #    match = m

        if not match:
            # print("No @ match found before cursor") # Debug
            return # Not an @ mention context

        full_mention = match.group(0) # e.g., @src/to
        partial_path = match.group(1) # e.g., src/to
        # print(f"Match found: full='{full_mention}', partial='{partial_path}'") # Debug

        base_dir = self.working_dir
        current_search_dir = base_dir
        prefix = partial_path

        # Adjust search directory and prefix based on the partial path
        if '/' in partial_path:
            dir_part = os.path.dirname(partial_path)
            prefix = os.path.basename(partial_path)
            # Important: Resolve the path relative to the working_dir
            candidate_search_dir = os.path.abspath(os.path.join(base_dir, dir_part))
            # print(f"Calculated candidate search dir: {candidate_search_dir}") # Debug
            # Only update search_dir if the calculated path is a valid directory
            if os.path.isdir(candidate_search_dir):
                current_search_dir = candidate_search_dir
            else: # If the dir_part isn't valid, we can't complete further down that tree
                # print(f"Candidate search dir '{candidate_search_dir}' is not a directory. Stopping.") # Debug
                return
        # else: # No slashes, search in the base_dir
            # print(f"No '/' in partial path. Searching in base_dir: {base_dir}") # Debug


        # print(f"Effective search directory: {current_search_dir}, prefix: '{prefix}'") # Debug

        try:
            if os.path.isdir(current_search_dir):
                # print(f"Listing items in {current_search_dir}") # Debug
                items = sorted(os.listdir(current_search_dir))
                # print(f"Found items: {items}") # Debug
                for item in items:
                    # Simple check: Don't suggest hidden files/folders unless explicitly typed
                    if not item.startswith('.') or prefix.startswith('.'):
                        if item.lower().startswith(prefix):
                            # print(f"Item '{item}' starts with prefix '{prefix}'") # Debug
                            full_item_path_in_search_dir = os.path.join(current_search_dir, item)
                            is_dir = os.path.isdir(full_item_path_in_search_dir)
                            # print(f"Item '{item}' is_dir: {is_dir}") # Debug

                            # Construct the completion *path part* relative to the original base_dir
                            if '/' in partial_path:
                                dir_part = os.path.dirname(partial_path)
                                completion_suffix = os.path.join(dir_part, item).replace('\\', '/') # Ensure forward slashes
                            else:
                                completion_suffix = item

                            # Text to insert (replaces the part *after* '@')
                            completion_text = completion_suffix
                            if is_dir:
                                completion_text

                            # Display text (how it appears in the dropdown)
                            display_text = item # Show only the item name in the list
                            if is_dir:
                                display_text += "/"

                            # start_position is relative to the beginning of the word being completed.
                            # The word being completed is the `partial_path`.
                            # We want to replace the partial_path part.
                            start_position = -len(partial_path)
                            # print(f"Yielding: text='{completion_text}', start={start_position}, display='{display_text}'") # Debug

                            yield Completion(
                                text=completion_text,
                                start_position=start_position,
                                display=display_text,
                                display_meta="dir" if is_dir else "file"
                            )
                        # else: # Debug
                            # print(f"Item '{item}' does not start with prefix '{prefix}'")
                    # else: # Debug
                        # print(f"Skipping hidden item '{item}'")

            # else: # Debug
                # print(f"Search directory '{current_search_dir}' is not a directory.")
        except OSError as e:
            # Log error maybe? Could be permissions issue
            # print(f"Error listing directory {current_search_dir}: {e}") # Debug
            pass # Fail gracefully for completion
