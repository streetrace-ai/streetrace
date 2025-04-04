import tools.read_directory_structure as rds
import tools.read_file as rf
import tools.write_file as wf
import tools.cli as cli
import tools.search as s

def _clean_input(input_str):
    """
    Clean the input by removing unwanted whitespace characters, but preserving quotes.
    """
    # Only strip whitespace, not quotes
    return input_str.strip('\"\'\r\n\t ')

def list_directory(path, work_dir):
    """Read directory structure while honoring .gitignore rules.
    
    Args:
        path (str): The path to scan. Must be within the work_dir.
        work_dir (str): The working directory.
    
    Returns:
        dict: Directory structure with files and subdirectories.
        
    Raises:
        ValueError: If the requested path is outside the allowed root path.
    """
    return rds.read_directory_structure(_clean_input(path), work_dir)

def read_file(path, work_dir, encoding='utf-8'):
    """Read file contents.
    
    Args:
        path (str): The path to the file to read. Must be within the work_dir.
        work_dir (str): The working directory. 
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.
    
    Returns:
        File contents.
    """
    return rf.read_file(_clean_input(path), work_dir, encoding)

def write_file(path, content, work_dir, encoding='utf-8'):
    """Write content to a file.
    
    Args:
        path (str): The path to the file to write. Must be within the work_dir.
        content (str or bytes): Content to write to the file.
        work_dir (str): The working directory. 
        encoding (str, optional): Text encoding to use. Defaults to 'utf-8'.
    
    Returns:
        Result of the operation.
    """
    return wf.write_file(_clean_input(path), content, work_dir, encoding, binary_mode=False)

def execute_cli_command(command, work_dir):
    """Execute a CLI command interactively. Does not provide shell access.
    
    Args:
        command (list or str): The command to execute.
        work_dir (str): The working directory.
    
    Returns:
        The stdio output.
    """
    return cli.execute_cli_command(command, work_dir)

def search_files(pattern, search_string, work_dir):
    """
    Searches for text occurrences in files given a glob pattern and a search
    string.

    Args:
        pattern (str): Glob pattern to match files (relative to work_dir).
        search_string (str): The string to search for.
        work_dir (str): The working directory for the glob pattern.

    Returns:
        list: A list of dictionaries, where each dictionary represents a match.
            Each dictionary contains the file path, line number, and a snippet
            of the line where the match was found.
    """
    return s.search_files(_clean_input(pattern), _clean_input(search_string), 
                              work_dir=work_dir)
    

# Define common tools list
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Searches for text occurrences in files given a glob pattern and a search string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files."
                    },
                    "search_string": {
                        "type": "string",
                        "description": "The string to search for."
                    }
                },
                "required": ["pattern", "search_string"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_cli_command",
            "description": "Executes a CLI command in interactive mode and returns the output, error, and return code. Does not provide shell access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "The CLI command to execute."
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Overwrites the file if it already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write to."
                    },
                    "content": {
                        "type": "string",
                        "description": "New content of the file."
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Text encoding to use. Defaults to \"utf-8\"."
                    }
                },
                "required": ["path", "content", "encoding"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to retrieve the contents from."
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Text encoding to use. Defaults to \"utf-8\"."
                    }
                },
                "required": ["path", "encoding"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List information about the files and directories in the requested directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to retrieve the contents from."
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]

TOOL_IMPL = {
    "search_files": search_files,
    "execute_cli_command": execute_cli_command,
    "write_file": write_file,
    "read_file": read_file,
    "list_directory": list_directory
}