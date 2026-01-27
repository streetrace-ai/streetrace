"""Tests for schema validation in WorkflowContext.

Test the response parsing, schema validation, and retry logic
in call_llm when prompts have schema expectations.
"""

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from streetrace.dsl.runtime.errors import JSONParseError, SchemaValidationError
from streetrace.dsl.runtime.events import LlmCallEvent
from streetrace.dsl.runtime.workflow import PromptSpec

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


class SimpleTestModel(BaseModel):
    """Simple test schema for validation."""

    name: str
    count: int


class ComplexTestModel(BaseModel):
    """Complex test schema with optional and list fields."""

    approved: bool
    items: list[str]
    notes: str | None = None


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    return MagicMock()


@pytest.fixture
def workflow_context(mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
    """Create a WorkflowContext with test configuration."""
    from streetrace.dsl.runtime.context import WorkflowContext

    ctx = WorkflowContext(workflow=mock_workflow)

    # Set up models
    ctx.set_models({
        "main": "anthropic/claude-sonnet",
    })

    # Set up prompts - including prompts with schema expectations
    ctx.set_prompts({
        "simple_prompt": lambda _: "Return a greeting",
        "schema_prompt": PromptSpec(
            body=lambda _: "Return structured data",
            schema="SimpleTestModel",
        ),
        "complex_schema_prompt": PromptSpec(
            body=lambda _: "Return complex data",
            schema="ComplexTestModel",
        ),
        "no_schema_prompt": PromptSpec(
            body=lambda _: "Return anything",
            schema=None,
        ),
    })

    # Set up schemas
    ctx.set_schemas({
        "SimpleTestModel": SimpleTestModel,
        "ComplexTestModel": ComplexTestModel,
    })

    return ctx


async def collect_events(generator: object) -> list[object]:
    """Collect all events from an async generator."""
    return [event async for event in generator]  # type: ignore[union-attr]


class TestParseJsonResponse:
    """Test _parse_json_response method."""

    def test_parse_plain_json(self, workflow_context: "WorkflowContext") -> None:
        """Parse plain JSON without code blocks."""
        content = '{"name": "test", "count": 42}'
        result = workflow_context._parse_json_response(content)  # noqa: SLF001
        assert result == {"name": "test", "count": 42}

    def test_parse_json_with_whitespace(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Parse JSON with leading/trailing whitespace."""
        content = '   {"name": "test", "count": 42}   '
        result = workflow_context._parse_json_response(content)  # noqa: SLF001
        assert result == {"name": "test", "count": 42}

    def test_parse_json_code_block(self, workflow_context: "WorkflowContext") -> None:
        """Parse JSON from ```json code block."""
        content = """Here is the result:
```json
{"name": "test", "count": 42}
```
"""
        result = workflow_context._parse_json_response(content)  # noqa: SLF001
        assert result == {"name": "test", "count": 42}

    def test_parse_unlabeled_code_block(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Parse JSON from ``` code block without language."""
        content = """Result:
```
{"name": "test", "count": 42}
```
"""
        result = workflow_context._parse_json_response(content)  # noqa: SLF001
        assert result == {"name": "test", "count": 42}

    def test_parse_multiple_code_blocks_raises_error(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Raise JSONParseError when multiple code blocks are present."""
        content = """Multiple results:
```json
{"first": 1}
```
And another:
```json
{"second": 2}
```
"""
        with pytest.raises(JSONParseError) as exc_info:
            workflow_context._parse_json_response(content)  # noqa: SLF001
        assert "multiple code blocks" in exc_info.value.parse_error.lower()

    def test_parse_invalid_json_raises_error(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Raise JSONParseError for invalid JSON."""
        content = "{ invalid json }"
        with pytest.raises(JSONParseError) as exc_info:
            workflow_context._parse_json_response(content)  # noqa: SLF001
        assert exc_info.value.raw_response == content

    def test_parse_empty_content_raises_error(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Raise JSONParseError for empty content."""
        content = ""
        with pytest.raises(JSONParseError):
            workflow_context._parse_json_response(content)  # noqa: SLF001

    def test_parse_code_block_with_invalid_json(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Raise JSONParseError for code block containing invalid JSON."""
        content = """```json
{ not valid json
```"""
        with pytest.raises(JSONParseError):
            workflow_context._parse_json_response(content)  # noqa: SLF001


class TestGetSchemaModel:
    """Test _get_schema_model method."""

    def test_returns_model_for_valid_schema(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Return Pydantic model when schema exists."""
        prompt_spec = PromptSpec(body=lambda _: "test", schema="SimpleTestModel")
        model = workflow_context._get_schema_model(prompt_spec)  # noqa: SLF001
        assert model is SimpleTestModel

    def test_returns_none_when_prompt_spec_is_none(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Return None when prompt_spec is None."""
        model = workflow_context._get_schema_model(None)  # noqa: SLF001
        assert model is None

    def test_returns_none_when_schema_is_none(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Return None when prompt_spec has no schema."""
        prompt_spec = PromptSpec(body=lambda _: "test", schema=None)
        model = workflow_context._get_schema_model(prompt_spec)  # noqa: SLF001
        assert model is None

    def test_returns_none_for_missing_schema(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Return None when schema name not in _schemas dict."""
        prompt_spec = PromptSpec(body=lambda _: "test", schema="NonExistentSchema")
        model = workflow_context._get_schema_model(prompt_spec)  # noqa: SLF001
        assert model is None


class TestEnrichPromptWithSchema:
    """Test _enrich_prompt_with_schema method."""

    def test_enriches_prompt_with_json_instructions(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Append JSON format instructions to prompt."""
        prompt_text = "Original prompt"
        json_schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = workflow_context._enrich_prompt_with_schema(  # noqa: SLF001
            prompt_text, json_schema,
        )

        assert "Original prompt" in result
        assert "IMPORTANT" in result
        assert "JSON" in result
        assert "schema" in result.lower()

    def test_enriched_prompt_includes_schema(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Enriched prompt includes the JSON schema."""
        prompt_text = "Return data"
        json_schema = SimpleTestModel.model_json_schema()
        result = workflow_context._enrich_prompt_with_schema(  # noqa: SLF001
            prompt_text, json_schema,
        )

        assert "name" in result
        assert "count" in result
        # Should contain stringified schema
        assert "properties" in result or '"name"' in result


class TestCallLlmWithSchemaValidation:
    """Test call_llm with schema validation and retry logic."""

    @pytest.mark.asyncio
    async def test_call_llm_without_schema_returns_content(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm without schema returns raw content."""
        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content="plain text response"))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            events = await collect_events(
                workflow_context.call_llm("simple_prompt"),
            )

            assert len(events) == 2
            assert workflow_context.get_last_result() == "plain text response"

    @pytest.mark.asyncio
    async def test_call_llm_with_schema_returns_validated_dict(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm with schema returns validated dict on success."""
        valid_json = json.dumps({"name": "test", "count": 42})
        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content=valid_json))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            await collect_events(
                workflow_context.call_llm("schema_prompt"),
            )

            result = workflow_context.get_last_result()
            assert isinstance(result, dict)
            assert result == {"name": "test", "count": 42}

    @pytest.mark.asyncio
    async def test_call_llm_enriches_prompt_when_schema_present(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm enriches prompt with JSON instructions when schema present."""
        valid_json = json.dumps({"name": "test", "count": 42})
        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content=valid_json))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            events = await collect_events(
                workflow_context.call_llm("schema_prompt"),
            )

            # Check LlmCallEvent contains enriched prompt
            call_event = events[0]
            assert isinstance(call_event, LlmCallEvent)
            assert "JSON" in call_event.prompt_text
            assert "schema" in call_event.prompt_text.lower()

    @pytest.mark.asyncio
    async def test_call_llm_retries_on_parse_error(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm retries when response cannot be parsed as JSON."""
        invalid_json = "not json"
        valid_json = json.dumps({"name": "test", "count": 42})

        with patch("litellm.acompletion") as mock_acompletion:
            # First call returns invalid JSON, second returns valid
            mock_response_bad = MagicMock()
            mock_choice_bad = MagicMock(message=MagicMock(content=invalid_json))
            mock_response_bad.choices = [mock_choice_bad]

            mock_response_good = MagicMock()
            mock_choice_good = MagicMock(message=MagicMock(content=valid_json))
            mock_response_good.choices = [mock_choice_good]

            mock_acompletion.side_effect = [mock_response_bad, mock_response_good]

            await collect_events(
                workflow_context.call_llm("schema_prompt"),
            )

            # Should have called LLM twice
            assert mock_acompletion.call_count == 2
            result = workflow_context.get_last_result()
            assert result == {"name": "test", "count": 42}

    @pytest.mark.asyncio
    async def test_call_llm_retries_on_validation_error(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm retries when response fails schema validation."""
        # Valid JSON but wrong schema (missing required field)
        invalid_schema = json.dumps({"name": "test"})
        valid_json = json.dumps({"name": "test", "count": 42})

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response_bad = MagicMock()
            mock_choice_bad = MagicMock(message=MagicMock(content=invalid_schema))
            mock_response_bad.choices = [mock_choice_bad]

            mock_response_good = MagicMock()
            mock_choice_good = MagicMock(message=MagicMock(content=valid_json))
            mock_response_good.choices = [mock_choice_good]

            mock_acompletion.side_effect = [mock_response_bad, mock_response_good]

            await collect_events(
                workflow_context.call_llm("schema_prompt"),
            )

            assert mock_acompletion.call_count == 2
            result = workflow_context.get_last_result()
            assert result == {"name": "test", "count": 42}

    @pytest.mark.asyncio
    async def test_call_llm_raises_schema_validation_error_after_exhaustion(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm raises SchemaValidationError after max retries."""
        invalid_json = "not json at all"

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content=invalid_json))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            with pytest.raises(SchemaValidationError) as exc_info:
                await collect_events(
                    workflow_context.call_llm("schema_prompt"),
                )

            assert exc_info.value.schema_name == "SimpleTestModel"
            assert len(exc_info.value.errors) > 0
            assert exc_info.value.raw_response == invalid_json

    @pytest.mark.asyncio
    async def test_call_llm_max_retries_is_three(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm makes maximum of 3 attempts."""
        invalid_json = "invalid"

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content=invalid_json))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            with pytest.raises(SchemaValidationError):
                await collect_events(
                    workflow_context.call_llm("schema_prompt"),
                )

            # Should have made exactly 3 attempts
            assert mock_acompletion.call_count == 3

    @pytest.mark.asyncio
    async def test_call_llm_parses_json_from_code_block(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm extracts JSON from markdown code block."""
        response_with_block = """Here's the data:
```json
{"name": "test", "count": 42}
```
"""
        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content=response_with_block))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            await collect_events(
                workflow_context.call_llm("schema_prompt"),
            )

            result = workflow_context.get_last_result()
            assert result == {"name": "test", "count": 42}

    @pytest.mark.asyncio
    async def test_call_llm_with_prompt_spec_without_schema(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm with PromptSpec but no schema returns raw content."""
        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_choice = MagicMock(message=MagicMock(content="raw response"))
            mock_response.choices = [mock_choice]
            mock_acompletion.return_value = mock_response

            await collect_events(
                workflow_context.call_llm("no_schema_prompt"),
            )

            result = workflow_context.get_last_result()
            assert result == "raw response"

    @pytest.mark.asyncio
    async def test_retry_feedback_includes_error_message(
        self, workflow_context: "WorkflowContext",
    ) -> None:
        """Retry feedback includes the error message for LLM."""
        invalid_schema = json.dumps({"name": "test"})  # Missing count
        valid_json = json.dumps({"name": "test", "count": 42})

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response_bad = MagicMock()
            mock_choice_bad = MagicMock(message=MagicMock(content=invalid_schema))
            mock_response_bad.choices = [mock_choice_bad]

            mock_response_good = MagicMock()
            mock_choice_good = MagicMock(message=MagicMock(content=valid_json))
            mock_response_good.choices = [mock_choice_good]

            mock_acompletion.side_effect = [mock_response_bad, mock_response_good]

            await collect_events(
                workflow_context.call_llm("schema_prompt"),
            )

            # Check second call included error feedback
            second_call_args = mock_acompletion.call_args_list[1]
            messages = second_call_args.kwargs.get("messages", [])

            # Should have original user, assistant response, and user error feedback
            assert len(messages) >= 3
            assert messages[-1]["role"] == "user"
            assert "error" in messages[-1]["content"].lower()


class TestSetSchemas:
    """Test set_schemas method."""

    def test_set_schemas_stores_models(self, mock_workflow: "DslAgentWorkflow") -> None:
        """set_schemas stores Pydantic models in context."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        schemas = {"SimpleTestModel": SimpleTestModel}
        ctx.set_schemas(schemas)

        assert ctx._schemas == schemas  # noqa: SLF001

    def test_set_schemas_replaces_existing(
        self, mock_workflow: "DslAgentWorkflow",
    ) -> None:
        """set_schemas replaces existing schemas."""
        from streetrace.dsl.runtime.context import WorkflowContext

        ctx = WorkflowContext(workflow=mock_workflow)
        ctx.set_schemas({"First": SimpleTestModel})
        ctx.set_schemas({"Second": ComplexTestModel})

        assert "First" not in ctx._schemas  # noqa: SLF001
        assert "Second" in ctx._schemas  # noqa: SLF001
