"""Pydantic models for YAML agent specification."""

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def expand_env_vars(value: str) -> str:
    """Expand environment variables in strings using ${VAR:-default} syntax.

    Args:
        value: String that may contain environment variables

    Returns:
        String with environment variables expanded

    """

    def replace_var(match: re.Match[str]) -> str:
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.environ.get(var_name, default)
        return os.environ.get(var_expr, "")

    # Match ${VAR} or ${VAR:-default}
    pattern = r"\$\{([^}]+)\}"
    return re.sub(pattern, replace_var, value)


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class StdioServerConfig(BaseModel):
    """Configuration for stdio MCP server."""

    type: Literal[TransportType.STDIO] = TransportType.STDIO
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("command", "args", mode="before")
    @classmethod
    def expand_command_env_vars(cls, v: object) -> object:
        """Expand environment variables in command and args."""
        if isinstance(v, str):
            return expand_env_vars(v)
        if isinstance(v, list):
            return [
                expand_env_vars(item) if isinstance(item, str) else item for item in v
            ]
        return v

    @field_validator("env", mode="before")
    @classmethod
    def expand_env_dict(cls, v: object) -> object:
        """Expand environment variables in env dict values."""
        if isinstance(v, dict):
            return {
                k: expand_env_vars(val) if isinstance(val, str) else val
                for k, val in v.items()
            }
        return v


class HttpServerConfig(BaseModel):
    """Configuration for HTTP/SSE MCP server."""

    type: Literal[TransportType.HTTP, TransportType.SSE]
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: int = 10

    @field_validator("url", mode="before")
    @classmethod
    def expand_url_env_vars(cls, v: object) -> object:
        """Expand environment variables in URL."""
        return expand_env_vars(v) if isinstance(v, str) else v

    @field_validator("headers", mode="before")
    @classmethod
    def expand_headers_env_vars(cls, v: object) -> object:
        """Expand environment variables in headers values."""
        if isinstance(v, dict):
            return {
                k: expand_env_vars(val) if isinstance(val, str) else val
                for k, val in v.items()
            }
        return v


ServerConfig = StdioServerConfig | HttpServerConfig


class StreetraceToolSpec(BaseModel):
    """Specification for StreetRace internal tool."""

    module: str
    function: str


class McpToolSpec(BaseModel):
    """Specification for MCP tool."""

    name: str
    server: ServerConfig
    tools: list[str] = Field(default_factory=list)


class ToolSpec(BaseModel):
    """Tool specification - either streetrace or mcp."""

    streetrace: StreetraceToolSpec | None = None
    mcp: McpToolSpec | None = None

    @model_validator(mode="after")
    def validate_tool_spec(self) -> "ToolSpec":
        """Ensure exactly one tool type is specified."""
        if self.streetrace and self.mcp:
            msg = "Tool specification cannot have both 'streetrace' and 'mcp' fields"
            raise ValueError(msg)
        if not self.streetrace and not self.mcp:
            msg = "Tool specification must have either 'streetrace' or 'mcp' field"
            raise ValueError(msg)
        return self


class AgentRef(BaseModel):
    """Reference to another agent file."""

    ref: str = Field(alias="$ref")

    @field_validator("ref")
    @classmethod
    def validate_ref_path(cls, v: str) -> str:
        """Validate that ref is a reasonable file path."""
        if not v or v.startswith("http"):
            msg = f"Agent reference must be a local file path, got: {v}"
            raise ValueError(msg)
        return v


class AdkConfig(BaseModel):
    """ADK-specific configuration passed through to Agent constructor."""

    generate_content_config: dict[str, Any] = Field(default_factory=dict)
    disallow_transfer_to_parent: bool = False
    disallow_transfer_to_peers: bool = False
    include_contents: str = "default"
    input_schema: str | None = None
    output_schema: str | None = None
    output_key: str | None = None
    planner: str | None = None
    code_executor: str | None = None


class InlineAgentSpec(BaseModel):
    """Inline agent specification."""

    agent: "YamlAgentSpec"


class YamlAgentSpec(BaseModel):
    """YAML agent specification model."""

    version: Literal[1] = 1
    kind: Literal["agent"] = "agent"
    name: str
    description: str
    model: str | None = None
    instruction: str | None = None
    global_instruction: str | None = None
    adk: AdkConfig = Field(default_factory=AdkConfig)
    tools: list[ToolSpec | AgentRef | InlineAgentSpec] = Field(default_factory=list)
    sub_agents: list[AgentRef | InlineAgentSpec] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name follows Python identifier rules."""
        if not v or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", v):
            msg = f"Agent name must be a valid Python identifier, got: {v}"
            raise ValueError(msg)
        return v

    @field_validator("instruction", "global_instruction", mode="before")
    @classmethod
    def expand_instruction_env_vars(cls, v: object) -> object:
        """Expand environment variables in instruction strings."""
        return expand_env_vars(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def validate_output_schema_constraint(self) -> "YamlAgentSpec":
        """Validate ADK constraint: output_schema cannot coexist with tools."""
        # tools/sub_agents
        if self.adk.output_schema and (self.tools or self.sub_agents):
            msg = (
                "Agent cannot have output_schema with tools or sub_agents "
                "(ADK constraint)"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_global_instruction_at_root_only(self) -> "YamlAgentSpec":
        """Validate that global_instruction is only used at root level."""
        # Note: This validation will be enforced during loading when we know the context
        return self


# Now update the forward reference
AgentRef.model_rebuild()
InlineAgentSpec.model_rebuild()


class YamlAgentDocument(BaseModel):
    """Root agent document with resolved references."""

    spec: YamlAgentSpec
    file_path: Path | None = None  # Path where this was loaded from

    def get_name(self) -> str:
        """Get the agent name."""
        return self.spec.name

    def get_description(self) -> str:
        """Get the agent description."""
        return self.spec.description
