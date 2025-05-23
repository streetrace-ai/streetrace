"""CLI command safety checking module.

This module provides functions to analyze CLI commands for safety concerns.
"""

import re
from enum import Enum
from pathlib import Path

import bashlex

from streetrace.log import get_logger

logger = get_logger(__name__)


class SafetyCategory(str, Enum):
    """Safety categories for CLI commands."""

    SAFE = "safe"
    AMBIGUOUS = "ambiguous"
    RISKY = "risky"


# List of commands considered safe by default
SAFE_COMMANDS = {
    # File navigation and viewing
    "ls",
    "dir",
    "cat",
    "less",
    "more",
    "head",
    "tail",
    # Basic file operations
    "cp",
    "mv",
    "rm",
    "mkdir",
    "touch",
    "echo",
    "find",
    "grep",
    "awk",
    "sed",
    # Git operations
    "git",
    # Build tools
    "make",
    "poetry",
    "pip",
    "npm",
    "yarn",
    "cargo",
    # Python related
    "python",
    "python3",
    "pytest",
    "mypy",
    "ruff",
    "flake8",
    # Package managers
    "apt-get",
    "apt",
    "brew",
    # Process viewing (not modification)
    "ps",
    "top",
    "htop",
    # Other utilities
    "diff",
    "wc",
    "sort",
    "uniq",
    "cut",
    "which",
    "whoami",
    "pwd",
}


def _parse_command(args: str | list[str]) -> list[tuple[str, list[str]]]:
    """Parse command arguments into a list of command and arguments.

    Args:
        args: The command string or list of command arguments

    Returns:
        A list of tuples containing (command, [arguments])

    """
    args_str = " ".join(args) if isinstance(args, list) else args

    parsed_commands: list[tuple[str, list[str]]] = []

    try:
        # Parse the command using bashlex
        parsed = bashlex.parse(args_str)

        for command_node in parsed:
            _extract_commands_from_node(command_node, parsed_commands)

        if not parsed_commands:
            # If parsing didn't yield anything, fall back to simple splitting
            if isinstance(args, list):
                if args:
                    parsed_commands.append((args[0], args[1:]))
            else:
                parts = args_str.split()
                if parts:
                    parsed_commands.append((parts[0], parts[1:]))

    except Exception as e:
        logger.exception(
            "Error parsing command",
            extra={"error": str(e), "command_str": args_str},
        )

        # Fall back to basic parsing if bashlex fails
        if isinstance(args, list):
            if args:
                return [(args[0], args[1:])]
            return []
        parts = args_str.split()
        if parts:
            return [(parts[0], parts[1:])]
        return []

    return parsed_commands


def _extract_commands_from_node(
    node: object,
    parsed_commands: list[tuple[str, list[str]]],
) -> None:
    """Extract commands and arguments from a bashlex node.

    Args:
        node: The bashlex AST node
        parsed_commands: List to add extracted commands to

    """
    if getattr(node, "kind", None) == "command":
        command = None
        args = []

        for part in getattr(node, "parts", []):
            if part.kind == "word" and command is None:
                command = part.word
            elif part.kind == "word":
                args.append(part.word)
            elif hasattr(part, "parts"):
                _extract_commands_from_node(part, parsed_commands)

        if command:
            parsed_commands.append((command, args))

    # Process pipe commands, list commands, etc.
    elif hasattr(node, "parts"):
        for part in getattr(node, "parts", []):
            _extract_commands_from_node(part, parsed_commands)


def _analyze_path_safety(path_str: str) -> tuple[bool, bool]:
    """Analyze a path string for safety concerns.

    Args:
        path_str: The path string to analyze

    Returns:
        Tuple of (is_relative, is_safe)
        - is_relative: True if the path is relative, False if absolute
        - is_safe: True if the path doesn't try to escape current directory

    """
    # Check if the path seems to be a flag/option rather than a path
    if path_str.startswith("-"):
        return True, True

    # Check if it's an absolute path
    is_relative = not Path(path_str).is_absolute()

    # Check for directory traversal attempts
    path_parts = Path(path_str).parts

    # Initialize with current depth 0
    depth = 0

    # Track if path tries to escape
    for part in path_parts:
        if part == "..":
            depth -= 1
            # If depth becomes negative, it's trying to go above current directory
            if depth < 0:
                return is_relative, False
        elif part != ".":  # Ignore '.' as it doesn't change depth
            depth += 1

    return is_relative, is_relative


def _analyze_command_safety(  # noqa: C901, PLR0911
    command: str,
    args: list[str],
) -> SafetyCategory:
    """Analyze the safety of a command and its arguments.

    Args:
        command: The command string
        args: List of arguments to the command

    Returns:
        A SafetyCategory value

    """
    # Check if the command is in our safe list
    is_safe_command = command in SAFE_COMMANDS

    # If no command found or empty command, consider risky
    if not command:
        logger.warning(
            "Empty command detected",
            extra={"command": command, "command_args": args},
        )
        return SafetyCategory.RISKY

    # If no arguments provided, be cautious
    if not args:
        if is_safe_command:
            return SafetyCategory.AMBIGUOUS
        return SafetyCategory.RISKY

    # Analyze path safety for each argument
    contains_absolute_path = False
    contains_unsafe_path = False
    args_look_like_paths = False

    for arg in args:
        # Skip flags/options from path analysis
        if arg.startswith("-"):
            continue

        # Simple heuristic to check if argument looks like a path
        # (contains slash, dot, or common extensions)
        path_pattern = re.compile(
            r"[/\\.]|\.(py|js|txt|md|json|yaml|yml|xml|csv|html|css)$",
        )
        if path_pattern.search(arg):
            args_look_like_paths = True
            is_relative, is_safe = _analyze_path_safety(arg)

            if not is_relative:
                contains_absolute_path = True

            if not is_safe:
                contains_unsafe_path = True

    # Determine safety category based on analysis
    if is_safe_command and not contains_absolute_path and not contains_unsafe_path:
        if args_look_like_paths:
            return SafetyCategory.SAFE
        return SafetyCategory.AMBIGUOUS

    if contains_absolute_path or contains_unsafe_path:
        return SafetyCategory.RISKY

    # Command not in safe list but arguments don't seem problematic
    return SafetyCategory.AMBIGUOUS


def cli_safe_category(args: str | list[str]) -> str:
    """Determine the safety category of a CLI command.

    The function analyzes the command and its arguments to classify them into
    one of three safety categories:

    - 'safe': Commands from the pre-configured safe list with only relative paths
    - 'ambiguous': Commands not in the safe list but without obvious risks
    - 'risky': Commands with absolute paths or directory traversal attempts

    Args:
        args: The CLI command as a string or list of arguments

    Returns:
        A string representing the safety category: 'safe', 'ambiguous', or 'risky'

    """
    parsed_commands = _parse_command(args)

    if not parsed_commands:
        logger.warning("No commands parsed from input", extra={"command_input": args})
        return SafetyCategory.RISKY

    # Analyze each command and take the most restrictive category
    categories = []

    for command, cmd_args in parsed_commands:
        category = _analyze_command_safety(command, cmd_args)
        categories.append(category)
        logger.debug(
            "Command safety analysis",
            extra={
                "command": command,
                "command_args": cmd_args,
                "category": category,
            },
        )

    # Return the most restrictive category (risky > ambiguous > safe)
    if SafetyCategory.RISKY in categories:
        return SafetyCategory.RISKY
    if SafetyCategory.AMBIGUOUS in categories:
        return SafetyCategory.AMBIGUOUS
    return SafetyCategory.SAFE
