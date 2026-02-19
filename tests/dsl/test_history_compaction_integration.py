"""Integration tests for history compaction code generation.

Test end-to-end parsing, code generation, and runtime integration
for the history management feature.
"""

import pytest

from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory


@pytest.fixture
def parser():
    """Create a parser instance."""
    return ParserFactory.create()


def parse_to_ast(parser, source: str):
    """Parse source and transform to AST."""
    tree = parser.parse(source)
    return transform(tree)


class TestHistoryCodeGeneration:
    """Test code generation for history property."""

    def test_generates_history_in_agent_dict(self, parser):
        """Test that history is included in generated agent definition."""
        dsl_code = """
prompt review_prompt: '''
Review the code.
'''

agent reviewer:
    instruction review_prompt
    tools file
    history summarize
"""
        ast = parse_to_ast(parser, dsl_code)
        generator = CodeGenerator()
        code, _ = generator.generate(ast, "test.sr")

        # Check that history is in the generated code
        assert "'history': 'summarize'" in code

    def test_generates_truncate_history(self, parser):
        """Test generation with truncate strategy."""
        dsl_code = """
prompt analyze_prompt: '''
Analyze input.
'''

agent analyzer:
    instruction analyze_prompt
    tools cli
    history truncate
"""
        ast = parse_to_ast(parser, dsl_code)
        generator = CodeGenerator()
        code, _ = generator.generate(ast, "test.sr")

        assert "'history': 'truncate'" in code

    def test_no_history_when_not_specified(self, parser):
        """Test that history is not in generated code when not specified."""
        dsl_code = """
prompt simple_prompt: '''
Simple prompt.
'''

agent simple:
    instruction simple_prompt
    tools file
"""
        ast = parse_to_ast(parser, dsl_code)
        generator = CodeGenerator()
        code, _ = generator.generate(ast, "test.sr")

        # Should not contain history key
        assert "'history':" not in code


class TestMaxInputTokensCodeGeneration:
    """Test code generation for max_input_tokens property."""

    def test_model_with_max_input_tokens_parses(self, parser):
        """Test that models with max_input_tokens parse correctly."""
        dsl_code = """
model main:
    provider: anthropic
    name: claude-sonnet
    max_input_tokens: 200000
"""
        ast = parse_to_ast(parser, dsl_code)
        from streetrace.dsl.ast.nodes import ModelDef

        model = ast.statements[0]
        assert isinstance(model, ModelDef)
        assert model.properties["max_input_tokens"] == 200000


class TestHistoryEventGeneration:
    """Test that HistoryCompactionEvent is properly structured."""

    def test_event_dataclass_fields(self):
        """Test HistoryCompactionEvent has required fields."""
        from streetrace.dsl.runtime.events import HistoryCompactionEvent

        event = HistoryCompactionEvent(
            strategy="summarize",
            original_tokens=10000,
            compacted_tokens=5000,
            messages_removed=8,
        )

        assert event.strategy == "summarize"
        assert event.original_tokens == 10000
        assert event.compacted_tokens == 5000
        assert event.messages_removed == 8
        assert event.type == "history_compaction"


class TestFullWorkflowWithHistory:
    """Test complete workflow with history configuration."""

    def test_workflow_with_history_agents(self, parser):
        """Test parsing and generating a workflow with history-enabled agents."""
        dsl_code = """
model main:
    provider: anthropic
    name: claude-sonnet
    max_input_tokens: 200000

prompt analyze_prompt: '''
Analyze the following code for issues:
$code
'''

prompt review_prompt: '''
Review the analysis results.
'''

agent analyzer:
    instruction analyze_prompt
    tools file, grep
    history summarize
    description "Analyzes code for issues"

agent reviewer:
    instruction review_prompt
    tools file
    history truncate
    description "Reviews analysis results"

flow main:
    $code = "def foo(): pass"
    $analysis = run agent analyzer with $code
    $review = run agent reviewer with $analysis
    return $review
"""
        ast = parse_to_ast(parser, dsl_code)
        generator = CodeGenerator()
        code, _ = generator.generate(ast, "test.sr")

        # Verify both agents have history in generated code
        assert "'history': 'summarize'" in code
        assert "'history': 'truncate'" in code

        # Verify workflow structure is correct
        assert "class TestWorkflow(DslAgentWorkflow):" in code
        assert "def flow_main" in code

    def test_mixed_agents_with_and_without_history(self, parser):
        """Test workflow with some agents having history and some not."""
        dsl_code = """
prompt p1: '''Prompt 1'''
prompt p2: '''Prompt 2'''
prompt p3: '''Prompt 3'''

agent agent1:
    instruction p1
    tools file
    history summarize

agent agent2:
    instruction p2
    tools file
    # No history configured

agent agent3:
    instruction p3
    tools file
    history truncate
"""
        ast = parse_to_ast(parser, dsl_code)
        generator = CodeGenerator()
        code, _ = generator.generate(ast, "test.sr")

        # Count occurrences of history in generated code
        history_count = code.count("'history':")
        # Should be exactly 2 (agent1 and agent3)
        assert history_count == 2
