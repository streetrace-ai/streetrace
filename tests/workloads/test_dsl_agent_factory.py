"""Tests for DslAgentFactory class.

These tests verify the DslAgentFactory class that extracts agent creation
logic from DslStreetRaceAgent for use by DslWorkload.
"""

from pathlib import Path
from typing import ClassVar
from unittest.mock import Mock

import pytest
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.dsl.sourcemap import SourceMapping


class SampleWorkflowWithAgents(DslAgentWorkflow):
    """Sample workflow with agents for testing."""

    _models: ClassVar[dict[str, str]] = {"main": "test-model"}
    _prompts: ClassVar[dict[str, object]] = {
        "main_prompt": lambda _ctx: "You are a main agent.",
        "sub_prompt": lambda _ctx: "You are a sub agent.",
    }
    _tools: ClassVar[dict[str, dict[str, object]]] = {
        "fs": {"type": "builtin", "builtin_ref": "streetrace.fs"},
    }
    _agents: ClassVar[dict[str, dict[str, object]]] = {
        "default": {
            "instruction": "main_prompt",
            "tools": ["fs"],
            "description": "Main agent",
        },
        "helper_agent": {
            "instruction": "sub_prompt",
            "tools": ["fs"],
            "description": "Helper agent",
        },
    }


class WorkflowWithDelegatePattern(DslAgentWorkflow):
    """Workflow with delegate pattern for testing sub_agents."""

    _models: ClassVar[dict[str, str]] = {"main": "test-model"}
    _prompts: ClassVar[dict[str, object]] = {
        "coordinator_prompt": lambda _ctx: "You are a coordinator.",
        "worker_prompt": lambda _ctx: "You are a worker.",
    }
    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    _agents: ClassVar[dict[str, dict[str, object]]] = {
        "default": {
            "instruction": "coordinator_prompt",
            "tools": [],
            "description": "Coordinator agent",
            "sub_agents": ["worker_agent"],
        },
        "worker_agent": {
            "instruction": "worker_prompt",
            "tools": [],
            "description": "Worker agent",
        },
    }


class WorkflowWithUsePattern(DslAgentWorkflow):
    """Workflow with use pattern for testing agent_tools."""

    _models: ClassVar[dict[str, str]] = {"main": "test-model"}
    _prompts: ClassVar[dict[str, object]] = {
        "main_prompt": lambda _ctx: "You are the main agent.",
        "tool_prompt": lambda _ctx: "You are a tool agent.",
    }
    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    _agents: ClassVar[dict[str, dict[str, object]]] = {
        "default": {
            "instruction": "main_prompt",
            "tools": [],
            "description": "Main agent",
            "agent_tools": ["tool_agent"],
        },
        "tool_agent": {
            "instruction": "tool_prompt",
            "tools": [],
            "description": "Tool agent for hierarchical pattern",
        },
    }


class MockLlmInterface:
    """Mock LLM interface for testing."""

    def __init__(self, model_name: str = "test-model") -> None:
        """Initialize mock interface."""
        self.model = model_name

    def get_adk_llm(self) -> str:
        """Return model name for ADK LLM."""
        return self.model


@pytest.fixture
def mock_model_factory() -> Mock:
    """Create a mock model factory."""
    factory = Mock()
    mock_interface = MockLlmInterface()
    factory.get_llm_interface.return_value = mock_interface
    factory.get_current_model.return_value = "test-model"
    return factory


@pytest.fixture
def mock_tool_provider() -> Mock:
    """Create a mock tool provider that returns empty tools."""
    provider = Mock()
    provider.get_tools.return_value = []
    return provider


@pytest.fixture
def mock_system_context() -> Mock:
    """Create a mock system context."""
    return Mock()


class TestDslAgentFactoryInit:
    """Test DslAgentFactory initialization."""

    def test_requires_workflow_class(self) -> None:
        """Test that workflow_class is required."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        with pytest.raises(TypeError):
            DslAgentFactory(  # type: ignore[call-arg]
                source_file=Path("/test.sr"),
                source_map=[],
            )

    def test_requires_source_file(self) -> None:
        """Test that source_file is required."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        with pytest.raises(TypeError):
            DslAgentFactory(  # type: ignore[call-arg]
                workflow_class=SampleWorkflowWithAgents,
                source_map=[],
            )

    def test_requires_source_map(self) -> None:
        """Test that source_map is required."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        with pytest.raises(TypeError):
            DslAgentFactory(  # type: ignore[call-arg]
                workflow_class=SampleWorkflowWithAgents,
                source_file=Path("/test.sr"),
            )

    def test_can_create_with_all_parameters(self) -> None:
        """Test factory can be created with all required parameters."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        assert factory is not None
        assert factory._workflow_class is SampleWorkflowWithAgents  # noqa: SLF001
        assert factory._source_file == Path("/test.sr")  # noqa: SLF001
        assert factory._source_map == []  # noqa: SLF001


class TestDslAgentFactoryProperties:
    """Test DslAgentFactory properties."""

    def test_workflow_class_property(self) -> None:
        """Test workflow_class property returns correct value."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        assert factory.workflow_class is SampleWorkflowWithAgents

    def test_source_file_property(self) -> None:
        """Test source_file property returns correct value."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test/agent.sr"),
            source_map=[],
        )

        assert factory.source_file == Path("/test/agent.sr")

    def test_source_map_property(self) -> None:
        """Test source_map property returns correct value."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        source_map = [
            SourceMapping(
                generated_line=1,
                generated_column=0,
                source_file="/test.sr",
                source_line=1,
                source_column=0,
            ),
        ]

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=source_map,
        )

        assert factory.source_map is source_map


class TestDslAgentFactoryGetDefaultAgentDef:
    """Test DslAgentFactory._get_default_agent_def()."""

    def test_returns_default_agent_when_exists(self) -> None:
        """Test returns default agent definition when it exists."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = factory._get_default_agent_def()  # noqa: SLF001

        assert agent_def is not None
        assert agent_def.get("instruction") == "main_prompt"
        assert agent_def.get("description") == "Main agent"

    def test_returns_first_agent_when_no_default(self) -> None:
        """Test returns first agent when no default exists."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        class NoDefaultWorkflow(DslAgentWorkflow):
            """Workflow without a default agent."""

            _agents: ClassVar[dict[str, dict[str, object]]] = {
                "first_agent": {"instruction": "test", "description": "First"},
            }

        factory = DslAgentFactory(
            workflow_class=NoDefaultWorkflow,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = factory._get_default_agent_def()  # noqa: SLF001

        assert agent_def is not None
        assert agent_def.get("description") == "First"

    def test_returns_empty_dict_when_no_agents(self) -> None:
        """Test returns empty dict when no agents defined."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        class EmptyWorkflow(DslAgentWorkflow):
            """Workflow with no agents."""

            _agents: ClassVar[dict[str, dict[str, object]]] = {}

        factory = DslAgentFactory(
            workflow_class=EmptyWorkflow,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = factory._get_default_agent_def()  # noqa: SLF001

        assert agent_def == {}


class TestDslAgentFactoryResolveInstruction:
    """Test DslAgentFactory._resolve_instruction()."""

    def test_resolves_instruction_from_prompts(self) -> None:
        """Test resolves instruction from prompts dict."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = {"instruction": "main_prompt"}
        instruction = factory._resolve_instruction(agent_def)  # noqa: SLF001

        assert instruction == "You are a main agent."

    def test_returns_empty_when_no_instruction(self) -> None:
        """Test returns empty string when no instruction specified."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def: dict[str, object] = {}
        instruction = factory._resolve_instruction(agent_def)  # noqa: SLF001

        assert instruction == ""

    def test_returns_empty_when_instruction_not_found(self) -> None:
        """Test returns empty string when instruction not in prompts."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = {"instruction": "nonexistent_prompt"}
        instruction = factory._resolve_instruction(agent_def)  # noqa: SLF001

        assert instruction == ""


class TestDslAgentFactoryResolveModel:
    """Test DslAgentFactory._resolve_model()."""

    def test_resolves_model_from_main(
        self, mock_model_factory: Mock,
    ) -> None:
        """Test resolves model from main model definition."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def: dict[str, object] = {"instruction": "main_prompt"}
        model = factory._resolve_model(mock_model_factory, agent_def)  # noqa: SLF001

        assert model == "test-model"

    def test_uses_current_model_when_no_main(
        self, mock_model_factory: Mock,
    ) -> None:
        """Test uses current model when no main model defined."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        class NoModelWorkflow(DslAgentWorkflow):
            """Workflow without model definitions."""

            _models: ClassVar[dict[str, str]] = {}
            _agents: ClassVar[dict[str, dict[str, object]]] = {
                "default": {"instruction": "test"},
            }

        factory = DslAgentFactory(
            workflow_class=NoModelWorkflow,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def: dict[str, object] = {}
        model = factory._resolve_model(mock_model_factory, agent_def)  # noqa: SLF001

        # Should fall back to get_current_model
        mock_model_factory.get_current_model.assert_called_once()
        assert model == "test-model"


class TestDslAgentFactoryResolveTools:
    """Test DslAgentFactory._resolve_tools()."""

    def test_returns_empty_list_when_no_tools(
        self, mock_tool_provider: Mock,
    ) -> None:
        """Test returns empty list when no tools specified."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def: dict[str, object] = {}
        tools = factory._resolve_tools(mock_tool_provider, agent_def)  # noqa: SLF001

        assert tools == []

    def test_calls_tool_provider_with_tool_refs(
        self, mock_tool_provider: Mock,
    ) -> None:
        """Test calls tool provider with resolved tool refs."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = {"tools": ["fs"]}
        factory._resolve_tools(mock_tool_provider, agent_def)  # noqa: SLF001

        # Verify get_tools was called
        mock_tool_provider.get_tools.assert_called_once()


@pytest.mark.asyncio
class TestDslAgentFactoryCreateAgent:
    """Test DslAgentFactory.create_agent()."""

    async def test_creates_llm_agent(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test creates an LlmAgent instance."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="default",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert isinstance(agent, LlmAgent)

    async def test_uses_agent_name(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test agent has correct name."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="helper_agent",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert agent.name == "helper_agent"

    async def test_raises_for_unknown_agent(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test raises ValueError for unknown agent name."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        with pytest.raises(ValueError, match="not found"):
            await factory.create_agent(
                agent_name="nonexistent_agent",
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

    async def test_agent_has_instruction(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test agent has resolved instruction."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="default",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert agent.instruction is not None
        assert "main agent" in agent.instruction

    async def test_agent_has_description(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test agent has description from definition."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="helper_agent",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert agent.description == "Helper agent"


@pytest.mark.asyncio
class TestDslAgentFactoryResolveSubAgents:
    """Test DslAgentFactory._resolve_sub_agents()."""

    async def test_creates_sub_agents_for_delegate_pattern(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test creates sub-agents from delegate keyword."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=WorkflowWithDelegatePattern,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = {"sub_agents": ["worker_agent"]}
        sub_agents = await factory._resolve_sub_agents(  # noqa: SLF001
            agent_def,
            mock_model_factory,
            mock_tool_provider,
            mock_system_context,
        )

        assert len(sub_agents) == 1
        assert isinstance(sub_agents[0], LlmAgent)
        assert sub_agents[0].name == "worker_agent"

    async def test_returns_empty_list_when_no_sub_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test returns empty list when no sub_agents specified."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def: dict[str, object] = {}
        sub_agents = await factory._resolve_sub_agents(  # noqa: SLF001
            agent_def,
            mock_model_factory,
            mock_tool_provider,
            mock_system_context,
        )

        assert sub_agents == []

    async def test_skips_unknown_sub_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test skips sub-agents that don't exist in workflow."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = {"sub_agents": ["nonexistent_agent"]}
        sub_agents = await factory._resolve_sub_agents(  # noqa: SLF001
            agent_def,
            mock_model_factory,
            mock_tool_provider,
            mock_system_context,
        )

        # Should log warning but not raise
        assert sub_agents == []


@pytest.mark.asyncio
class TestDslAgentFactoryResolveAgentTools:
    """Test DslAgentFactory._resolve_agent_tools()."""

    async def test_creates_agent_tools_for_use_pattern(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test creates AgentTool wrappers from use keyword."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=WorkflowWithUsePattern,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def = {"agent_tools": ["tool_agent"]}
        agent_tools = await factory._resolve_agent_tools(  # noqa: SLF001
            agent_def,
            mock_model_factory,
            mock_tool_provider,
            mock_system_context,
        )

        assert len(agent_tools) == 1
        assert isinstance(agent_tools[0], AgentTool)
        assert agent_tools[0].agent.name == "tool_agent"

    async def test_returns_empty_list_when_no_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test returns empty list when no agent_tools specified."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent_def: dict[str, object] = {}
        agent_tools = await factory._resolve_agent_tools(  # noqa: SLF001
            agent_def,
            mock_model_factory,
            mock_tool_provider,
            mock_system_context,
        )

        assert agent_tools == []


@pytest.mark.asyncio
class TestDslAgentFactoryClose:
    """Test DslAgentFactory.close()."""

    async def test_close_completes_without_error(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test close completes without error."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="default",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        # Should not raise
        await factory.close(agent)

    async def test_close_with_sub_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test close handles agents with sub_agents."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=WorkflowWithDelegatePattern,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="default",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        # Should not raise
        await factory.close(agent)

    async def test_close_with_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test close handles agents with agent_tools."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=WorkflowWithUsePattern,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="default",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        # Should not raise
        await factory.close(agent)


@pytest.mark.asyncio
class TestDslAgentFactoryCreateRootAgent:
    """Test DslAgentFactory.create_root_agent() convenience method."""

    async def test_creates_root_agent_using_source_file_stem(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test create_root_agent uses source file stem as name."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test/my_agent.sr"),
            source_map=[],
        )

        agent = await factory.create_root_agent(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert isinstance(agent, LlmAgent)
        assert agent.name == "my_agent"

    async def test_creates_agent_with_default_definition(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test create_root_agent uses default agent definition."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=SampleWorkflowWithAgents,
            source_file=Path("/test/agent.sr"),
            source_map=[],
        )

        agent = await factory.create_root_agent(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert "main agent" in agent.instruction


class WorkflowWithSelfReference(DslAgentWorkflow):
    """Workflow where an agent references itself via use (agent_tools)."""

    _models: ClassVar[dict[str, str]] = {"main": "test-model"}
    _prompts: ClassVar[dict[str, object]] = {
        "chunker_prompt": lambda _ctx: "You are a recursive chunker.",
    }
    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    _agents: ClassVar[dict[str, dict[str, object]]] = {
        "diff_chunker": {
            "instruction": "chunker_prompt",
            "tools": [],
            "description": "Recursively chunks diffs",
            "agent_tools": ["diff_chunker"],
        },
    }


@pytest.mark.asyncio
class TestDslAgentFactorySelfReference:
    """Test self-referencing agent creation with bounded depth."""

    async def test_self_ref_agent_creates_without_infinite_recursion(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Self-referencing agent creation completes without hanging."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=WorkflowWithSelfReference,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="diff_chunker",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        assert isinstance(agent, LlmAgent)
        assert agent.name == "diff_chunker"

    async def test_top_level_has_self_tool(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Top-level agent includes an AgentTool wrapping itself."""
        from streetrace.workloads.dsl_agent_factory import DslAgentFactory

        factory = DslAgentFactory(
            workflow_class=WorkflowWithSelfReference,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="diff_chunker",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        agent_tools = [t for t in agent.tools if isinstance(t, AgentTool)]
        assert len(agent_tools) == 1
        assert agent_tools[0].agent.name == "diff_chunker"

    async def test_deepest_agent_lacks_self_tool(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Deepest nested agent has no self-tool (depth limit reached)."""
        from streetrace.workloads.dsl_agent_factory import (
            _MAX_SELF_REF_DEPTH,
            DslAgentFactory,
        )

        factory = DslAgentFactory(
            workflow_class=WorkflowWithSelfReference,
            source_file=Path("/test.sr"),
            source_map=[],
        )

        agent = await factory.create_agent(
            agent_name="diff_chunker",
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
        )

        # Traverse the AgentTool chain to the deepest level.
        # With depth limit N, the first create_agent pushes onto the
        # stack (count=1), so we get N-1 nested AgentTool levels.
        current = agent
        depth = 0
        while True:
            nested_tools = [
                t for t in current.tools if isinstance(t, AgentTool)
            ]
            if not nested_tools:
                break
            current = nested_tools[0].agent
            depth += 1

        # The deepest agent should have no AgentTool referencing itself
        deepest_agent_tools = [
            t for t in current.tools if isinstance(t, AgentTool)
        ]
        assert deepest_agent_tools == []
        assert depth == _MAX_SELF_REF_DEPTH - 1
