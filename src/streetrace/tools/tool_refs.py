"""Tool reference models for structured tool configuration."""

from typing import Literal

from pydantic import BaseModel, Field

from streetrace.tools.mcp_transport import Transport


class McpToolRef(BaseModel):
    """Reference to MCP (Model Context Protocol) tools."""

    kind: Literal["mcp"] = "mcp"
    name: str  # MCP server name
    server: Transport  # inline transport config
    tools: list[str] = Field(default_factory=list)  # ["*", "all"] -> wildcard


class StreetraceToolRef(BaseModel):
    """Reference to StreetRace internal tools."""

    kind: Literal["streetrace"] = "streetrace"
    module: str  # e.g., "fs", "cli"
    function: str  # e.g., "list_files", "run_command"


class CallableToolRef(BaseModel):
    """Reference to directly callable functions."""

    kind: Literal["callable"] = "callable"
    import_path: str  # "package.module:function"


ToolRef = McpToolRef | StreetraceToolRef | CallableToolRef


def tool_name(tool_ref: ToolRef) -> str:
    """Return the name of the tool."""
    if tool_ref.kind == "mcp":
        return tool_ref.name
    if tool_ref.kind == "streetrace":
        return f"{tool_ref.module}:{tool_ref.function}"
    if tool_ref.kind == "callable":
        return tool_ref.import_path
    msg = f"Unknown tool reference kind: {tool_ref.kind}"
    raise TypeError(msg)
