"""Tests for filter expression with implicit property access.

Test coverage for filter expression syntax:
    filter $list where .property op value
"""

import pytest

from streetrace.dsl.ast.nodes import (
    BinaryOp,
    FilterExpr,
    ImplicitProperty,
    Literal,
    VarRef,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.visitors.expressions import ExpressionVisitor
from streetrace.dsl.grammar.parser import ParserFactory


class TestFilterExpressionGrammar:
    """Test grammar parsing of filter expressions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_filter_with_comparison(self, parser):
        """Test parsing filter with >= comparison."""
        source = """
flow test:
    $filtered = filter $findings where .confidence >= 80
    return $filtered
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_filter_with_not_equal_null(self, parser):
        """Test parsing filter with != null comparison."""
        source = """
flow test:
    $fixable = filter $findings where .suggested_fix != null
    return $fixable
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_filter_with_nested_property(self, parser):
        """Test parsing filter with nested property access."""
        source = """
flow test:
    $filtered = filter $items where .finding.severity == "high"
    return $filtered
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_filter_with_variable_comparison(self, parser):
        """Test parsing filter with variable on right side."""
        source = """
flow test:
    $threshold = 80
    $filtered = filter $findings where .confidence >= $threshold
    return $filtered
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_filter_in_for_loop(self, parser):
        """Test parsing filter inside a for loop."""
        source = """
flow test:
    $results = []
    for $item in filter $items where .active == true do
        push $item to $results
    end
    return $results
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_implicit_property_in_condition(self, parser):
        """Test parsing implicit property with boolean expression."""
        source = """
flow test:
    $filtered = filter $items where .status == "active" and .score > 50
    return $filtered
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestFilterExpressionTransformer:
    """Test AST transformer for filter expressions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_filter_expression(self, parser):
        """Test transforming filter expression to FilterExpr node."""
        source = """
flow test:
    $filtered = filter $findings where .confidence >= 80
    return $filtered
"""
        tree = parser.parse(source)
        ast = transform(tree)

        # Find the assignment with filter expression
        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment.value, FilterExpr)
        assert isinstance(assignment.value.list_expr, VarRef)
        assert assignment.value.list_expr.name == "findings"

    def test_transforms_implicit_property(self, parser):
        """Test transforming implicit property access to ImplicitProperty node."""
        source = """
flow test:
    $filtered = filter $items where .value > 10
    return $filtered
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]
        filter_expr = assignment.value

        assert isinstance(filter_expr, FilterExpr)
        assert isinstance(filter_expr.condition, BinaryOp)
        assert isinstance(filter_expr.condition.left, ImplicitProperty)
        assert filter_expr.condition.left.properties == ["value"]

    def test_transforms_nested_implicit_property(self, parser):
        """Test transforming nested implicit property access."""
        source = """
flow test:
    $filtered = filter $items where .nested.prop == "x"
    return $filtered
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]
        filter_expr = assignment.value

        assert isinstance(filter_expr.condition.left, ImplicitProperty)
        assert filter_expr.condition.left.properties == ["nested", "prop"]

    def test_transforms_filter_with_null_comparison(self, parser):
        """Test transforming filter with null comparison."""
        source = """
flow test:
    $filtered = filter $items where .fix != null
    return $filtered
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]
        filter_expr = assignment.value

        assert isinstance(filter_expr.condition, BinaryOp)
        assert filter_expr.condition.op == "!="
        assert isinstance(filter_expr.condition.right, Literal)
        assert filter_expr.condition.right.literal_type == "null"


class TestFilterExpressionCodegen:
    """Test code generation for filter expressions."""

    def test_generates_code_for_implicit_property(self):
        """Test code generation for single implicit property."""
        visitor = ExpressionVisitor()
        node = ImplicitProperty(properties=["confidence"])

        code = visitor.visit(node)

        assert code == "_item['confidence']"

    def test_generates_code_for_nested_implicit_property(self):
        """Test code generation for nested implicit property."""
        visitor = ExpressionVisitor()
        node = ImplicitProperty(properties=["nested", "prop"])

        code = visitor.visit(node)

        assert code == "_item['nested']['prop']"

    def test_generates_code_for_filter_expression(self):
        """Test code generation for filter expression."""
        visitor = ExpressionVisitor()
        node = FilterExpr(
            list_expr=VarRef(name="findings"),
            condition=BinaryOp(
                op=">=",
                left=ImplicitProperty(properties=["confidence"]),
                right=Literal(value=80, literal_type="int"),
            ),
        )

        code = visitor.visit(node)

        expected = (
            "[_item for _item in ctx.vars['findings'] "
            "if (_item['confidence'] >= 80)]"
        )
        assert code == expected

    def test_generates_code_for_filter_with_null(self):
        """Test code generation for filter with null comparison."""
        visitor = ExpressionVisitor()
        node = FilterExpr(
            list_expr=VarRef(name="items"),
            condition=BinaryOp(
                op="!=",
                left=ImplicitProperty(properties=["fix"]),
                right=Literal(value=None, literal_type="null"),
            ),
        )

        code = visitor.visit(node)

        expected = (
            "[_item for _item in ctx.vars['items'] "
            "if (_item['fix'] != None)]"
        )
        assert code == expected

    def test_generates_code_for_filter_with_string(self):
        """Test code generation for filter with string comparison."""
        visitor = ExpressionVisitor()
        node = FilterExpr(
            list_expr=VarRef(name="list"),
            condition=BinaryOp(
                op="==",
                left=ImplicitProperty(properties=["a", "b"]),
                right=Literal(value="x", literal_type="string"),
            ),
        )

        code = visitor.visit(node)

        expected = (
            "[_item for _item in ctx.vars['list'] "
            "if (_item['a']['b'] == \"x\")]"
        )
        assert code == expected


class TestImplicitPropertyNodeCreation:
    """Test ImplicitProperty AST node creation."""

    def test_creates_implicit_property_node(self):
        """Test creating ImplicitProperty node with single property."""
        node = ImplicitProperty(properties=["value"])
        assert node.properties == ["value"]
        assert node.meta is None

    def test_creates_implicit_property_node_with_multiple_properties(self):
        """Test creating ImplicitProperty node with multiple properties."""
        node = ImplicitProperty(properties=["nested", "deep", "prop"])
        assert node.properties == ["nested", "deep", "prop"]


class TestFilterExprNodeCreation:
    """Test FilterExpr AST node creation."""

    def test_creates_filter_expr_node(self):
        """Test creating FilterExpr node."""
        list_expr = VarRef(name="items")
        condition = BinaryOp(
            op=">",
            left=ImplicitProperty(properties=["score"]),
            right=Literal(value=50, literal_type="int"),
        )
        node = FilterExpr(list_expr=list_expr, condition=condition)

        assert node.list_expr is list_expr
        assert node.condition is condition
        assert node.meta is None


class TestFilterExpressionIntegration:
    """Integration tests for filter expression end-to-end."""

    def test_generated_code_contains_list_comprehension(self):
        """Test that generated filter code contains correct list comprehension."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow filter_findings:
    $filtered = filter $findings where .confidence >= 80
    return $filtered
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the list comprehension is generated correctly
        assert "[_item for _item in ctx.vars['findings']" in code
        assert "if (_item['confidence'] >= 80)" in code

    def test_generated_code_contains_null_comparison(self):
        """Test filtering with != null generates correct code."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow filter_fixable:
    $fixable = filter $items where .fix != null
    return $fixable
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify null comparison generates != None
        assert "[_item for _item in ctx.vars['items']" in code
        assert "_item['fix'] != None" in code

    def test_generated_code_contains_nested_property(self):
        """Test filtering with nested property generates correct code."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow filter_high_severity:
    $high = filter $items where .finding.severity == "high"
    return $high
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify nested property access generates correctly
        assert "[_item for _item in ctx.vars['items']" in code
        assert "_item['finding']['severity'] ==" in code
        assert '"high"' in code
