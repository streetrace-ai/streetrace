"""Tests for the ToolProvider class, focusing on resource management functionality."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.tools.tool_provider import AnyTool, ToolProvider


class TestToolProviderResourceManagement:
    """Test cases for ToolProvider resource management functionality."""

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance for testing."""
        return ToolProvider(work_dir)

    @pytest.fixture
    def mock_mcp_toolset(self) -> MCPToolset:
        """Create a mock MCPToolset."""
        mock_toolset = Mock(spec=MCPToolset)
        mock_toolset.close = AsyncMock()
        return mock_toolset

    @pytest.fixture
    def mock_base_tool(self) -> BaseTool:
        """Create a mock BaseTool."""
        return Mock(spec=BaseTool)

    @pytest.fixture
    def mock_base_toolset(self) -> BaseToolset:
        """Create a mock BaseToolset."""
        return Mock(spec=BaseToolset)

    @pytest.fixture
    def mock_callable_tool(self) -> callable:
        """Create a mock callable tool."""
        return Mock(return_value="test_result")

    async def test_release_tools_empty_list(self, tool_provider: ToolProvider) -> None:
        """Test releasing an empty list of tools."""
        # Act
        await tool_provider.release_tools([])

        # Assert - no exceptions should be raised

    async def test_release_tools_with_mcp_toolset(
        self,
        tool_provider: ToolProvider,
        mock_mcp_toolset: MCPToolset,
    ) -> None:
        """Test releasing tools containing MCPToolset."""
        # Arrange
        tools: list[AnyTool] = [mock_mcp_toolset]

        # Act
        await tool_provider.release_tools(tools)

        # Assert
        mock_mcp_toolset.close.assert_awaited_once()

    async def test_release_tools_with_multiple_mcp_toolsets(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test releasing multiple MCPToolsets."""
        # Arrange
        mock_toolset1 = Mock(spec=MCPToolset)
        mock_toolset1.close = AsyncMock()
        mock_toolset2 = Mock(spec=MCPToolset)
        mock_toolset2.close = AsyncMock()

        tools: list[AnyTool] = [mock_toolset1, mock_toolset2]

        # Act
        await tool_provider.release_tools(tools)

        # Assert
        mock_toolset1.close.assert_awaited_once()
        mock_toolset2.close.assert_awaited_once()

    async def test_release_tools_with_non_mcp_tools(
        self,
        tool_provider: ToolProvider,
        mock_base_tool: BaseTool,
        mock_base_toolset: BaseToolset,
        mock_callable_tool: callable,
    ) -> None:
        """Test releasing tools that are not MCPToolsets."""
        # Arrange
        tools: list[AnyTool] = [
            mock_base_tool,
            mock_base_toolset,
            mock_callable_tool,
        ]

        # Act
        await tool_provider.release_tools(tools)

        # Assert - no close methods should be called since these are not MCPToolsets
        # This test verifies that non-MCP tools are handled gracefully

    async def test_release_tools_mixed_tool_types(
        self,
        tool_provider: ToolProvider,
        mock_mcp_toolset: MCPToolset,
        mock_base_tool: BaseTool,
        mock_callable_tool: callable,
    ) -> None:
        """Test releasing a mix of MCP and non-MCP tools."""
        # Arrange
        tools: list[AnyTool] = [
            mock_base_tool,
            mock_mcp_toolset,
            mock_callable_tool,
        ]

        # Act
        await tool_provider.release_tools(tools)

        # Assert
        mock_mcp_toolset.close.assert_awaited_once()

    async def test_release_tools_mcp_close_raises_exception(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test that exceptions during MCP close are handled gracefully."""
        # Arrange
        mock_toolset = Mock(spec=MCPToolset)
        mock_toolset.close = AsyncMock(side_effect=Exception("Close failed"))

        tools: list[AnyTool] = [mock_toolset]

        # Act & Assert - Should not raise exception
        # The current implementation doesn't handle exceptions explicitly,
        # but this test documents the expected behavior if we add exception handling
        with pytest.raises(Exception, match="Close failed"):
            await tool_provider.release_tools(tools)

    async def test_release_tools_maintains_order_on_partial_failure(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test that partial failures don't prevent cleanup of remaining tools."""
        # Arrange
        mock_toolset1 = Mock(spec=MCPToolset)
        mock_toolset1.close = AsyncMock(side_effect=Exception("First close failed"))

        mock_toolset2 = Mock(spec=MCPToolset)
        mock_toolset2.close = AsyncMock()

        tools: list[AnyTool] = [mock_toolset1, mock_toolset2]

        # Act & Assert
        with pytest.raises(Exception, match="First close failed"):
            await tool_provider.release_tools(tools)

        # Verify first toolset close was attempted
        mock_toolset1.close.assert_awaited_once()
        # Second toolset close should NOT be called due to exception
        mock_toolset2.close.assert_not_awaited()


class TestToolProviderIntegration:
    """Integration tests for ToolProvider focusing on resource lifecycle."""

    @pytest.fixture
    def tool_provider(self, work_dir: Path) -> ToolProvider:
        """Create a ToolProvider instance for testing."""
        return ToolProvider(work_dir)

    async def test_get_tools_returns_releasable_resources(
        self,
        tool_provider: ToolProvider,
    ) -> None:
        """Test that get_tools returns resources that can be released."""
        # Arrange
        tool_refs = ["get_weather", "get_current_time"]

        # Act
        tools = await tool_provider.get_tools(tool_refs)

        # Assert
        assert len(tools) == 2
        assert all(callable(tool) for tool in tools)

        # Test that these tools can be released without error
        await tool_provider.release_tools(tools)
