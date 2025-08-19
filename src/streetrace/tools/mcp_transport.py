"""MCP transport connection configuration classes."""

from dataclasses import dataclass
from typing import Any


@dataclass
class StdioConnectionConfig:
    """Configuration for STDIO-based MCP connections."""

    command: str
    args: list[str]
    cwd: str | None = None
    env: dict[str, str] | None = None


@dataclass
class HttpConnectionConfig:
    """Configuration for HTTP-based MCP connections."""

    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None


@dataclass
class SSEConnectionConfig:
    """Configuration for Server-Sent Events (SSE) based MCP connections."""

    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None


type MCPConnectionConfig = (
    StdioConnectionConfig | HttpConnectionConfig | SSEConnectionConfig
)


def parse_connection_config(config_data: dict[str, Any]) -> MCPConnectionConfig:
    """Parse connection configuration from dictionary data.

    Args:
        config_data: Dictionary containing connection configuration

    Returns:
        Appropriate connection configuration instance

    Raises:
        ValueError: If configuration type is invalid or required fields are missing

    """
    config_type = config_data.get("type", "stdio").lower()

    if config_type == "stdio":
        command = config_data.get("command")
        if not command:
            msg = "STDIO configuration requires 'command' field"
            raise ValueError(msg)

        return StdioConnectionConfig(
            command=command,
            args=config_data.get("args", []),
            cwd=config_data.get("cwd"),
            env=config_data.get("env"),
        )

    if config_type == "http":
        url = config_data.get("url")
        if not url:
            msg = "HTTP configuration requires 'url' field"
            raise ValueError(msg)

        return HttpConnectionConfig(
            url=url,
            headers=config_data.get("headers"),
            timeout=config_data.get("timeout"),
        )

    if config_type == "sse":
        url = config_data.get("url")
        if not url:
            msg = "SSE configuration requires 'url' field"
            raise ValueError(msg)

        return SSEConnectionConfig(
            url=url,
            headers=config_data.get("headers"),
            timeout=config_data.get("timeout"),
        )

    msg = f"Unknown connection type: {config_type}"
    raise ValueError(msg)
