"""Tests for the normalized comparison operator (~).

Test the full pipeline from DSL parsing through code generation
for the ~ operator that performs normalized equality comparison.
"""

import pytest

from streetrace.dsl.ast import BinaryOp, Literal, VarRef
from streetrace.dsl.codegen.visitors.expressions import ExpressionVisitor
from streetrace.dsl.grammar.parser import ParserFactory


class TestNormalizedOperatorParsing:
    """Test parsing of ~ operator expressions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_normalized_equals_in_if_condition(self, parser):
        """Test ~ operator in if condition."""
        source = """
flow check_response:
    if $response ~ "YES":
        log "Confirmed"
    return $response
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_normalized_equals_in_assignment(self, parser):
        """Test ~ operator in variable assignment."""
        source = """
flow check_approval:
    $is_approved = $answer ~ "APPROVED"
    return $is_approved
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_normalized_equals_with_variable(self, parser):
        """Test ~ operator comparing two variables."""
        source = """
flow compare_responses:
    $match = $response1 ~ $response2
    return $match
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_normalized_equals_in_complex_condition(self, parser):
        """Test ~ operator in complex boolean expression."""
        source = """
flow complex_check:
    if $response ~ "YES" and $score > 0.5:
        log "High confidence yes"
    return $response
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestNormalizedOperatorCodegen:
    """Test code generation for ~ operator."""

    def test_generates_normalized_equals_call(self):
        """Test that ~ generates normalized_equals function call."""
        visitor = ExpressionVisitor()

        node = BinaryOp(
            op="~",
            left=VarRef(name="response"),
            right=Literal(value="YES", literal_type="string"),
        )

        result = visitor.visit(node)

        assert "normalized_equals" in result
        assert "ctx.vars['response']" in result
        assert '"YES"' in result

    def test_generates_correct_function_signature(self):
        """Test that generated code has correct function call format."""
        visitor = ExpressionVisitor()

        node = BinaryOp(
            op="~",
            left=VarRef(name="answer"),
            right=Literal(value="APPROVED", literal_type="string"),
        )

        result = visitor.visit(node)

        # Should be: normalized_equals(ctx.vars['answer'], "APPROVED")
        assert result == 'normalized_equals(ctx.vars[\'answer\'], "APPROVED")'


class TestNormalizedOperatorFullPipeline:
    """Test full pipeline from DSL to generated Python."""

    def test_generated_code_is_valid_python(self):
        """Test that generated code with ~ operator is valid Python."""
        from streetrace.dsl.ast.transformer import AstTransformer
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = '''
model main = anthropic/claude-sonnet

prompt check_prompt: """
Check the input
"""

agent checker:
    instruction check_prompt

flow check_response:
    $response = run agent checker with $input_prompt
    $is_drifting = $response ~ "DRIFTING"
    return $is_drifting
'''
        parser = ParserFactory.create()
        tree = parser.parse(source)

        transformer = AstTransformer()
        ast = transformer.transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code compiles
        compile(code, "<generated>", "exec")

        # Verify normalized_equals is imported and used
        assert "from streetrace.dsl.runtime.utils import normalized_equals" in code
        assert "normalized_equals" in code

    def test_generated_code_contains_correct_imports(self):
        """Test that generated code imports normalized_equals."""
        from streetrace.dsl.ast.transformer import AstTransformer
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow simple:
    $match = $a ~ "test"
    return $match
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)

        transformer = AstTransformer()
        ast = transformer.transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "normalized_equals" in code


class TestNormalizedOperatorWithLlmOutputs:
    """Test ~ operator with realistic LLM output patterns."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_drifting_check(self, parser):
        """Test parsing DRIFTING check pattern from design doc."""
        source = """
flow resolver:
    $current = $input_prompt
    $new = run agent peer1 with $current
    if $new ~ "DRIFTING":
        return $current
    return $new
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_escalate_check(self, parser):
        """Test parsing ESCALATE check pattern."""
        source = """
flow process:
    $result = run agent analyzer with $input_prompt
    if $result ~ "ESCALATE":
        log "Escalating to human"
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_yes_no_check(self, parser):
        """Test parsing YES/NO response patterns."""
        source = """
flow confirm:
    $answer = call llm confirm_prompt with $question
    if $answer ~ "YES":
        return { confirmed: true }
    return { confirmed: false }
"""
        tree = parser.parse(source)
        assert tree.data == "start"
