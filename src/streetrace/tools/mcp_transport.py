"""MCP transport configuration classes."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class StdioTransport(BaseModel):
    """Configuration for STDIO-based MCP connections."""

    type: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str | None = Field(
        default=None,
        description="MCP Server cwd, overrides allowed dirs.",
    )
    env: dict[str, str] | None = None


class HttpTransport(BaseModel):
    """Configuration for HTTP-based MCP connections."""

    type: Literal["http"] = "http"
    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None


class SseTransport(BaseModel):
    """Configuration for Server-Sent Events (SSE) based MCP connections."""

    type: Literal["sse"] = "sse"
    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None


Transport = StdioTransport | HttpTransport | SseTransport


def parse_transport_config(config_data: dict[str, Any] | str) -> Transport:
    """Parse transport configuration from dictionary data.

    Args:
        config_data: Dictionary containing transport configuration

    Returns:
        Appropriate transport configuration instance

    Raises:
        ValueError: If configuration type is invalid or required fields are missing

    """
    if isinstance(config_data, str):
        import json

        config_data = json.loads(config_data)

        if not isinstance(config_data, dict):
            msg = "Transport configuration must be a dictionary or JSON dictionary"
            raise TypeError(msg)

    config_type = config_data.get("type", "stdio").lower()

    if config_type == "stdio":
        return StdioTransport.model_validate(config_data)
    if config_type == "http":
        return HttpTransport.model_validate(config_data)
    if config_type == "sse":
        return SseTransport.model_validate(config_data)
    msg = f"Unknown transport type: {config_type}"
    raise ValueError(msg)
