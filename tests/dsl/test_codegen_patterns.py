"""Tests for code generation of agentic patterns.

Test code generation for delegate, use, and loop patterns to ensure
correct Python code is produced that integrates with Google ADK.
"""

from streetrace.dsl.ast import (
    AgentDef,
    Assignment,
    ContinueStmt,
    DslFile,
    FlowDef,
    IfBlock,
    Literal,
    LoopBlock,
    PromptDef,
    ReturnStmt,
    RunStmt,
    SourcePosition,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator

# =============================================================================
# Delegate Code Generation Tests
# =============================================================================


class TestDelegateCodeGeneration:
    """Test code generation for delegate (sub_agents) pattern."""

    def test_delegate_generates_sub_agents_key(self) -> None:
        """Agent with delegate generates _agents dict with sub_agents key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="worker_prompt", body="Do work"),
                PromptDef(name="coord_prompt", body="Coordinate work"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="worker_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["worker"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test_delegate.sr")

        assert "_agents = {" in code
        assert "'coordinator'" in code
        assert "'sub_agents': ['worker']" in code

    def test_delegate_multiple_agents_generates_sub_agents_list(self) -> None:
        """Agent with multiple delegates generates sub_agents list."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="w1_prompt", body="Worker 1"),
                PromptDef(name="w2_prompt", body="Worker 2"),
                PromptDef(name="coord_prompt", body="Coordinate"),
                AgentDef(
                    name="worker1",
                    tools=[],
                    instruction="w1_prompt",
                ),
                AgentDef(
                    name="worker2",
                    tools=[],
                    instruction="w2_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["worker1", "worker2"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'sub_agents': ['worker1', 'worker2']" in code

    def test_agent_without_delegate_has_no_sub_agents(self) -> None:
        """Agent without delegate does not have sub_agents key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="simple_prompt", body="Simple agent"),
                AgentDef(
                    name="simple",
                    tools=[],
                    instruction="simple_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'simple'" in code
        assert "'sub_agents'" not in code

    def test_delegate_with_empty_list_has_no_sub_agents(self) -> None:
        """Agent with empty delegate list does not have sub_agents key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_prompt", body="Agent"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    delegate=[],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'sub_agents'" not in code


# =============================================================================
# Use Code Generation Tests
# =============================================================================


class TestUseCodeGeneration:
    """Test code generation for use (agent_tools) pattern."""

    def test_use_generates_agent_tools_key(self) -> None:
        """Agent with use generates _agents dict with agent_tools key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="helper_prompt", body="Help"),
                PromptDef(name="main_prompt", body="Main agent"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["helper"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test_use.sr")

        assert "_agents = {" in code
        assert "'main_agent'" in code
        assert "'agent_tools': ['helper']" in code

    def test_use_multiple_agents_generates_agent_tools_list(self) -> None:
        """Agent with multiple use generates agent_tools list."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="h1_prompt", body="Helper 1"),
                PromptDef(name="h2_prompt", body="Helper 2"),
                PromptDef(name="main_prompt", body="Main"),
                AgentDef(
                    name="helper1",
                    tools=[],
                    instruction="h1_prompt",
                ),
                AgentDef(
                    name="helper2",
                    tools=[],
                    instruction="h2_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["helper1", "helper2"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'agent_tools': ['helper1', 'helper2']" in code

    def test_agent_without_use_has_no_agent_tools(self) -> None:
        """Agent without use does not have agent_tools key."""
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

        assert "'simple'" in code
        assert "'agent_tools'" not in code

    def test_use_with_empty_list_has_no_agent_tools(self) -> None:
        """Agent with empty use list does not have agent_tools key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_prompt", body="Agent"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    use=[],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'agent_tools'" not in code


# =============================================================================
# Combined Delegate and Use Code Generation Tests
# =============================================================================


class TestCombinedDelegateAndUseCodeGeneration:
    """Test code generation for agents with both delegate and use."""

    def test_agent_with_both_delegate_and_use(self) -> None:
        """Agent with both delegate and use generates both keys."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="sub_prompt", body="Sub agent"),
                PromptDef(name="helper_prompt", body="Helper"),
                PromptDef(name="main_prompt", body="Main"),
                AgentDef(
                    name="sub_agent",
                    tools=[],
                    instruction="sub_prompt",
                ),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="main_prompt",
                    delegate=["sub_agent"],
                    use=["helper"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'sub_agents': ['sub_agent']" in code
        assert "'agent_tools': ['helper']" in code


# =============================================================================
# Loop Block Code Generation Tests
# =============================================================================


class TestLoopBlockCodeGeneration:
    """Test code generation for loop blocks."""

    def test_loop_max_generates_while_with_counter(self) -> None:
        """Loop with max iterations generates while loop with counter."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="refine",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=5,
                            body=[
                                Assignment(
                                    target="$counter",
                                    value=Literal(value=1, literal_type="int"),
                                ),
                            ],
                            meta=SourcePosition(line=3, column=4),
                        ),
                        ReturnStmt(value=VarRef(name="counter")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "_loop_count = 0" in code
        assert "_max_iterations = 5" in code
        assert "while _loop_count < _max_iterations:" in code
        assert "_loop_count += 1" in code

    def test_unbounded_loop_generates_while_true(self) -> None:
        """Loop without max iterations generates while True loop."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="infinite",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=None,
                            body=[
                                ReturnStmt(
                                    value=Literal(value="done", literal_type="string"),
                                ),
                            ],
                            meta=SourcePosition(line=3, column=4),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "while True:" in code
        # Should not have counter variables
        assert "_max_iterations" not in code

    def test_loop_with_multiple_statements(self) -> None:
        """Loop with multiple statements generates all statements in body."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="process",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=3,
                            body=[
                                Assignment(
                                    target="$x",
                                    value=Literal(value=1, literal_type="int"),
                                ),
                                Assignment(
                                    target="$y",
                                    value=Literal(value=2, literal_type="int"),
                                ),
                            ],
                        ),
                        ReturnStmt(value=VarRef(name="x")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['x'] = 1" in code
        assert "ctx.vars['y'] = 2" in code

    def test_loop_with_if_block(self) -> None:
        """Loop with if block generates proper nested structure."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="conditional_loop",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=5,
                            body=[
                                IfBlock(
                                    condition=VarRef(name="done"),
                                    body=[
                                        ReturnStmt(
                                            value=Literal(
                                                value="complete",
                                                literal_type="string",
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ReturnStmt(
                            value=Literal(value="timeout", literal_type="string"),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "while _loop_count < _max_iterations:" in code
        assert "if ctx.vars['done']:" in code
        assert 'return "complete"' in code

    def test_loop_with_continue_statement(self) -> None:
        """Loop with continue statement generates continue keyword."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="continue_loop",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=10,
                            body=[
                                IfBlock(
                                    condition=VarRef(name="skip"),
                                    body=[ContinueStmt()],
                                ),
                            ],
                        ),
                        ReturnStmt(value=Literal(value="done", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "continue" in code


# =============================================================================
# Generated Code Compilation Tests
# =============================================================================


class TestGeneratedCodeCompilation:
    """Test that generated Python code compiles successfully."""

    def test_delegate_code_compiles(self) -> None:
        """Generated code with delegate compiles successfully."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="worker_prompt", body="Work"),
                PromptDef(name="coord_prompt", body="Coordinate"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="worker_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["worker"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # This should not raise a SyntaxError
        compile(code, "<generated>", "exec")

    def test_use_code_compiles(self) -> None:
        """Generated code with use compiles successfully."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="helper_prompt", body="Help"),
                PromptDef(name="main_prompt", body="Main"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["helper"],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_loop_max_code_compiles(self) -> None:
        """Generated code with loop max compiles successfully."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="iterate",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=5,
                            body=[
                                Assignment(
                                    target="$x",
                                    value=Literal(value=1, literal_type="int"),
                                ),
                            ],
                        ),
                        ReturnStmt(value=VarRef(name="x")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_unbounded_loop_code_compiles(self) -> None:
        """Generated code with unbounded loop compiles successfully."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="infinite",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=None,
                            body=[
                                ReturnStmt(
                                    value=Literal(value="done", literal_type="string"),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_combined_patterns_code_compiles(self) -> None:
        """Generated code with multiple patterns compiles successfully."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="sub_prompt", body="Sub"),
                PromptDef(name="helper_prompt", body="Helper"),
                PromptDef(name="coord_prompt", body="Coordinator"),
                AgentDef(
                    name="sub_agent",
                    tools=[],
                    instruction="sub_prompt",
                ),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["sub_agent"],
                    use=["helper"],
                ),
                FlowDef(
                    name="main_flow",
                    params=[],
                    body=[
                        LoopBlock(
                            max_iterations=3,
                            body=[
                                RunStmt(
                                    target="$result",
                                    agent="coordinator",
                                    args=[VarRef(name="input")],
                                ),
                                IfBlock(
                                    condition=VarRef(name="done"),
                                    body=[
                                        ReturnStmt(value=VarRef(name="result")),
                                    ],
                                ),
                            ],
                        ),
                        ReturnStmt(
                            value=Literal(value="timeout", literal_type="string"),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")


# =============================================================================
# Loop Block in Event Handler Tests
# =============================================================================


# =============================================================================
# Agent Description Code Generation Tests
# =============================================================================


class TestAgentDescriptionCodeGeneration:
    """Test code generation for agent description field."""

    def test_agent_with_description_generates_description_key(self) -> None:
        """Agent with description generates _agents dict with description key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                    description="A helpful assistant agent",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test_description.sr")

        assert "_agents = {" in code
        assert "'helper'" in code
        assert "'description': 'A helpful assistant agent'" in code

    def test_agent_without_description_has_no_description_key(self) -> None:
        """Agent without description does not have description key."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="simple_prompt", body="Simple agent"),
                AgentDef(
                    name="simple",
                    tools=[],
                    instruction="simple_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'simple'" in code
        assert "'description'" not in code

    def test_agent_with_description_and_delegate(self) -> None:
        """Agent with both description and delegate generates both keys."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="worker_prompt", body="Worker"),
                PromptDef(name="coord_prompt", body="Coordinate"),
                AgentDef(
                    name="worker",
                    tools=[],
                    instruction="worker_prompt",
                ),
                AgentDef(
                    name="coordinator",
                    tools=[],
                    instruction="coord_prompt",
                    delegate=["worker"],
                    description="Coordinates worker agents",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'sub_agents': ['worker']" in code
        assert "'description': 'Coordinates worker agents'" in code

    def test_agent_with_description_and_use(self) -> None:
        """Agent with both description and use generates both keys."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="helper_prompt", body="Help"),
                PromptDef(name="main_prompt", body="Main"),
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="helper_prompt",
                ),
                AgentDef(
                    name="main_agent",
                    tools=[],
                    instruction="main_prompt",
                    use=["helper"],
                    description="Main orchestrator agent",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'agent_tools': ['helper']" in code
        assert "'description': 'Main orchestrator agent'" in code

    def test_agent_description_with_quotes_escaped(self) -> None:
        """Agent description with quotes is properly escaped."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_prompt", body="Do task"),
                AgentDef(
                    name="quoter",
                    tools=[],
                    instruction="agent_prompt",
                    description='An agent that handles "special" cases',
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'quoter'" in code
        # repr() handles escaping properly
        assert "'description':" in code
        # Verify it compiles
        compile(code, "<generated>", "exec")

    def test_agent_description_code_compiles(self) -> None:
        """Generated code with agent description compiles successfully."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="agent_prompt", body="Task"),
                AgentDef(
                    name="my_agent",
                    tools=[],
                    instruction="agent_prompt",
                    description="A descriptive agent for testing",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")


class TestLoopBlockInEventHandler:
    """Test code generation for loop blocks in event handlers."""

    def test_loop_in_handler_generates_correct_code(self) -> None:
        """Loop block in event handler generates correct Python code."""
        from streetrace.dsl.ast import EventHandler

        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                EventHandler(
                    timing="on",
                    event_type="output",
                    body=[
                        LoopBlock(
                            max_iterations=3,
                            body=[
                                Assignment(
                                    target="$check",
                                    value=Literal(value=True, literal_type="bool"),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def on_output" in code
        assert "_loop_count = 0" in code
        assert "_max_iterations = 3" in code
        assert "while _loop_count < _max_iterations:" in code
        compile(code, "<generated>", "exec")
