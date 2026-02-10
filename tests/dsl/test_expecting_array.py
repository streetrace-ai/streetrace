"""Tests for array expecting type in Streetrace DSL (Phase 5).

Test that `expecting Finding[]` (array of schema objects) is supported
in addition to the existing `expecting Finding` (single schema).
Covers grammar, transformer, semantic analysis, code generation,
and runtime validation.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from streetrace.dsl.ast import (
    DslFile,
    PromptDef,
    SchemaDef,
    SchemaField,
    TypeExpr,
    VersionDecl,
)
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.errors import ErrorCode

if TYPE_CHECKING:
    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow


def _make_schema(name: str) -> SchemaDef:
    """Create a simple test schema."""
    return SchemaDef(
        name=name,
        fields=[SchemaField(name="value", type_expr=TypeExpr(base_type="string"))],
    )


# =========================================================================
# Grammar Tests
# =========================================================================


class TestExpectingArrayGrammar:
    """Test grammar parsing of expecting array syntax."""

    def test_parse_expecting_array(self) -> None:
        """Parse `expecting Finding[]` produces correct tree."""
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding[]: """Review code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        assert tree is not None

    def test_parse_expecting_single_still_works(self) -> None:
        """Parse `expecting Finding` (single) still works."""
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding: """Review code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        assert tree is not None

    def test_parse_expecting_array_declaration(self) -> None:
        """Parse array expecting in prompt declaration (no body)."""
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding[]
prompt reviewer: """Review code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        assert tree is not None


# =========================================================================
# Transformer Tests
# =========================================================================


class TestExpectingArrayTransformer:
    """Test transformer produces correct AST for array expecting."""

    def test_transformer_array_expecting(self) -> None:
        """Transformer produces PromptDef(expecting='Finding[]') for array."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding[]: """Review code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        # Find the prompt def
        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 1
        assert prompts[0].expecting == "Finding[]"

    def test_transformer_single_expecting(self) -> None:
        """Transformer produces PromptDef(expecting='Finding') for single."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding: """Review code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 1
        assert prompts[0].expecting == "Finding"

    def test_transformer_array_declaration_then_body(self) -> None:
        """Array expecting in declaration merges with body definition."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding[]
prompt reviewer: """Review code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 2
        # First (declaration) has expecting, second (body) does not
        assert prompts[0].expecting == "Finding[]"
        assert prompts[1].expecting is None


# =========================================================================
# Semantic Analyzer Tests
# =========================================================================


class TestExpectingArraySemantic:
    """Test semantic analysis validates array expecting correctly."""

    def test_valid_array_schema_reference(self) -> None:
        """Array expecting with defined schema is valid."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                _make_schema("Finding"),
                PromptDef(
                    name="reviewer",
                    body="Review this code.",
                    expecting="Finding[]",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

    def test_valid_single_schema_reference(self) -> None:
        """Single expecting with defined schema still works."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                _make_schema("Finding"),
                PromptDef(
                    name="reviewer",
                    body="Review this code.",
                    expecting="Finding",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

    def test_undefined_array_schema_rejected(self) -> None:
        """Array expecting with undefined schema produces error."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="reviewer",
                    body="Review this code.",
                    expecting="Unknown[]",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert any(e.code == ErrorCode.E0001 for e in result.errors)

    def test_undefined_single_schema_rejected(self) -> None:
        """Single expecting with undefined schema produces error."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                PromptDef(
                    name="reviewer",
                    body="Review this code.",
                    expecting="Unknown",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert any(e.code == ErrorCode.E0001 for e in result.errors)

    def test_array_schema_in_merged_prompt(self) -> None:
        """Array expecting survives prompt merge."""
        ast = DslFile(
            version=VersionDecl(version="1"),
            statements=[
                _make_schema("Finding"),
                PromptDef(
                    name="reviewer",
                    body="",
                    expecting="Finding[]",
                ),
                PromptDef(
                    name="reviewer",
                    body="Review this code.",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        merged = result.symbols.prompts["reviewer"]
        assert merged.expecting == "Finding[]"
        assert merged.body == "Review this code."


# =========================================================================
# Code Generation Tests
# =========================================================================


class TestExpectingArrayCodegen:
    """Test code generation emits correct schema for array types."""

    def test_codegen_emits_array_schema(self) -> None:
        """Generated code contains schema='Finding[]' for array type."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding[]: """Review the code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

        generator = CodeGenerator()
        python_source, _ = generator.generate(
            ast,
            "test.sr",
            merged_prompts=result.symbols.prompts,
        )

        assert "schema='Finding[]'" in python_source

    def test_codegen_emits_single_schema(self) -> None:
        """Generated code contains schema='Finding' for single type."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding: """Review the code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

        generator = CodeGenerator()
        python_source, _ = generator.generate(
            ast,
            "test.sr",
            merged_prompts=result.symbols.prompts,
        )

        assert "schema='Finding'" in python_source

    def test_codegen_merged_prompt_has_array_schema(self) -> None:
        """Merged prompt declaration with array expecting emits schema."""
        from streetrace.dsl.ast.transformer import transform
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''streetrace v1

schema Finding:
    value: string

prompt reviewer expecting Finding[]
prompt reviewer: """Review the code."""
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid

        generator = CodeGenerator()
        python_source, _ = generator.generate(
            ast,
            "test.sr",
            merged_prompts=result.symbols.prompts,
        )

        assert "schema='Finding[]'" in python_source


# =========================================================================
# Runtime Tests
# =========================================================================


@pytest.fixture
def mock_workflow() -> "DslAgentWorkflow":
    """Create a mock DslAgentWorkflow for testing."""
    return MagicMock()


async def consume_generator(generator: object) -> list[object]:
    """Consume an async generator and return all events."""
    return [event async for event in generator]  # type: ignore[union-attr]


class TestExpectingArrayRuntime:
    """Test runtime behavior for array schema validation."""

    @pytest.fixture
    def workflow_context(self, mock_workflow: "DslAgentWorkflow") -> "WorkflowContext":
        """Create a WorkflowContext with test configuration."""
        from pydantic import create_model

        from streetrace.dsl.runtime.context import WorkflowContext
        from streetrace.dsl.runtime.workflow import PromptSpec

        ctx = WorkflowContext(workflow=mock_workflow)

        # Set up models
        ctx.set_models({"main": "anthropic/claude-sonnet"})

        # Create a schema model
        finding_model = create_model(
            "Finding",
            value=(str, ...),
        )
        ctx.set_schemas({"Finding": finding_model})

        # Set up prompts with array schema
        ctx.set_prompts({
            "array_prompt": PromptSpec(
                body=lambda _: "Find issues.",
                schema="Finding[]",
            ),
            "single_prompt": PromptSpec(
                body=lambda _: "Find one issue.",
                schema="Finding",
            ),
            "no_schema_prompt": PromptSpec(
                body=lambda _: "Just do something.",
            ),
        })

        return ctx

    def test_parse_json_response_with_array(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """_parse_json_response handles JSON array input."""
        import json

        result = workflow_context._parse_json_response(  # noqa: SLF001
            json.dumps([{"value": "issue1"}, {"value": "issue2"}]),
        )
        assert isinstance(result, list)
        assert len(result) == 2

    def test_parse_json_response_with_object(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """_parse_json_response handles JSON object input."""
        import json

        result = workflow_context._parse_json_response(  # noqa: SLF001
            json.dumps({"value": "issue1"}),
        )
        assert isinstance(result, dict)

    def test_is_array_schema(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """_is_array_schema detects array suffix."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        array_spec = PromptSpec(body=lambda _: "", schema="Finding[]")
        single_spec = PromptSpec(body=lambda _: "", schema="Finding")
        no_schema_spec = PromptSpec(body=lambda _: "")

        assert workflow_context._is_array_schema(array_spec) is True  # noqa: SLF001
        assert workflow_context._is_array_schema(single_spec) is False  # noqa: SLF001
        assert workflow_context._is_array_schema(no_schema_spec) is False  # noqa: SLF001

    def test_get_schema_model_strips_array_suffix(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """_get_schema_model resolves base schema name for array types."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        array_spec = PromptSpec(body=lambda _: "", schema="Finding[]")
        model = workflow_context._get_schema_model(array_spec)  # noqa: SLF001
        assert model is not None
        assert model.__name__ == "Finding"

    def test_get_schema_model_single(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """_get_schema_model resolves schema name for single types."""
        from streetrace.dsl.runtime.workflow import PromptSpec

        single_spec = PromptSpec(body=lambda _: "", schema="Finding")
        model = workflow_context._get_schema_model(single_spec)  # noqa: SLF001
        assert model is not None
        assert model.__name__ == "Finding"

    @pytest.mark.asyncio
    async def test_call_llm_array_schema_validates_each_element(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm with array schema validates each element and returns list."""
        import json

        response_data = [{"value": "issue1"}, {"value": "issue2"}]

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content=json.dumps(response_data))),
            ]
            mock_acompletion.return_value = mock_response

            await consume_generator(
                workflow_context.call_llm("array_prompt"),
            )
            result = workflow_context.get_last_result()

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0] == {"value": "issue1"}
            assert result[1] == {"value": "issue2"}

    @pytest.mark.asyncio
    async def test_call_llm_single_schema_returns_dict(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm with single schema validates and returns dict."""
        import json

        response_data = {"value": "issue1"}

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content=json.dumps(response_data))),
            ]
            mock_acompletion.return_value = mock_response

            await consume_generator(
                workflow_context.call_llm("single_prompt"),
            )
            result = workflow_context.get_last_result()

            assert isinstance(result, dict)
            assert result == {"value": "issue1"}

    @pytest.mark.asyncio
    async def test_call_llm_array_schema_enriches_prompt(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm with array schema enriches prompt with array instructions."""
        import json

        response_data = [{"value": "issue1"}]

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content=json.dumps(response_data))),
            ]
            mock_acompletion.return_value = mock_response

            await consume_generator(
                workflow_context.call_llm("array_prompt"),
            )

            # Check that prompt was enriched with array instructions
            call_kwargs = mock_acompletion.call_args.kwargs
            messages = call_kwargs.get("messages", [])
            prompt_text = messages[0]["content"]
            assert "JSON array" in prompt_text

    @pytest.mark.asyncio
    async def test_call_llm_array_invalid_element_retries(
        self,
        workflow_context: "WorkflowContext",
    ) -> None:
        """call_llm with array schema retries on invalid element."""
        import json

        # First response: invalid (missing required field)
        invalid_response = [{"wrong_field": "data"}]
        # Second response: valid
        valid_response = [{"value": "fixed"}]

        with patch("litellm.acompletion") as mock_acompletion:
            mock_response_1 = MagicMock()
            mock_response_1.choices = [
                MagicMock(
                    message=MagicMock(content=json.dumps(invalid_response)),
                ),
            ]

            mock_response_2 = MagicMock()
            mock_response_2.choices = [
                MagicMock(
                    message=MagicMock(content=json.dumps(valid_response)),
                ),
            ]

            mock_acompletion.side_effect = [mock_response_1, mock_response_2]

            await consume_generator(
                workflow_context.call_llm("array_prompt"),
            )
            result = workflow_context.get_last_result()

            assert isinstance(result, list)
            assert result[0] == {"value": "fixed"}
            assert mock_acompletion.call_count == 2


class TestExpectingArrayEndToEnd:
    """End-to-end tests parsing actual DSL source code."""

    def test_full_pipeline_array_expecting(self) -> None:
        """Full pipeline from DSL source to generated Python with array schema."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = '''streetrace v1

model main = anthropic/claude-sonnet

schema Finding:
    file: string
    line: int
    severity: string

prompt reviewer expecting Finding[] using model "main": """
You are a code reviewer. Find all issues.
Return a JSON array of findings.
"""
'''
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_full_pipeline_declaration_with_array(self) -> None:
        """Declaration with array expecting, body separate."""
        from streetrace.dsl.compiler import validate_dsl
        from streetrace.dsl.errors.diagnostics import Severity

        source = '''streetrace v1

model main = anthropic/claude-sonnet

schema Finding:
    file: string
    line: int
    severity: string

prompt reviewer expecting Finding[] using model "main"
prompt reviewer: """You are a code reviewer."""
'''
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 0
