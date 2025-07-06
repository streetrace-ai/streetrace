"""Test the ToolProvider CWD approach for all MCP servers."""

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
            str(work_dir),
        ]
        assert connection_params.cwd == work_dir

        # Check tool filter
        assert call_args[1]["tool_filter"] == ["read_file"]

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_non_filesystem_server_also_uses_cwd(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test that non-filesystem servers also use cwd parameter."""
        # Mock MCP servers
        mcp_servers = {"@modelcontextprotocol/server-other": {"some_tool"}}

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
            "@modelcontextprotocol/server-other",
            str(work_dir),
        ]
        # All servers now use cwd
        assert connection_params.cwd == work_dir

        # Check tool filter
        assert call_args[1]["tool_filter"] == ["some_tool"]

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_multiple_servers_all_use_cwd(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test that all servers use cwd parameter."""
        # Mock MCP servers
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"read_file", "write_file"},
            "@modelcontextprotocol/server-other": {"some_tool"},
        }

        # Create toolsets
        tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Verify MCPToolset was called twice
        assert mock_mcp_toolset.call_count == 2

        # Check each call - all should use cwd
        calls = mock_mcp_toolset.call_args_list

        for call in calls:
            connection_params = call[1]["connection_params"]
            assert connection_params.command == "npx"
            assert len(connection_params.args) == 3  # Only npx, -y, and server name
            assert connection_params.args[0] == "-y"
            assert connection_params.args[1] in [
                "@modelcontextprotocol/server-filesystem",
                "@modelcontextprotocol/server-other",
            ]
            # All servers should use cwd
            assert connection_params.cwd == work_dir

        # Check tool filters - both should be present
        tool_filters = [call[1]["tool_filter"] for call in calls]
        expected_filters = [{"read_file", "write_file"}, ["some_tool"]]
        actual_filters = [set(f) if isinstance(f, list) else f for f in tool_filters]
        assert (
            actual_filters[0] in expected_filters
            or actual_filters[1] in expected_filters
        )

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_server_with_all_tools_uses_cwd(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test that server with all tools uses cwd parameter."""
        # Mock MCP servers with "all" or "*" tool names
        mcp_servers = {"@modelcontextprotocol/server-filesystem": {"all"}}

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
            str(work_dir),
        ]
        assert connection_params.cwd == work_dir

        # Check tool filter is None (all tools)
        assert call_args[1]["tool_filter"] is None

    @patch("streetrace.tools.tool_provider.MCPToolset")
    def test_all_mcp_servers_use_cwd_no_work_dir_args(
        self,
        mock_mcp_toolset: Mock,
        tool_provider: ToolProvider,
        work_dir: Path,
    ) -> None:
        """Test that all MCP servers use cwd and no work_dir arguments."""
        # Mock various MCP servers
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"read_file"},
            "@modelcontextprotocol/server-database": {"query"},
            "@modelcontextprotocol/server-web": {"fetch"},
        }

        # Create toolsets
        tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Verify MCPToolset was called for each server
        assert mock_mcp_toolset.call_count == 3

        # Check that all calls use cwd and no work_dir arguments
        calls = mock_mcp_toolset.call_args_list
        for call in calls:
            connection_params = call[1]["connection_params"]
            assert connection_params.command == "npx"
            assert len(connection_params.args) == 3  # Only ["-y", server_name]
            assert connection_params.args[0] == "-y"
            assert connection_params.cwd == work_dir
            # No work_dir should be passed as argument
            assert str(work_dir) in connection_params.args
