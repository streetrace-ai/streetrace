"""Tests for the ToolProvider class, focusing on resource management functionality."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.tools.tool_provider import AdkTool, ToolProvider


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
    def mock_callable_tool(self) -> Callable:
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
        mock_mcp_toolset: Mock,
    ) -> None:
        """Test releasing tools containing MCPToolset."""
        # Arrange
        tools: list[AdkTool] = [mock_mcp_toolset]

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

        tools: list[AdkTool] = [mock_toolset1, mock_toolset2]

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
        mock_callable_tool: Callable,
    ) -> None:
        """Test releasing tools that are not MCPToolsets."""
        # Arrange
        tools: list[AdkTool] = [
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
        mock_mcp_toolset: Mock,
        mock_base_tool: BaseTool,
        mock_callable_tool: Callable,
    ) -> None:
        """Test releasing a mix of MCP and non-MCP tools."""
        # Arrange
        tools: list[AdkTool] = [
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

        tools: list[AdkTool] = [mock_toolset]

        # Act & Assert - Should not raise exception
        await tool_provider.release_tools(tools)
