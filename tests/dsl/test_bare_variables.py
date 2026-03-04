"""Tests for bare variable syntax (optional $ prefix).

Verify that both $var and bare var forms are accepted in flow code.
The $ prefix is optional -- both forms produce identical AST nodes.
Prompt templates still use $var for interpolation (unchanged).
"""

import pytest

from streetrace.dsl.ast.nodes import (
    Assignment,
    DslFile,
    FlowDef,
    ForLoop,
    Literal,
    PropertyAccess,
    PushStmt,
    ReturnStmt,
    VarRef,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer


class TestBareVariableGrammar:
    """Test that the grammar accepts bare variables (without $)."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_assignment_with_bare_name(self, parser):
        """Parse assignment with bare variable name as target."""
        source = """
flow test:
    pr_context = run agent fetcher
    return pr_context
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_assignment_with_dollar_prefix(self, parser):
        """Parse assignment with $ prefix -- still works."""
        source = """
flow test:
    $pr_context = run agent fetcher
    return $pr_context
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_for_loop_with_bare_names(self, parser):
        """Parse for loop with bare variable names."""
        source = """
flow test:
    for chunk in chunks do
        log chunk
    end
    return chunks
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_for_loop_with_dollar_prefix(self, parser):
        """Parse for loop with $ prefix -- still works."""
        source = """
flow test:
    for $chunk in $chunks do
        log $chunk
    end
    return $chunks
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_push_with_bare_names(self, parser):
        """Parse push statement with bare variable names."""
        source = """
flow test:
    results = []
    push item to results
    return results
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_expression_with_bare_names(self, parser):
        """Parse expression using bare variable names."""
        source = """
flow test:
    all_findings = all_findings + security_findings
    return all_findings
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_return_with_bare_name(self, parser):
        """Parse return with bare variable name."""
        source = """
flow test:
    final = "done"
    return final
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_if_with_bare_property_access(self, parser):
        """Parse if with bare variable property access."""
        source = """
flow test:
    result = "test"
    if result.valid:
        log "valid"
    return result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_filter_with_bare_name(self, parser):
        """Parse filter expression with bare variable name."""
        source = """
flow test:
    high_confidence = filter findings where .confidence >= 80
    return high_confidence
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_mixing_dollar_and_bare_in_same_flow(self, parser):
        """Parse flow mixing $ and bare variable references."""
        source = """
flow test:
    $old_style = "value1"
    new_style = "value2"
    combined = $old_style + new_style
    return combined
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestBareVariableTransformer:
    """Test that the transformer normalizes bare variables consistently."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_bare_assignment_target_normalized(self, parser):
        """Bare name in assignment target produces normalized name."""
        source = """
flow test:
    pr_context = "value"
    return pr_context
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment, Assignment)
        # Transformer normalizes: no $ prefix in stored target
        assert assignment.target == "pr_context"

    def test_dollar_assignment_target_normalized(self, parser):
        """$ prefixed name in assignment target produces normalized name (no $)."""
        source = """
flow test:
    $pr_context = "value"
    return $pr_context
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment, Assignment)
        # Transformer normalizes: $ is stripped, same output as bare name
        assert assignment.target == "pr_context"

    def test_bare_var_ref_in_expression(self, parser):
        """Bare name in expression produces VarRef with no $ prefix."""
        source = """
flow test:
    result = "test"
    return result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flow = ast.statements[0]
        return_stmt = flow.body[1]

        assert isinstance(return_stmt, ReturnStmt)
        assert isinstance(return_stmt.value, VarRef)
        assert return_stmt.value.name == "result"

    def test_bare_for_loop_variable(self, parser):
        """Bare name in for loop variable is normalized."""
        source = """
flow test:
    items = []
    for chunk in items do
        log chunk
    end
    return items
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flow = ast.statements[0]
        for_loop = flow.body[1]

        assert isinstance(for_loop, ForLoop)
        # Variable name stored without $
        assert for_loop.variable == "chunk"

    def test_bare_property_access(self, parser):
        """Bare name with property access produces PropertyAccess node."""
        source = """
flow test:
    result = "test"
    if result.valid:
        log "ok"
    return result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flow = ast.statements[0]
        if_block = flow.body[1]

        # The condition should be a PropertyAccess or similar
        assert isinstance(if_block.condition, PropertyAccess)

    def test_bare_push_target(self, parser):
        """Bare name in push target is normalized."""
        source = """
flow test:
    results = []
    push "item" to results
    return results
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flow = ast.statements[0]
        push_stmt = flow.body[1]

        assert isinstance(push_stmt, PushStmt)
        # Target stored without $ prefix
        assert push_stmt.target == "results"

    def test_both_forms_produce_same_var_ref_name(self, parser):
        """Both $var and var forms produce VarRef with same name field."""
        source_bare = """
flow test:
    x = "val"
    return x
"""
        source_dollar = """
flow test:
    $x = "val"
    return $x
"""
        tree_bare = parser.parse(source_bare)
        ast_bare = transform(tree_bare)
        flow_bare = ast_bare.statements[0]
        ret_bare = flow_bare.body[1]

        tree_dollar = parser.parse(source_dollar)
        ast_dollar = transform(tree_dollar)
        flow_dollar = ast_dollar.statements[0]
        ret_dollar = flow_dollar.body[1]

        assert isinstance(ret_bare.value, VarRef)
        assert isinstance(ret_dollar.value, VarRef)
        # Both should produce the same name
        assert ret_bare.value.name == ret_dollar.value.name


class TestBareVariableSemantic:
    """Test semantic analysis with bare variable names."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_bare_variable_resolves_from_scope(self):
        """Bare variable names resolve correctly from scope."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="test",
                    params=[],
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
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_undefined_bare_variable_triggers_error(self):
        """Undefined bare variable name triggers semantic error."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="test",
                    params=[],
                    body=[
                        ReturnStmt(value=VarRef(name="undefined_var")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_var" in e.message for e in result.errors)

    def test_bare_assignment_defines_variable(self):
        """Assignment with bare name defines variable in scope."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="test",
                    params=[],
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

    def test_bare_names_in_for_loop(self):
        """For loop with bare names validates correctly."""
        ast = DslFile(
            version=None,
            statements=[
                FlowDef(
                    name="test",
                    params=[],
                    body=[
                        Assignment(
                            target="items",
                            value=Literal(value="[]", literal_type="list"),
                        ),
                        ForLoop(
                            variable="item",
                            iterable=VarRef(name="items"),
                            body=[
                                ReturnStmt(
                                    value=VarRef(name="item"),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"


class TestBareVariableCodegen:
    """Test code generation with bare variable names."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_assignment_generates_ctx_vars(self, parser):
        """Assignment with bare name generates ctx.vars['name'] = value."""
        source = """
flow test:
    result = "hello"
    return result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['result'] = " in code

    def test_var_ref_generates_ctx_vars(self, parser):
        """Bare name reference generates ctx.vars['name']."""
        source = """
flow test:
    x = "hello"
    return x
"""
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['x']" in code

    def test_for_loop_generates_ctx_vars(self, parser):
        """For loop with bare name generates correct loop variable code."""
        source = """
flow test:
    items = []
    for chunk in items do
        log chunk
    end
    return items
"""
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "for _item_chunk in ctx.vars['items']:" in code
        assert "ctx.vars['chunk'] = _item_chunk" in code

    def test_push_generates_ctx_vars(self, parser):
        """Push with bare name generates ctx.vars['target'].append()."""
        source = """
flow test:
    results = []
    push "item" to results
    return results
"""
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['results'].append(" in code


class TestPromptInterpolationUnchanged:
    """Verify that prompt bodies still use $var for interpolation."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_prompt_body_keeps_dollar_interpolation(self, parser):
        """Prompt body text with $var is preserved as-is for runtime interpolation."""
        source = """
prompt review_prompt: '''
Review the following code: $code_snippet
Provide feedback based on $guidelines
'''
"""
        tree = parser.parse(source)
        ast = transform(tree)

        prompt = ast.statements[0]
        # Prompt body should contain $var references as raw text
        assert "$code_snippet" in prompt.body
        assert "$guidelines" in prompt.body


class TestBareVariableEndToEnd:
    """End-to-end tests: parse, transform, analyze, codegen with bare variables."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_full_pipeline_with_bare_variables(self, parser):
        """Full compilation pipeline works with bare variables."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow review:
    context = run agent processor
    result = run agent processor with context
    return result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Semantic errors: {result.errors}"

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_review" in code
        assert "ctx.vars['context']" in code
        assert "ctx.vars['result']" in code

    def test_full_pipeline_mixing_dollar_and_bare(self, parser):
        """Full pipeline works when mixing $ and bare variable styles."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent processor:
    tools fs
    instruction my_prompt

flow review:
    $old_var = run agent processor
    new_var = run agent processor with $old_var
    return new_var
"""
        tree = parser.parse(source)
        ast = transform(tree)

        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Semantic errors: {result.errors}"

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_review" in code
