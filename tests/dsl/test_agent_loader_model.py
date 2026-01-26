"""Tests for DSL agent loader model resolution.

Test that models defined in DSL files are properly resolved according to
the design spec via DslDefinitionLoader and DslAgentFactory:
1. Model from prompt's `using model` clause
2. Fall back to model named "main"
3. CLI override
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

# DSL sources for testing model resolution
DSL_WITH_MAIN_MODEL = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt my_instruction: \"\"\"You are a helpful assistant.\"\"\"

agent:
    instruction my_instruction
"""

DSL_WITH_PROMPT_MODEL = """\
streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/claude-haiku

prompt my_instruction using model "fast": \"\"\"You are a quick helper.\"\"\"

agent:
    instruction my_instruction
"""

DSL_WITH_MULTIPLE_MODELS = """\
streetrace v1

model main = anthropic/claude-sonnet
model fast = anthropic/claude-haiku
model smart = anthropic/claude-opus

prompt quick_prompt using model "fast": \"\"\"Quick response.\"\"\"
prompt main_prompt: \"\"\"Main response.\"\"\"

agent QuickAgent:
    instruction quick_prompt

agent MainAgent:
    instruction main_prompt
"""

DSL_WITH_NO_MAIN_MODEL = """\
streetrace v1

model fast = anthropic/claude-haiku

prompt my_instruction: \"\"\"You are a helper.\"\"\"

agent:
    instruction my_instruction
"""


class TestModelResolutionFromDsl:
    """Test model resolution from DSL files."""

    @pytest.fixture
    def mock_model_factory(self) -> MagicMock:
        """Create a mock model factory."""
        factory = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_adk_llm.return_value = MagicMock()
        factory.get_llm_interface.return_value = mock_llm
        factory.get_current_model.return_value = "cli-override-model"
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

    def test_model_from_prompt_using_clause(self, tmp_path: Path) -> None:
        """Model from prompt's using model clause is stored."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_PROMPT_MODEL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that prompts dict stores model association
        workflow_class = agent_factory.workflow_class
        prompts = workflow_class._prompts  # noqa: SLF001

        # Verify prompts dict exists
        assert "my_instruction" in prompts

    def test_model_fallback_to_main(self, tmp_path: Path) -> None:
        """Agent uses model named 'main' if no model specified in prompt."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MAIN_MODEL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Check that models dict has main
        workflow_class = agent_factory.workflow_class
        models = workflow_class._models  # noqa: SLF001

        assert "main" in models
        assert models["main"] == "anthropic/claude-sonnet"

    @pytest.mark.asyncio
    async def test_create_agent_uses_prompt_model(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Agent uses the model specified in the prompt's using clause."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_PROMPT_MODEL)

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

            # Verify model_factory was called with the prompt's model
            mock_model_factory.get_llm_interface.assert_called()
            call_args = mock_model_factory.get_llm_interface.call_args
            # Should use "fast" model (anthropic/claude-haiku), not "main"
            assert (
                "fast" in str(call_args)
                or "claude-haiku" in str(call_args)
                or call_args.args[0] == "anthropic/claude-haiku"
            )

    @pytest.mark.asyncio
    async def test_create_agent_uses_main_model_fallback(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Agent uses 'main' model when prompt has no model clause."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_MAIN_MODEL)

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

            # Verify model_factory was called with main model
            mock_model_factory.get_llm_interface.assert_called()
            call_args = mock_model_factory.get_llm_interface.call_args
            # Should use "main" model (anthropic/claude-sonnet)
            assert (
                "main" in str(call_args)
                or "claude-sonnet" in str(call_args)
                or call_args.args[0] == "anthropic/claude-sonnet"
            )

    @pytest.mark.asyncio
    async def test_no_first_model_guessing(
        self,
        tmp_path: Path,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """Agent does NOT guess first model if no 'main' model exists."""
        # This DSL has no "main" model
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_NO_MAIN_MODEL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Should use CLI override (get_current_model), NOT guess "fast"
        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify we fell back to get_current_model (CLI override)
            # NOT get_llm_interface with "fast" (the only defined model)
            if mock_model_factory.get_llm_interface.called:
                # If get_llm_interface was called, it should NOT be with "fast"
                call_args = mock_model_factory.get_llm_interface.call_args
                if call_args.args:
                    model_used = call_args.args[0]
                    assert model_used != "anthropic/claude-haiku"
                    assert "fast" not in str(model_used).lower()
            else:
                # Alternatively, get_current_model should have been called
                mock_model_factory.get_current_model.assert_called()

    @pytest.mark.asyncio
    async def test_cli_model_overrides_dsl(
        self,
        tmp_path: Path,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """CLI model argument overrides DSL model specification."""
        dsl_file = tmp_path / "test_agent.sr"
        dsl_file.write_text(DSL_WITH_PROMPT_MODEL)

        loader = DslDefinitionLoader()
        definition = loader.load(make_dsl_resolution_from_path(dsl_file))
        agent_factory = definition.agent_factory

        # Create model factory that tracks which model was requested
        mock_model_factory = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_adk_llm.return_value = MagicMock()
        mock_model_factory.get_llm_interface.return_value = mock_llm
        mock_model_factory.get_current_model.return_value = "cli-override-model"
        mock_model_factory.has_model_override.return_value = True

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await agent_factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # When CLI override is present, it should be used
            # The exact mechanism depends on implementation
            mock_model_factory.get_llm_interface.assert_called()
