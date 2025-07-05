"""Test the ToolProvider CWD approach for MCP filesystem servers."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from streetrace.tools.tool_provider import ToolProvider


class TestToolProviderCwd:
    """Test cases for ToolProvider CWD behavior."""

    @pytest.fixture
    def work_dir(self) -> Path:
        """Create a temporary work directory."""
        return Path(tempfile.mkdtemp())

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance."""
        return ToolProvider(work_dir)

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_filesystem_server_uses_cwd(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test that filesystem servers are created with cwd parameter."""
        # Mock MCP servers
        mcp_servers = {"@modelcontextprotocol/server-filesystem": {"read_file"}}

        # Create toolsets
        tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Verify MCPToolset was called with cwd parameter
        mock_mcp_toolset.assert_called_once()
        call_args = mock_mcp_toolset.call_args

        # Check connection parameters
        connection_params = call_args[1]["connection_params"]
        assert connection_params.command == "npx"
        assert connection_params.args == [
            "-y",
            "@modelcontextprotocol/server-filesystem",
        ]
        assert connection_params.cwd == work_dir

        # Check tool filter
        assert call_args[1]["tool_filter"] == ["read_file"]

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_non_filesystem_server_uses_work_dir_arg(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test that non-filesystem servers use work_dir as command argument."""
        # Mock MCP servers
        mcp_servers = {"@modelcontextprotocol/server-other": {"some_tool"}}

        # Create toolsets
        tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Verify MCPToolset was called with work_dir as argument
        mock_mcp_toolset.assert_called_once()
        call_args = mock_mcp_toolset.call_args

        # Check connection parameters
        connection_params = call_args[1]["connection_params"]
        assert connection_params.command == "npx"
        assert connection_params.args == [
            "-y",
            "@modelcontextprotocol/server-other",
            str(work_dir),
        ]
        # Should not set cwd for non-filesystem servers
        assert connection_params.cwd is None

        # Check tool filter
        assert call_args[1]["tool_filter"] == ["some_tool"]

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_multiple_servers_mixed_types(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test mixed filesystem and non-filesystem servers."""
        # Mock MCP servers
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"read_file", "write_file"},
            "@modelcontextprotocol/server-other": {"some_tool"},
        }

        # Create toolsets
        tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Verify MCPToolset was called twice
        assert mock_mcp_toolset.call_count == 2

        # Check each call
        calls = mock_mcp_toolset.call_args_list

        # Find the filesystem server call
        filesystem_call = None
        other_call = None
        for call in calls:
            connection_params = call[1]["connection_params"]
            if "server-filesystem" in connection_params.args[1]:
                filesystem_call = call
            else:
                other_call = call

        # Verify filesystem server call
        assert filesystem_call is not None
        fs_connection_params = filesystem_call[1]["connection_params"]
        assert fs_connection_params.command == "npx"
        assert fs_connection_params.args == [
            "-y",
            "@modelcontextprotocol/server-filesystem",
        ]
        assert fs_connection_params.cwd == work_dir
        assert set(filesystem_call[1]["tool_filter"]) == {"read_file", "write_file"}

        # Verify other server call
        assert other_call is not None
        other_connection_params = other_call[1]["connection_params"]
        assert other_connection_params.command == "npx"
        assert other_connection_params.args == [
            "-y",
            "@modelcontextprotocol/server-other",
            str(work_dir),
        ]
        assert other_connection_params.cwd is None
        assert other_call[1]["tool_filter"] == ["some_tool"]

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_filesystem_server_all_tools(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test filesystem server with all tools (no filter)."""
        # Mock MCP servers with "all" or "*" tool names
        mcp_servers = {"@modelcontextprotocol/server-filesystem": {"all"}}

        # Create toolsets
        tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Verify MCPToolset was called with no tool filter
        mock_mcp_toolset.assert_called_once()
        call_args = mock_mcp_toolset.call_args

        # Check connection parameters
        connection_params = call_args[1]["connection_params"]
        assert connection_params.command == "npx"
        assert connection_params.args == [
            "-y",
            "@modelcontextprotocol/server-filesystem",
        ]
        assert connection_params.cwd == work_dir

        # Check tool filter is None (all tools)
        assert call_args[1]["tool_filter"] is None
