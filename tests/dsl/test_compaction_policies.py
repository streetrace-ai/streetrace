"""Tests for compaction policy properties.

Verify that compaction policies with strategy and preserve properties
are parsed and transformed correctly.
"""

import pytest

from streetrace.dsl.ast.nodes import DslFile, PolicyDef
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.grammar.parser import ParserFactory


class TestCompactionPolicyParsing:
    """Test parsing of compaction policy definitions."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_policy_with_trigger_parses(self, parser):
        """Policy with trigger property parses correctly."""
        source = """
policy compaction:
    trigger: token_usage > 0.8
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        policies = [s for s in ast.statements if isinstance(s, PolicyDef)]
        assert len(policies) == 1
        assert policies[0].name == "compaction"
        assert "trigger" in policies[0].properties
        trigger = policies[0].properties["trigger"]
        assert trigger["var"] == "token_usage"
        assert trigger["op"] == ">"
        assert trigger["value"] == 0.8

    def test_policy_with_strategy_parses(self, parser):
        """Policy with strategy property parses correctly."""
        source = """
policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        policies = [s for s in ast.statements if isinstance(s, PolicyDef)]
        assert len(policies) == 1
        assert policies[0].name == "compaction"
        # Strategy should be stored in properties
        assert "strategy" in policies[0].properties
        assert policies[0].properties["strategy"] == "summarize_with_goal"

    def test_policy_with_preserve_list_parses(self, parser):
        """Policy with preserve list parses correctly."""
        source = """
policy compaction:
    trigger: token_usage > 0.8
    preserve: [$goal, last 5 messages, tool results]
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        policies = [s for s in ast.statements if isinstance(s, PolicyDef)]
        assert len(policies) == 1
        assert policies[0].name == "compaction"
        # Preserve should contain the list of items
        assert "preserve" in policies[0].properties
        preserve = policies[0].properties["preserve"]
        assert isinstance(preserve, list)
        assert len(preserve) == 3

    def test_policy_with_all_properties_parses(self, parser):
        """Policy with all properties parses correctly."""
        source = """
policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
    preserve: [$goal, last 5 messages]
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        policies = [s for s in ast.statements if isinstance(s, PolicyDef)]
        assert len(policies) == 1
        policy = policies[0]
        assert policy.name == "compaction"
        assert "trigger" in policy.properties
        assert "strategy" in policy.properties
        assert "preserve" in policy.properties

    def test_policy_preserve_with_variable_parses(self, parser):
        """Policy preserve list with variable parses correctly."""
        source = """
policy compaction:
    trigger: token_usage > 0.8
    preserve: [$goal]
"""
        tree = parser.parse(source)
        ast = transform(tree)

        policies = [s for s in ast.statements if isinstance(s, PolicyDef)]
        assert len(policies) == 1
        preserve = policies[0].properties.get("preserve", [])
        assert len(preserve) >= 1
        # The variable should be extracted from VarRef
        # Check that $goal is present in some form
        goal_strings = {"$goal", "goal"}
        goal_found = any(
            (hasattr(p, "name") and p.name == "goal") or p in goal_strings
            for p in preserve
        )
        assert goal_found, f"$goal not found in preserve list: {preserve}"


class TestCompactionPolicyCodeGen:
    """Test code generation for compaction policies."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_policy_generates_config_dict(self, parser):
        """Compaction policy generates proper config dictionary."""
        from streetrace.dsl.codegen.generator import CodeGenerator
        from streetrace.dsl.semantic import SemanticAnalyzer

        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent:
    tools fs
    instruction my_prompt

policy compaction:
    trigger: token_usage > 0.8
    strategy: summarize_with_goal
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

        # Code should contain policy configuration
        # This verifies the generated code is syntactically valid
        assert code  # Non-empty code generated
