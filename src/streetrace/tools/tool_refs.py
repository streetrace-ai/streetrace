"""Tool reference models for structured tool configuration."""

from typing import Literal

from pydantic import BaseModel, Field

from streetrace.tools.mcp_transport import Transport


class McpToolRef(BaseModel):
    """Reference to MCP (Model Context Protocol) tools."""

    kind: Literal["mcp"] = "mcp"
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
