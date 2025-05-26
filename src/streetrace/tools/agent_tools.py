"""Agent management tools for discovering and working with agents.

This module provides tools for AI assistants to discover available agents in the system
and the tools that can be provided to them. These tools help in building a modular,
extensible agent ecosystem.
"""

from pathlib import Path
from typing import Any

import streetrace.tools.definitions.list_agents as la
import streetrace.tools.definitions.list_tools as lt


def list_agents(work_dir: Path) -> dict[str, Any]:
    """List all available agents in the system.

    Searches for agent directories in predefined locations and returns information
    about each valid agent found.

    Args:
        work_dir: Current working directory

    Returns:
        dict[str,Any]:
            "tool_name": "list_agents"
            "result": "success" or "failure"
            "error": error message if the operation failed
            "output": List of agents if successful, each containing:
                - "name": agent name
                - "path": path to the agent
                - "description": brief description from README.md (if available)

    """
    return dict(la.list_agents(work_dir))


def list_tools(work_dir: Path) -> dict[str, Any]:
    """List all available tools that can be provided to agents.

    Returns information about each tool that can be used in the system,
    including built-in tools and any that require agent capabilities.

    Args:
        work_dir: Current working directory

    Returns:
        dict[str,Any]:
            "tool_name": "list_tools"
            "result": "success" or "failure"
            "error": error message if the operation failed
            "output": List of tools if successful, each containing:
                - "name": tool name
                - "description": brief description of the tool
                - "requires_agent": whether the tool requires agent capabilities

    """
    return dict(lt.list_tools(work_dir))
