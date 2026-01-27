"""Tests for escalation transformer.

Test coverage for transforming parsed escalation clauses and handlers
into proper AST nodes.
"""

import pytest

from streetrace.dsl.ast.nodes import (
    DslFile,
    FlowDef,
    PromptDef,
    RunStmt,
    VarRef,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.grammar.parser import ParserFactory


class TestPromptEscalationTransformer:
    """Test transformation of prompt escalation clauses to AST."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_prompt_with_normalized_escalation(self, parser):
        """Test transforming prompt with ~ escalation condition."""
        source = '''
prompt pi_enhancer: """
You are a prompt improvement assistant.
"""
    escalate if ~ "DRIFTING"
'''
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 1

        prompt = prompts[0]
        assert prompt.name == "pi_enhancer"
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "~"
        assert prompt.escalation_condition.value == "DRIFTING"

    def test_transforms_prompt_with_exact_match_escalation(self, parser):
        """Test transforming prompt with == escalation condition."""
        source = '''
prompt classifier: """
Classify the input.
"""
    escalate if == "NEEDS_HUMAN"
'''
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        prompt = prompts[0]
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "=="
        assert prompt.escalation_condition.value == "NEEDS_HUMAN"

    def test_transforms_prompt_with_not_equal_escalation(self, parser):
        """Test transforming prompt with != escalation condition."""
        source = '''
prompt validator: """
Validate the input.
"""
    escalate if != "VALID"
'''
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        prompt = prompts[0]
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "!="
        assert prompt.escalation_condition.value == "VALID"

    def test_transforms_prompt_with_contains_escalation(self, parser):
        """Test transforming prompt with contains escalation condition."""
        source = '''
prompt detector: """
Detect errors in the input.
"""
    escalate if contains "ERROR"
'''
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        prompt = prompts[0]
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "contains"
        assert prompt.escalation_condition.value == "ERROR"

    def test_transforms_prompt_without_escalation(self, parser):
        """Test backward compat - prompt without escalation has None condition."""
        source = '''
prompt simple_prompt: """
You are a helpful assistant.
"""
'''
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        prompt = prompts[0]
        assert prompt.escalation_condition is None

    def test_transforms_prompt_with_modifiers_and_escalation(self, parser):
        """Test transforming prompt with modifiers and escalation clause."""
        source = '''
prompt analyzer using model "compact": """
Analyze the input data.
"""
    escalate if ~ "ESCALATE"
'''
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        prompt = prompts[0]
        assert prompt.name == "analyzer"
        assert prompt.model == "compact"
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "~"


class TestRunStatementEscalationTransformer:
    """Test transformation of run statement escalation handlers to AST."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_run_with_return_escalation(self, parser):
        """Test transforming run statement with on escalate return handler."""
        source = """
flow resolver:
    $current = run agent peer1 $input, on escalate return $input
    return $current
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        flow = flows[0]

        # Find the RunStmt
        run_stmts = [s for s in flow.body if isinstance(s, RunStmt)]
        assert len(run_stmts) == 1
        run_stmt = run_stmts[0]

        assert run_stmt.target == "$current"
        assert run_stmt.agent == "peer1"
        assert run_stmt.escalation_handler is not None
        assert run_stmt.escalation_handler.action == "return"
        assert isinstance(run_stmt.escalation_handler.value, VarRef)
        assert run_stmt.escalation_handler.value.name == "input"

    def test_transforms_run_with_continue_escalation(self, parser):
        """Test transforming run statement with on escalate continue handler."""
        source = """
flow processor:
    for $item in $items do
        $processed = run agent validator $item, on escalate continue
    end
    return $items
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]

        # Get the for loop and its body
        from streetrace.dsl.ast.nodes import ForLoop

        for_loop = next(s for s in flow.body if isinstance(s, ForLoop))
        run_stmts = [s for s in for_loop.body if isinstance(s, RunStmt)]
        run_stmt = run_stmts[0]

        assert run_stmt.escalation_handler is not None
        assert run_stmt.escalation_handler.action == "continue"
        assert run_stmt.escalation_handler.value is None

    def test_transforms_run_with_abort_escalation(self, parser):
        """Test transforming run statement with on escalate abort handler."""
        source = """
flow critical_flow:
    $result = run agent processor $input, on escalate abort
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]
        run_stmts = [s for s in flow.body if isinstance(s, RunStmt)]
        run_stmt = run_stmts[0]

        assert run_stmt.escalation_handler is not None
        assert run_stmt.escalation_handler.action == "abort"
        assert run_stmt.escalation_handler.value is None

    def test_transforms_run_without_escalation(self, parser):
        """Test backward compat - run without escalation has None handler."""
        source = """
flow simple_flow:
    $result = run agent processor $input
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]
        run_stmts = [s for s in flow.body if isinstance(s, RunStmt)]
        run_stmt = run_stmts[0]

        assert run_stmt.escalation_handler is None

    def test_transforms_run_without_assignment_with_escalation(self, parser):
        """Test transforming run without assignment but with escalation handler."""
        source = """
flow validator_flow:
    run agent checker $data, on escalate abort
    return $data
"""
        tree = parser.parse(source)
        ast = transform(tree)

        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]
        run_stmts = [s for s in flow.body if isinstance(s, RunStmt)]
        run_stmt = run_stmts[0]

        assert run_stmt.target is None
        assert run_stmt.agent == "checker"
        assert run_stmt.escalation_handler is not None
        assert run_stmt.escalation_handler.action == "abort"


class TestCompleteEscalationTransformer:
    """Test complete examples with both prompt and run escalation."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_transforms_complete_resolver_example(self, parser):
        """Test transforming the complete resolver example."""
        source = '''
model main = anthropic/claude-sonnet

prompt pi_enhancer using model "main": """
You are a prompt improvement assistant.
Reply with DRIFTING if conversation is going off track.
"""
    escalate if ~ "DRIFTING"

agent peer1:
    instruction pi_enhancer

flow default:
    $current = $input_prompt
    $current = run agent peer1 $current, on escalate return $current
    return $current
'''
        tree = parser.parse(source)
        ast = transform(tree)

        # Check prompt
        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        prompt = prompts[0]
        assert prompt.escalation_condition is not None
        assert prompt.escalation_condition.op == "~"
        assert prompt.escalation_condition.value == "DRIFTING"

        # Check flow
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        flow = flows[0]
        run_stmts = [s for s in flow.body if isinstance(s, RunStmt)]

        # Find the run statement with escalation
        escalation_runs = [r for r in run_stmts if r.escalation_handler is not None]
        assert len(escalation_runs) == 1
        assert escalation_runs[0].escalation_handler.action == "return"

    def test_transforms_multiple_prompts_different_escalations(self, parser):
        """Test transforming multiple prompts with different escalation conditions."""
        source = '''
prompt analyzer: """
Analyze the data.
"""
    escalate if ~ "ESCALATE"

prompt classifier: """
Classify the input.
"""
    escalate if == "UNKNOWN"

prompt validator: """
Validate the result.
"""
    escalate if contains "ERROR"
'''
        tree = parser.parse(source)
        ast = transform(tree)

        prompts = [s for s in ast.statements if isinstance(s, PromptDef)]
        assert len(prompts) == 3

        # Check each prompt's escalation condition
        analyzer = next(p for p in prompts if p.name == "analyzer")
        assert analyzer.escalation_condition.op == "~"

        classifier = next(p for p in prompts if p.name == "classifier")
        assert classifier.escalation_condition.op == "=="

        validator = next(p for p in prompts if p.name == "validator")
        assert validator.escalation_condition.op == "contains"
