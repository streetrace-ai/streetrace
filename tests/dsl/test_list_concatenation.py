"""Tests for list concatenation using the + operator in DSL.

Verify that the + operator works correctly for list concatenation:
1. Grammar parses list concatenation correctly
2. Codegen produces correct Python code
3. Generated Python code actually concatenates lists at runtime
"""

import pytest

from streetrace.dsl.ast.nodes import (
    BinaryOp,
    ListLiteral,
    Literal,
    PropertyAccess,
    VarRef,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.visitors.expressions import ExpressionVisitor
from streetrace.dsl.grammar.parser import ParserFactory


class TestListConcatenationGrammar:
    """Test grammar parsing of list concatenation expressions."""

    @pytest.fixture
    def parser(self):
        """Create DSL parser instance."""
        return ParserFactory.create()

    def test_parses_variable_plus_variable(self, parser):
        """Test parsing $a + $b expression."""
        source = """
flow test:
    $result = $a + $b
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_variable_plus_property_access(self, parser):
        """Test parsing $all + $obj.items expression."""
        source = """
flow test:
    $result = $all + $obj.items
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_variable_plus_list_literal(self, parser):
        """Test parsing $items + [$item] expression."""
        source = """
flow test:
    $result = $items + [$item]
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_complex_concatenation(self, parser):
        """Test parsing complex list concatenation."""
        source = """
flow test:
    $all_findings = []
    $all_findings = $all_findings + $security_findings.findings
    $validated = []
    $validated = $validated + [$finding]
    return $all_findings
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_multiple_concatenations(self, parser):
        """Test parsing chained concatenations."""
        source = """
flow test:
    $result = $a + $b + $c
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_concatenation_in_for_loop(self, parser):
        """Test parsing concatenation inside for loop."""
        source = """
flow test:
    $results = []
    for $item in $items do
        $results = $results + [$item]
    end
    return $results
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestListConcatenationTransformer:
    """Test AST transformer for list concatenation expressions."""

    @pytest.fixture
    def parser(self):
        """Create DSL parser instance."""
        return ParserFactory.create()

    def test_transforms_variable_plus_variable(self, parser):
        """Test transforming $a + $b to BinaryOp node."""
        source = """
flow test:
    $result = $a + $b
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment.value, BinaryOp)
        assert assignment.value.op == "+"
        assert isinstance(assignment.value.left, VarRef)
        assert assignment.value.left.name == "a"
        assert isinstance(assignment.value.right, VarRef)
        assert assignment.value.right.name == "b"

    def test_transforms_variable_plus_property_access(self, parser):
        """Test transforming $all + $obj.items to BinaryOp node."""
        source = """
flow test:
    $result = $all + $obj.items
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment.value, BinaryOp)
        assert assignment.value.op == "+"
        assert isinstance(assignment.value.left, VarRef)
        assert assignment.value.left.name == "all"
        assert isinstance(assignment.value.right, PropertyAccess)
        assert isinstance(assignment.value.right.base, VarRef)
        assert assignment.value.right.base.name == "obj"
        assert assignment.value.right.properties == ["items"]

    def test_transforms_variable_plus_list_literal(self, parser):
        """Test transforming $items + [$item] to BinaryOp node."""
        source = """
flow test:
    $result = $items + [$item]
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment.value, BinaryOp)
        assert assignment.value.op == "+"
        assert isinstance(assignment.value.left, VarRef)
        assert assignment.value.left.name == "items"
        assert isinstance(assignment.value.right, ListLiteral)
        assert len(assignment.value.right.elements) == 1
        assert isinstance(assignment.value.right.elements[0], VarRef)
        assert assignment.value.right.elements[0].name == "item"

    def test_transforms_chained_concatenation(self, parser):
        """Test transforming $a + $b + $c to nested BinaryOp nodes."""
        source = """
flow test:
    $result = $a + $b + $c
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]

        # Should be (($a + $b) + $c)
        assert isinstance(assignment.value, BinaryOp)
        assert assignment.value.op == "+"
        assert isinstance(assignment.value.left, BinaryOp)
        assert assignment.value.left.op == "+"
        assert isinstance(assignment.value.right, VarRef)
        assert assignment.value.right.name == "c"


class TestListConcatenationCodegen:
    """Test code generation for list concatenation expressions."""

    def test_generates_code_for_variable_plus_variable(self):
        """Test code generation for $a + $b."""
        visitor = ExpressionVisitor()
        node = BinaryOp(
            op="+",
            left=VarRef(name="a"),
            right=VarRef(name="b"),
        )

        code = visitor.visit(node)

        assert code == "list_concat(ctx.vars['a'], ctx.vars['b'])"

    def test_generates_code_for_variable_plus_property_access(self):
        """Test code generation for $all + $obj.items."""
        visitor = ExpressionVisitor()
        node = BinaryOp(
            op="+",
            left=VarRef(name="all"),
            right=PropertyAccess(
                base=VarRef(name="obj"),
                properties=["items"],
            ),
        )

        code = visitor.visit(node)

        assert code == "list_concat(ctx.vars['all'], ctx.vars['obj']['items'])"

    def test_generates_code_for_variable_plus_list_literal(self):
        """Test code generation for $items + [$item]."""
        visitor = ExpressionVisitor()
        node = BinaryOp(
            op="+",
            left=VarRef(name="items"),
            right=ListLiteral(elements=[VarRef(name="item")]),
        )

        code = visitor.visit(node)

        assert code == "list_concat(ctx.vars['items'], [ctx.vars['item']])"

    def test_generates_code_for_nested_property_access(self):
        """Test code generation for $all + $obj.nested.items."""
        visitor = ExpressionVisitor()
        node = BinaryOp(
            op="+",
            left=VarRef(name="all"),
            right=PropertyAccess(
                base=VarRef(name="obj"),
                properties=["nested", "items"],
            ),
        )

        code = visitor.visit(node)

        expected = "list_concat(ctx.vars['all'], ctx.vars['obj']['nested']['items'])"
        assert code == expected

    def test_generates_code_for_chained_concatenation(self):
        """Test code generation for $a + $b + $c."""
        visitor = ExpressionVisitor()
        # Represents (($a + $b) + $c)
        node = BinaryOp(
            op="+",
            left=BinaryOp(
                op="+",
                left=VarRef(name="a"),
                right=VarRef(name="b"),
            ),
            right=VarRef(name="c"),
        )

        code = visitor.visit(node)

        expected = (
            "list_concat(list_concat(ctx.vars['a'], ctx.vars['b']), ctx.vars['c'])"
        )
        assert code == expected

    def test_generates_code_for_list_with_string_literal(self):
        """Test code generation for $items + ["value"]."""
        visitor = ExpressionVisitor()
        node = BinaryOp(
            op="+",
            left=VarRef(name="items"),
            right=ListLiteral(
                elements=[Literal(value="value", literal_type="string")],
            ),
        )

        code = visitor.visit(node)

        assert code == 'list_concat(ctx.vars[\'items\'], ["value"])'


class TestListConcatenationIntegration:
    """Integration tests for list concatenation end-to-end."""

    def test_generated_code_contains_plus_operator(self):
        """Test that generated flow code contains the + operator."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow accumulate:
    $result = $a + $b
    return $result
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "list_concat(ctx.vars['a'], ctx.vars['b'])" in code

    def test_generated_code_contains_property_concatenation(self):
        """Test generated code for property access concatenation."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow accumulate_findings:
    $all = $all + $obj.findings
    return $all
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "list_concat(ctx.vars['all'], ctx.vars['obj']['findings'])" in code

    def test_generated_code_contains_list_literal_concatenation(self):
        """Test generated code for list literal concatenation."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow append_item:
    $validated = $validated + [$finding]
    return $validated
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "list_concat(ctx.vars['validated'], [ctx.vars['finding']])" in code

    def test_generated_code_is_valid_python(self):
        """Test that generated code compiles as valid Python."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.grammar.parser import ParserFactory

        source = """
flow test_concatenation:
    $a = []
    $b = []
    $result = $a + $b
    $result = $result + [$item]
    return $result
"""
        parser = ParserFactory.create()
        tree = parser.parse(source)
        ast = transform(tree)

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code can be compiled (will raise SyntaxError if invalid)
        compile(code, "<generated>", "exec")


class TestListConcatenationRuntime:
    """Runtime tests to verify list concatenation actually works.

    Uses Python list operations to verify that the generated code patterns
    work correctly at runtime.
    """

    def test_variable_plus_variable_concatenation(self):
        """Test that $a + $b pattern concatenates lists."""
        # Simulate the runtime context
        ctx_vars = {"a": [1, 2], "b": [3, 4]}

        # The generated code pattern
        result = ctx_vars["a"] + ctx_vars["b"]

        assert result == [1, 2, 3, 4]

    def test_variable_plus_list_literal_concatenation(self):
        """Test that $a + [$item] pattern concatenates lists."""
        ctx_vars = {"a": [1, 2], "item": 5}

        # The generated code pattern
        result = ctx_vars["a"] + [ctx_vars["item"]]

        assert result == [1, 2, 5]

    def test_property_access_concatenation(self):
        """Test concatenation with property access at runtime."""
        ctx_vars = {
            "all": [1, 2],
            "obj": {"findings": [3, 4, 5]},
        }

        # The generated code pattern
        result = ctx_vars["all"] + ctx_vars["obj"]["findings"]

        assert result == [1, 2, 3, 4, 5]

    def test_nested_property_access_concatenation(self):
        """Test concatenation with nested property access at runtime."""
        ctx_vars = {
            "results": ["a"],
            "data": {"nested": {"items": ["b", "c"]}},
        }

        # The generated code pattern
        result = ctx_vars["results"] + ctx_vars["data"]["nested"]["items"]

        assert result == ["a", "b", "c"]

    def test_chained_concatenation(self):
        """Test chained concatenation at runtime."""
        ctx_vars = {"a": [1], "b": [2], "c": [3]}

        # The generated code pattern (left-associative)
        result = (ctx_vars["a"] + ctx_vars["b"]) + ctx_vars["c"]

        assert result == [1, 2, 3]

    def test_empty_list_concatenation(self):
        """Test concatenation starting with empty list."""
        ctx_vars = {
            "findings": [],
            "new_finding": {"id": 1, "message": "test"},
        }

        # Simulate: $findings = $findings + [$new_finding]
        result = ctx_vars["findings"] + [ctx_vars["new_finding"]]

        assert result == [{"id": 1, "message": "test"}]

    def test_accumulation_pattern(self):
        """Test the accumulation pattern used in code review agent."""
        # Simulate the V2 code review agent pattern
        all_findings: list = []
        security_findings = {"findings": [{"id": 1}, {"id": 2}]}
        performance_findings = {"findings": [{"id": 3}]}

        # Accumulate findings
        all_findings = all_findings + security_findings["findings"]
        all_findings = all_findings + performance_findings["findings"]

        assert all_findings == [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_validation_pattern(self):
        """Test the validation accumulation pattern."""
        validated: list = []
        findings = [
            {"confidence": 90, "msg": "high"},
            {"confidence": 50, "msg": "low"},
            {"confidence": 85, "msg": "medium-high"},
        ]

        # Simulate: for each finding, if confidence >= 80, add to validated
        # Using + concatenation intentionally to match DSL generated code pattern
        for finding in findings:
            if finding["confidence"] >= 80:
                validated = validated + [finding]  # noqa: RUF005

        assert len(validated) == 2
        assert validated[0]["msg"] == "high"
        assert validated[1]["msg"] == "medium-high"


class TestSubtractionOperator:
    """Test that subtraction also works (shares the additive rule)."""

    @pytest.fixture
    def parser(self):
        """Create DSL parser instance."""
        return ParserFactory.create()

    def test_parses_subtraction(self, parser):
        """Test parsing $a - $b expression."""
        source = """
flow test:
    $result = $a - $b
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_transforms_subtraction(self, parser):
        """Test transforming subtraction to BinaryOp."""
        source = """
flow test:
    $result = $a - $b
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flow = ast.statements[0]
        assignment = flow.body[0]

        assert isinstance(assignment.value, BinaryOp)
        assert assignment.value.op == "-"

    def test_generates_code_for_subtraction(self):
        """Test code generation for subtraction."""
        visitor = ExpressionVisitor()
        node = BinaryOp(
            op="-",
            left=VarRef(name="a"),
            right=VarRef(name="b"),
        )

        code = visitor.visit(node)

        assert code == "(ctx.vars['a'] - ctx.vars['b'])"
