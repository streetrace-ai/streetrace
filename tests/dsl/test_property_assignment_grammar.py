"""Tests for property assignment grammar extensions.

Test coverage for parsing property assignment statements in the DSL.
"""

import pytest

from streetrace.dsl.grammar.parser import ParserFactory


class TestPropertyAssignmentParsing:
    """Test parsing of property assignment statements."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_simple_property_assignment(self, parser):
        """Test parsing simple property assignment: $obj.prop = value."""
        source = """
flow test_flow:
    $review.findings = $filtered
    return $review
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_nested_property_assignment(self, parser):
        """Test parsing nested property assignment: $obj.a.b = value."""
        source = """
flow test_flow:
    $data.nested.deep = "value"
    return $data
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_property_assignment_with_integer_value(self, parser):
        """Test parsing property assignment with integer value."""
        source = """
flow test_flow:
    $data.count = 0
    return $data
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_property_assignment_with_expression(self, parser):
        """Test parsing property assignment with expression value."""
        source = """
flow test_flow:
    $obj.total = $a + $b
    return $obj
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_property_assignment_with_list_literal(self, parser):
        """Test parsing property assignment with list literal."""
        source = """
flow test_flow:
    $review.issues = []
    return $review
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_property_assignment_with_object_literal(self, parser):
        """Test parsing property assignment with object literal."""
        source = """
flow test_flow:
    $result.metadata = { status: "complete", count: 5 }
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_simple_variable_assignment_still_works(self, parser):
        """Test backward compatibility - simple assignment still works."""
        source = """
flow test_flow:
    $result = "value"
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_both_assignment_types_in_same_flow(self, parser):
        """Test parsing both simple and property assignment in same flow."""
        source = """
flow test_flow:
    $review = { findings: [], score: 0 }
    $review.score = 100
    $review.findings = $new_findings
    return $review
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_property_assignment_with_keyword_property_name(self, parser):
        """Test property assignment where property name is a keyword."""
        source = """
flow test_flow:
    $obj.result = $value
    $obj.data = $other
    return $obj
"""
        tree = parser.parse(source)
        assert tree.data == "start"
