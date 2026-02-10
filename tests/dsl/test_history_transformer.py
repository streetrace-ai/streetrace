"""Tests for history management grammar and transformer parsing.

Test the DSL grammar extensions for history management:
- model max_input_tokens property
- agent history property
"""

import pytest

from streetrace.dsl.ast.nodes import AgentDef, ModelDef
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.grammar.parser import ParserFactory


@pytest.fixture
def parser():
    """Create a parser instance for testing."""
    return ParserFactory.create()


def parse_to_ast(parser, source: str):
    """Parse source and transform to AST."""
    tree = parser.parse(source)
    return transform(tree)


class TestModelMaxInputTokensGrammar:
    """Test parsing of max_input_tokens in model definitions."""

    def test_model_with_max_input_tokens(self, parser):
        """Test parsing a model with max_input_tokens."""
        dsl_code = """
model main:
    provider: anthropic
    name: claude-sonnet
    max_input_tokens: 200000
"""
        ast = parse_to_ast(parser, dsl_code)
        assert len(ast.statements) == 1
        model = ast.statements[0]
        assert isinstance(model, ModelDef)
        assert model.name == "main"
        assert model.properties is not None
        assert model.properties.get("max_input_tokens") == 200000

    def test_model_with_all_properties(self, parser):
        """Test parsing a model with all properties including max_input_tokens."""
        dsl_code = """
model main:
    provider: anthropic
    temperature: 0.7
    max_tokens: 4096
    max_input_tokens: 128000
"""
        ast = parse_to_ast(parser, dsl_code)
        model = ast.statements[0]
        assert isinstance(model, ModelDef)
        assert model.properties["provider"] == "anthropic"
        assert model.properties["temperature"] == 0.7
        assert model.properties["max_tokens"] == 4096
        assert model.properties["max_input_tokens"] == 128000


class TestAgentHistoryGrammar:
    """Test parsing of history property in agent definitions."""

    def test_agent_with_history_summarize(self, parser):
        """Test parsing an agent with history summarize strategy."""
        dsl_code = """
prompt review_instructions: '''
Review the code.
'''

agent reviewer:
    instruction review_instructions
    tools file, grep
    history summarize
"""
        ast = parse_to_ast(parser, dsl_code)
        # Find the agent
        agent = None
        for stmt in ast.statements:
            if isinstance(stmt, AgentDef):
                agent = stmt
                break

        assert agent is not None
        assert agent.name == "reviewer"
        assert agent.history == "summarize"

    def test_agent_with_history_truncate(self, parser):
        """Test parsing an agent with history truncate strategy."""
        dsl_code = """
prompt analyze_prompt: '''
Analyze the input.
'''

agent analyzer:
    instruction analyze_prompt
    tools cli
    history truncate
"""
        ast = parse_to_ast(parser, dsl_code)
        agent = None
        for stmt in ast.statements:
            if isinstance(stmt, AgentDef):
                agent = stmt
                break

        assert agent is not None
        assert agent.name == "analyzer"
        assert agent.history == "truncate"

    def test_agent_without_history(self, parser):
        """Test that agents without history have None."""
        dsl_code = """
prompt simple_prompt: '''
Do something.
'''

agent simple:
    instruction simple_prompt
    tools cli
"""
        ast = parse_to_ast(parser, dsl_code)
        agent = None
        for stmt in ast.statements:
            if isinstance(stmt, AgentDef):
                agent = stmt
                break

        assert agent is not None
        assert agent.name == "simple"
        assert agent.history is None

    def test_agent_with_all_properties(self, parser):
        """Test agent with history and all other properties."""
        dsl_code = """
prompt full_prompt: '''
Full agent prompt.
'''

agent complete:
    instruction full_prompt
    prompt full_prompt
    produces findings
    tools file, grep, cli
    description "A complete agent with all properties"
    history summarize
"""
        ast = parse_to_ast(parser, dsl_code)
        agent = None
        for stmt in ast.statements:
            if isinstance(stmt, AgentDef):
                agent = stmt
                break

        assert agent is not None
        assert agent.name == "complete"
        assert agent.instruction == "full_prompt"
        assert agent.prompt == "full_prompt"
        assert agent.produces == "findings"
        assert agent.description == "A complete agent with all properties"
        assert agent.history == "summarize"


class TestHistoryAsContextualKeyword:
    """Test that 'history' works as a contextual keyword."""

    def test_history_as_field_name_in_schema(self, parser):
        """Test using 'history' as a schema field name."""
        dsl_code = """
schema Record:
    history: string
    data: string
"""
        ast = parse_to_ast(parser, dsl_code)
        from streetrace.dsl.ast.nodes import SchemaDef

        schema = None
        for stmt in ast.statements:
            if isinstance(stmt, SchemaDef):
                schema = stmt
                break

        assert schema is not None
        field_names = [f.name for f in schema.fields]
        assert "history" in field_names

    def test_history_in_variable_name(self, parser):
        """Test using 'history' in expressions."""
        dsl_code = """
prompt simple: '''Simple prompt'''

flow main:
    $history = "test"
    log $history
"""
        # Should parse without error
        ast = parse_to_ast(parser, dsl_code)
        assert len(ast.statements) == 2  # prompt + flow
