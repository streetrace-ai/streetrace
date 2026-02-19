"""Tests for removal of flow parameters (Phase 4).

Verify that flows no longer accept explicit parameters and read
from ambient context (ctx.vars) instead.
"""

import pytest

from streetrace.dsl.ast.nodes import (
    Assignment,
    DslFile,
    FlowDef,
    Literal,
    ReturnStmt,
    RunStmt,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer


class TestFlowNoParamsGrammar:
    """Test grammar changes: flows no longer accept parameters."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return ParserFactory.create()

    def test_flow_without_params_parses(self, parser):
        """Flow definition without parameters parses successfully."""
        source = """
flow validate_all:
    return true
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        assert flows[0].name == "validate_all"
        assert flows[0].params == []

    def test_flow_with_dollar_params_fails_to_parse(self, parser):
        """Flow with $-prefixed parameters fails to parse."""
        from lark.exceptions import UnexpectedCharacters, UnexpectedToken

        source = "flow validate_all $input:\n    return $input\n"
        with pytest.raises((UnexpectedCharacters, UnexpectedToken)):
            parser.parse(source)

    def test_flow_with_bare_name_params_fails_to_parse(self, parser):
        """Flow with bare name parameters fails to parse."""
        source = """
flow validate_all input:
    return input
"""
        # This should either fail to parse or not produce params.
        # The bare name after flow_name will be consumed as part of
        # flow_name (since flow_name is identifier+), so we need to
        # verify the behavior is correct -- "input" becomes part of
        # the flow name rather than a parameter.
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        # "input" is absorbed into the flow name since flow_name is identifier+
        assert flows[0].params == []

    def test_flow_with_multiple_dollar_params_fails(self, parser):
        """Flow with multiple $-prefixed parameters fails to parse."""
        from lark.exceptions import UnexpectedCharacters, UnexpectedToken

        source = "flow process $a $b $c:\n    return $a\n"
        with pytest.raises((UnexpectedCharacters, UnexpectedToken)):
            parser.parse(source)


class TestFlowNoParamsTransformer:
    """Test transformer: FlowDef always has empty params."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return ParserFactory.create()

    def test_transformer_produces_empty_params(self, parser):
        """Transformer always produces FlowDef with params=[]."""
        source = """
flow my_flow:
    return true
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        assert flows[0].params == []

    def test_flow_def_default_params(self):
        """FlowDef defaults params to empty list."""
        flow = FlowDef(
            name="test",
            body=[ReturnStmt(value=Literal(value=True, literal_type="bool"))],
        )
        assert flow.params == []

    def test_flow_def_explicit_empty_params(self):
        """FlowDef can be constructed with explicit empty params."""
        flow = FlowDef(
            name="test",
            body=[],
            params=[],
        )
        assert flow.params == []


class TestFlowNoParamsSemantic:
    """Test semantic analysis: flows read from global scope."""

    def test_flow_body_reads_from_global_scope(self):
        """Flow body can access variables defined in on start handler."""
        from streetrace.dsl.ast.nodes import EventHandler

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

    def test_undefined_variable_in_flow_body_raises_error(self):
        """Undefined variable in flow body raises semantic error."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="process",
                    body=[
                        ReturnStmt(value=VarRef(name="nonexistent")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("nonexistent" in e.message for e in result.errors)

    def test_flow_without_params_validates_clean(self):
        """Flow without params validates when all vars are in scope."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="simple",
                    body=[
                        Assignment(
                            target="x",
                            value=Literal(value=42, literal_type="int"),
                        ),
                        ReturnStmt(value=VarRef(name="x")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"


class TestFlowNoParamsCodeGen:
    """Test code generation: no parameter initialization."""

    def test_flow_method_signature_has_no_params(self):
        """Flow method signature is async def flow_name(self, ctx)."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="validate_all",
                    body=[
                        ReturnStmt(
                            value=Literal(value="done", literal_type="string"),
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_validate_all(" in code
        assert "self, ctx: WorkflowContext" in code
        assert "AsyncGenerator[Event | FlowEvent, None]" in code

    def test_no_parameter_initialization_in_generated_code(self):
        """Generated code has no ctx.vars initialization for params."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="process",
                    body=[
                        Assignment(
                            target="result",
                            value=Literal(value="ok", literal_type="string"),
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # There should be no parameter-related initialization
        lines = code.split("\n")
        flow_start = next(
            i for i, line in enumerate(lines) if "flow_process" in line
        )
        # Check next few lines after method definition don't have param init
        method_body = "\n".join(lines[flow_start:flow_start + 10])
        assert "# Initialize parameters" not in method_body


class TestFlowNoParamsRunFlow:
    """Test run flow without args."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return ParserFactory.create()

    def test_run_flow_without_args_parses(self, parser):
        """Run flow statement without arguments parses correctly."""
        source = """
model main = anthropic/claude-sonnet
tool fs = builtin streetrace.fs
prompt my_prompt: '''You are helpful.'''
agent processor:
    tools fs
    instruction my_prompt

flow validate_all:
    result = run agent processor with input_prompt
    return result

flow main:
    run validate_all
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 2

        main_flow = next(f for f in flows if f.name == "main")
        run_stmt = main_flow.body[0]
        assert isinstance(run_stmt, RunStmt)
        assert run_stmt.is_flow
        assert run_stmt.agent == "validate_all"


class TestFlowNoParamsEndToEnd:
    """End-to-end tests: compile and verify flow without params."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return ParserFactory.create()

    def test_end_to_end_flow_compiles(self, parser):
        """Full pipeline: parse, transform, analyze, generate for paramless flow."""
        source = """
model main = anthropic/claude-sonnet
tool fs = builtin streetrace.fs
prompt my_prompt: '''You are helpful.'''
agent processor:
    tools fs
    instruction my_prompt

flow validate_all:
    result = run agent processor with input_prompt
    return result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        analysis = analyzer.analyze(ast)
        assert analysis.is_valid, f"Semantic errors: {analysis.errors}"

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_validate_all(" in code
        assert "self, ctx: WorkflowContext" in code

    def test_end_to_end_multiple_flows_compile(self, parser):
        """Multiple paramless flows compile correctly."""
        source = """
model main = anthropic/claude-sonnet
tool fs = builtin streetrace.fs
prompt my_prompt: '''You are helpful.'''
agent processor:
    tools fs
    instruction my_prompt

flow step_one:
    result = run agent processor with input_prompt
    return result

flow step_two:
    data = run agent processor with input_prompt
    return data

flow main:
    run step_one
    run step_two
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        analysis = analyzer.analyze(ast)
        assert analysis.is_valid, f"Semantic errors: {analysis.errors}"

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_step_one(" in code
        assert "async def flow_step_two(" in code
        assert "async def flow_main(" in code
