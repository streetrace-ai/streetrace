"""Tests for ToolProvider HTTP and SSE connection support."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from streetrace.tools.tool_provider import ToolProvider


class TestToolProviderConnectionParsing:
    """Test ToolProvider's ability to parse different connection configurations."""

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance for testing."""
        return ToolProvider(work_dir)

    def test_create_connection_params_simple_server_name(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test creating connection params from simple server name (default STDIO)."""
        # Act
        params = tool_provider._create_connection_params("@modelcontextprotocol/server-filesystem")

        # Assert
        from mcp import StdioServerParameters
        assert isinstance(params, StdioServerParameters)
        assert params.command == "npx"
        assert params.args == ["-y", "@modelcontextprotocol/server-filesystem", str(tool_provider.work_dir)]
        assert params.cwd == tool_provider.work_dir

    def test_create_connection_params_stdio_json_config(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test creating STDIO connection params from JSON config."""
        # Arrange
        config = {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "my_server"],
            "cwd": "/tmp",
            "env": {"API_KEY": "secret"},
        }
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)

        # Assert
        from mcp import StdioServerParameters
        assert isinstance(params, StdioServerParameters)
        assert params.command == "python"
        assert params.args == ["-m", "my_server"]
        assert params.cwd == "/tmp"
        assert params.env == {"API_KEY": "secret"}

    def test_create_connection_params_http_json_config(
        self, tool_provider: ToolProvider,
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
        params = tool_provider._create_connection_params(config_json)

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )
        assert isinstance(params, StreamableHTTPConnectionParams)
        assert params.url == "https://api.example.com/mcp"
        assert params.headers == {"Authorization": "Bearer token"}
        assert params.timeout == 30.0

    def test_create_connection_params_sse_json_config(
        self, tool_provider: ToolProvider,
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
        params = tool_provider._create_connection_params(config_json)

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams
        assert isinstance(params, SseConnectionParams)
        assert params.url == "https://api.example.com/sse"
        assert params.headers == {"Authorization": "Bearer token"}
        assert params.timeout == 60.0

    def test_create_connection_params_http_config_no_headers(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test creating HTTP connection params with empty headers."""
        # Arrange
        config = {
            "type": "http",
            "url": "http://localhost:8000/mcp",
        }
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)

        # Assert
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )
        assert isinstance(params, StreamableHTTPConnectionParams)
        assert params.url == "http://localhost:8000/mcp"
        assert params.headers == {}
        # StreamableHTTPConnectionParams has default timeout, not None
        assert params.timeout is not None

    def test_create_connection_params_invalid_json_fallback(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test fallback to STDIO for invalid JSON."""
        # Act
        params = tool_provider._create_connection_params("invalid-json-{")

        # Assert
        from mcp import StdioServerParameters
        assert isinstance(params, StdioServerParameters)
        assert params.command == "npx"
        assert params.args == ["-y", "invalid-json-{", str(tool_provider.work_dir)]

    def test_create_connection_params_missing_required_fields(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test fallback when JSON config is missing required fields."""
        # Arrange
        config = {"type": "http"}  # Missing required 'url' field
        config_json = json.dumps(config)

        # Act
        params = tool_provider._create_connection_params(config_json)

        # Assert - Should fallback to STDIO
        from mcp import StdioServerParameters
        assert isinstance(params, StdioServerParameters)
        assert params.command == "npx"

    def test_create_mcp_toolsets_with_http_config(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test creating MCP toolsets with HTTP configuration."""
        # Arrange
        http_config = {
            "type": "http",
            "url": "http://localhost:8000/mcp",
            "headers": {"Authorization": "Bearer token"},
        }
        mcp_servers = {json.dumps(http_config): {"tool1", "tool2"}}

        # Act
        with patch("google.adk.tools.mcp_tool.mcp_toolset.MCPToolset") as mock_toolset_class:
            mock_toolset = Mock()
            mock_toolset_class.return_value = mock_toolset

            toolsets = tool_provider._create_mcp_toolsets(mcp_servers)

        # Assert
        assert len(toolsets) == 1
        assert toolsets[0] == mock_toolset
        mock_toolset_class.assert_called_once()

        # Check connection params passed to MCPToolset
        call_args = mock_toolset_class.call_args
        assert call_args is not None
        connection_params = call_args.kwargs["connection_params"]

        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )
        assert isinstance(connection_params, StreamableHTTPConnectionParams)
        assert connection_params.url == "http://localhost:8000/mcp"

    def test_create_mcp_toolsets_with_sse_config(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test creating MCP toolsets with SSE configuration."""
        # Arrange
        sse_config = {
            "type": "sse",
            "url": "http://localhost:8000/sse",
            "timeout": 45.0,
        }
        mcp_servers = {json.dumps(sse_config): {"all"}}

        # Act
        with patch("google.adk.tools.mcp_tool.mcp_toolset.MCPToolset") as mock_toolset_class:
            mock_toolset = Mock()
            mock_toolset_class.return_value = mock_toolset

            toolsets = tool_provider._create_mcp_toolsets(mcp_servers)

        # Assert
        assert len(toolsets) == 1
        assert toolsets[0] == mock_toolset
        mock_toolset_class.assert_called_once()

        # Check connection params passed to MCPToolset
        call_args = mock_toolset_class.call_args
        assert call_args is not None
        connection_params = call_args.kwargs["connection_params"]

        from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams
        assert isinstance(connection_params, SseConnectionParams)
        assert connection_params.url == "http://localhost:8000/sse"
        assert connection_params.timeout == 45.0

    def test_create_mcp_toolsets_mixed_connection_types(
        self, tool_provider: ToolProvider,
    ) -> None:
        """Test creating MCP toolsets with mixed connection types."""
        # Arrange
        http_config = {"type": "http", "url": "http://localhost:8000/mcp"}
        sse_config = {"type": "sse", "url": "http://localhost:8001/sse"}
        stdio_server = "simple-filesystem-server"

        mcp_servers = {
            json.dumps(http_config): {"http_tool"},
            json.dumps(sse_config): {"sse_tool"},
            stdio_server: {"filesystem_tool"},
        }

        # Act
        with patch("google.adk.tools.mcp_tool.mcp_toolset.MCPToolset") as mock_toolset_class:
            mock_toolset = Mock()
            mock_toolset_class.return_value = mock_toolset

            toolsets = tool_provider._create_mcp_toolsets(mcp_servers)

        # Assert
        assert len(toolsets) == 3
        assert mock_toolset_class.call_count == 3

        # Verify different connection types were used
        call_args_list = mock_toolset_class.call_args_list
        connection_types = [type(call.kwargs["connection_params"]).__name__ for call in call_args_list]

        # Should have one of each connection type
        assert "StreamableHTTPConnectionParams" in connection_types
        assert "SseConnectionParams" in connection_types
        assert "StdioServerParameters" in connection_types
