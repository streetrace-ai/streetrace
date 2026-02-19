"""Tests for escalation code generation.

Test coverage for code generation of prompt escalation conditions and
run statement escalation handlers.
"""


from streetrace.dsl.ast.nodes import (
    AgentDef,
    DslFile,
    EscalationCondition,
    EscalationHandler,
    FlowDef,
    LoopBlock,
    PromptDef,
    ReturnStmt,
    RunStmt,
    ToolDef,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator


class TestPromptEscalationCodegen:
    """Test code generation for prompts with escalation conditions."""

    def test_generates_prompt_with_normalized_escalation(self) -> None:
        """Generate code for prompt with ~ escalation condition."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="pi_enhancer",
                    body="You are a prompt improvement assistant.",
                    escalation_condition=EscalationCondition(op="~", value="DRIFTING"),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should include PromptSpec with escalation
        assert "_prompts = {" in code
        assert "'pi_enhancer'" in code
        assert "EscalationSpec" in code
        assert "op='~'" in code
        assert "value='DRIFTING'" in code

    def test_generates_prompt_with_exact_match_escalation(self) -> None:
        """Generate code for prompt with == escalation condition."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="classifier",
                    body="Classify the input.",
                    escalation_condition=EscalationCondition(
                        op="==",
                        value="NEEDS_HUMAN",
                    ),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "EscalationSpec" in code
        assert "op='=='" in code
        assert "value='NEEDS_HUMAN'" in code

    def test_generates_prompt_with_contains_escalation(self) -> None:
        """Generate code for prompt with contains escalation condition."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="detector",
                    body="Detect errors.",
                    escalation_condition=EscalationCondition(
                        op="contains",
                        value="ERROR",
                    ),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "EscalationSpec" in code
        assert "op='contains'" in code
        assert "value='ERROR'" in code

    def test_generates_prompt_without_escalation(self) -> None:
        """Generate code for prompt without escalation (backward compat)."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="simple_prompt",
                    body="You are a helpful assistant.",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should still work without escalation
        assert "_prompts = {" in code
        assert "'simple_prompt'" in code
        # Should have lambda body without EscalationSpec
        compile(code, "<generated>", "exec")

    def test_generates_prompt_with_model_and_escalation(self) -> None:
        """Generate code for prompt with model modifier and escalation."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="analyzer",
                    body="Analyze the data.",
                    model="compact",
                    escalation_condition=EscalationCondition(op="~", value="ESCALATE"),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should include escalation
        assert "EscalationSpec" in code
        assert "op='~'" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")


class TestRunStatementEscalationCodegen:
    """Test code generation for run statements with escalation handlers."""

    def test_generates_run_with_return_escalation(self) -> None:
        """Generate code for run statement with on escalate return handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="peer1",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="resolver",
                    params=[],
                    body=[
                        RunStmt(
                            target="current",
                            agent="peer1",
                            input=VarRef(name="input"),
                            escalation_handler=EscalationHandler(
                                action="return",
                                value=VarRef(name="current"),
                            ),
                        ),
                        ReturnStmt(value=VarRef(name="current")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate escalation check
        assert "run_agent_with_escalation" in code
        assert "if _escalated:" in code
        assert "ctx.vars['_return_value']" in code
        assert "return" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_run_with_continue_escalation(self) -> None:
        """Generate code for run statement with on escalate continue handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="validator_prompt", body="Validate data"),
                AgentDef(
                    name="validator",
                    tools=["fs"],
                    instruction="validator_prompt",
                ),
                FlowDef(
                    name="processor",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=3,
                            body=[
                                RunStmt(
                                    target="result",
                                    agent="validator",
                                    input=VarRef(name="item"),
                                    escalation_handler=EscalationHandler(
                                        action="continue",
                                    ),
                                ),
                            ],
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate continue in escalation handler
        assert "run_agent_with_escalation" in code
        assert "if _escalated:" in code
        assert "continue" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_run_with_abort_escalation(self) -> None:
        """Generate code for run statement with on escalate abort handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="processor_prompt", body="Process data"),
                AgentDef(
                    name="processor",
                    tools=["fs"],
                    instruction="processor_prompt",
                ),
                FlowDef(
                    name="critical_flow",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="processor",
                            input=VarRef(name="input"),
                            escalation_handler=EscalationHandler(
                                action="abort",
                            ),
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate AbortError raise in escalation handler
        assert "run_agent_with_escalation" in code
        assert "if _escalated:" in code
        assert "AbortError" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_run_without_escalation_unchanged(self) -> None:
        """Generate code for run statement without escalation (backward compat)."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="simple_flow",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="helper",
                            input=VarRef(name="input"),
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should use regular run_agent without escalation check
        assert "ctx.run_agent(" in code
        # Should NOT have escalation code
        assert "run_agent_with_escalation" not in code
        assert "_escalated" not in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_run_without_target_with_escalation(self) -> None:
        """Generate code for run without assignment but with escalation handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="checker_prompt", body="Check data"),
                AgentDef(
                    name="checker",
                    tools=["fs"],
                    instruction="checker_prompt",
                ),
                FlowDef(
                    name="validator_flow",
                    params=[],
                    body=[
                        RunStmt(
                            target=None,
                            agent="checker",
                            input=VarRef(name="data"),
                            escalation_handler=EscalationHandler(
                                action="abort",
                            ),
                        ),
                        ReturnStmt(value=VarRef(name="data")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should still handle escalation even without assignment
        assert "run_agent_with_escalation" in code
        assert "if _escalated:" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")


class TestEscalationCodegenImports:
    """Test that generated code includes necessary imports."""

    def test_generates_escalation_spec_import(self) -> None:
        """Generated code should import EscalationSpec."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="test_prompt",
                    body="Test prompt",
                    escalation_condition=EscalationCondition(op="~", value="TEST"),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should import EscalationSpec from runtime
        assert "EscalationSpec" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")


class TestCompleteEscalationCodegen:
    """Test complete examples combining prompts and runs with escalation."""

    def test_generates_complete_resolver_example(self) -> None:
        """Generate code for the complete resolver example from design doc."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(
                    name="pi_enhancer",
                    body="You are a prompt improvement assistant.",
                    model="main",
                    escalation_condition=EscalationCondition(op="~", value="DRIFTING"),
                ),
                AgentDef(
                    name="peer1",
                    tools=["fs"],
                    instruction="pi_enhancer",
                ),
                AgentDef(
                    name="peer2",
                    tools=["fs"],
                    instruction="pi_enhancer",
                ),
                FlowDef(
                    name="default",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=3,
                            body=[
                                RunStmt(
                                    target="current",
                                    agent="peer1",
                                    input=VarRef(name="current"),
                                    escalation_handler=EscalationHandler(
                                        action="return",
                                        value=VarRef(name="current"),
                                    ),
                                ),
                                RunStmt(
                                    target="current",
                                    agent="peer2",
                                    input=VarRef(name="current"),
                                    escalation_handler=EscalationHandler(
                                        action="return",
                                        value=VarRef(name="current"),
                                    ),
                                ),
                            ],
                        ),
                        ReturnStmt(value=VarRef(name="current")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify prompt has escalation spec
        assert "EscalationSpec" in code
        assert "op='~'" in code
        assert "value='DRIFTING'" in code

        # Verify run statements have escalation handlers
        assert "run_agent_with_escalation" in code
        assert "if _escalated:" in code

        # Verify code is valid Python
        compile(code, "<generated>", "exec")

    def test_generates_valid_python_for_all_escalation_patterns(self) -> None:
        """All generated escalation code should be valid Python."""
        test_cases = [
            # Prompt with different escalation operators
            PromptDef(
                name="p1",
                body="Test",
                escalation_condition=EscalationCondition(op="~", value="X"),
            ),
            PromptDef(
                name="p2",
                body="Test",
                escalation_condition=EscalationCondition(op="==", value="Y"),
            ),
            PromptDef(
                name="p3",
                body="Test",
                escalation_condition=EscalationCondition(op="!=", value="Z"),
            ),
            PromptDef(
                name="p4",
                body="Test",
                escalation_condition=EscalationCondition(op="contains", value="W"),
            ),
        ]

        for prompt in test_cases:
            ast = DslFile(
                version=VersionDecl(version="v1"),
                statements=[prompt],
            )

            generator = CodeGenerator()
            code, _mappings = generator.generate(ast, "test.sr")

            # Each should compile successfully
            compile(code, "<generated>", "exec")
