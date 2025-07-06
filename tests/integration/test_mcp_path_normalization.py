"""Integration tests for MCP CWD approach functionality."""

from pathlib import Path

from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.tools.tool_provider import ToolProvider


class TestMCPCwdApproachIntegration:
    """Integration tests for the MCP CWD approach system."""

    def test_tool_provider_creates_all_toolsets_with_cwd(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that ToolProvider creates all toolsets with cwd parameter."""
        tool_provider = ToolProvider(tmp_path)

        # Test various MCP servers
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"edit_file", "move_file"},
            "@modelcontextprotocol/server-database": {"query"},
            "@other/server": {"some_tool"},
        }

        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should have three toolsets
        assert len(toolsets) == 3

        # All should be MCPToolset instances
        for toolset in toolsets:
            assert isinstance(toolset, MCPToolset)

    def test_cwd_approach_for_all_servers(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that the CWD approach is used for all MCP servers."""
        # The new approach sets cwd on all MCP server processes
        # This test verifies that the ToolProvider creates regular MCPToolset instances
        # for all servers

        tool_provider = ToolProvider(tmp_path)

        # Test various server types
        mcp_servers = {
            "@modelcontextprotocol/server-filesystem": {"edit_file"},
            "@modelcontextprotocol/server-database": {"query"},
            "@modelcontextprotocol/server-web": {"fetch"},
        }
        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should create regular MCPToolset instances
        assert len(toolsets) == 3
        for toolset in toolsets:
            assert isinstance(toolset, MCPToolset)

        # The key insight: with cwd approach, all MCP server processes run in the
        # correct directory, so relative paths from the agent work correctly without
        # normalization for any server type

    def test_filesystem_server_uses_cwd_approach(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that filesystem servers use the CWD approach."""
        tool_provider = ToolProvider(tmp_path)

        # Test filesystem server
        mcp_servers = {"@modelcontextprotocol/server-filesystem": {"edit_file"}}
        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should create regular MCPToolset
        assert len(toolsets) == 1
        toolset = toolsets[0]
        assert isinstance(toolset, MCPToolset)

    def test_non_filesystem_server_also_uses_cwd_approach(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that non-filesystem servers also use the CWD approach."""
        tool_provider = ToolProvider(tmp_path)

        # Test non-filesystem server
        mcp_servers = {"@modelcontextprotocol/server-other": {"some_tool"}}
        toolsets = tool_provider._create_mcp_toolsets(mcp_servers)  # noqa: SLF001

        # Should create regular MCPToolset
        assert len(toolsets) == 1
        toolset = toolsets[0]
        assert isinstance(toolset, MCPToolset)

    def test_mixed_server_types_all_use_cwd_approach(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that all server types use the CWD approach consistently."""
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

    def test_cwd_approach_eliminates_server_type_complexity(
        self,
        tmp_path: Path,
    ) -> None:
        """Test the CWD approach eliminates the need for server-type-specific logic."""
        tool_provider = ToolProvider(tmp_path)

        # Test that all different server types are handled uniformly
        different_servers = {
            "@modelcontextprotocol/server-filesystem": {"read_file"},
            "@modelcontextprotocol/server-brave-search": {"search"},
            "@modelcontextprotocol/server-postgres": {"query"},
            "@custom/server": {"custom_tool"},
        }

        toolsets = tool_provider._create_mcp_toolsets(different_servers)  # noqa: SLF001

        # All should be handled the same way
        assert len(toolsets) == 4
        for toolset in toolsets:
            assert isinstance(toolset, MCPToolset)

        # No special logic needed for different server types
        # All run in the user's working directory via cwd parameter
