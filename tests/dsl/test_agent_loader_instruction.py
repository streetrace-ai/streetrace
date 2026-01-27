"""Tests for DSL agent loader instruction resolution.

Test that instructions defined in DSL files are properly resolved and loaded
into ADK agents via DslDefinitionLoader and DslAgentFactory.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from streetrace.agents.resolver import SourceResolution, SourceType
from streetrace.workloads.dsl_loader import DslDefinitionLoader


def make_dsl_resolution_from_path(file_path: Path) -> SourceResolution:
    """Create a SourceResolution by reading content from file."""
    content = file_path.read_text()
    return SourceResolution(
        content=content,
        source=str(file_path),
        source_type=SourceType.FILE_PATH,
        file_path=file_path,
        format="dsl",
    )

# DSL sources for testing instruction loading
DSL_WITH_NAMED_INSTRUCTION = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt my_instruction: \"\"\"You are a helpful coding assistant.\"\"\"

agent:
    instruction my_instruction
"""

DSL_WITH_NAMED_AGENT = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt assistant_prompt: \"\"\"You are a code reviewer.\"\"\"

agent CodeReviewer:
    instruction assistant_prompt
    description "Reviews code"
"""

DSL_WITH_MULTILINE_INSTRUCTION = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt detailed_instruction: \"\"\"
You are a helpful assistant.

Follow these guidelines:
- Be concise
- Be accurate
- Be helpful
\"\"\"

agent:
    instruction detailed_instruction
"""

DSL_WITHOUT_INSTRUCTION = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt some_prompt: \"\"\"Some text\"\"\"

agent:
    tools fs
"""

DSL_WITH_MULTIPLE_PROMPTS = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello there!\"\"\"
prompt my_instruction: \"\"\"You are a professional developer.\"\"\"
prompt farewell: \"\"\"Goodbye!\"\"\"

agent:
    instruction my_instruction
"""


class TestInstructionResolutionFromDsl:
    """Test instruction resolution from DSL files."""

    @pytest.fixture
    def mock_model_factory(self) -> MagicMock:
        """Create a mock model factory."""
        factory = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_adk_llm.return_value = MagicMock()
        factory.get_llm_interface.return_value = mock_llm
        factory.get_current_model.return_value = MagicMock()
        return factory

    @pytest.fixture
    def mock_tool_provider(self) -> MagicMock:
        """Create a mock tool provider."""
        from streetrace.tools.tool_provider import ToolProvider

        provider = MagicMock(spec=ToolProvider)
        provider.get_tools.return_value = []
        provider.work_dir = Path.cwd()
        return provider

    @pytest.fixture
    def mock_system_context(self) -> MagicMock:
        """Create a mock system context."""
        from streetrace.system_context import SystemContext

        return MagicMock(spec=SystemContext)

    def test_instruction_loaded_from_dsl_agent_definition(
        self, tmp_path: Path,
    ) -> None:
        """Instruction is loaded from the agent's instruction field."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_NAMED_INSTRUCTION)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that the agent definition includes instruction reference
        workflow_class = agent_factory.workflow_class
        agents = workflow_class._agents  # noqa: SLF001
        default_agent = agents.get("default")

        assert default_agent is not None
        assert "instruction" in default_agent
        assert default_agent["instruction"] == "my_instruction"

    def test_instruction_not_guessed_by_keyword(self, tmp_path: Path) -> None:
        """Instruction is NOT guessed by keyword matching in prompt name."""
        # This DSL has multiple prompts - only the one specified in
        # agent.instruction should be used
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_PROMPTS)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that the agent uses exactly the specified instruction
        workflow_class = agent_factory.workflow_class
        agents = workflow_class._agents  # noqa: SLF001
        default_agent = agents.get("default")

        assert default_agent is not None
        assert default_agent["instruction"] == "my_instruction"

    @pytest.mark.asyncio
    async def test_create_agent_resolves_instruction_from_prompts(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Instruction is resolved from prompts dict during create_agent."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_NAMED_INSTRUCTION)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called with the correct instruction
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs

            assert "instruction" in call_kwargs
            assert call_kwargs["instruction"] == "You are a helpful coding assistant."

    @pytest.mark.asyncio
    async def test_multiline_instruction_resolved_correctly(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Multiline instructions are resolved correctly."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MULTILINE_INSTRUCTION)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called with multiline instruction
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs

            assert "instruction" in call_kwargs
            instruction = call_kwargs["instruction"]
            assert "You are a helpful assistant" in instruction
            assert "Be concise" in instruction
            assert "Be accurate" in instruction

    @pytest.mark.asyncio
    async def test_named_agent_uses_correct_instruction(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Named agent uses its specified instruction."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_NAMED_AGENT)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called with the correct instruction
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs

            assert "instruction" in call_kwargs
            assert call_kwargs["instruction"] == "You are a code reviewer."

    @pytest.mark.asyncio
    async def test_uses_exact_instruction_not_keyword_match(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Uses exact instruction specified, not keyword match."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MULTIPLE_PROMPTS)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called with exact instruction
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs

            assert "instruction" in call_kwargs
            # Should NOT be "Hello there!" (greeting has "greeting" in name)
            assert call_kwargs["instruction"] != "Hello there!"
            # Should be the exact instruction specified
            assert call_kwargs["instruction"] == "You are a professional developer."
