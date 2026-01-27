"""Tests for schema support in DslAgentFactory.

Test that _resolve_output_schema finds the schema from prompts
and that create_agent passes output_schema to LlmAgent.
"""

from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from streetrace.dsl.runtime.workflow import DslAgentWorkflow, PromptSpec
from streetrace.workloads.dsl_agent_factory import DslAgentFactory


class OutputModel(BaseModel):
    """Test output schema for agents."""

    result: str
    confidence: float


class AnotherModel(BaseModel):
    """Another test schema."""

    value: int


class SchemaWorkflow(DslAgentWorkflow):
    """Test workflow with schemas."""

    _models: ClassVar[dict[str, str]] = {"main": "test-model"}
    _schemas: ClassVar[dict[str, type[BaseModel]]] = {
        "OutputModel": OutputModel,
        "AnotherModel": AnotherModel,
    }
    _prompts: ClassVar[dict[str, object]] = {
        "with_schema": PromptSpec(
            body=lambda _: "Return structured data",
            schema="OutputModel",
        ),
        "without_schema": PromptSpec(
            body=lambda _: "Return anything",
            schema=None,
        ),
        "missing_schema": PromptSpec(
            body=lambda _: "Return data",
            schema="NonExistentSchema",
        ),
        "old_style": lambda _: "Old style prompt",
    }
    _agents: ClassVar[dict[str, dict[str, object]]] = {
        "schema_agent": {
            "instruction": "with_schema",
            "description": "Agent with schema",
        },
        "no_schema_agent": {
            "instruction": "without_schema",
            "description": "Agent without schema",
        },
        "missing_schema_agent": {
            "instruction": "missing_schema",
            "description": "Agent with missing schema",
        },
        "old_style_agent": {
            "instruction": "old_style",
            "description": "Agent with old style prompt",
        },
        "no_instruction_agent": {
            "description": "Agent without instruction",
        },
    }


@pytest.fixture
def factory() -> DslAgentFactory:
    """Create a DslAgentFactory for testing."""
    return DslAgentFactory(
        workflow_class=SchemaWorkflow,
        source_file=Path("/test/workflow.sr"),
        source_map=[],
    )


@pytest.fixture
def mock_model_factory() -> MagicMock:
    """Create a mock ModelFactory."""
    factory = MagicMock()
    mock_llm = MagicMock()
    mock_llm.get_adk_llm.return_value = "mock-adk-model"
    factory.get_llm_interface.return_value = mock_llm
    factory.get_current_model.return_value = "default-model"
    return factory


@pytest.fixture
def mock_tool_provider() -> MagicMock:
    """Create a mock ToolProvider."""
    provider = MagicMock()
    provider.get_tools.return_value = []
    return provider


@pytest.fixture
def mock_system_context() -> MagicMock:
    """Create a mock SystemContext."""
    return MagicMock()


class TestResolveOutputSchema:
    """Test _resolve_output_schema method."""

    def test_returns_model_for_agent_with_schema(
        self, factory: DslAgentFactory,
    ) -> None:
        """Return Pydantic model when agent's instruction has schema."""
        agent_def = {"instruction": "with_schema"}
        result = factory._resolve_output_schema(agent_def)  # noqa: SLF001
        assert result is OutputModel

    def test_returns_none_when_prompt_has_no_schema(
        self, factory: DslAgentFactory,
    ) -> None:
        """Return None when agent's prompt has no schema."""
        agent_def = {"instruction": "without_schema"}
        result = factory._resolve_output_schema(agent_def)  # noqa: SLF001
        assert result is None

    def test_returns_none_when_schema_not_in_dict(
        self, factory: DslAgentFactory,
    ) -> None:
        """Return None when schema name not in _schemas dict."""
        agent_def = {"instruction": "missing_schema"}
        result = factory._resolve_output_schema(agent_def)  # noqa: SLF001
        assert result is None

    def test_returns_none_for_old_style_prompt(
        self, factory: DslAgentFactory,
    ) -> None:
        """Return None for old-style lambda prompts."""
        agent_def = {"instruction": "old_style"}
        result = factory._resolve_output_schema(agent_def)  # noqa: SLF001
        assert result is None

    def test_returns_none_when_no_instruction(
        self, factory: DslAgentFactory,
    ) -> None:
        """Return None when agent has no instruction."""
        agent_def = {"description": "No instruction"}
        result = factory._resolve_output_schema(agent_def)  # noqa: SLF001
        assert result is None

    def test_returns_none_when_instruction_not_in_prompts(
        self, factory: DslAgentFactory,
    ) -> None:
        """Return None when instruction name not in prompts dict."""
        agent_def = {"instruction": "nonexistent_prompt"}
        result = factory._resolve_output_schema(agent_def)  # noqa: SLF001
        assert result is None


class TestCreateAgentWithSchema:
    """Test create_agent passes output_schema to LlmAgent."""

    @pytest.mark.asyncio
    async def test_create_agent_passes_output_schema(
        self,
        factory: DslAgentFactory,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """create_agent includes output_schema for schema-expecting prompts."""
        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await factory.create_agent(
                agent_name="schema_agent",
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called with output_schema
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs
            assert "output_schema" in call_kwargs
            assert call_kwargs["output_schema"] is OutputModel

    @pytest.mark.asyncio
    async def test_create_agent_without_schema_omits_output_schema(
        self,
        factory: DslAgentFactory,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """create_agent omits output_schema for prompts without schema."""
        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await factory.create_agent(
                agent_name="no_schema_agent",
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            # Verify LlmAgent was called without output_schema
            mock_llm_agent.assert_called_once()
            call_kwargs = mock_llm_agent.call_args.kwargs
            assert "output_schema" not in call_kwargs

    @pytest.mark.asyncio
    async def test_create_agent_with_old_style_prompt_omits_schema(
        self,
        factory: DslAgentFactory,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """create_agent omits output_schema for old-style prompts."""
        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await factory.create_agent(
                agent_name="old_style_agent",
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            call_kwargs = mock_llm_agent.call_args.kwargs
            assert "output_schema" not in call_kwargs


class TestCreateRootAgentWithSchema:
    """Test create_root_agent passes output_schema to LlmAgent."""

    @pytest.mark.asyncio
    async def test_create_root_agent_passes_output_schema(
        self,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """create_root_agent includes output_schema when default agent has schema."""

        class RootWorkflow(DslAgentWorkflow):
            _models = {"main": "test-model"}  # noqa: RUF012
            _schemas = {"OutputModel": OutputModel}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "root_prompt": PromptSpec(
                    body=lambda _: "Root instruction",
                    schema="OutputModel",
                ),
            }
            _agents = {  # noqa: RUF012
                "default": {
                    "instruction": "root_prompt",
                    "description": "Default agent",
                },
            }

        factory = DslAgentFactory(
            workflow_class=RootWorkflow,
            source_file=Path("/test/root.sr"),
            source_map=[],
        )

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            call_kwargs = mock_llm_agent.call_args.kwargs
            assert "output_schema" in call_kwargs
            assert call_kwargs["output_schema"] is OutputModel

    @pytest.mark.asyncio
    async def test_create_root_agent_omits_schema_when_not_present(
        self,
        mock_model_factory: MagicMock,
        mock_tool_provider: MagicMock,
        mock_system_context: MagicMock,
    ) -> None:
        """create_root_agent omits output_schema when default agent has no schema."""

        class NoSchemaWorkflow(DslAgentWorkflow):
            _models = {"main": "test-model"}  # noqa: RUF012
            _prompts = {  # noqa: RUF012
                "simple_prompt": PromptSpec(
                    body=lambda _: "Simple instruction",
                    schema=None,
                ),
            }
            _agents = {  # noqa: RUF012
                "default": {
                    "instruction": "simple_prompt",
                    "description": "Default agent",
                },
            }

        factory = DslAgentFactory(
            workflow_class=NoSchemaWorkflow,
            source_file=Path("/test/no_schema.sr"),
            source_map=[],
        )

        with patch("google.adk.agents.LlmAgent") as mock_llm_agent:
            mock_llm_agent.return_value = MagicMock()

            await factory.create_root_agent(
                model_factory=mock_model_factory,
                tool_provider=mock_tool_provider,
                system_context=mock_system_context,
            )

            call_kwargs = mock_llm_agent.call_args.kwargs
            assert "output_schema" not in call_kwargs
