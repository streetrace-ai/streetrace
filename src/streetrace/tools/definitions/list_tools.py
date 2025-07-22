"""list_tools tool implementation.

Provides information about available tools that can be used by agents.
"""

from pathlib import Path
from typing import Any, TypedDict

import yaml

from streetrace.log import get_logger
from streetrace.tools.definitions.result import OpResult, OpResultCode

logger = get_logger(__name__)


class ToolInfo(TypedDict):
    """Information about an available tool."""

    name: str


_DEFAULT_TOOLS = [
    ToolInfo(
        name="list_directory",
    ),
    ToolInfo(
        name="read_file",
    ),
    ToolInfo(
        name="write_file",
    ),
    ToolInfo(
        name="append_to_file",
    ),
    ToolInfo(
        name="create_directory",
    ),
    ToolInfo(
        name="find_in_files",
    ),
    ToolInfo(
        name="execute_cli_command",
    ),
    ToolInfo(
        name="list_agents",
    ),
    ToolInfo(
        name="list_tools",
    ),
    ToolInfo(
        name="run_agent",
    ),
]


class ToolListResult(OpResult):
    """Result containing the list of available tools."""

    output: list[ToolInfo] | None  # type: ignore[misc]


def _load_tools_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists() or not config_path.is_file():
        msg = f"Tools configuration file not found: {config_path}"
        raise FileNotFoundError(msg)

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if (
        not config
        or not isinstance(config, dict)
        or "tools" not in config
        or not isinstance(config["tools"], list)
    ):
        msg = f"Invalid tools configuration format in {config_path}: {config}"
        raise TypeError(msg)

    return config  # type: ignore[no-any-return]


def _get_tools_from_config(tools_config: dict[str, Any]) -> dict[str, ToolInfo]:
    """Load tools configuration from yaml file."""
    tools_dict: dict[str, ToolInfo] = {}
    counter = 0
    if "tools" not in tools_config:
        logger.warning("No tools found in configuration file: %s", tools_config)
        return tools_dict
    if not isinstance(tools_config["tools"], list):
        msg = (
            "Invalid tools configuration format: "
            f"expected list, got {tools_config['tools']}"
        )
        raise TypeError(msg)
    for tool_def in tools_config["tools"]:
        counter += 1
        if not isinstance(tool_def, dict):
            logger.error(
                "Invalid tools configuration format: %s",
                tool_def,
            )
            continue

        # Extract required fields
        name = tool_def.get("name")

        if not name:
            logger.error(
                "Invalid tools configuration format: %s",
                tool_def,
            )
            continue

        tools_dict[name] = ToolInfo(
            name=name,
        )

    if counter > 0 and not tools_dict:
        msg = "No valid tools found in configuration file. See log for details."
        raise ValueError(msg)

    return tools_dict


def list_tools(work_dir: Path) -> ToolListResult:
    """List all available tools that can be provided to agents.

    Returns information about each tool that can be used in the system,
    including built-in tools and any that require agent capabilities.

    Args:
        work_dir: Current working directory

    Returns:
        ToolListResult containing available tools

    """
    config_paths = [
        work_dir / "tools" / "tools.yaml",  # ./tools/tools.yaml
        # ../../tools/tools.yaml (relative to src/streetrace/app.py)
        Path(__file__).parent.parent.parent.parent.parent / "tools" / "tools.yaml",
    ]
    tools: dict[str, ToolInfo] = {}
    for path in config_paths:
        if not path.exists() or not path.is_file():
            continue

        try:
            tools_config = _load_tools_config(path)
            tools = {**tools, **_get_tools_from_config(tools_config)}
        except:  # noqa: E722
            logger.exception("Failed to load tools from %s", path)

    return ToolListResult(
        tool_name="list_tools",
        result=OpResultCode.SUCCESS,
        output=list(tools.values()) if tools else _DEFAULT_TOOLS,
        error=None,
    )
