"""Provide tools to agents."""

import importlib
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.base_toolset import BaseToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        SseConnectionParams,
        StdioConnectionParams,
        StreamableHTTPConnectionParams,
    )
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.log import get_logger
from streetrace.tools.mcp_transport import (
    StdioTransport,
    Transport,
    parse_transport_config,
)
from streetrace.tools.tool_refs import (
    CallableToolRef,
    McpToolRef,
    StreetraceToolRef,
    ToolRef,
)
from streetrace.utils.hide_args import hide_args

type AnyTool = Callable[..., Any] | "BaseTool" | "BaseToolset" | ToolRef
type AdkTool = Callable[..., Any] | "BaseTool" | "BaseToolset"

logger = get_logger(__name__)

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


def _args_with_allowed_dirs(
    transport: StdioTransport,
    work_dir: Path,
) -> list[str]:
    """Ensure work_dir is included in args if not already present."""
    args = transport.args or []
    if str(work_dir) not in args:
        # use cwd as allowed directory
        if transport.cwd:
            if str(transport.cwd) not in args:
                args.append(str(transport.cwd))
        elif str(work_dir) not in args:
            # Ensure work_dir is included in allowed directories
            args.append(str(work_dir))
    return args


def _log_retrieved_tools(tools: list[AdkTool]) -> None:
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

    def get_tools(
        self,
        tool_refs: Sequence[AnyTool],
    ) -> list[AdkTool]:
        """Get a full list of tool implementations as a context-managed resource.

        Args:
            tool_refs: List of tool references to load.
                Can be:
                - Legacy string format: "prefix:server/path::tool_name"
                  or "static_tool_name"
                - ToolRef objects (McpToolRef, StreetraceToolRef, CallableToolRef)
                - AnyTool objects (already instantiated tools)

        Returns:
            List of tool implementations from all requested sources.

        """
        tools: list[AdkTool] = []

        for tool_ref in tool_refs:
            if isinstance(tool_ref, (McpToolRef, StreetraceToolRef, CallableToolRef)):
                tools.extend(self._process_tool_ref(tool_ref))
            else:
                # Assume it's an already instantiated tool
                tools.append(tool_ref)

        _log_retrieved_tools(tools)

        return tools

    def _process_tool_ref(self, tool_ref: ToolRef) -> Iterable[AdkTool]:
        """Process a structured ToolRef and return list of tool implementations.

        Args:
            tool_ref: ToolRef object (McpToolRef, StreetraceToolRef, or CallableToolRef)

        Returns:
            List of tool implementations

        """
        if tool_ref.kind == "mcp":
            yield from self._process_mcp_tool_ref(tool_ref)
        elif tool_ref.kind == "streetrace":
            yield from self._process_streetrace_tool_ref(tool_ref)
        elif tool_ref.kind == "callable":
            yield from self._process_callable_tool_ref(tool_ref)
        else:
            msg = f"Unknown tool reference type: {type(tool_ref)}"
            raise TypeError(msg)

    def _process_mcp_tool_ref(self, tool_ref: McpToolRef) -> "Iterable[MCPToolset]":
        """Process an MCP tool reference."""
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

        server_def = tool_ref.server
        # Handle server configuration

        connection_params = self._create_connection_params(server_def)

        # Create tool filter
        tool_filter: list[str] | None = None
        if tool_ref.tools and not any(t in ["*", "all"] for t in tool_ref.tools):
            tool_filter = tool_ref.tools

        toolset = MCPToolset(
            connection_params=connection_params,
            tool_filter=tool_filter,
        )

        logger.debug(
            "Created MCP toolset from ToolRef",
            extra={
                "server": tool_ref.server,
                "tools": tool_ref.tools,
                "connection_type": type(connection_params).__name__,
            },
        )

        return [toolset]

    def _process_streetrace_tool_ref(
        self,
        tool_ref: StreetraceToolRef,
    ) -> Iterable[AdkTool]:
        """Process a StreetRace tool reference."""
        # Convert delimiter and build full import path
        full_module_path = f"{_STREETRACE_TOOLS_MODULE}.{tool_ref.module}"

        # Dynamically import module
        module = importlib.import_module(full_module_path)

        # Get function from module
        func = getattr(module, tool_ref.function)

        if not callable(func):
            msg = f"{tool_ref} resolved to non-callable: {func}"
            raise TypeError(msg)

        logger.debug(
            "Created StreetRace tool from ToolRef",
            extra={
                "tool_module": tool_ref.module,
                "function": tool_ref.function,
            },
        )

        return [hide_args(func, work_dir=self.work_dir)]

    def _process_callable_tool_ref(
        self,
        tool_ref: CallableToolRef,
    ) -> Iterable[AdkTool]:
        """Process a callable tool reference."""
        # Parse import path
        if ":" not in tool_ref.import_path:
            msg = (
                f"Invalid import path format: {tool_ref.import_path}. "
                "Expected 'module:function'"
            )
            raise ValueError(msg)

        module_name, func_name = tool_ref.import_path.split(":", 1)

        # Dynamically import and get the function
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)

        if not callable(func):
            msg = f"Import path {tool_ref.import_path} resolved to non-callable: {func}"
            raise TypeError(msg)

        logger.debug(
            "Created callable tool from ToolRef",
            extra={
                "import_path": tool_ref.import_path,
            },
        )

        return [func]

    def _create_connection_params(
        self,
        transport: Transport | dict[str, Any] | str,
    ) -> "StdioConnectionParams | StreamableHTTPConnectionParams | SseConnectionParams":
        """Create appropriate connection parameters based on the defined transport.

        Args:
            transport: MCP transport configuration.

        Returns:
            Appropriate connection parameters instance

        """
        if isinstance(transport, (dict, str)):
            transport = parse_transport_config(transport)

        from google.adk.tools.mcp_tool.mcp_session_manager import (
            SseConnectionParams,
            StdioConnectionParams,
            StreamableHTTPConnectionParams,
        )
        from mcp import StdioServerParameters

        if transport.type == "stdio":
            server_params = StdioServerParameters(
                command=transport.command,
                args=_args_with_allowed_dirs(transport, self.work_dir),
                cwd=transport.cwd or self.work_dir,
                env=transport.env,
            )
            return StdioConnectionParams(server_params=server_params)

        if transport.type == "http":
            # Build kwargs excluding None values for Pydantic validation
            kwargs: dict[str, Any] = {
                "url": transport.url,
                "headers": transport.headers or {},
            }
            if transport.timeout is not None:
                kwargs["timeout"] = transport.timeout
            return StreamableHTTPConnectionParams(**kwargs)

        if transport.type == "sse":
            # Build kwargs excluding None values for Pydantic validation
            kwargs = {"url": transport.url, "headers": transport.headers or {}}
            if transport.timeout is not None:
                kwargs["timeout"] = transport.timeout
            return SseConnectionParams(**kwargs)

        msg = f"Unknown transport type: {transport.type}"
        raise TypeError(msg)
