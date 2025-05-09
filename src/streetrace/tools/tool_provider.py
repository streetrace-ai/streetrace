"""Provide tools to agents."""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

from streetrace.tools.fake_tools import get_current_time, get_weather

AnyTool = Callable | BaseTool | None


class ToolProvider:
    """Provides access to requested tools to agents."""

    @asynccontextmanager
    async def get_tools(
        self,
        tool_refs: list[str],
    ) -> AsyncGenerator[list[AnyTool], None]:
        """Yield a full list of tool implementations as a context-managed resource."""
        tools: list[AnyTool] = []

        # Add static tools
        if "get_weather" in tool_refs:
            tools.append(get_weather)
        if "get_current_time" in tool_refs:
            tools.append(get_current_time)

        # Add MCP tools via context-managed server connection
        async with MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", str(Path.cwd())],
            ),
        ) as toolset:
            mcp_tools = await toolset.load_tools()
            tools.extend(mcp_tools)
            yield tools  # ✅ SINGLE yield here
