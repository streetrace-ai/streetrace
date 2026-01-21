"""Integration tests for DSL agentic patterns with ADK.

Test the full pipeline: parse -> analyze -> generate -> load -> create_agent
for the coordinator (delegate) and hierarchical (use) patterns.
"""

from pathlib import Path
from types import CodeType
from unittest.mock import Mock

import pytest
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from streetrace.agents.dsl_agent_loader import DslStreetRaceAgent, compiled_exec
from streetrace.dsl import compile_dsl
from streetrace.dsl.runtime.workflow import DslAgentWorkflow
from streetrace.llm.model_factory import ModelFactory
from streetrace.system_context import SystemContext
from streetrace.tools.tool_provider import ToolProvider

# DSL source for coordinator pattern with delegate keyword
COORDINATOR_DSL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt coordinator_prompt: \"\"\"
You are a coordinator agent that delegates tasks to specialized sub-agents.
\"\"\"

prompt research_prompt: \"\"\"
You are a research agent that gathers information.
\"\"\"

prompt code_prompt: \"\"\"
You are a code agent that writes code.
\"\"\"

tool fs = builtin streetrace.fs

agent research_agent:
    tools fs
    instruction research_prompt
    description "Research agent for gathering information"

agent code_agent:
    tools fs
    instruction code_prompt
    description "Code agent for writing code"

agent:
    tools fs
    instruction coordinator_prompt
    delegate research_agent, code_agent
"""

# DSL source for hierarchical pattern with use keyword
HIERARCHICAL_DSL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt main_prompt: \"\"\"
You are a main agent that can use other agents as tools.
\"\"\"

prompt summarizer_prompt: \"\"\"
You are a summarizer agent.
\"\"\"

prompt validator_prompt: \"\"\"
You are a validator agent.
\"\"\"

tool fs = builtin streetrace.fs

agent summarizer_agent:
    tools fs
    instruction summarizer_prompt
    description "Summarizes content"

agent validator_agent:
    tools fs
    instruction validator_prompt
    description "Validates results"

agent:
    tools fs
    instruction main_prompt
    use summarizer_agent, validator_agent
"""

# DSL source for combined patterns (both delegate and use)
COMBINED_DSL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt coordinator_prompt: \"\"\"
You are a coordinator that both delegates and uses agents as tools.
\"\"\"

prompt worker_prompt: \"\"\"
You are a worker agent.
\"\"\"

prompt analyzer_prompt: \"\"\"
You are an analyzer agent.
\"\"\"

prompt helper_prompt: \"\"\"
You are a helper agent used as a tool.
\"\"\"

tool fs = builtin streetrace.fs

agent worker_agent:
    tools fs
    instruction worker_prompt
    description "Performs work tasks"

agent analyzer_agent:
    tools fs
    instruction analyzer_prompt
    description "Analyzes data"

agent helper_agent:
    tools fs
    instruction helper_prompt
    description "Helper utility agent"

agent:
    tools fs
    instruction coordinator_prompt
    delegate worker_agent, analyzer_agent
    use helper_agent
"""

# Simple DSL for basic tests
SIMPLE_DSL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt main_prompt: \"\"\"
You are a simple agent.
\"\"\"

tool fs = builtin streetrace.fs

agent:
    tools fs
    instruction main_prompt
"""


class MockLlmInterface:
    """Mock LLM interface for testing."""

    def __init__(self, model_name: str = "test-model") -> None:
        """Initialize mock interface."""
        self.model = model_name

    def get_adk_llm(self) -> str:
        """Return model name for ADK LLM."""
        # LlmAgent accepts string model names directly
        return self.model


@pytest.fixture
def mock_model_factory() -> Mock:
    """Create a mock model factory."""
    factory = Mock(spec=ModelFactory)
    mock_interface = MockLlmInterface()
    factory.get_llm_interface.return_value = mock_interface
    # Return string model name which LlmAgent accepts
    factory.get_current_model.return_value = "test-model"
    return factory


@pytest.fixture
def mock_tool_provider() -> Mock:
    """Create a mock tool provider that returns empty tools."""
    provider = Mock(spec=ToolProvider)
    provider.get_tools.return_value = []
    return provider


@pytest.fixture
def mock_system_context() -> Mock:
    """Create a mock system context."""
    return Mock(spec=SystemContext)


def compile_and_load(source: str, filename: str = "test.sr") -> DslStreetRaceAgent:
    """Compile DSL source and load as agent.

    Args:
        source: DSL source code.
        filename: Filename for error reporting.

    Returns:
        DslStreetRaceAgent wrapping the compiled workflow.

    """
    bytecode, source_map = compile_dsl(source, filename, use_cache=False)
    workflow_class = run_bytecode(bytecode)
    return DslStreetRaceAgent(
        workflow_class=workflow_class,
        source_file=Path(filename),
        source_map=source_map,
    )


def run_bytecode(bytecode: CodeType) -> type[DslAgentWorkflow]:
    """Run bytecode and extract workflow class.

    Args:
        bytecode: Compiled bytecode.

    Returns:
        The generated workflow class.

    """
    namespace: dict[str, object] = {}
    compiled_exec(bytecode, namespace)

    for obj_name, obj in namespace.items():
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, DslAgentWorkflow):
            continue
        if obj_name == "DslAgentWorkflow":
            continue
        return obj

    msg = "No workflow class found in compiled bytecode"
    raise ValueError(msg)


@pytest.mark.asyncio
class TestCoordinatorPattern:
    """Test the coordinator pattern with delegate keyword."""

    async def test_delegate_creates_sub_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that delegate keyword creates sub_agents on LlmAgent."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Verify root agent has sub_agents
        assert hasattr(root_agent, "sub_agents")
        assert root_agent.sub_agents is not None
        assert len(root_agent.sub_agents) == 2

    async def test_sub_agents_have_correct_names(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that sub-agents are created with correct names."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        sub_agent_names = {agent.name for agent in root_agent.sub_agents}
        assert "research_agent" in sub_agent_names
        assert "code_agent" in sub_agent_names

    async def test_sub_agents_have_descriptions(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that sub-agents have descriptions from DSL."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Find research agent and check description
        research_agent = next(
            a for a in root_agent.sub_agents if a.name == "research_agent"
        )
        assert "Research agent" in research_agent.description

    async def test_sub_agents_are_llm_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that sub-agents are LlmAgent instances."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        for sub_agent in root_agent.sub_agents:
            assert isinstance(sub_agent, LlmAgent)


@pytest.mark.asyncio
class TestHierarchicalPattern:
    """Test the hierarchical pattern with use keyword."""

    async def test_use_creates_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that use keyword creates AgentTool wrappers in tools."""
        dsl_agent = compile_and_load(HIERARCHICAL_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Find AgentTool instances in tools
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        assert len(agent_tools) == 2

    async def test_agent_tools_wrap_correct_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that AgentTools wrap the correct agents."""
        dsl_agent = compile_and_load(HIERARCHICAL_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        wrapped_agent_names = {tool.agent.name for tool in agent_tools}

        assert "summarizer_agent" in wrapped_agent_names
        assert "validator_agent" in wrapped_agent_names

    async def test_wrapped_agents_have_instructions(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that wrapped agents have proper instructions."""
        dsl_agent = compile_and_load(HIERARCHICAL_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        summarizer_tool = next(
            t for t in agent_tools if t.agent.name == "summarizer_agent"
        )

        # Verify the wrapped agent has an instruction
        assert summarizer_tool.agent.instruction is not None
        assert len(summarizer_tool.agent.instruction) > 0

    async def test_no_sub_agents_for_use_only(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that use-only pattern has no sub_agents."""
        dsl_agent = compile_and_load(HIERARCHICAL_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # sub_agents should be empty or None for use-only pattern
        sub_agents = getattr(root_agent, "sub_agents", None) or []
        assert len(sub_agents) == 0


@pytest.mark.asyncio
class TestCombinedPatterns:
    """Test combined delegate and use patterns."""

    async def test_combined_has_both_sub_agents_and_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that combined pattern has both sub_agents and agent tools."""
        dsl_agent = compile_and_load(COMBINED_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Verify sub_agents from delegate
        assert root_agent.sub_agents is not None
        assert len(root_agent.sub_agents) == 2

        # Verify AgentTools from use
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        assert len(agent_tools) == 1

    async def test_combined_sub_agents_are_separate_from_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that sub_agents and agent_tools contain different agents."""
        dsl_agent = compile_and_load(COMBINED_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        sub_agent_names = {a.name for a in root_agent.sub_agents}
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        agent_tool_names = {t.agent.name for t in agent_tools}

        # worker_agent and analyzer_agent should be in sub_agents
        assert "worker_agent" in sub_agent_names
        assert "analyzer_agent" in sub_agent_names

        # helper_agent should be in agent_tools
        assert "helper_agent" in agent_tool_names

        # No overlap
        assert len(sub_agent_names & agent_tool_names) == 0

    async def test_combined_all_agents_have_correct_types(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that all agents in combined pattern have correct types."""
        dsl_agent = compile_and_load(COMBINED_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Root is LlmAgent
        assert isinstance(root_agent, LlmAgent)

        # Sub-agents are LlmAgents
        for sub_agent in root_agent.sub_agents:
            assert isinstance(sub_agent, LlmAgent)

        # Agent tools wrap LlmAgents
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        for tool in agent_tools:
            assert isinstance(tool.agent, LlmAgent)


@pytest.mark.asyncio
class TestFullPipeline:
    """Test the complete pipeline from DSL source to agent creation."""

    async def test_pipeline_parse_analyze_generate_load_create(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test the full pipeline from DSL string to working agent."""
        # Step 1: Compile (parse + analyze + generate)
        bytecode, source_map = compile_dsl(COORDINATOR_DSL, "test.sr", use_cache=False)

        # Verify bytecode is valid
        assert isinstance(bytecode, CodeType)
        assert len(source_map) > 0

        # Step 2: Run and load workflow class
        workflow_class = run_bytecode(bytecode)
        assert issubclass(workflow_class, DslAgentWorkflow)

        # Step 3: Create DslStreetRaceAgent
        dsl_agent = DslStreetRaceAgent(
            workflow_class=workflow_class,
            source_file=Path("test.sr"),
            source_map=source_map,
        )

        # Step 4: Create ADK agent
        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Verify final agent structure
        assert isinstance(root_agent, LlmAgent)
        assert root_agent.name == "test"
        assert len(root_agent.sub_agents) == 2

    async def test_pipeline_preserves_agent_hierarchy(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that the pipeline preserves agent hierarchy from DSL."""
        dsl_agent = compile_and_load(COORDINATOR_DSL, "coordinator.sr")

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # The DSL defined: default -> [research_agent, code_agent]
        assert root_agent.name == "coordinator"
        assert len(root_agent.sub_agents) == 2

        sub_names = {a.name for a in root_agent.sub_agents}
        assert sub_names == {"research_agent", "code_agent"}

    async def test_pipeline_with_simple_agent(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test pipeline with a simple agent without agentic patterns."""
        dsl_agent = compile_and_load(SIMPLE_DSL, "simple.sr")

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        assert isinstance(root_agent, LlmAgent)
        assert root_agent.name == "simple"

        # No sub_agents or agent_tools for simple agent
        sub_agents = getattr(root_agent, "sub_agents", None) or []
        assert len(sub_agents) == 0

        agent_tools = [t for t in (root_agent.tools or []) if isinstance(t, AgentTool)]
        assert len(agent_tools) == 0


@pytest.mark.asyncio
class TestAgentClose:
    """Test resource cleanup for agents with nested patterns."""

    async def test_close_cleans_up_workflow_instance(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that close() clears the workflow instance."""
        dsl_agent = compile_and_load(SIMPLE_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Workflow instance should exist after create_agent
        assert dsl_agent._workflow_instance is not None  # noqa: SLF001

        await dsl_agent.close(root_agent)

        # Workflow instance should be cleared after close
        assert dsl_agent._workflow_instance is None  # noqa: SLF001

    async def test_close_with_sub_agents(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that close() handles agents with sub_agents."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Should not raise even with sub_agents
        await dsl_agent.close(root_agent)

        assert dsl_agent._workflow_instance is None  # noqa: SLF001

    async def test_close_with_agent_tools(
        self,
        mock_model_factory: Mock,
        mock_tool_provider: Mock,
        mock_system_context: Mock,
    ) -> None:
        """Test that close() handles agents with agent tools."""
        dsl_agent = compile_and_load(HIERARCHICAL_DSL)

        root_agent = await dsl_agent.create_agent(
            mock_model_factory, mock_tool_provider, mock_system_context,
        )

        # Should not raise even with agent tools
        await dsl_agent.close(root_agent)

        assert dsl_agent._workflow_instance is None  # noqa: SLF001


class TestWorkflowAttributes:
    """Test that workflow class attributes are set correctly."""

    def test_workflow_has_agents_dict(self) -> None:
        """Test that compiled workflow has _agents dict."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)
        workflow_class = dsl_agent._workflow_class  # noqa: SLF001

        assert hasattr(workflow_class, "_agents")
        agents = workflow_class._agents  # noqa: SLF001

        # Should have default, research_agent, code_agent
        assert "default" in agents
        assert "research_agent" in agents
        assert "code_agent" in agents

    def test_workflow_agents_have_sub_agents_field(self) -> None:
        """Test that agents in workflow have sub_agents field from delegate."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)
        workflow_class = dsl_agent._workflow_class  # noqa: SLF001

        default_agent = workflow_class._agents["default"]  # noqa: SLF001
        assert "sub_agents" in default_agent
        assert default_agent["sub_agents"] == ["research_agent", "code_agent"]

    def test_workflow_agents_have_agent_tools_field(self) -> None:
        """Test that agents in workflow have agent_tools field from use."""
        dsl_agent = compile_and_load(HIERARCHICAL_DSL)
        workflow_class = dsl_agent._workflow_class  # noqa: SLF001

        default_agent = workflow_class._agents["default"]  # noqa: SLF001
        assert "agent_tools" in default_agent
        assert default_agent["agent_tools"] == ["summarizer_agent", "validator_agent"]

    def test_workflow_has_prompts_dict(self) -> None:
        """Test that compiled workflow has _prompts dict."""
        dsl_agent = compile_and_load(COORDINATOR_DSL)
        workflow_class = dsl_agent._workflow_class  # noqa: SLF001

        assert hasattr(workflow_class, "_prompts")
        prompts = workflow_class._prompts  # noqa: SLF001

        assert "coordinator_prompt" in prompts
        assert "research_prompt" in prompts
        assert "code_prompt" in prompts
