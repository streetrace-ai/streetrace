"""Tests for comma-separated tool lists in agent definitions.

Verify that agents can define multiple tools using comma-separated lists.
This addresses the known limitation documented in getting-started.md.
"""

import pytest

from streetrace.dsl.ast.nodes import AgentDef, DslFile
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer


class TestCommaSeparatedToolsParsing:
    """Test parsing of comma-separated tool lists."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_agent_with_single_tool_parses(self, parser):
        """Single tool in agent definition parses correctly."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs

prompt my_prompt: '''You are helpful.'''

agent:
    tools fs
    instruction my_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert agents[0].tools == ["fs"]

    def test_agent_with_two_comma_separated_tools_parses(self, parser):
        """Two comma-separated tools in agent definition parse correctly."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs
tool cli = builtin streetrace.cli

prompt my_prompt: '''You are helpful.'''

agent:
    tools fs, cli
    instruction my_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        # Key assertion: tool list should not contain comma tokens
        assert agents[0].tools == ["fs", "cli"]
        assert "," not in agents[0].tools

    def test_agent_with_three_comma_separated_tools_parses(self, parser):
        """Three comma-separated tools in agent definition parse correctly."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs
tool cli = builtin streetrace.cli
tool github = mcp "https://api.github.com"

prompt my_prompt: '''You are helpful.'''

agent:
    tools fs, cli, github
    instruction my_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        # Key assertion: tool list should contain exactly three tools
        assert len(agents[0].tools) == 3
        assert agents[0].tools == ["fs", "cli", "github"]

    def test_agent_with_dotted_tool_names_parses(self, parser):
        """Dotted tool names in comma-separated list parse correctly."""
        source = """
model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs
tool context = mcp "https://context7.io"

prompt my_prompt: '''You are helpful.'''

agent:
    tools fs, context
    instruction my_prompt
"""
        tree = parser.parse(source)
        ast = transform(tree)

        assert isinstance(ast, DslFile)
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert len(agents[0].tools) == 2


class TestCommaSeparatedToolsSemanticAnalysis:
    """Test semantic analysis of agents with comma-separated tools."""

    def test_agent_with_valid_comma_separated_tools_passes_validation(self):
        """Agent with valid comma-separated tools passes semantic validation."""
        from streetrace.dsl.ast.nodes import PromptDef, ToolDef

        ast = DslFile(
            version=None,
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="streetrace.fs"),
                ToolDef(name="cli", tool_type="builtin", builtin_ref="streetrace.cli"),
                PromptDef(name="my_prompt", body="You are helpful"),
                AgentDef(
                    name="helper",
                    tools=["fs", "cli"],
                    instruction="my_prompt",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"

    def test_agent_with_undefined_tool_in_list_fails_validation(self):
        """Agent with undefined tool in comma-separated list fails validation."""
        from streetrace.dsl.ast.nodes import PromptDef, ToolDef

        ast = DslFile(
            version=None,
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="streetrace.fs"),
                PromptDef(name="my_prompt", body="You are helpful"),
                AgentDef(
                    name="helper",
                    tools=["fs", "undefined_tool"],
                    instruction="my_prompt",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_tool" in e.message for e in result.errors)


class TestCommaSeparatedToolsEndToEnd:
    """End-to-end tests for comma-separated tool lists."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_full_dsl_with_comma_separated_tools(self, parser):
        """Full DSL file with comma-separated tools parses and validates."""
        source = """
streetrace v1

model main = anthropic/claude-sonnet

tool fs = builtin streetrace.fs
tool cli = builtin streetrace.cli
tool github = mcp "https://api.github.com"

prompt greeting: '''You are a helpful assistant with access to multiple tools.'''

agent main_agent:
    tools fs, cli, github
    instruction greeting
    description "Main agent with multiple tools"

flow main:
    $result = run agent main_agent with $input_prompt
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)

        # Verify agent has all three tools
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert len(agents[0].tools) == 3
        assert agents[0].tools == ["fs", "cli", "github"]

        # Semantic analysis should pass
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid, f"Expected valid, got errors: {result.errors}"
