"""Tests for ToolProvider ToolRef processing functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from streetrace.tools.mcp_transport import HttpTransport, StdioTransport
from streetrace.tools.tool_provider import ToolProvider
from streetrace.tools.tool_refs import CallableToolRef, McpToolRef, StreetraceToolRef


class TestToolProviderToolRefProcessing:
    """Test ToolProvider's new ToolRef processing capabilities."""

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance for testing."""
        return ToolProvider(work_dir)

    async def test_process_mcp_tool_ref_with_inline_transport(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test processing MCP tool reference with inline transport."""
        transport = HttpTransport(
            url="http://localhost:8000/mcp",
            headers={"Auth": "Bearer token"},
        )
        tool_ref = McpToolRef(name="fake_tool", server=transport, tools=["*"])

        with patch(
            "google.adk.tools.mcp_tool.mcp_toolset.MCPToolset",
        ) as mock_toolset_class:
            mock_toolset = Mock()
            mock_toolset_class.return_value = mock_toolset

            tools = list(tool_provider._process_mcp_tool_ref(tool_ref))  # noqa: SLF001

            assert len(tools) == 1
            assert tools[0] == mock_toolset
            mock_toolset_class.assert_called_once()

            # Verify connection params and tool filter
            call_args = mock_toolset_class.call_args
            assert call_args is not None
            connection_params = call_args.kwargs["connection_params"]
            assert call_args.kwargs["tool_filter"] is None  # "*" means all tools

            # Check that StreamableHTTPConnectionParams was created
            from google.adk.tools.mcp_tool.mcp_session_manager import (
                StreamableHTTPConnectionParams,
            )

            assert isinstance(connection_params, StreamableHTTPConnectionParams)
            assert connection_params.url == "http://localhost:8000/mcp"

    def test_process_callable_tool_ref(self, tool_provider: ToolProvider) -> None:
        """Test processing callable tool reference."""
        tool_ref = CallableToolRef(import_path="os.path:exists")

        tools = list(tool_provider._process_callable_tool_ref(tool_ref))  # noqa: SLF001

        assert len(tools) == 1
        assert callable(tools[0])
        # os.path.exists should be imported successfully
        assert tools[0].__name__ == "exists"

    def test_process_callable_tool_ref_invalid_import_path(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test processing callable tool reference with invalid import path."""
        tool_ref = CallableToolRef(import_path="invalid_path_no_colon")

        with pytest.raises(
            ValueError,
            match="Invalid import path format.*Expected 'module:function'",
        ):
            list(tool_provider._process_callable_tool_ref(tool_ref))  # noqa: SLF001

    def test_process_callable_tool_ref_non_callable(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test processing callable tool reference that resolves to non-callable."""
        tool_ref = CallableToolRef(import_path="os:name")  # os.name is a string

        with pytest.raises(
            TypeError,
            match="resolved to non-callable",
        ):
            tool_provider._process_callable_tool_ref(tool_ref)  # noqa: SLF001

    def test_create_connection_params_stdio(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test converting StdioTransport to connection parameters."""
        transport = StdioTransport(
            command="python",
            args=["-m", "server"],
            cwd="/tmp",  # noqa: S108
            env={"API_KEY": "secret"},
        )

        params = tool_provider._create_connection_params(transport)  # noqa: SLF001

        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StdioConnectionParams,
        )

        assert isinstance(params, StdioConnectionParams)
        assert params.server_params.command == "python"
        assert params.server_params.args == [
            "-m",
            "server",
            "/tmp",  # noqa: S108
        ]
        assert params.server_params.cwd == "/tmp"  # noqa: S108
        assert params.server_params.env == {"API_KEY": "secret"}

    def test_create_connection_params_http(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test converting HttpTransport to connection parameters."""
        transport = HttpTransport(
            url="https://api.example.com/mcp",
            headers={"Auth": "Bearer token"},
            timeout=30.0,
        )

        params = tool_provider._create_connection_params(transport)  # noqa: SLF001

        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )

        assert isinstance(params, StreamableHTTPConnectionParams)
        assert params.url == "https://api.example.com/mcp"
        assert params.headers == {"Auth": "Bearer token"}
        assert params.timeout == 30.0

    def test_create_connection_params_unknown_type(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test converting unknown transport type raises error."""
        # Create a mock transport that isn't one of the known types
        mock_transport = Mock()
        mock_transport.__class__.__name__ = "UnknownTransport"

        with pytest.raises(TypeError, match="Unknown transport type"):
            tool_provider._create_connection_params(mock_transport)  # noqa: SLF001

    async def test_get_tools_with_mixed_tool_refs(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test get_tools with mixed legacy strings and new ToolRef objects."""
        # Create mixed tool references
        mcp_tool_ref = McpToolRef(
            name="fake_tool",
            server=StdioTransport(command="fake", args=["server"]),
            tools=["tool1"],
        )
        streetrace_tool_ref = StreetraceToolRef(
            module="fake_lib",
            function="some_tool",
        )

        tool_refs = [mcp_tool_ref, streetrace_tool_ref]

        # Mock the various dependencies
        with (
            patch(
                "google.adk.tools.mcp_tool.mcp_toolset.MCPToolset",
            ) as mock_mcp_toolset,
            patch(
                "streetrace.tools.tool_provider.ToolProvider._process_streetrace_tool_ref",
                return_value=[Mock(name="StreetraceTool")],
            ),
            patch("streetrace.tools.tool_provider._log_retrieved_tools"),
        ):
            mock_toolset = Mock()
            mock_toolset.__class__.__name__ = "MCPToolset"
            mock_mcp_toolset.return_value = mock_toolset

            tools = tool_provider.get_tools(tool_refs)

            # Should get: static tool + MCP toolset + StreetRace tool
            assert len(tools) >= 2

    async def test_process_tool_ref_unknown_type(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test processing unknown ToolRef type raises error."""
        # Create a mock tool ref that isn't one of the known types
        mock_tool_ref = Mock()
        mock_tool_ref.__class__.__name__ = "UnknownToolRef"

        with pytest.raises(TypeError, match="Unknown tool reference type"):
            list(tool_provider._process_tool_ref(mock_tool_ref))  # noqa: SLF001


class TestToolRefIntegrationWithProvider:
    """Integration tests for ToolRef system with ToolProvider."""

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance for testing."""
        return ToolProvider(work_dir)

    async def test_end_to_end_tool_ref_processing(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test end-to-end processing of various ToolRef types."""
        # Create different types of tool references
        tool_refs = [
            # MCP tool with named server
            McpToolRef(
                name="fake_tool",
                server=StdioTransport(command="filesystem", args=["fake_server"]),
                tools=["list"],
            ),
            # StreetRace tool
            StreetraceToolRef(module="fs_tool", function="read_file"),
            # Callable tool
            CallableToolRef(import_path="os.path:exists"),
        ]

        with (
            patch("google.adk.tools.mcp_tool.mcp_toolset.MCPToolset") as mock_mcp,
            patch("streetrace.tools.tool_provider._log_retrieved_tools"),
        ):
            mock_toolset = Mock()
            mock_toolset.__class__.__name__ = "MCPToolset"
            mock_mcp.return_value = mock_toolset

            tools = tool_provider.get_tools(tool_refs)

            # Should have processed all tool types
            assert len(tools) >= 3
            # Verify we have different types of tools
            tool_types = {type(tool) for tool in tools}
            assert len(tool_types) >= 2  # At least function and Mock types
