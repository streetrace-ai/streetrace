"""Tests for flow parameters and variable binding.

Verify that flow parameters are correctly bound in scope and
that variable passing between flow steps works correctly.
"""

import pytest

from streetrace.dsl.ast.nodes import DslFile, FlowDef
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer


class TestFlowParametersParsing:
    """Test parsing of flow parameters."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_flow_with_single_parameter_parses(self, parser):
        """Flow with single parameter parses correctly."""
        source = """
flow process $input:
    return $input
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        assert len(flows[0].params) == 1
        assert flows[0].params[0] == "$input"

    def test_flow_with_multiple_parameters_parses(self, parser):
        """Flow with multiple parameters parses correctly."""
        source = """
flow process $input $context $options:
    return $input
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        assert len(flows[0].params) == 3
        assert flows[0].params == ["$input", "$context", "$options"]


class TestFlowParametersSemanticAnalysis:
    """Test semantic analysis of flow parameters."""

    def test_flow_parameter_is_in_scope_for_body(self):
        """Flow parameters are available in the flow body scope."""
        from streetrace.dsl.ast.nodes import ReturnStmt, VarRef

        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="process",
                    params=["$input"],
                    body=[
                        ReturnStmt(value=VarRef(name="input")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_multiple_flow_parameters_are_in_scope(self):
        """Multiple flow parameters are all available in scope."""
        from streetrace.dsl.ast.nodes import Assignment, BinaryOp, ReturnStmt, VarRef

        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="combine",
                    params=["$a", "$b", "$c"],
                    body=[
                        Assignment(
                            target="result",
                            value=BinaryOp(
                                op="+",
                                left=VarRef(name="a"),
                                right=VarRef(name="b"),
                            ),
                        ),
                        ReturnStmt(value=VarRef(name="c")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_undefined_variable_in_flow_with_params_fails(self):
        """Undefined variable in flow with parameters fails validation."""
        from streetrace.dsl.ast.nodes import ReturnStmt, VarRef

        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="process",
                    params=["$input"],
                    body=[
                        # Try to use $undefined which is not a param
                        ReturnStmt(value=VarRef(name="undefined")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined" in e.message for e in result.errors)

    def test_flow_parameter_shadows_global_not_error(self):
        """Flow parameter that shadows a global name is allowed."""
        from streetrace.dsl.ast.nodes import ReturnStmt, VarRef

        ast = DslFile(
            version=None,
            statements=[
                # Use a flow param named 'input' which might shadow a global
                FlowDef(
                    name="process",
                    params=["$input"],
                    body=[
                        ReturnStmt(value=VarRef(name="input")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"


class TestFlowVariablePassing:
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
    $step1_result = run agent processor $input_prompt
    $step2_result = run agent processor $step1_result
    return $step2_result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_flow_parameter_used_in_run_statement(self, parser):
        """Flow parameter can be used as argument to run statement."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow process_item $item:
    $result = run agent processor $item
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"


class TestFlowParametersCodeGen:
    """Test code generation for flow parameters."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_flow_parameters_generate_valid_python(self, parser):
        """Flow with parameters generates syntactically valid Python."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow process $input:
    $result = run agent processor $input
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

    def test_multiple_flow_parameters_generate_valid_python(self, parser):
        """Flow with multiple parameters generates valid Python."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow combine $a $b:
    $result = run agent processor $a
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
        assert "async def flow_combine" in code
