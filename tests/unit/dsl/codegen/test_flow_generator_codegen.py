"""Tests for flow code generation with async generator pattern.

Test that generated flow methods produce async generator code that yields
events from run_agent and call_llm operations.
"""

from streetrace.dsl.ast import (
    AgentDef,
    Assignment,
    CallStmt,
    DslFile,
    FlowDef,
    Literal,
    ParallelBlock,
    PromptDef,
    ReturnStmt,
    RunStmt,
    SourcePosition,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator


class TestFlowMethodSignature:
    """Test flow method generates async generator signature."""

    def test_flow_method_has_async_generator_return_type(self) -> None:
        """Flow method signature returns AsyncGenerator[Event | FlowEvent, None]."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value="done", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_main(" in code
        assert "AsyncGenerator[Event | FlowEvent, None]" in code

    def test_flow_method_signature_multiline_format(self) -> None:
        """Flow method signature spans multiple lines for readability."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="process",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value=42, literal_type="int")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Check multiline signature format
        assert "async def flow_process(" in code
        assert "self, ctx: WorkflowContext" in code
        assert ") -> AsyncGenerator[Event | FlowEvent, None]:" in code


class TestRunAgentCodeGeneration:
    """Test run_agent statement generates async for pattern."""

    def test_run_agent_generates_async_for_loop(self) -> None:
        """Run agent generates async for loop to yield events."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="helper_prompt", body="Help"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="$result",
                            agent="helper",
                            args=[VarRef(name="input_prompt")],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async for _event in ctx.run_agent('helper'" in code
        assert "yield _event" in code

    def test_run_agent_with_target_assigns_from_get_last_result(self) -> None:
        """Run agent with target uses ctx.get_last_result() for assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_agent",
                    tools=[],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="$result",
                            agent="task_agent",
                            args=[],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['result'] = ctx.get_last_result()" in code

    def test_run_agent_without_target_no_assignment(self) -> None:
        """Run agent without target does not generate assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="fire_prompt", body="Fire and forget"),
                AgentDef(
                    name="fire_forget",
                    tools=[],
                    instruction="fire_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target=None,
                            agent="fire_forget",
                            args=[],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async for _event in ctx.run_agent('fire_forget'):" in code
        assert "yield _event" in code
        # No get_last_result assignment since no target
        assert "ctx.get_last_result()" not in code

    def test_run_agent_with_args(self) -> None:
        """Run agent with arguments passes them correctly."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="analyze_prompt", body="Analyze"),
                AgentDef(
                    name="analyzer",
                    tools=[],
                    instruction="analyze_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="$analysis",
                            agent="analyzer",
                            args=[
                                VarRef(name="data"),
                                Literal(value="deep", literal_type="string"),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        expected = (
            "async for _event in ctx.run_agent('analyzer', "
            "ctx.vars['data'], \"deep\"):"
        )
        assert expected in code


class TestCallLlmCodeGeneration:
    """Test call_llm statement generates async for pattern."""

    def test_call_llm_generates_async_for_loop(self) -> None:
        """Call LLM generates async for loop to yield events."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="summarize", body="Summarize this"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="$summary",
                            prompt="summarize",
                            args=[VarRef(name="text")],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async for _event in ctx.call_llm('summarize'" in code
        assert "yield _event" in code

    def test_call_llm_with_target_assigns_from_get_last_result(self) -> None:
        """Call LLM with target uses ctx.get_last_result() for assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="generate", body="Generate output"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="$output",
                            prompt="generate",
                            args=[],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['output'] = ctx.get_last_result()" in code

    def test_call_llm_without_target_no_assignment(self) -> None:
        """Call LLM without target does not generate assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="log_prompt", body="Log this"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target=None,
                            prompt="log_prompt",
                            args=[],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async for _event in ctx.call_llm('log_prompt'):" in code
        assert "yield _event" in code
        # No get_last_result assignment since no target
        assert "ctx.get_last_result()" not in code

    def test_call_llm_with_model_specified(self) -> None:
        """Call LLM with model parameter passes it correctly."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="fast_prompt", body="Quick response"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="$response",
                            prompt="fast_prompt",
                            args=[],
                            model="fast_model",
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "model='fast_model'" in code

    def test_call_llm_with_args_and_model(self) -> None:
        """Call LLM with both args and model passes all correctly."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="analyze_prompt", body="Analyze $input"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="$result",
                            prompt="analyze_prompt",
                            args=[VarRef(name="data")],
                            model="analysis_model",
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        expected = (
            "ctx.call_llm('analyze_prompt', ctx.vars['data'], "
            "model='analysis_model')"
        )
        assert expected in code


class TestParallelBlockCodeGeneration:
    """Test parallel block generates sequential with comment."""

    def test_parallel_block_falls_back_to_sequential(self) -> None:
        """Parallel block generates sequential execution with comment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=[],
                    instruction="task_prompt",
                ),
                AgentDef(
                    name="task_b",
                    tools=[],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(target="$a", agent="task_a", args=[]),
                                RunStmt(target="$b", agent="task_b", args=[]),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should have a comment explaining sequential fallback
        assert "# Sequential execution" in code or "parallel" in code.lower()
        # Should still execute both agents
        assert "run_agent('task_a')" in code
        assert "run_agent('task_b')" in code


class TestImportsInGeneratedCode:
    """Test generated code includes necessary imports."""

    def test_generated_code_imports_async_generator(self) -> None:
        """Generated code imports AsyncGenerator."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value="done", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "from collections.abc import AsyncGenerator" in code

    def test_generated_code_imports_event(self) -> None:
        """Generated code imports Event from google.adk.events."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value="done", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "from google.adk.events import Event" in code

    def test_generated_code_imports_flow_event(self) -> None:
        """Generated code imports FlowEvent from dsl.runtime.events."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value="done", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "from streetrace.dsl.runtime.events import FlowEvent" in code


class TestGeneratedCodeCompilation:
    """Test generated flow code compiles successfully."""

    def test_simple_flow_compiles(self) -> None:
        """Simple flow with return generates valid Python."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value="done", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should compile without syntax errors
        compile(code, "<generated>", "exec")

    def test_flow_with_run_agent_compiles(self) -> None:
        """Flow with run_agent statement generates valid Python."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="helper_prompt", body="Help"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="$result",
                            agent="helper",
                            args=[VarRef(name="input_prompt")],
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                    meta=SourcePosition(line=5, column=0),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_flow_with_call_llm_compiles(self) -> None:
        """Flow with call_llm statement generates valid Python."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="analyze", body="Analyze this"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="$analysis",
                            prompt="analyze",
                            args=[VarRef(name="input_prompt")],
                        ),
                        ReturnStmt(value=VarRef(name="analysis")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_flow_with_multiple_operations_compiles(self) -> None:
        """Flow with multiple run_agent and call_llm compiles."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="extract_prompt", body="Extract data"),
                PromptDef(name="analyze_prompt", body="Analyze $data"),
                AgentDef(
                    name="extractor",
                    tools=[],
                    instruction="extract_prompt",
                ),
                FlowDef(
                    name="pipeline",
                    params=[],
                    body=[
                        RunStmt(
                            target="$data",
                            agent="extractor",
                            args=[VarRef(name="input_prompt")],
                        ),
                        CallStmt(
                            target="$analysis",
                            prompt="analyze_prompt",
                            args=[VarRef(name="data")],
                        ),
                        ReturnStmt(value=VarRef(name="analysis")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_flow_with_assignments_and_operations_compiles(self) -> None:
        """Flow with variable assignments and operations compiles."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="process_prompt", body="Process"),
                AgentDef(
                    name="processor",
                    tools=[],
                    instruction="process_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        Assignment(
                            target="$count",
                            value=Literal(value=0, literal_type="int"),
                        ),
                        RunStmt(
                            target="$result",
                            agent="processor",
                            args=[],
                        ),
                        Assignment(
                            target="$count",
                            value=Literal(value=1, literal_type="int"),
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")


class TestSourceMappingsPreserved:
    """Test source mappings are preserved with new code generation."""

    def test_run_agent_preserves_source_mapping(self) -> None:
        """Run agent statement preserves source line mapping."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_prompt", body="Do work"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="agent_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="$result",
                            agent="worker",
                            args=[],
                            meta=SourcePosition(line=10, column=4),
                        ),
                    ],
                    meta=SourcePosition(line=8, column=0),
                ),
            ],
        )

        generator = CodeGenerator()
        code, mappings = generator.generate(ast, "test.sr")

        # Should have source mappings
        assert len(mappings) > 0
        # Should have mapping for line 10
        source_lines = {m.source_line for m in mappings}
        assert 10 in source_lines

    def test_call_llm_preserves_source_mapping(self) -> None:
        """Call LLM statement preserves source line mapping."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="call_prompt", body="Call LLM"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="$response",
                            prompt="call_prompt",
                            args=[],
                            meta=SourcePosition(line=15, column=4),
                        ),
                    ],
                    meta=SourcePosition(line=12, column=0),
                ),
            ],
        )

        generator = CodeGenerator()
        code, mappings = generator.generate(ast, "test.sr")

        source_lines = {m.source_line for m in mappings}
        assert 15 in source_lines
