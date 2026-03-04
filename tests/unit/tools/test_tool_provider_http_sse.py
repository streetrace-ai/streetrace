"""Tests for ToolProvider HTTP and SSE connection support."""

import json
from pathlib import Path

import pytest

from streetrace.tools.tool_provider import ToolProvider


class TestToolProviderConnectionParsing:
    """Test ToolProvider's ability to parse different connection configurations."""

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance for testing."""
        return ToolProvider(work_dir)

    def test_create_connection_params_stdio_json_config(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test creating STDIO connection params from JSON config."""
        # Arrange
        config = {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "my_server"],
            "env": {"API_KEY": "secret"},
        }
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)  # noqa: SLF001

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StdioConnectionParams,
        )

        assert isinstance(params, StdioConnectionParams)
        assert params.server_params.command == "python"
        assert params.server_params.args == [
            "-m",
            "my_server",
            str(tool_provider.work_dir),
        ]
        assert params.server_params.cwd == tool_provider.work_dir
        assert params.server_params.env == {"API_KEY": "secret"}

    def test_create_connection_params_http_json_config(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test creating HTTP connection params from JSON config."""
        # Arrange
        config = {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30.0,
        }
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)  # noqa: SLF001

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )

        assert isinstance(params, StreamableHTTPConnectionParams)
        assert params.url == "https://api.example.com/mcp"
        assert params.headers == {"Authorization": "Bearer token"}
        assert params.timeout == 30.0

    def test_create_connection_params_sse_json_config(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test creating SSE connection params from JSON config."""
        # Arrange
        config = {
            "type": "sse",
            "url": "https://api.example.com/sse",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60.0,
        }
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)  # noqa: SLF001

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

        assert isinstance(params, SseConnectionParams)
        assert params.url == "https://api.example.com/sse"
        assert params.headers == {"Authorization": "Bearer token"}
        assert params.timeout == 60.0

    def test_create_connection_params_http_config_no_headers(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test creating HTTP connection params with empty headers."""
        # Arrange
        config = {
            "type": "http",
            "url": "http://localhost:8000/mcp",
        }
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)  # noqa: SLF001

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )

        assert isinstance(params, StreamableHTTPConnectionParams)
        assert params.url == "http://localhost:8000/mcp"
        assert params.headers == {}
        # Falls back to DEFAULT_HTTP_TIMEOUT_SECONDS when unset
        assert params.timeout == 30.0

    def test_create_connection_params_invalid_json_fallback(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test fallback to STDIO for invalid JSON."""
        # Act
        with pytest.raises(json.JSONDecodeError):
            tool_provider._create_connection_params("invalid-json-{")  # noqa: SLF001
