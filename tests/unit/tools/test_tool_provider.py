"""Tests for the ToolProvider class, focusing on resource management functionality."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from streetrace.tools.tool_provider import ToolProvider


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

        # Assert - no exceptions should be raised
