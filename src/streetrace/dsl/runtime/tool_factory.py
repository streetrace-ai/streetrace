"""Factory for creating ToolRef objects from DSL tool configurations.

Convert DSL tool definitions (emitted by code generator) into proper
ToolRef objects that can be used by the tool provider.
"""

import os
import re
from typing import Any

from streetrace.log import get_logger
from streetrace.tools.mcp_transport import HttpTransport, SseTransport
from streetrace.tools.tool_refs import McpToolRef, StreetraceToolRef

logger = get_logger(__name__)


def create_mcp_tool_ref(name: str, tool_def: dict[str, Any]) -> McpToolRef:
    """Create an McpToolRef from a DSL tool definition.

    Build the transport with proper headers based on auth configuration.

    Args:
        name: Tool name.
        tool_def: Tool definition dict with url, auth, headers, etc.

    Returns:
        McpToolRef with configured transport.

    """
    url = tool_def.get("url", "")
    headers = _build_headers(tool_def)
    timeout_raw = tool_def.get("timeout")
    timeout = float(timeout_raw) if timeout_raw is not None else None

    # Determine transport type from URL
    transport: HttpTransport | SseTransport
    if url.endswith("/sse") or "/sse" in url.lower():
        transport = SseTransport(url=url, headers=headers, timeout=timeout)
    else:
        transport = HttpTransport(url=url, headers=headers, timeout=timeout)

    return McpToolRef(
        name=name,
        server=transport,
        tools=["*"],  # Include all tools from this server
    )


def _build_headers(tool_def: dict[str, Any]) -> dict[str, str] | None:
    """Build HTTP headers from tool definition.

    Combine explicit headers with auth-derived Authorization header.

    Args:
        tool_def: Tool definition dict.

    Returns:
        Headers dict or None if no headers needed.

    """
    headers: dict[str, str] = {}

    # Add explicit headers first
    explicit_headers = tool_def.get("headers")
    if explicit_headers and isinstance(explicit_headers, dict):
        headers.update(explicit_headers)

    # Add Authorization header from auth config
    auth = tool_def.get("auth")
    if auth and isinstance(auth, dict):
        auth_header = _build_auth_header(auth)
        if auth_header:
            headers["Authorization"] = auth_header

    return headers if headers else None


def _build_auth_header(auth: dict[str, Any]) -> str | None:
    """Build Authorization header value from auth config.

    Args:
        auth: Auth configuration with 'type' and 'value' keys.

    Returns:
        Authorization header value or None.

    """
    auth_type = auth.get("type", "").lower()
    auth_value = auth.get("value", "")

    if not auth_value:
        return None

    # Resolve environment variable interpolation
    resolved_value = _resolve_interpolation(auth_value)

    if auth_type == "bearer":
        return f"Bearer {resolved_value}"
    if auth_type == "basic":
        return f"Basic {resolved_value}"

    logger.warning("Unknown auth type: %s", auth_type)
    return None


def _resolve_interpolation(value: str) -> str:
    """Resolve environment variable interpolation in a string.

    Support patterns like:
    - ${VAR_NAME} - environment variable
    - ${env:VAR_NAME} - explicit env prefix

    Args:
        value: String that may contain interpolation patterns.

    Returns:
        String with interpolations resolved.

    """
    # Pattern for ${VAR} or ${env:VAR}
    pattern = r"\$\{(?:env:)?([^}]+)\}"

    def replace_env(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name, "")
        if not env_value:
            logger.warning("Environment variable not set: %s", var_name)
        return env_value

    return re.sub(pattern, replace_env, value)


def create_builtin_tool_refs(
    tool_name: str,
    tool_def: dict[str, Any],
) -> list[StreetraceToolRef]:
    """Create StreetraceToolRef objects for a builtin tool definition.

    Args:
        tool_name: Name of the tool.
        tool_def: Tool definition dict.

    Returns:
        List of StreetraceToolRef objects.

    """
    # Default fs tools to provide
    fs_tool_functions = [
        "read_file",
        "create_directory",
        "write_file",
        "append_to_file",
        "list_directory",
        "find_in_files",
    ]

    cli_tool_functions = [
        "execute_cli_command",
    ]

    refs: list[StreetraceToolRef] = []

    # Check for specific builtin ref patterns
    builtin_ref = tool_def.get("builtin_ref") or tool_def.get("url")
    if builtin_ref:
        # Handle patterns like "streetrace.fs", "streetrace.cli"
        if "fs" in str(builtin_ref).lower():
            refs.extend(
                StreetraceToolRef(module="fs_tool", function=func)
                for func in fs_tool_functions
            )
        elif "cli" in str(builtin_ref).lower():
            refs.extend(
                StreetraceToolRef(module="cli_tool", function=func)
                for func in cli_tool_functions
            )
    elif "fs" in tool_name.lower():
        # Infer from tool name
        refs.extend(
            StreetraceToolRef(module="fs_tool", function=func)
            for func in fs_tool_functions
        )
    elif "cli" in tool_name.lower():
        refs.extend(
            StreetraceToolRef(module="cli_tool", function=func)
            for func in cli_tool_functions
        )

    return refs
