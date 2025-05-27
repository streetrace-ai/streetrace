"""Provide tools to agents."""

import contextlib
import importlib
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

from streetrace.tools.definitions.fake_tools import get_current_time, get_weather
from streetrace.utils.hide_args import hide_args

type AnyTool = Callable[..., Any] | BaseTool

_MCP_TOOLS_PREFIX = "mcp:"
_STREETRACE_TOOLS_PREFIX = "streetrace:"
_STREETRACE_TOOLS_MODULE = "streetrace.tools"


class ToolProvider:
    """Provides access to requested tools to agents."""

    def __init__(self, work_dir: Path) -> None:
        """Initialize ToolProvider."""
        self.work_dir = work_dir

    @asynccontextmanager
    async def get_tools(
        self,
        tool_refs: list[str | AnyTool],
    ) -> AsyncGenerator[list[AnyTool], None]:
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

        base_tools = [tool for tool in tool_refs if isinstance(tool, BaseTool)]
        tools.extend(base_tools)

        tool_names = [tool for tool in tool_refs if isinstance(tool, str)]

        # Add StreetRace tools
        streetrace_tools = list(self._get_streetrace_tools(tool_names, self.work_dir))
        tools.extend(streetrace_tools)

        # Get MCP servers and their tools
        mcp_servers = self._get_mcp_servers_and_tools(tool_names)

        # Use nested async context managers to handle all servers
        async with self._create_mcp_toolsets(mcp_servers) as server_toolsets:
            # Process tools from all MCP servers
            for toolset, requested_tools in server_toolsets:
                mcp_tools = await toolset.load_tools()
                # Add only the tools that were requested
                tools.extend(
                    [
                        mcp_tool
                        for mcp_tool in mcp_tools
                        if mcp_tool.name in requested_tools
                    ],
                )

            yield tools  # ✅ SINGLE yield here

    @asynccontextmanager
    async def _create_mcp_toolsets(
        self,
        mcp_servers: dict[str, set[str]],
    ) -> AsyncGenerator[list[tuple[MCPToolset, set[str]]], None]:
        """Create and yield a dictionary of MCPToolsets for all requested servers.

        Args:
            mcp_servers: Dictionary mapping server names to sets of tool names.

        Yields:
            Dictionary mapping server names to tuples of (toolset, tool_names).

        """
        toolsets: list[tuple[MCPToolset, set[str]]] = []

        # Create all toolsets
        for server_name, tool_names in mcp_servers.items():
            toolset = MCPToolset(
                connection_params=StdioServerParameters(
                    command="npx",
                    args=["-y", server_name, str(self.work_dir)],
                ),
            )
            toolsets.append((toolset, tool_names))

        # Enter all context managers
        try:
            for toolset, _ in toolsets:
                await toolset.__aenter__()

            yield toolsets

        # Exit all context managers
        finally:
            for toolset, _ in toolsets:
                with contextlib.suppress(Exception):
                    await toolset.__aexit__(None, None, None)

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
