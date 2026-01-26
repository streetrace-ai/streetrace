"""Tests for DSL agent ADK integration with agentic patterns.

Test the integration of DSL agentic patterns (delegate, use) with
StreetRace's ADK agent creation pipeline via DslAgentFactory.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.tools.agent_tool import AgentTool

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider
from streetrace.workloads.dsl_agent_factory import DslAgentFactory


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name: str, *, has_close: bool = True) -> None:
        """Initialize mock tool."""
        self.name = name
        self.closed = False
        if has_close:
            self.close = AsyncMock(side_effect=self._close_impl)

    async def _close_impl(self) -> None:
        """Mock close implementation."""
        self.closed = True


class MockAgentTool(AgentTool):
    """Mock AgentTool for testing."""

    def __init__(self, name: str, agent: BaseAgent) -> None:
        """Initialize mock AgentTool."""
        mock_agent = Mock(spec=BaseAgent)
        mock_agent.name = name
        mock_agent.description = f"Mock agent {name}"
        super().__init__(mock_agent)
        self.agent = agent  # type: ignore[assignment]
        self.closed = False
        self.close = AsyncMock(side_effect=self._close_impl)

    async def _close_impl(self) -> None:
        """Mock close implementation."""
        self.closed = True


class MockLlmAgent(BaseAgent):
    """Mock LlmAgent for testing."""

    tools: list[MockTool | AgentTool] | None = None


@pytest.fixture
def mock_model_factory() -> Mock:
    """Create a mock model factory."""
    factory = Mock(spec=ModelFactory)
    mock_llm = Mock()
    mock_interface = Mock()
    mock_interface.get_adk_llm.return_value = mock_llm
    factory.get_llm_interface.return_value = mock_interface
    factory.get_current_model.return_value = mock_llm
    return factory


@pytest.fixture
def mock_tool_provider() -> Mock:
    """Create a mock tool provider."""
    provider = Mock(spec=ToolProvider)
    provider.get_tools.return_value = []
    return provider


@pytest.fixture
def mock_system_context() -> Mock:
    """Create a mock system context."""
    return Mock(spec=SystemContext)


def create_workflow_class(
    agents: dict, prompts: dict | None = None, models: dict | None = None,
) -> type:
    """Create a workflow class with specified agents and prompts.

    Args:
        agents: Agent definitions dict.
        prompts: Optional prompts dict.
        models: Optional models dict.

    Returns:
        A workflow class type.

    """
    prompts = prompts or {}
    models = models or {"main": "test-model"}

    class TestWorkflow(DslAgentWorkflow):
        _agents = agents
        _prompts = prompts
        _models = models

    return TestWorkflow


@pytest.mark.asyncio
class TestResolveSubAgents:
    """Test cases for _resolve_sub_agents method."""

    async def test_empty_sub_agents_returns_empty_list(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that empty sub_agents field returns empty list."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "sub_agents": [],
                },
            },
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"sub_agents": []}
        with patch.object(LlmAgent, "__init__", return_value=None):
            result = await factory._resolve_sub_agents(  # noqa: SLF001
                agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
            )

        assert result == []

    async def test_missing_sub_agents_returns_empty_list(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that missing sub_agents field returns empty list."""
        workflow_class = create_workflow_class(
            agents={"default": {"tools": [], "instruction": "main_prompt"}},
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {}
        with patch.object(LlmAgent, "__init__", return_value=None):
            result = await factory._resolve_sub_agents(  # noqa: SLF001
                agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
            )

        assert result == []

    async def test_single_sub_agent_created(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that a single sub-agent is created correctly."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "sub_agents": ["expert"],
                },
                "expert": {
                    "tools": [],
                    "instruction": "expert_prompt",
                    "description": "Expert agent",
                },
            },
            prompts={
                "main_prompt": lambda _ctx: "Coordinate tasks",
                "expert_prompt": lambda _ctx: "Provide expertise",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"sub_agents": ["expert"]}

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_agent_instance = Mock(spec=LlmAgent)
            mock_llm_agent.return_value = mock_agent_instance

            result = await factory._resolve_sub_agents(  # noqa: SLF001
                agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
            )

        assert len(result) == 1
        assert result[0] is mock_agent_instance

    async def test_multiple_sub_agents_created(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that multiple sub-agents are created correctly."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "sub_agents": ["expert1", "expert2", "expert3"],
                },
                "expert1": {"tools": [], "instruction": "expert1_prompt"},
                "expert2": {"tools": [], "instruction": "expert2_prompt"},
                "expert3": {"tools": [], "instruction": "expert3_prompt"},
            },
            prompts={
                "main_prompt": lambda _ctx: "Coordinate",
                "expert1_prompt": lambda _ctx: "Expert 1",
                "expert2_prompt": lambda _ctx: "Expert 2",
                "expert3_prompt": lambda _ctx: "Expert 3",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"sub_agents": ["expert1", "expert2", "expert3"]}

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_agents = [Mock(spec=LlmAgent) for _ in range(3)]
            mock_llm_agent.side_effect = mock_agents

            result = await factory._resolve_sub_agents(  # noqa: SLF001
                agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
            )

        assert len(result) == 3
        assert result == mock_agents

    async def test_undefined_sub_agent_logs_warning(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that undefined sub-agent references log a warning."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "sub_agents": ["undefined_agent"],
                },
            },
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"sub_agents": ["undefined_agent"]}

        result = await factory._resolve_sub_agents(  # noqa: SLF001
            agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
        )

        assert result == []
        assert "Sub-agent 'undefined_agent' not found in workflow" in caplog.text


@pytest.mark.asyncio
class TestResolveAgentTools:
    """Test cases for _resolve_agent_tools method."""

    async def test_empty_agent_tools_returns_empty_list(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that empty agent_tools field returns empty list."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "agent_tools": [],
                },
            },
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"agent_tools": []}

        result = await factory._resolve_agent_tools(  # noqa: SLF001
            agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
        )

        assert result == []

    async def test_missing_agent_tools_returns_empty_list(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that missing agent_tools field returns empty list."""
        workflow_class = create_workflow_class(
            agents={"default": {"tools": [], "instruction": "main_prompt"}},
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {}

        result = await factory._resolve_agent_tools(  # noqa: SLF001
            agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
        )

        assert result == []

    async def test_single_agent_tool_created(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that a single agent tool is created correctly."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "agent_tools": ["extractor"],
                },
                "extractor": {
                    "tools": [],
                    "instruction": "extractor_prompt",
                    "description": "Data extractor",
                },
            },
            prompts={
                "main_prompt": lambda _ctx: "Use the extractor",
                "extractor_prompt": lambda _ctx: "Extract data",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"agent_tools": ["extractor"]}

        with (
            patch("google.adk.agents.LlmAgent") as mock_llm_agent,
            patch(
                "google.adk.tools.agent_tool.AgentTool",
            ) as mock_agent_tool_cls,
        ):
            mock_agent_instance = Mock(spec=LlmAgent)
            mock_agent_instance.name = "extractor"
            mock_llm_agent.return_value = mock_agent_instance

            mock_tool_instance = Mock(spec=AgentTool)
            mock_agent_tool_cls.return_value = mock_tool_instance

            result = await factory._resolve_agent_tools(  # noqa: SLF001
                agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
            )

        assert len(result) == 1
        assert result[0] is mock_tool_instance
        mock_agent_tool_cls.assert_called_once_with(mock_agent_instance)

    async def test_multiple_agent_tools_created(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that multiple agent tools are created correctly."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "agent_tools": ["tool1", "tool2"],
                },
                "tool1": {"tools": [], "instruction": "tool1_prompt"},
                "tool2": {"tools": [], "instruction": "tool2_prompt"},
            },
            prompts={
                "main_prompt": lambda _ctx: "Use tools",
                "tool1_prompt": lambda _ctx: "Tool 1",
                "tool2_prompt": lambda _ctx: "Tool 2",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"agent_tools": ["tool1", "tool2"]}

        with (
            patch("google.adk.agents.LlmAgent") as mock_llm_agent,
            patch(
                "google.adk.tools.agent_tool.AgentTool",
            ) as mock_agent_tool_cls,
        ):
            mock_agents = [Mock(spec=LlmAgent) for _ in range(2)]
            mock_agents[0].name = "tool1"
            mock_agents[1].name = "tool2"
            mock_llm_agent.side_effect = mock_agents

            mock_tools = [Mock(spec=AgentTool) for _ in range(2)]
            mock_agent_tool_cls.side_effect = mock_tools

            result = await factory._resolve_agent_tools(  # noqa: SLF001
                agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
            )

        assert len(result) == 2
        assert result == mock_tools

    async def test_undefined_agent_tool_logs_warning(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that undefined agent tool references log a warning."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "agent_tools": ["undefined_tool"],
                },
            },
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        agent_def = {"agent_tools": ["undefined_tool"]}

        result = await factory._resolve_agent_tools(  # noqa: SLF001
            agent_def, mock_model_factory, mock_tool_provider, mock_system_context,
        )

        assert result == []
        assert "Agent tool 'undefined_tool' not found in workflow" in caplog.text


@pytest.mark.asyncio
class TestCreateAgentFromDef:
    """Test cases for create_agent method."""

    async def test_creates_agent_with_description(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that agent is created with description from definition."""
        workflow_class = create_workflow_class(
            agents={
                "expert": {
                    "tools": [],
                    "instruction": "expert_prompt",
                    "description": "An expert agent for testing",
                },
            },
            prompts={"expert_prompt": lambda _ctx: "Be an expert"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_agent_instance = Mock(spec=LlmAgent)
            mock_llm_agent.return_value = mock_agent_instance

            await factory.create_agent(
                agent_name="expert",
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

        call_kwargs = mock_llm_agent.call_args[1]
        assert call_kwargs["description"] == "An expert agent for testing"

    async def test_uses_default_description_when_missing(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that default description is used when not provided."""
        workflow_class = create_workflow_class(
            agents={"expert": {"tools": [], "instruction": "expert_prompt"}},
            prompts={"expert_prompt": lambda _ctx: "Be an expert"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_agent_instance = Mock(spec=LlmAgent)
            mock_llm_agent.return_value = mock_agent_instance

            await factory.create_agent(
                agent_name="expert",
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

        call_kwargs = mock_llm_agent.call_args[1]
        assert call_kwargs["description"] == "Agent: expert"


@pytest.mark.asyncio
class TestCreateRootAgent:
    """Test cases for create_root_agent method."""

    async def test_creates_agent_with_sub_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that create_root_agent passes sub_agents to LlmAgent."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "sub_agents": ["expert"],
                },
                "expert": {
                    "tools": [],
                    "instruction": "expert_prompt",
                    "description": "Expert",
                },
            },
            prompts={
                "main_prompt": lambda _ctx: "Coordinate",
                "expert_prompt": lambda _ctx: "Expertise",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_sub_agent = Mock(spec=LlmAgent)
            mock_sub_agent.name = "expert"
            mock_root_agent = Mock(spec=LlmAgent)
            mock_llm_agent.side_effect = [mock_sub_agent, mock_root_agent]

            await factory.create_root_agent(
                mock_model_factory, mock_tool_provider, mock_system_context,
            )

        # Verify root agent was created with sub_agents
        root_call = mock_llm_agent.call_args_list[-1]
        assert "sub_agents" in root_call[1]
        assert mock_sub_agent in root_call[1]["sub_agents"]

    async def test_creates_agent_with_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that create_root_agent adds agent tools to tools list."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "agent_tools": ["helper"],
                },
                "helper": {
                    "tools": [],
                    "instruction": "helper_prompt",
                    "description": "Helper",
                },
            },
            prompts={
                "main_prompt": lambda _ctx: "Use helper",
                "helper_prompt": lambda _ctx: "Help",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        with (
            patch("google.adk.agents.LlmAgent") as mock_llm_agent,
            patch(
                "google.adk.tools.agent_tool.AgentTool",
            ) as mock_agent_tool_cls,
        ):
            mock_helper_agent = Mock(spec=LlmAgent)
            mock_helper_agent.name = "helper"
            mock_root_agent = Mock(spec=LlmAgent)
            mock_llm_agent.side_effect = [mock_helper_agent, mock_root_agent]

            mock_agent_tool = Mock(spec=AgentTool)
            mock_agent_tool_cls.return_value = mock_agent_tool

            await factory.create_root_agent(
                mock_model_factory, mock_tool_provider, mock_system_context,
            )

        # Verify AgentTool was created and added to tools
        mock_agent_tool_cls.assert_called_once_with(mock_helper_agent)
        root_call = mock_llm_agent.call_args_list[-1]
        assert mock_agent_tool in root_call[1]["tools"]

    async def test_creates_agent_with_both_patterns(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that create_root_agent handles both delegate and use patterns."""
        workflow_class = create_workflow_class(
            agents={
                "default": {
                    "tools": [],
                    "instruction": "main_prompt",
                    "sub_agents": ["researcher"],
                    "agent_tools": ["summarizer"],
                },
                "researcher": {
                    "tools": [],
                    "instruction": "researcher_prompt",
                    "description": "Researcher",
                },
                "summarizer": {
                    "tools": [],
                    "instruction": "summarizer_prompt",
                    "description": "Summarizer",
                },
            },
            prompts={
                "main_prompt": lambda _ctx: "Coordinate",
                "researcher_prompt": lambda _ctx: "Research",
                "summarizer_prompt": lambda _ctx: "Summarize",
            },
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        with (
            patch("google.adk.agents.LlmAgent") as mock_llm_agent,
            patch(
                "google.adk.tools.agent_tool.AgentTool",
            ) as mock_agent_tool_cls,
        ):
            mock_researcher = Mock(spec=LlmAgent)
            mock_researcher.name = "researcher"
            mock_summarizer = Mock(spec=LlmAgent)
            mock_summarizer.name = "summarizer"
            mock_root_agent = Mock(spec=LlmAgent)
            mock_llm_agent.side_effect = [
                mock_researcher,
                mock_summarizer,
                mock_root_agent,
            ]

            mock_agent_tool = Mock(spec=AgentTool)
            mock_agent_tool_cls.return_value = mock_agent_tool

            await factory.create_root_agent(
                mock_model_factory, mock_tool_provider, mock_system_context,
            )

        # Verify both patterns are used
        root_call = mock_llm_agent.call_args_list[-1]
        assert "sub_agents" in root_call[1]
        assert mock_researcher in root_call[1]["sub_agents"]
        assert mock_agent_tool in root_call[1]["tools"]


@pytest.mark.asyncio
class TestClose:
    """Test cases for close method with nested agents."""

    async def test_close_simple_agent(self) -> None:
        """Test closing a simple agent without nested agents."""
        workflow_class = create_workflow_class(
            agents={"default": {"tools": [], "instruction": "main_prompt"}},
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        mock_agent_instance = Mock(spec=LlmAgent)
        mock_agent_instance.sub_agents = []
        mock_agent_instance.tools = None

        # Should complete without error
        await factory.close(mock_agent_instance)

    async def test_close_agent_with_sub_agents(self) -> None:
        """Test closing an agent with sub-agents."""
        workflow_class = create_workflow_class(
            agents={"default": {"tools": [], "instruction": "main_prompt"}},
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        sub_tool = MockTool("sub_tool")
        sub_agent = MockLlmAgent(name="sub_agent", tools=[sub_tool])

        root_tool = MockTool("root_tool")
        root_agent = MockLlmAgent(
            name="root_agent",
            tools=[root_tool],
            sub_agents=[sub_agent],
        )

        await factory.close(root_agent)

        assert sub_tool.closed
        assert root_tool.closed

    async def test_close_agent_with_agent_tools(self) -> None:
        """Test closing an agent with AgentTool objects."""
        workflow_class = create_workflow_class(
            agents={"default": {"tools": [], "instruction": "main_prompt"}},
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        wrapped_tool = MockTool("wrapped_tool")
        wrapped_agent = MockLlmAgent(name="wrapped_agent", tools=[wrapped_tool])

        agent_tool = MockAgentTool("agent_tool", wrapped_agent)

        root_agent = MockLlmAgent(name="root_agent", tools=[agent_tool])

        await factory.close(root_agent)

        assert wrapped_tool.closed
        assert agent_tool.closed

    async def test_close_depth_first_order(self) -> None:
        """Test that closing happens in depth-first order."""
        workflow_class = create_workflow_class(
            agents={"default": {"tools": [], "instruction": "main_prompt"}},
            prompts={"main_prompt": lambda _ctx: "Do something"},
        )
        factory = DslAgentFactory(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=[],
        )

        close_order: list[str] = []

        class OrderTrackingTool(MockTool):
            """Tool that tracks close order."""

            def __init__(self, name: str) -> None:
                self.name = name
                self.closed = False

            async def close(self) -> None:
                self.closed = True
                close_order.append(self.name)

        sub_tool = OrderTrackingTool("sub_tool")
        sub_agent = MockLlmAgent(name="sub_agent", tools=[sub_tool])

        root_tool = OrderTrackingTool("root_tool")
        root_agent = MockLlmAgent(
            name="root_agent",
            tools=[root_tool],
            sub_agents=[sub_agent],
        )

        await factory.close(root_agent)

        # Sub-agent's tools should be closed before root agent's tools
        assert close_order == ["sub_tool", "root_tool"]
