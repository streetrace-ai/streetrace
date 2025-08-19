"""Provide tools to agents."""

import importlib
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.base_toolset import BaseToolset
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.log import get_logger
from streetrace.tools.definitions.fake_tools import get_current_time, get_weather
from streetrace.tools.mcp_transport import (
    HttpConnectionConfig,
    SSEConnectionConfig,
    StdioConnectionConfig,
    parse_connection_config,
)
from streetrace.utils.hide_args import hide_args

type AnyTool = Callable[..., Any] | "BaseTool" | "BaseToolset"

logger = get_logger(__name__)

_MCP_TOOLS_PREFIX = "mcp:"
_STREETRACE_TOOLS_PREFIX = "streetrace:"
_STREETRACE_TOOLS_MODULE = "streetrace.tools"


def _is_base_tool(tool: AnyTool | str) -> bool:
    if isinstance(tool, str):
        return False
    if "google.adk.tools.base_tool" in sys.modules:
        return isinstance(tool, sys.modules["google.adk.tools.base_tool"].BaseTool)
    return False


def _is_base_toolset(tool: AnyTool | str) -> bool:
    if isinstance(tool, str):
        return False
    if "google.adk.tools.base_toolset" in sys.modules:
        return isinstance(
            tool,
            sys.modules["google.adk.tools.base_toolset"].BaseToolset,
        )
    return False


def _as_mcp_toolset(tool: AnyTool | str) -> "MCPToolset | None":
    if isinstance(tool, str):
        return None
    if "google.adk.tools.mcp_tool.mcp_toolset" in sys.modules and isinstance(
        tool,
        sys.modules["google.adk.tools.mcp_tool.mcp_toolset"].MCPToolset,
    ):
        return cast("MCPToolset", tool)
    return None


def _log_retrieved_tools(tools: list[AnyTool]) -> None:
    """Log the retrieved tools."""
    retrieved_tools = []
    for tool in tools:
        if _is_base_toolset(tool):
            tool_names = (
                getattr(tool, "tool_filter")  # noqa: B009
                if hasattr(tool, "tool_filter") and getattr(tool, "tool_filter")  # noqa: B009
                else "*"
            )
            retrieved_tools.append(f"{tool.__class__.__name__}, {tool_names}")
        elif _is_base_tool(tool):
            retrieved_tools.append(
                f"{tool.__class__.__name__}, {getattr(tool, 'name')}",  # noqa: B009
            )
        elif callable(tool):
            retrieved_tools.append(f"{tool.__class__.__name__}, {tool.__name__}")
    logger.info("Retrieved tools:\n%s", retrieved_tools)


class ToolProvider:
    """Provides access to requested tools to agents."""

    def __init__(self, work_dir: Path) -> None:
        """Initialize ToolProvider."""
        self.work_dir = work_dir

    async def release_tools(self, tools: list[AnyTool]) -> None:
        """Release all tools."""
        for tool in tools:
            mcp_tool = _as_mcp_toolset(tool)
            if mcp_tool:
                await mcp_tool.close()

    async def get_tools(
        self,
        tool_refs: list[str | AnyTool],
    ) -> list[AnyTool]:
        """Yield a full list of tool implementations as a context-managed resource.

        Args:
            tool_refs: List of tool references to load.
                Format: "prefix:server/path::tool_name" or "static_tool_name"

        Yields:
            List of tool implementations from all requested sources.

        """
        tools: list[AnyTool] = []

        # Add static tools
        if "get_weather" in tool_refs:
            tools.append(get_weather)
        if "get_current_time" in tool_refs:
            tools.append(get_current_time)

        base_tools = [
            tool
            for tool in tool_refs
            if _is_base_tool(tool) and not isinstance(tool, str)
        ]
        tools.extend(base_tools)

        tool_names = [tool for tool in tool_refs if isinstance(tool, str)]

        # Add StreetRace tools
        streetrace_tools = list(self._get_streetrace_tools(tool_names, self.work_dir))
        tools.extend(streetrace_tools)

        # Get MCP servers and their tools
        mcp_servers = self._get_mcp_servers_and_tools(tool_names)

        mcp_toolsets = self._create_mcp_toolsets(mcp_servers)
        tools.extend(mcp_toolsets)

        _log_retrieved_tools(tools)

        return tools

    def _create_mcp_toolsets(
        self,
        mcp_servers: dict[str, set[str]],
    ) -> list["MCPToolset"]:
        """Create and yield a list of MCPToolsets for all requested servers.

        Args:
            mcp_servers: Dictionary mapping server names to sets of tool names.

        Returns:
            List of MCPToolset instances.

        """
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

        toolsets: list[MCPToolset] = []

        # Create all toolsets
        for server_name, tool_names in mcp_servers.items():
            tool_filter: list[str] | None = None
            if len(tool_names.intersection(["all", "*"])) == 0:
                tool_filter = list(tool_names)

            # Try to parse server_name as connection config first,
            # otherwise fall back to default STDIO behavior
            connection_params = self._create_connection_params(server_name)

            toolset = MCPToolset(
                connection_params=connection_params,
                tool_filter=tool_filter,
            )
            logger.debug(
                "Created MCP toolset",
                extra={
                    "server_name": server_name,
                    "work_dir": str(self.work_dir),
                    "tool_filter": tool_filter,
                    "connection_type": type(connection_params).__name__,
                },
            )

            toolsets.append(toolset)

        return toolsets

    def _get_streetrace_tools(
        self,
        tool_refs: list[str],
        work_dir: Path,
    ) -> Iterator[AnyTool]:
        """Get StreetRace tools from tool references.

        Args:
            tool_refs: List of tool references.
            work_dir: Working directory to pass to tools.

        Yields:
            Tools with work_dir argument hidden.

        """
        tool_refs = [
            tool_ref[len(_STREETRACE_TOOLS_PREFIX) :]
            for tool_ref in tool_refs
            if tool_ref.startswith(_STREETRACE_TOOLS_PREFIX)
        ]

        for tool_ref in tool_refs:
            # Convert delimiter and build full import path
            module_name, func_name = tool_ref.split("::")
            full_module_path = f"{_STREETRACE_TOOLS_MODULE}.{module_name}"

            # Dynamically import module
            module = importlib.import_module(full_module_path)

            # Get function from module
            func = getattr(module, func_name)

            if not callable(func):
                msg = "%s resolved to non-callable: %s"
                raise TypeError(msg, tool_ref, func)

            yield hide_args(func, work_dir=work_dir)

    def _get_mcp_servers_and_tools(self, tool_refs: list[str]) -> dict[str, set[str]]:
        """Extract MCP server names and tool names from tool references.

        Args:
            tool_refs: List of tool references.

        Returns:
            Dictionary mapping server names to sets of tool names.

        """
        tool_refs = [
            tool_ref[len(_MCP_TOOLS_PREFIX) :]
            for tool_ref in tool_refs
            if tool_ref.startswith(_MCP_TOOLS_PREFIX)
        ]

        servers: dict[str, set[str]] = {}

        for tool_ref in tool_refs:
            server_name, func_name = tool_ref.split("::")
            if server_name not in servers:
                servers[server_name] = {func_name}
            else:
                servers[server_name].add(func_name)

        return servers

    def _create_connection_params(
        self,
        server_identifier: str,
    ) -> Any:
        """Create appropriate connection parameters based on server identifier.

        Args:
            server_identifier: Either a server name for default STDIO,
                             or a JSON string with connection config

        Returns:
            Appropriate connection parameters instance

        """
        import json

        from google.adk.tools.mcp_tool.mcp_session_manager import (
            SseConnectionParams,
            StreamableHTTPConnectionParams,
        )
        from mcp import StdioServerParameters

        # Try to parse as JSON config first
        try:
            config_data = json.loads(server_identifier)
            config = parse_connection_config(config_data)

            if isinstance(config, StdioConnectionConfig):
                return StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    cwd=config.cwd or self.work_dir,
                    env=config.env,
                )
            if isinstance(config, HttpConnectionConfig):
                # Build kwargs excluding None values for Pydantic validation
                kwargs: dict[str, Any] = {
                    "url": config.url,
                    "headers": config.headers or {},
                }
                if config.timeout is not None:
                    kwargs["timeout"] = config.timeout
                return StreamableHTTPConnectionParams(**kwargs)
            if isinstance(config, SSEConnectionConfig):
                # Build kwargs excluding None values for Pydantic validation
                kwargs = {"url": config.url, "headers": config.headers or {}}
                if config.timeout is not None:
                    kwargs["timeout"] = config.timeout
                return SseConnectionParams(**kwargs)

        except (json.JSONDecodeError, ValueError, KeyError):
            # Fall back to default STDIO behavior for simple server names
            pass

        # Default STDIO connection for simple server names
        return StdioServerParameters(
            command="npx",
            args=["-y", server_identifier, str(self.work_dir)],
            cwd=self.work_dir,
        )
