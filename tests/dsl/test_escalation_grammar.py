"""Tests for escalation grammar extensions.

Test coverage for parsing prompt escalation clauses and run statement
escalation handlers.
"""

import pytest

from streetrace.dsl.grammar.parser import ParserFactory


class TestPromptEscalationClauseParsing:
    """Test parsing of prompt escalation clauses."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_prompt_with_normalized_escalation(self, parser):
        """Test parsing prompt with ~ escalation condition."""
        source = '''
prompt pi_enhancer: """
You are a prompt improvement assistant.
"""
    escalate if ~ "DRIFTING"
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_exact_match_escalation(self, parser):
        """Test parsing prompt with == escalation condition."""
        source = '''
prompt classifier: """
Classify the input.
"""
    escalate if == "NEEDS_HUMAN"
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_not_equal_escalation(self, parser):
        """Test parsing prompt with != escalation condition."""
        source = '''
prompt validator: """
Validate the input.
"""
    escalate if != "VALID"
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_contains_escalation(self, parser):
        """Test parsing prompt with contains escalation condition."""
        source = '''
prompt detector: """
Detect errors in the input.
"""
    escalate if contains "ERROR"
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_with_modifiers_and_escalation(self, parser):
        """Test parsing prompt with modifiers and escalation clause."""
        source = '''
prompt analyzer using model "compact" expecting AnalysisResult: """
Analyze the input data.
"""
    escalate if ~ "ESCALATE"
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_prompt_without_escalation(self, parser):
        """Test backward compatibility - prompt without escalation still works."""
        source = '''
prompt simple_prompt: """
You are a helpful assistant.
"""
'''
        tree = parser.parse(source)
        assert tree.data == "start"


class TestRunStatementEscalationParsing:
    """Test parsing of run statement escalation handlers."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_run_with_return_escalation(self, parser):
        """Test parsing run statement with on escalate return handler."""
        source = """
flow resolver:
    $current = $input_prompt
    $current = run agent peer1 with $current, on escalate return $current
    return $current
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_run_with_continue_escalation(self, parser):
        """Test parsing run statement with on escalate continue handler."""
        source = """
flow processor:
    for $item in $items do
        run agent validator with $item, on escalate continue
    end
    return $items
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_run_with_abort_escalation(self, parser):
        """Test parsing run statement with on escalate abort handler."""
        source = """
flow critical_flow:
    $result = run agent processor with $input, on escalate abort
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_run_without_assignment_with_escalation(self, parser):
        """Test parsing run without assignment but with escalation handler."""
        source = """
flow validator_flow:
    run agent checker with $data, on escalate abort
    return $data
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_run_without_escalation(self, parser):
        """Test backward compatibility - run without escalation still works."""
        source = """
flow simple_flow:
    $result = run agent processor with $input
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_run_with_input_and_escalation(self, parser):
        """Test parsing run with input and escalation handler."""
        source = """
flow single_arg_flow:
    $result = run agent processor with $arg1, on escalate return $fallback
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestLoopWithEscalation:
    """Test escalation patterns in loop contexts."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_loop_with_escalation_return(self, parser):
        """Test parsing loop block with escalation return pattern."""
        source = """
flow iterative_resolver:
    $current = $input_prompt
    loop max 3 do
        $current = run agent peer1 with $current, on escalate return $current
        $current = run agent peer2 with $current, on escalate return $current
    end
    return $current
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_for_loop_with_escalation_continue(self, parser):
        """Test parsing for loop with escalation continue pattern."""
        source = """
flow batch_processor:
    $results = []
    for $item in $items do
        $processed = run agent processor with $item, on escalate continue
        push $processed to $results
    end
    return $results
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestCompleteEscalationExample:
    """Test complete examples combining prompts and runs with escalation."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_complete_resolver_example(self, parser):
        """Test parsing the resolver example from design doc."""
        source = '''
model main = anthropic/claude-sonnet

prompt pi_enhancer using model "main": """
You are a prompt improvement assistant.
Reply with DRIFTING if conversation is going off track.
"""
    escalate if ~ "DRIFTING"

agent peer1:
    instruction pi_enhancer

agent peer2:
    instruction pi_enhancer

flow default:
    $current = $input_prompt
    loop max 3 do
        $current = run agent peer1 with $current, on escalate return $current
        $current = run agent peer2 with $current, on escalate return $current
    end
    return $current
'''
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_multiple_prompts_with_different_escalations(self, parser):
        """Test parsing multiple prompts with different escalation conditions."""
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
        assert tree.data == "start"
