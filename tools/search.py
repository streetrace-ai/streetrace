import glob
import os


def search_files(pattern, search_string, work_dir):
    """
    Searches for text occurrences in files given a glob pattern and a search
    string.

    Args:
        pattern (str): Glob pattern to match files (relative to work_dir).
        search_string (str): The string to search for.
        work_dir (str): The root directory for the glob pattern. Defaults to
            "./".

    Returns:
        list: A list of dictionaries, where each dictionary represents a match.
            Each dictionary contains the file path, line number, and a snippet
            of the line where the match was found.
    """
    matches = []
    # Construct the full glob pattern
    full_pattern = os.path.join(work_dir, pattern)
    for filepath in glob.glob(full_pattern, recursive=True):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if search_string in line:
                        matches.append({
                            'filepath': filepath,
                            'line_number': i + 1,
                            'snippet': line.strip()
                        })
        except Exception as e:
            print(f"Error reading file {filepath}: {e}")

    return matches
