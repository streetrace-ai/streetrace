"""Tests for property assignment transformer.

Test coverage for transforming parsed property assignment statements
into proper AST nodes.
"""

import pytest

from streetrace.dsl.ast.nodes import (
    DslFile,
    FlowDef,
    Literal,
    PropertyAccess,
    PropertyAssignment,
    VarRef,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.grammar.parser import ParserFactory


class TestPropertyAssignmentTransformer:
    """Test transformation of property assignment statements to AST."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_simple_property_assignment(self, parser):
        """Test transforming simple property assignment."""
        source = """
flow test_flow:
    $review.findings = $filtered
    return $review
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1

        flow = flows[0]
        # First statement should be PropertyAssignment
        prop_assigns = [s for s in flow.body if isinstance(s, PropertyAssignment)]
        assert len(prop_assigns) == 1

        prop_assign = prop_assigns[0]
        assert isinstance(prop_assign.target, PropertyAccess)
        assert isinstance(prop_assign.target.base, VarRef)
        assert prop_assign.target.base.name == "review"
        assert prop_assign.target.properties == ["findings"]
        assert isinstance(prop_assign.value, VarRef)
        assert prop_assign.value.name == "filtered"

    def test_transforms_nested_property_assignment(self, parser):
        """Test transforming nested property assignment."""
        source = """
flow test_flow:
    $data.nested.deep = "value"
    return $data
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]

        prop_assigns = [s for s in flow.body if isinstance(s, PropertyAssignment)]
        assert len(prop_assigns) == 1

        prop_assign = prop_assigns[0]
        assert isinstance(prop_assign.target, PropertyAccess)
        assert prop_assign.target.base.name == "data"
        assert prop_assign.target.properties == ["nested", "deep"]
        assert isinstance(prop_assign.value, Literal)
        assert prop_assign.value.value == "value"

    def test_transforms_property_assignment_with_integer(self, parser):
        """Test transforming property assignment with integer value."""
        source = """
flow test_flow:
    $data.count = 0
    return $data
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]

        prop_assigns = [s for s in flow.body if isinstance(s, PropertyAssignment)]
        prop_assign = prop_assigns[0]

        assert isinstance(prop_assign.value, Literal)
        assert prop_assign.value.value == 0
        assert prop_assign.value.literal_type == "int"

    def test_backward_compat_simple_assignment(self, parser):
        """Test backward compat - simple assignment creates Assignment node."""
        from streetrace.dsl.ast.nodes import Assignment

        source = """
flow test_flow:
    $result = "value"
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]

        # Should be Assignment, not PropertyAssignment
        assigns = [s for s in flow.body if isinstance(s, Assignment)]
        assert len(assigns) == 1
        assert assigns[0].target == "$result"

    def test_transforms_both_assignment_types(self, parser):
        """Test both simple and property assignment in same flow."""
        from streetrace.dsl.ast.nodes import Assignment

        source = """
flow test_flow:
    $review = { score: 0 }
    $review.score = 100
    return $review
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]

        # Should have one Assignment and one PropertyAssignment
        assigns = [s for s in flow.body if isinstance(s, Assignment)]
        prop_assigns = [s for s in flow.body if isinstance(s, PropertyAssignment)]

        assert len(assigns) == 1
        assert assigns[0].target == "$review"

        assert len(prop_assigns) == 1
        assert prop_assigns[0].target.base.name == "review"
        assert prop_assigns[0].target.properties == ["score"]
