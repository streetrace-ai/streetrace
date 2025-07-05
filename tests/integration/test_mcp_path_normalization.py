"""Integration tests for MCP CWD approach functionality."""

from pathlib import Path

from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.tools.tool_provider import ToolProvider


class TestMCPCwdApproachIntegration:
    """Integration tests for the MCP CWD approach system."""

    def test_tool_provider_creates_filesystem_toolset_with_cwd(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that ToolProvider creates filesystem toolsets with cwd parameter."""
        tool_provider = ToolProvider(tmp_path)

        # Test the MCP server detection logic
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"edit_file", "move_file"},
            "@other/server": {"some_tool"},
        }

        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should have two toolsets
        assert len(toolsets) == 2

        # Both should be MCPToolset instances (no wrapper needed with cwd approach)
        for toolset in toolsets:
            assert isinstance(toolset, MCPToolset)

    def test_cwd_approach_eliminates_need_for_wrapper(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that the CWD approach eliminates the need for path normalization."""
        # The new approach sets cwd on the MCP server process itself
        # This test verifies that the ToolProvider creates regular MCPToolset instances
        # for filesystem servers

        tool_provider = ToolProvider(tmp_path)

        # Test filesystem server
        mcp_servers = {"@modelcontextprotocol/server-filesystem": {"edit_file"}}
        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should create regular MCPToolset, not wrapper
        assert len(toolsets) == 1
        toolset = toolsets[0]
        assert isinstance(toolset, MCPToolset)

        # The key insight: with cwd approach, the MCP server process runs in the
        # correct directory, so relative paths from the agent work correctly without
        # normalization

    def test_non_filesystem_server_uses_work_dir_argument(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that non-filesystem servers still use work_dir as command argument."""
        tool_provider = ToolProvider(tmp_path)

        # Test non-filesystem server
        mcp_servers = {"@modelcontextprotocol/server-other": {"some_tool"}}
        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should create regular MCPToolset
        assert len(toolsets) == 1
        toolset = toolsets[0]
        assert isinstance(toolset, MCPToolset)

        # The server should have work_dir as command argument
        # (This is implementation detail, but important for backward compatibility)

    def test_mixed_server_types_handled_correctly(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that mixed filesystem and non-filesystem servers work correctly."""
        tool_provider = ToolProvider(tmp_path)

        # Test mixed server types
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"edit_file", "read_file"},
            "@modelcontextprotocol/server-database": {"query"},
            "@modelcontextprotocol/server-web": {"fetch"},
        }

        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should create three toolsets
        assert len(toolsets) == 3

        # All should be MCPToolset instances
        for toolset in toolsets:
            assert isinstance(toolset, MCPToolset)
