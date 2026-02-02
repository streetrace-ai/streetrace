"""Tests for parallel block code generation.

Test that parallel do blocks correctly validate statements and generate
code for true parallel execution using asyncio.gather.
"""

import pytest

from streetrace.dsl.ast import (
    AgentDef,
    CallStmt,
    DslFile,
    FlowDef,
    Literal,
    ParallelBlock,
    PromptDef,
    RunStmt,
    ToolDef,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator


class TestParallelBlockValidation:
    """Test parallel block statement validation."""

    def test_parallel_block_rejects_call_stmt(self) -> None:
        """Parallel block should reject call llm statements."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="task_prompt", body="Do task"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                CallStmt(
                                    target="result",
                                    prompt="task_prompt",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()

        with pytest.raises(TypeError, match="parallel do only supports"):
            generator.generate(ast, "test.sr")

    def test_parallel_block_rejects_mixed_statements(self) -> None:
        """Parallel block should reject mixed RunStmt and other statements."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(target="a", agent="task_a"),
                                CallStmt(
                                    target="result",
                                    prompt="task_prompt",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()

        with pytest.raises(TypeError, match="parallel do only supports"):
            generator.generate(ast, "test.sr")

    def test_parallel_block_accepts_only_run_agent(self) -> None:
        """Parallel block should accept only run agent statements."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                AgentDef(
                    name="task_b",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(target="a", agent="task_a"),
                                RunStmt(target="b", agent="task_b"),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        # Should not raise - only RunStmt is allowed
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code compiles
        compile(code, "<generated>", "exec")


class TestParallelBlockCodeGeneration:
    """Test parallel block code generation."""

    def test_parallel_block_generates_parallel_specs(self) -> None:
        """Parallel block should generate parallel agent specs."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                AgentDef(
                    name="task_b",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(target="a", agent="task_a"),
                                RunStmt(target="b", agent="task_b"),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate _parallel_specs list
        assert "_parallel_specs" in code
        # Should call _execute_parallel_agents
        assert "_execute_parallel_agents" in code
        # Should include agent names
        assert "'task_a'" in code
        assert "'task_b'" in code

    def test_parallel_block_assigns_results(self) -> None:
        """Parallel block should assign results to target variables.

        Results are stored directly in ctx.vars by _execute_parallel_agents,
        so target variables are specified in _parallel_specs.
        """
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                AgentDef(
                    name="task_b",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(target="result_a", agent="task_a"),
                                RunStmt(target="result_b", agent="task_b"),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Target variables are specified in _parallel_specs
        # Results are stored directly in ctx.vars by _execute_parallel_agents
        assert "'result_a'" in code
        assert "'result_b'" in code
        assert "_parallel_specs" in code
        # Should use async for loop to yield events
        assert "async for _event in self._execute_parallel_agents" in code

    def test_parallel_block_with_args(self) -> None:
        """Parallel block should handle run agent statements with arguments."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(
                                    target="a",
                                    agent="task_a",
                                    input=VarRef(name="input"),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should include args in the spec
        assert "ctx.vars['input']" in code

    def test_parallel_block_without_target(self) -> None:
        """Parallel block should handle run agent without assignment target."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(target=None, agent="task_a"),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should still generate parallel execution, just with None as target
        assert "_parallel_specs" in code
        assert "_execute_parallel_agents" in code
        # Should use None for target
        assert "None" in code

    def test_parallel_block_empty_body(self) -> None:
        """Parallel block with empty body should generate pass."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(body=[]),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should compile without errors
        compile(code, "<generated>", "exec")

    def test_parallel_block_generates_valid_python(self) -> None:
        """Parallel block should generate valid Python syntax."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="task_prompt", body="Do task"),
                AgentDef(
                    name="task_a",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                AgentDef(
                    name="task_b",
                    tools=["fs"],
                    instruction="task_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ParallelBlock(
                            body=[
                                RunStmt(
                                    target="a",
                                    agent="task_a",
                                    input=VarRef(name="input"),
                                ),
                                RunStmt(
                                    target="b",
                                    agent="task_b",
                                    input=Literal(value="test", literal_type="string"),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code can be compiled
        compile(code, "<generated>", "exec")
