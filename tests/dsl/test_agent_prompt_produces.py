"""Tests for agent prompt and produces fields (Phase 3).

Test grammar, transformer, semantic validation, and code generation
for agent prompt (default input) and produces (auto-assign output) fields.
"""

import pytest

from streetrace.dsl.ast import (
    AgentDef,
    DslFile,
    FlowDef,
    PromptDef,
    RunStmt,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.errors import ErrorCode

# =============================================================================
# Grammar / Parser Tests
# =============================================================================


class TestAgentPromptGrammar:
    """Test parsing of agent prompt property."""

    @pytest.fixture
    def parser(self):
        return ParserFactory.create()

    def test_parses_agent_with_prompt(self, parser):
        """Agent with prompt property parses successfully."""
        source = """
agent reviewer:
    tools github
    instruction review_prompt
    prompt review_input
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_agent_with_produces(self, parser):
        """Agent with produces property parses successfully."""
        source = """
agent reviewer:
    tools github
    instruction review_prompt
    produces review_result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_agent_with_both_prompt_and_produces(self, parser):
        """Agent with both prompt and produces parses successfully."""
        source = """
agent reviewer:
    tools github
    instruction review_prompt
    prompt review_input
    produces review_result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_parses_agent_prompt_with_other_properties(self, parser):
        """Agent with prompt alongside delegate and retry parses."""
        source = """
agent coordinator:
    tools github
    instruction coord_prompt
    prompt user_input
    delegate worker
    retry standard_retry
"""
        tree = parser.parse(source)
        assert tree.data == "start"


# =============================================================================
# Transformer Tests
# =============================================================================


class TestAgentPromptTransformer:
    """Test AST transformation of agent prompt and produces fields."""

    @pytest.fixture
    def parse_and_transform(self):
        from streetrace.dsl.ast.transformer import AstTransformer

        parser = ParserFactory.create()
        transformer = AstTransformer()

        def _do(source: str) -> DslFile:
            tree = parser.parse(source)
            return transformer.transform(tree)

        return _do

    def test_transforms_prompt_to_ast(self, parse_and_transform):
        """Agent prompt property becomes AgentDef.prompt field."""
        ast = parse_and_transform("""
agent reviewer:
    tools github
    instruction review_prompt
    prompt review_input
""")
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert agents[0].prompt == "review_input"

    def test_transforms_produces_to_ast(self, parse_and_transform):
        """Agent produces property becomes AgentDef.produces field."""
        ast = parse_and_transform("""
agent reviewer:
    tools github
    instruction review_prompt
    produces review_result
""")
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert agents[0].produces == "review_result"

    def test_transforms_both_prompt_and_produces(self, parse_and_transform):
        """Agent with both prompt and produces sets both fields."""
        ast = parse_and_transform("""
agent reviewer:
    tools github
    instruction review_prompt
    prompt review_input
    produces review_result
""")
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert agents[0].prompt == "review_input"
        assert agents[0].produces == "review_result"

    def test_agent_without_prompt_produces_has_none(self, parse_and_transform):
        """Agent without prompt/produces has None for both fields."""
        ast = parse_and_transform("""
agent simple:
    tools github
    instruction simple_prompt
""")
        agents = [s for s in ast.statements if isinstance(s, AgentDef)]
        assert len(agents) == 1
        assert agents[0].prompt is None
        assert agents[0].produces is None


# =============================================================================
# Semantic Validation Tests
# =============================================================================


class TestAgentPromptSemanticValidation:
    """Test semantic validation of agent prompt references."""

    def test_valid_prompt_reference_passes(self) -> None:
        """Agent with prompt referencing a defined prompt passes."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="review_input", body="Review this code"),
                PromptDef(name="review_prompt", body="You are a reviewer"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    prompt="review_input",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        e0001_errors = [e for e in result.errors if e.code == ErrorCode.E0001]
        assert not e0001_errors

    def test_undefined_prompt_reference_error(self) -> None:
        """Agent with prompt referencing undefined prompt reports error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="review_prompt", body="You are a reviewer"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    prompt="nonexistent_input",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        e0001_errors = [e for e in result.errors if e.code == ErrorCode.E0001]
        assert len(e0001_errors) >= 1
        assert any("nonexistent_input" in e.message for e in e0001_errors)

    def test_no_prompt_skips_validation(self) -> None:
        """Agent without prompt field does not trigger prompt validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="agent_prompt", body="Do work"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="agent_prompt",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        e0001_errors = [e for e in result.errors if e.code == ErrorCode.E0001]
        assert not e0001_errors


# =============================================================================
# Code Generation Tests
# =============================================================================


class TestAgentPromptCodeGeneration:
    """Test code generation for agent prompt and produces fields."""

    def test_prompt_emits_in_agent_dict(self) -> None:
        """Agent with prompt emits 'prompt' key in _agents dict."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_input", body="Review this"),
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    prompt="review_input",
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'prompt': 'review_input'" in code

    def test_produces_emits_in_agent_dict(self) -> None:
        """Agent with produces emits 'produces' key in _agents dict."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    produces="review_result",
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'produces': 'review_result'" in code

    def test_no_prompt_produces_omits_keys(self) -> None:
        """Agent without prompt/produces omits both keys from _agents dict."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="simple_prompt", body="Simple"),
                AgentDef(
                    name="simple",
                    tools=[],
                    instruction="simple_prompt",
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'prompt':" not in code
        assert "'produces':" not in code


# =============================================================================
# Runtime Code Generation Tests (prompt default input, produces auto-assign)
# =============================================================================


class TestAgentPromptRuntimeCodegen:
    """Test runtime codegen for prompt (default input) behavior."""

    def test_run_agent_without_with_uses_prompt(self) -> None:
        """Run agent without `with` resolves prompt as default input."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_input", body="Review this code"),
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    prompt="review_input",
                ),
                FlowDef(
                    name="main",
                    body=[
                        RunStmt(target="result", agent="reviewer"),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should resolve prompt as default input
        assert "ctx.run_agent('reviewer', ctx.resolve('review_input'))" in code

    def test_run_agent_with_input_ignores_prompt(self) -> None:
        """Run agent with explicit `with` input ignores agent prompt."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_input", body="Review this code"),
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    prompt="review_input",
                ),
                FlowDef(
                    name="main",
                    body=[
                        RunStmt(
                            target="result",
                            agent="reviewer",
                            input=VarRef(name="my_input"),
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should use explicit input, not the agent's prompt
        assert "ctx.vars['my_input']" in code or "ctx.resolve('my_input')" in code
        assert "ctx.resolve('review_input')" not in code

    def test_run_agent_without_prompt_no_default_input(self) -> None:
        """Run agent without prompt field generates no default input."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                ),
                FlowDef(
                    name="main",
                    body=[
                        RunStmt(target="result", agent="reviewer"),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # No default input - just run agent with no args
        assert "ctx.run_agent('reviewer')" in code


class TestAgentProducesRuntimeCodegen:
    """Test runtime codegen for produces (auto-assign) behavior."""

    def test_run_agent_without_target_uses_produces(self) -> None:
        """Run agent without assignment auto-assigns to produces variable."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    produces="review_result",
                ),
                FlowDef(
                    name="main",
                    body=[
                        RunStmt(target=None, agent="reviewer"),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['review_result'] = ctx.get_last_result()" in code

    def test_run_agent_with_target_ignores_produces(self) -> None:
        """Run agent with explicit target ignores produces field."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    produces="review_result",
                ),
                FlowDef(
                    name="main",
                    body=[
                        RunStmt(target="my_result", agent="reviewer"),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Uses explicit target, not produces
        assert "ctx.vars['my_result'] = ctx.get_last_result()" in code
        assert "ctx.vars['review_result']" not in code

    def test_run_agent_without_produces_no_auto_assign(self) -> None:
        """Run agent without produces and without target does not assign."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                ),
                FlowDef(
                    name="main",
                    body=[
                        RunStmt(target=None, agent="reviewer"),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.get_last_result()" not in code

    def test_prompt_and_produces_together(self) -> None:
        """Agent with both prompt and produces generates correct code."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_input", body="Review this"),
                PromptDef(name="review_prompt", body="You review code"),
                AgentDef(
                    name="reviewer",
                    tools=[],
                    instruction="review_prompt",
                    prompt="review_input",
                    produces="review_result",
                ),
                FlowDef(
                    name="main",
                    body=[
                        # No target, no input - both prompt and produces activate
                        RunStmt(target=None, agent="reviewer"),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Prompt provides default input
        assert "ctx.resolve('review_input')" in code
        # Produces provides auto-assign
        assert "ctx.vars['review_result'] = ctx.get_last_result()" in code

    def test_flow_run_ignores_prompt_produces(self) -> None:
        """Flow invocations ignore agent prompt/produces fields."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="main_prompt", body="Main"),
                AgentDef(
                    name="main",
                    tools=[],
                    instruction="main_prompt",
                ),
                FlowDef(
                    name="helper",
                    body=[
                        RunStmt(
                            target=None,
                            agent="helper",
                            is_flow=True,
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Flow calls should not trigger prompt/produces lookup
        assert "ctx.resolve(" not in code or "ctx.resolve('helper')" not in code
