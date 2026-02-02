"""Tests for flow definitions without parameters.

Verify that flows no longer accept explicit parameters and read
from shared ctx.vars (global scope) instead.
"""

import pytest

from streetrace.dsl.ast.nodes import (
    Assignment,
    DslFile,
    EventHandler,
    FlowDef,
    Literal,
    ReturnStmt,
    VarRef,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer


class TestFlowNoParametersParsing:
    """Test parsing of flows without parameters."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_flow_without_params_parses(self, parser):
        """Flow without parameters parses correctly."""
        source = """
flow process:
    return $input_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        assert flows[0].params == []

    def test_flow_body_can_reference_global_scope_variables(self, parser):
        """Flow body can reference variables from global scope."""
        source = """
flow check:
    $x = $input_prompt
    return $x
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1

    def test_flow_with_dollar_param_fails_to_parse(self, parser):
        """Old parameter syntax with $ is rejected by parser."""
        from lark.exceptions import UnexpectedCharacters, UnexpectedToken

        source = "flow process $input:\n    return $input\n"
        with pytest.raises((UnexpectedCharacters, UnexpectedToken)):
            parser.parse(source)


class TestFlowNoParametersSemanticAnalysis:
    """Test semantic analysis of flows without parameters."""

    def test_flow_body_reads_from_global_scope(self):
        """Flow body can access variables defined in on start handler."""
        ast = DslFile(
            version=None,
            statements=[
                EventHandler(
                    timing="on",
                    event_type="start",
                    body=[
                        Assignment(
                            target="context",
                            value=Literal(value="data", literal_type="string"),
                        ),
                    ],
                ),
                FlowDef(
                    name="process",
                    body=[
                        ReturnStmt(value=VarRef(name="context")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_undefined_variable_in_flow_body_fails(self):
        """Undefined variable in flow body fails validation."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="process",
                    body=[
                        ReturnStmt(value=VarRef(name="undefined")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined" in e.message for e in result.errors)


class TestFlowNoParametersVariablePassing:
    """Test variable passing between flow steps."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_variable_assigned_then_used_in_next_step(self, parser):
        """Variable assigned in one step is available in the next."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow multi_step:
    $step1_result = run agent processor with $input_prompt
    $step2_result = run agent processor with $step1_result
    return $step2_result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"


class TestFlowNoParametersCodeGen:
    """Test code generation for flows without parameters."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_flow_generates_valid_python(self, parser):
        """Flow without parameters generates syntactically valid Python."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow process:
    $result = run agent processor with $input_prompt
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        # Semantic analysis should pass
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Semantic errors: {result.errors}"

        # Generate code
        generator = CodeGenerator()
        code, mappings = generator.generate(ast, "test.sr")

        # Flow method should be generated
        assert "async def flow_process" in code
        # Code should reference ctx.vars
        assert "ctx.vars" in code
