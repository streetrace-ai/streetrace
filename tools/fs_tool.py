import json
import tools.read_directory_structure as rds
import tools.read_file as rf
import tools.write_file as wf
import tools.cli_tool as cli
import tools.search as s

def _clean_input(input_str):
    return input_str.strip('"\'\r\n\t ')

def list_directory(path):
    """Read directory structure while honoring .gitignore rules.
    
    Args:
        path (str): The path to scan within current directory, defaults to current directory.
    
    Returns:
        dict: Directory structure with files and subdirectories.
        
    Raises:
        ValueError: If the requested path is outside the allowed root path.
    """
    try:
        structure = rds.read_directory_structure(_clean_input(path))
        return json.dumps(structure, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)

def read_file(path, encoding='utf-8'):
    """Read file contents.
    
    Args:
        path (str): The path to the file to read.
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.
    
    Returns:
        File contents.
    """
    try:
        contents = rf.read_file(_clean_input(path), encoding=encoding)
        return json.dumps(contents, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)

def write_file(path, content, encoding='utf-8'):
    """Write content to a file.
    
    Args:
        path (str): The path to the file to write.
        content (str or bytes): Content to write to the file.
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.
        binary_mode (bool, optional): If True, write in binary mode. Defaults to False.
    
    Returns:
        Result of the operation.
    """
    try:
        result = wf.write_file(_clean_input(path), content, encoding=encoding, binary_mode=False)
        return json.dumps({"success": True, "path": result}, indent=2)
    except (ValueError, TypeError, IOError, OSError) as e:
        return json.dumps({"error": str(e)}, indent=2)

def execute_cli_command(command):
    """Write content to a file.
    
    Args:
        command (str): The command to execute.
    
    Returns:
        The stdio output.
    """
    try:
        result = cli.execute_cli_command(_clean_input(command))
        return json.dumps({"success": True, "output": result}, indent=2)
    except (ValueError, TypeError, IOError, OSError) as e:
        return json.dumps({"error": str(e)}, indent=2)

def search_files(pattern, search_string):
    """
    Searches for text occurrences in files given a glob pattern and a search
    string.

    Args:
        pattern (str): Glob pattern to match files (relative to root_dir).
        search_string (str): The string to search for.

    Returns:
        list: A list of dictionaries, where each dictionary represents a match.
            Each dictionary contains the file path, line number, and a snippet
            of the line where the match was found.
    """
    try:
        result = s.search_files(_clean_input(pattern), _clean_input(search_string))
        return json.dumps({"success": True, "output": result}, indent=2)
    except (ValueError, TypeError, IOError, OSError) as e:
        return json.dumps({"error": str(e)}, indent=2)