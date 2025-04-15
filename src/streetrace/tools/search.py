import glob
import os

from streetrace.tools.path_utils import normalize_and_validate_path


def search_files(pattern, search_string, work_dir):
    """
    Searches for text occurrences in files given a glob pattern and a search
    string.

    Args:
        pattern (str): Glob pattern to match files (relative to work_dir).
        search_string (str): The string to search for.
        work_dir (str): The root directory for the glob pattern.

    Returns:
        list: A list of dictionaries, where each dictionary represents a match.
            Each dictionary contains the file path, line number, and a snippet
            of the line where the match was found.

    Raises:
        ValueError: If the pattern resolves to paths outside the work_dir.
    """
    matches = []

    # Normalize the work_dir
    abs_work_dir = os.path.abspath(os.path.normpath(work_dir))

    # Construct the full glob pattern
    # We'll keep the pattern relative and join with normalized work_dir
    full_pattern = os.path.join(abs_work_dir, pattern)

    for filepath in glob.glob(full_pattern, recursive=True):
        # Validate each matching file is within work_dir
        try:
            abs_filepath = normalize_and_validate_path(filepath, work_dir)

            with open(abs_filepath, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if search_string in line:
                        # Get path relative to work_dir for display
                        rel_path = os.path.relpath(abs_filepath, abs_work_dir)
                        matches.append(
                            {
                                "filepath": rel_path,
                                "line_number": i + 1,
                                "snippet": line.strip(),
                            }
                        )
        except (ValueError, UnicodeDecodeError, IOError) as e:
            # If the file is outside work_dir, can't be read, or is binary
            # Just skip it and continue with other files
            print(f"Error reading file {filepath}: {e}")

    return matches, f"{len(matches)} matches found"
