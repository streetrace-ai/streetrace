"""Tests for the YamlAgentBuilder class."""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from google.adk.agents import BaseAgent
from google.adk.tools.agent_tool import AgentTool

from streetrace.agents.yaml_agent_builder import YamlAgentBuilder
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name: str, has_close: bool = True) -> None:
        """Initialize mock tool."""
        self.name = name
        self.closed = False
        self.close_order: int | None = None
        if has_close:
            self.close = AsyncMock(side_effect=self._close_impl)

    async def _close_impl(self) -> None:
        """Mock close implementation."""
        self.closed = True


class MockAgentTool(AgentTool):
    """Mock AgentTool for testing."""

    def __init__(self, name: str, agent: BaseAgent) -> None:
        """Initialize mock AgentTool."""
        # Create a mock agent to satisfy AgentTool's requirements
        mock_agent = Mock(spec=BaseAgent)
        mock_agent.name = name
        mock_agent.description = f"Mock agent {name}"

        super().__init__(mock_agent)

        # Override the agent property to use our test agent
        self.agent = agent  # type: ignore[assignment]
        self.closed = False
        self.close_order: int | None = None

        # Mock the close method
        self.close = AsyncMock(side_effect=self._close_impl)

    async def _close_impl(self) -> None:
        """Mock close implementation."""
        self.closed = True


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    tools: list[MockTool | AgentTool] | None = None


@pytest.fixture
def yaml_agent_builder():
    """Create a YamlAgentBuilder instance for testing."""
    model_factory = Mock(spec=ModelFactory)
    tool_provider = Mock(spec=ToolProvider)
    system_context = Mock(spec=SystemContext)

    return YamlAgentBuilder(
        model_factory=model_factory,
        tool_provider=tool_provider,
        system_context=system_context,
    )


@pytest.mark.asyncio
class TestYamlAgentBuilderClose:
    """Test cases for YamlAgentBuilder.close method."""

    async def test_close_simple_agent_no_tools(
        self,
        yaml_agent_builder: YamlAgentBuilder,
    ):
        """Test closing a simple agent with no tools or sub-agents."""
        agent = MockAgent(name="test_agent")

        # Should not raise any exceptions
        await yaml_agent_builder.close(agent)

    async def test_close_agent_with_regular_tools(self, yaml_agent_builder):
        """Test closing an agent with regular tools that have close methods."""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        tool_no_close = MockTool("tool_no_close", has_close=False)

        agent = MockAgent(name="test_agent", tools=[tool1, tool2, tool_no_close])

        await yaml_agent_builder.close(agent)

        # Verify tools with close methods were closed
        assert tool1.closed
        assert tool2.closed
        # Tool without close method should not cause errors
        assert not hasattr(tool_no_close, "closed") or not tool_no_close.closed

        # Verify close methods were called
        tool1.close.assert_called_once()
        tool2.close.assert_called_once()

    async def test_close_agent_with_sub_agents(self, yaml_agent_builder):
        """Test closing an agent with sub-agents."""
        sub_tool1 = MockTool("sub_tool1")
        sub_tool2 = MockTool("sub_tool2")
        sub_agent = MockAgent(name="sub_agent", tools=[sub_tool1, sub_tool2])

        root_tool = MockTool("root_tool")
        root_agent = MockAgent(
            name="root_agent",
            tools=[root_tool],
            sub_agents=[sub_agent],
        )

        await yaml_agent_builder.close(root_agent)

        # All tools should be closed
        assert sub_tool1.closed
        assert sub_tool2.closed
        assert root_tool.closed

        sub_tool1.close.assert_called_once()
        sub_tool2.close.assert_called_once()
        root_tool.close.assert_called_once()

    async def test_close_agent_with_agent_tools(self, yaml_agent_builder):
        """Test closing an agent with AgentTool objects."""
        # Create a wrapped agent with its own tool
        wrapped_tool = MockTool("wrapped_tool")
        wrapped_agent = MockAgent(name="wrapped_agent", tools=[wrapped_tool])

        # Create an AgentTool that wraps the agent
        agent_tool = MockAgentTool("agent_tool", wrapped_agent)

        # Create root agent with the AgentTool
        root_agent = MockAgent(name="root_agent", tools=[agent_tool])

        await yaml_agent_builder.close(root_agent)

        # Both the wrapped agent's tool and the AgentTool should be closed
        assert wrapped_tool.closed
        assert agent_tool.closed

        wrapped_tool.close.assert_called_once()
        agent_tool.close.assert_called_once()

    async def test_close_complex_hierarchy(self, yaml_agent_builder):
        """Test closing a complex hierarchy with nested agents and AgentTools."""
        # Create deepest level
        deep_tool = MockTool("deep_tool")
        deep_agent = MockAgent(name="deep_agent", tools=[deep_tool])

        # Create AgentTool wrapping deep agent
        deep_agent_tool = MockAgentTool("deep_agent_tool", deep_agent)

        # Create middle level agent with the AgentTool
        mid_tool = MockTool("mid_tool")
        mid_sub_agent = MockAgent(name="mid_sub_agent", tools=[deep_agent_tool])
        mid_agent = MockAgent(
            name="mid_agent",
            tools=[mid_tool],
            sub_agents=[mid_sub_agent],
        )

        # Create root level
        root_tool1 = MockTool("root_tool1")
        root_tool2 = MockTool("root_tool2")
        root_agent = MockAgent(
            name="root_agent",
            tools=[root_tool1, root_tool2],
            sub_agents=[mid_agent],
        )

        await yaml_agent_builder.close(root_agent)

        # All tools should be closed
        assert deep_tool.closed
        assert deep_agent_tool.closed
        assert mid_tool.closed
        assert root_tool1.closed
        assert root_tool2.closed

        # Verify all close methods were called
        deep_tool.close.assert_called_once()
        deep_agent_tool.close.assert_called_once()
        mid_tool.close.assert_called_once()
        root_tool1.close.assert_called_once()
        root_tool2.close.assert_called_once()

    async def test_close_depth_first_order(self, yaml_agent_builder):
        """Test that closing happens in depth-first order."""
        close_order = []

        class OrderTrackingTool(MockTool):
            """Tool that tracks close order."""

            def __init__(self, name: str) -> None:
                self.name = name
                self.closed = False

            async def close(self) -> None:
                self.closed = True
                close_order.append(self.name)

        class OrderTrackingAgentTool(AgentTool):
            """AgentTool that tracks close order."""

            def __init__(self, name: str, agent: MockAgent) -> None:
                # Create a mock agent to satisfy AgentTool's requirements
                mock_agent = Mock(spec=BaseAgent)
                mock_agent.name = name
                mock_agent.description = f"Mock agent {name}"

                super().__init__(mock_agent)

                # Override the agent property to use our test agent
                self.agent = agent  # type: ignore[assignment]
                self.closed = False

            async def close(self) -> None:
                self.closed = True
                close_order.append(self.name)

        # Create hierarchy:
        # root
        #   - sub_agent1
        #     - sub_tool1
        #   - sub_agent2
        #     - agent_tool (wraps wrapped_agent)
        #       - wrapped_agent
        #         - wrapped_tool
        #   - root_tool

        wrapped_tool = OrderTrackingTool("wrapped_tool")
        wrapped_agent = MockAgent(name="wrapped_agent", tools=[wrapped_tool])
        agent_tool = OrderTrackingAgentTool("agent_tool", wrapped_agent)

        sub_tool1 = OrderTrackingTool("sub_tool1")
        sub_agent1 = MockAgent(name="sub_agent1", tools=[sub_tool1])
        sub_agent2 = MockAgent(name="sub_agent2", tools=[agent_tool])

        root_tool = OrderTrackingTool("root_tool")
        root_agent = MockAgent(
            name="root_agent",
            tools=[root_tool],
            sub_agents=[sub_agent1, sub_agent2],
        )

        await yaml_agent_builder.close(root_agent)

        # Expected order: depth-first traversal
        # 1. sub_agent1's tools: sub_tool1
        # 2. sub_agent2's tools: agent_tool (but first its wrapped agent's tools)
        #    - wrapped_agent's tools: wrapped_tool
        #    - then agent_tool itself
        # 3. root_agent's tools: root_tool
        expected_order = ["sub_tool1", "wrapped_tool", "agent_tool", "root_tool"]

        assert close_order == expected_order

    async def test_close_handles_missing_close_methods_gracefully(
        self,
        yaml_agent_builder,
    ):
        """Test that tools without close methods don't cause errors."""

        class ToolWithoutClose(MockTool):
            """Tool without close method."""

            def __init__(self, name: str) -> None:
                self.name = name

        tool_without_close = ToolWithoutClose("no_close_tool")
        tool_with_close = MockTool("with_close_tool")

        agent = MockAgent(
            name="test_agent", tools=[tool_without_close, tool_with_close],
        )

        # Should not raise any exceptions
        await yaml_agent_builder.close(agent)

        # Tool with close method should still be closed
        assert tool_with_close.closed
        tool_with_close.close.assert_called_once()

    async def test_close_handles_non_callable_close_attribute(self, yaml_agent_builder):
        """Test that tools with non-callable close attributes don't cause errors."""

        class ToolWithNonCallableClose(MockTool):
            """Tool with non-callable close attribute."""

            def __init__(self, name: str) -> None:
                self.name = name
                self.close = "not_callable"  # Non-callable close attribute

        tool_bad_close = ToolWithNonCallableClose("bad_close_tool")
        tool_good_close = MockTool("good_close_tool")

        agent = MockAgent(name="test_agent", tools=[tool_bad_close, tool_good_close])

        # Should not raise any exceptions
        await yaml_agent_builder.close(agent)

        # Good tool should still be closed
        assert tool_good_close.closed
        tool_good_close.close.assert_called_once()

    async def test_close_agent_without_tools_attribute(self, yaml_agent_builder):
        """Test closing an agent that doesn't have a tools attribute."""

        class AgentWithoutTools:
            """Agent without tools attribute."""

            def __init__(self, name: str) -> None:
                self.name = name
                self.sub_agents: list[Any] = []

        agent = AgentWithoutTools("no_tools_agent")

        # Should not raise any exceptions
        await yaml_agent_builder.close(agent)
