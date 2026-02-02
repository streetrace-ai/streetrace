"""Tests for `with` keyword syntax in agent and LLM invocations.

Verify that `run agent X with expr` and `call llm X with expr` parse,
transform, validate, and generate correct Python code. Also verify
backward compatibility for invocations without `with`.
"""

import pytest

from streetrace.dsl.ast.nodes import (
    CallStmt,
    DslFile,
    FlowDef,
    PromptDef,
    RunStmt,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.ast.transformer import transform
from streetrace.dsl.codegen.generator import CodeGenerator
from streetrace.dsl.grammar.parser import ParserFactory
from streetrace.dsl.semantic import SemanticAnalyzer


class TestWithKeywordGrammar:
    """Test that the grammar accepts `with` keyword in invocations."""

    @pytest.fixture
    def parser(self) -> ParserFactory:
        """Create parser instance."""
        return ParserFactory.create()

    def test_run_agent_with_keyword_and_target(self, parser: ParserFactory) -> None:
        """Parse: $result = run agent reviewer with $review_prompt."""
        source = """
flow test:
    $result = run agent reviewer with $review_prompt
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_run_agent_with_keyword_no_target(self, parser: ParserFactory) -> None:
        """Parse: run agent fetcher with $input_prompt."""
        source = """
flow test:
    run agent fetcher with $input_prompt
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_call_llm_with_keyword(self, parser: ParserFactory) -> None:
        """Parse: $result = call llm deduplicator with $validated_findings."""
        source = """
flow test:
    $result = call llm deduplicator with $validated_findings
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_run_agent_no_with_backward_compat(self, parser: ParserFactory) -> None:
        """Parse: run agent fetcher (no with -- backward compatible)."""
        source = """
flow test:
    run agent fetcher
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_run_agent_with_and_escalation(self, parser: ParserFactory) -> None:
        """Parse: run agent with input and escalation handler."""
        source = """
flow test:
    $result = run agent reviewer with $review_prompt, on escalate return $result
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_run_flow_with_keyword(self, parser: ParserFactory) -> None:
        """Parse: $result = run get_data with $some_input."""
        source = """
flow get_data:
    return $input_prompt

flow test:
    $result = run get_data with $some_input
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_run_flow_with_keyword_no_target(self, parser: ParserFactory) -> None:
        """Parse: run get_data with $some_input."""
        source = """
flow get_data:
    return $input_prompt

flow test:
    run get_data with $some_input
"""
        tree = parser.parse(source)
        assert tree.data == "start"

    def test_call_llm_no_with(self, parser: ParserFactory) -> None:
        """Parse: $result = call llm analyzer (no with)."""
        source = """
flow test:
    $result = call llm analyzer
    return $result
"""
        tree = parser.parse(source)
        assert tree.data == "start"


class TestWithKeywordTransformer:
    """Test that transformer produces correct AST nodes for with keyword."""

    @pytest.fixture
    def parser(self) -> ParserFactory:
        """Create parser instance."""
        return ParserFactory.create()

    def test_run_agent_with_produces_input(self, parser: ParserFactory) -> None:
        """Run agent with keyword produces RunStmt(input=VarRef(...))."""
        source = """
flow test:
    $result = run agent reviewer with $review_prompt
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        run_stmt = flows[0].body[0]
        assert isinstance(run_stmt, RunStmt)
        assert run_stmt.target == "result"
        assert run_stmt.agent == "reviewer"
        assert isinstance(run_stmt.input, VarRef)
        assert run_stmt.input.name == "review_prompt"
        assert run_stmt.is_flow is False

    def test_run_agent_no_with_produces_none_input(
        self, parser: ParserFactory,
    ) -> None:
        """Run agent without with keyword produces RunStmt(input=None)."""
        source = """
flow test:
    run agent fetcher
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        run_stmt = flows[0].body[0]
        assert isinstance(run_stmt, RunStmt)
        assert run_stmt.agent == "fetcher"
        assert run_stmt.input is None

    def test_call_llm_with_produces_input(self, parser: ParserFactory) -> None:
        """Call llm with keyword produces CallStmt(input=VarRef(...))."""
        source = """
flow test:
    $result = call llm deduplicator with $validated_findings
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        call_stmt = flows[0].body[0]
        assert isinstance(call_stmt, CallStmt)
        assert call_stmt.target == "result"
        assert call_stmt.prompt == "deduplicator"
        assert isinstance(call_stmt.input, VarRef)
        assert call_stmt.input.name == "validated_findings"

    def test_call_llm_no_with_produces_none_input(
        self, parser: ParserFactory,
    ) -> None:
        """Call llm without with keyword produces CallStmt(input=None)."""
        source = """
flow test:
    $result = call llm analyzer
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        call_stmt = flows[0].body[0]
        assert isinstance(call_stmt, CallStmt)
        assert call_stmt.prompt == "analyzer"
        assert call_stmt.input is None

    def test_run_flow_with_produces_input(self, parser: ParserFactory) -> None:
        """Run flow with keyword produces RunStmt(input=VarRef(...), is_flow=True)."""
        source = """
flow get_data:
    return $input_prompt

flow test:
    $result = run get_data with $some_input
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        # Second flow is "test"
        test_flow = flows[1]
        run_stmt = test_flow.body[0]
        assert isinstance(run_stmt, RunStmt)
        assert run_stmt.agent == "get_data"
        assert run_stmt.is_flow is True
        assert isinstance(run_stmt.input, VarRef)
        assert run_stmt.input.name == "some_input"

    def test_run_flow_no_target_with_produces_input(
        self, parser: ParserFactory,
    ) -> None:
        """Run flow (no target) with keyword produces RunStmt(input=VarRef(...))."""
        source = """
flow get_data:
    return $input_prompt

flow test:
    run get_data with $some_input
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        test_flow = flows[1]
        run_stmt = test_flow.body[0]
        assert isinstance(run_stmt, RunStmt)
        assert run_stmt.target is None
        assert run_stmt.agent == "get_data"
        assert run_stmt.is_flow is True
        assert isinstance(run_stmt.input, VarRef)
        assert run_stmt.input.name == "some_input"

    def test_run_agent_with_escalation_handler(
        self, parser: ParserFactory,
    ) -> None:
        """Run agent with keyword and escalation handler."""
        source = """
flow test:
    $result = run agent reviewer with $review_prompt, on escalate return $result
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        run_stmt = flows[0].body[0]
        assert isinstance(run_stmt, RunStmt)
        assert isinstance(run_stmt.input, VarRef)
        assert run_stmt.input.name == "review_prompt"
        assert run_stmt.escalation_handler is not None
        assert run_stmt.escalation_handler.action == "return"


class TestWithKeywordSemantic:
    """Test semantic analysis for with keyword."""

    def test_with_expression_references_defined_name(self) -> None:
        """Semantic analysis passes when `with` references a defined name."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="Review this"),
                PromptDef(name="agent_instruction", body="You are a reviewer"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="reviewer",
                            input=VarRef(name="input_prompt"),
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        # input_prompt is a builtin -- should pass
        result = analyzer.analyze(ast)
        # Check that no error about input_prompt undefined
        var_errors = [
            e for e in result.errors
            if "input_prompt" in e.message and "undefined" in e.message.lower()
        ]
        assert len(var_errors) == 0

    def test_with_expression_undefined_name_errors(self) -> None:
        """Semantic analysis fails when `with` references undefined name."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_instruction", body="You are a reviewer"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="reviewer",
                            input=VarRef(name="nonexistent_var"),
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        var_errors = [
            e for e in result.errors
            if "nonexistent_var" in e.message
        ]
        assert len(var_errors) > 0

    def test_agent_without_with_is_valid(self) -> None:
        """Semantic analysis passes for agent invocation without with."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_instruction", body="You are a fetcher"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target=None,
                            agent="fetcher",
                            input=None,
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        # Should not have errors about missing args
        run_errors = [
            e for e in result.errors
            if "args" in e.message.lower() or "input" in e.message.lower()
        ]
        assert len(run_errors) == 0

    def test_call_llm_with_undefined_input_errors(self) -> None:
        """Semantic analysis fails for call llm with undefined input."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="dedup_prompt", body="Deduplicate"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="dedup_prompt",
                            input=VarRef(name="missing_var"),
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        var_errors = [
            e for e in result.errors
            if "missing_var" in e.message
        ]
        assert len(var_errors) > 0


class TestWithKeywordCodeGen:
    """Test code generation for with keyword."""

    def test_run_agent_with_input_generates_correct_code(self) -> None:
        """$result = run agent reviewer with $prompt generates correct Python."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="review_prompt", body="Review this"),
                PromptDef(name="reviewer_instruction", body="You are a reviewer"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="reviewer",
                            input=VarRef(name="review_prompt"),
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")
        assert "ctx.run_agent('reviewer', ctx.vars['review_prompt'])" in code
        assert "ctx.vars['result'] = ctx.get_last_result()" in code

    def test_run_agent_no_input_generates_correct_code(self) -> None:
        """Run agent fetcher (no with) generates ctx.run_agent('fetcher')."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="fetcher_instruction", body="Fetch data"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target=None,
                            agent="fetcher",
                            input=None,
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")
        assert "ctx.run_agent('fetcher')" in code

    def test_call_llm_with_input_generates_correct_code(self) -> None:
        """$result = call llm dedup with $findings generates correct Python."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="dedup_prompt", body="Deduplicate"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="dedup_prompt",
                            input=VarRef(name="findings"),
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")
        assert "ctx.call_llm('dedup_prompt', ctx.vars['findings'])" in code
        assert "ctx.vars['result'] = ctx.get_last_result()" in code

    def test_call_llm_no_input_generates_correct_code(self) -> None:
        """Call llm without with generates ctx.call_llm('prompt')."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="analyzer_prompt", body="Analyze this"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="analyzer_prompt",
                            input=None,
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")
        assert "ctx.call_llm('analyzer_prompt')" in code

    def test_call_llm_with_input_and_model(self) -> None:
        """Call llm with input and model generates correct code."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="dedup_prompt", body="Deduplicate"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="dedup_prompt",
                            input=VarRef(name="findings"),
                            model="fast_model",
                        ),
                    ],
                ),
            ],
        )
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")
        assert (
            "ctx.call_llm('dedup_prompt', ctx.vars['findings'], "
            "model='fast_model')"
        ) in code


class TestWithKeywordEndToEnd:
    """End-to-end tests for with keyword through full compilation pipeline."""

    @pytest.fixture
    def parser(self) -> ParserFactory:
        """Create parser instance."""
        return ParserFactory.create()

    def test_full_pipeline_with_keyword(self, parser: ParserFactory) -> None:
        """Full compilation pipeline with `with` keyword."""
        source = """
streetrace v1

schema Finding:
    message: string
    severity: string

model fast = anthropic/claude-sonnet

prompt reviewer_instruction: '''You are a code reviewer.'''

prompt review_prompt expecting Finding: '''Review: $input_prompt'''

agent reviewer:
    tools github
    instruction reviewer_instruction

tool github = mcp "https://github.com"

flow main:
    $result = run agent reviewer with $input_prompt
    return $result
"""
        tree = parser.parse(source)
        ast = transform(tree)
        assert isinstance(ast, DslFile)

        # Verify AST
        flows = [s for s in ast.statements if isinstance(s, FlowDef)]
        assert len(flows) == 1
        run_stmt = flows[0].body[0]
        assert isinstance(run_stmt, RunStmt)
        assert isinstance(run_stmt.input, VarRef)
        assert run_stmt.input.name == "input_prompt"

        # Generate code
        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")
        assert "ctx.run_agent('reviewer', ctx.vars['input_prompt'])" in code
