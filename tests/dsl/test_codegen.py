"""Tests for code generation.

Test the code emitter and code generator that transform DSL AST
into Python source code.
"""

from streetrace.dsl.ast import (
    AgentDef,
    Assignment,
    BinaryOp,
    BlockAction,
    CallStmt,
    DslFile,
    EventHandler,
    FlowDef,
    ForLoop,
    Literal,
    MaskAction,
    MatchBlock,
    MatchCase,
    ModelDef,
    ParallelBlock,
    PromptDef,
    PropertyAccess,
    PushStmt,
    ReturnStmt,
    RunStmt,
    SourcePosition,
    ToolDef,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.emitter import CodeEmitter
from streetrace.dsl.codegen.generator import CodeGenerator

# =============================================================================
# CodeEmitter Tests
# =============================================================================


class TestCodeEmitterBasics:
    """Test basic CodeEmitter functionality."""

    def test_create_emitter(self) -> None:
        """Create a code emitter for a source file."""
        emitter = CodeEmitter("my_agent.sr")
        assert emitter.get_code() == ""

    def test_emit_single_line(self) -> None:
        """Emit a single line of code."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("x = 42")
        assert emitter.get_code() == "x = 42\n"

    def test_emit_multiple_lines(self) -> None:
        """Emit multiple lines of code."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("x = 1")
        emitter.emit("y = 2")
        emitter.emit("z = x + y")
        assert emitter.get_code() == "x = 1\ny = 2\nz = x + y\n"

    def test_emit_blank_line(self) -> None:
        """Emit a blank line."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("x = 1")
        emitter.emit_blank()
        emitter.emit("y = 2")
        assert emitter.get_code() == "x = 1\n\ny = 2\n"


class TestCodeEmitterIndentation:
    """Test CodeEmitter indentation handling."""

    def test_indent_increases_level(self) -> None:
        """Indenting increases the indentation level."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("def foo():")
        emitter.indent()
        emitter.emit("pass")
        assert "    pass\n" in emitter.get_code()

    def test_dedent_decreases_level(self) -> None:
        """Dedenting decreases the indentation level."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("def foo():")
        emitter.indent()
        emitter.emit("x = 1")
        emitter.dedent()
        emitter.emit("y = 2")

        code = emitter.get_code()
        assert "def foo():\n" in code
        assert "    x = 1\n" in code
        assert "y = 2\n" in code
        assert "    y = 2" not in code

    def test_nested_indentation(self) -> None:
        """Handle multiple levels of nested indentation."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("class Foo:")
        emitter.indent()
        emitter.emit("def bar(self):")
        emitter.indent()
        emitter.emit("if True:")
        emitter.indent()
        emitter.emit("return 42")
        emitter.dedent()
        emitter.dedent()
        emitter.dedent()

        code = emitter.get_code()
        assert "class Foo:\n" in code
        assert "    def bar(self):\n" in code
        assert "        if True:\n" in code
        assert "            return 42\n" in code

    def test_custom_indent_string(self) -> None:
        """Use custom indentation string."""
        emitter = CodeEmitter("test.sr", indent_str="  ")
        emitter.emit("def foo():")
        emitter.indent()
        emitter.emit("pass")
        assert "  pass\n" in emitter.get_code()

    def test_dedent_below_zero_is_safe(self) -> None:
        """Dedenting below zero indentation is safe."""
        emitter = CodeEmitter("test.sr")
        emitter.dedent()  # Should not raise
        emitter.emit("x = 1")
        assert emitter.get_code() == "x = 1\n"


class TestCodeEmitterComments:
    """Test CodeEmitter comment handling."""

    def test_emit_comment(self) -> None:
        """Emit a comment line."""
        emitter = CodeEmitter("test.sr")
        emitter.emit_comment("This is a comment")
        assert emitter.get_code() == "# This is a comment\n"

    def test_emit_comment_respects_indent(self) -> None:
        """Comments respect indentation level."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("def foo():")
        emitter.indent()
        emitter.emit_comment("Inside function")
        emitter.emit("pass")

        code = emitter.get_code()
        assert "    # Inside function\n" in code

    def test_emit_source_comment(self) -> None:
        """Emit a source location comment."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("x = 1", source_line=5)

        code = emitter.get_code()
        # Source comment should be on its own line before the code
        assert "# test.sr:5" in code


class TestCodeEmitterSourceMappings:
    """Test CodeEmitter source mapping generation."""

    def test_emit_with_source_line(self) -> None:
        """Emit code with source line tracking."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("x = 42", source_line=5)

        mappings = emitter.get_source_mappings()
        assert len(mappings) >= 1
        # Find the mapping for our emitted line
        mapping = next(
            (m for m in mappings if m.source_line == 5),
            None,
        )
        assert mapping is not None
        assert mapping.source_file == "test.sr"

    def test_multiple_source_mappings(self) -> None:
        """Track multiple source mappings."""
        emitter = CodeEmitter("test.sr")
        emitter.emit("x = 1", source_line=10)
        emitter.emit("y = 2", source_line=15)
        emitter.emit("z = 3", source_line=20)

        mappings = emitter.get_source_mappings()
        source_lines = {m.source_line for m in mappings}
        assert 10 in source_lines
        assert 15 in source_lines
        assert 20 in source_lines

    def test_get_line_count(self) -> None:
        """Get the current line count."""
        emitter = CodeEmitter("test.sr")
        assert emitter.get_line_count() == 0

        emitter.emit("line 1")
        assert emitter.get_line_count() == 1

        emitter.emit("line 2")
        assert emitter.get_line_count() == 2


# =============================================================================
# CodeGenerator Tests - Model Definitions
# =============================================================================


class TestCodeGeneratorModels:
    """Test code generation for model definitions."""

    def test_generate_single_model(self) -> None:
        """Generate code for a single model definition."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "_models = {" in code
        assert "'main': 'anthropic/claude-sonnet'" in code

    def test_generate_multiple_models(self) -> None:
        """Generate code for multiple model definitions."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                ModelDef(name="fast", provider_model="anthropic/claude-haiku"),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'main': 'anthropic/claude-sonnet'" in code
        assert "'fast': 'anthropic/claude-haiku'" in code


# =============================================================================
# CodeGenerator Tests - Prompt Definitions
# =============================================================================


class TestCodeGeneratorPrompts:
    """Test code generation for prompt definitions."""

    def test_generate_simple_prompt(self) -> None:
        """Generate code for a simple prompt definition."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="greeting", body="Hello, how can I help you?"),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "_prompts = {" in code
        assert "'greeting'" in code

    def test_generate_prompt_with_variable_interpolation(self) -> None:
        """Generate code for a prompt with variable interpolation."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="analyze",
                    body="Analyze: $input_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Variable interpolation should use ctx.resolve
        assert "ctx.resolve" in code


# =============================================================================
# CodeGenerator Tests - Event Handlers
# =============================================================================


class TestCodeGeneratorEventHandlers:
    """Test code generation for event handlers."""

    def test_generate_on_input_handler(self) -> None:
        """Generate code for on input handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                EventHandler(
                    timing="on",
                    event_type="input",
                    body=[
                        MaskAction(guardrail="pii"),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def on_input" in code
        assert "ctx" in code

    def test_generate_on_output_handler(self) -> None:
        """Generate code for on output handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                EventHandler(
                    timing="on",
                    event_type="output",
                    body=[
                        MaskAction(guardrail="pii"),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def on_output" in code

    def test_generate_on_start_handler(self) -> None:
        """Generate code for on start handler."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                EventHandler(
                    timing="on",
                    event_type="start",
                    body=[
                        Assignment(
                            target="config",
                            value=Literal(value="production", literal_type="string"),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def on_start" in code

    def test_generate_mask_action(self) -> None:
        """Generate code for mask guardrail action."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                EventHandler(
                    timing="on",
                    event_type="input",
                    body=[
                        MaskAction(guardrail="pii"),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "guardrails.mask" in code
        assert "'pii'" in code

    def test_generate_block_action(self) -> None:
        """Generate code for block guardrail action."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                EventHandler(
                    timing="on",
                    event_type="input",
                    body=[
                        BlockAction(condition=VarRef(name="jailbreak")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "BlockedInputError" in code or "guardrails.check" in code


# =============================================================================
# CodeGenerator Tests - Flow Definitions
# =============================================================================


class TestCodeGeneratorFlows:
    """Test code generation for flow definitions."""

    def test_generate_simple_flow(self) -> None:
        """Generate code for a simple flow definition."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main_flow",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value=42, literal_type="int")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_main_flow" in code
        assert "return" in code

    def test_generate_flow_with_params(self) -> None:
        """Generate code for a flow with parameters."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="process",
                    params=["$input", "$config"],
                    body=[
                        ReturnStmt(value=VarRef(name="input")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "async def flow_process" in code

    def test_generate_run_agent_statement(self) -> None:
        """Generate code for run agent statement."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with files"),
                AgentDef(
                    name="file_helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="file_helper",
                            input=VarRef(name="input_prompt"),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "run_agent" in code
        assert "'file_helper'" in code

    def test_generate_call_llm_statement(self) -> None:
        """Generate code for call LLM statement."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="analyze_prompt", body="Analyze this"),
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="analyze_prompt",
                            input=VarRef(name="input_prompt"),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "call_llm" in code
        assert "'analyze_prompt'" in code

    def test_generate_variable_assignment(self) -> None:
        """Generate code for variable assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        Assignment(
                            target="x",
                            value=Literal(value=42, literal_type="int"),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['x']" in code
        assert "= 42" in code

    def test_generate_variable_read(self) -> None:
        """Generate code for reading a variable."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        Assignment(
                            target="x",
                            value=Literal(value=42, literal_type="int"),
                        ),
                        ReturnStmt(value=VarRef(name="x")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['x']" in code


# =============================================================================
# CodeGenerator Tests - Control Flow
# =============================================================================


class TestCodeGeneratorControlFlow:
    """Test code generation for control flow statements."""

    def test_generate_for_loop(self) -> None:
        """Generate code for for loop."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ForLoop(
                            variable="item",
                            iterable=VarRef(name="items"),
                            body=[
                                Assignment(
                                    target="result",
                                    value=VarRef(name="item"),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "for " in code
        assert "ctx.vars['items']" in code

    def test_generate_parallel_block(self) -> None:
        """Generate code for parallel block."""
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

        # Parallel block generates true parallel execution using asyncio.gather
        assert "_parallel_specs" in code
        assert "_execute_parallel_agents" in code
        assert "'task_a'" in code
        assert "'task_b'" in code

    def test_generate_match_block(self) -> None:
        """Generate code for match block."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        MatchBlock(
                            expression=VarRef(name="status"),
                            cases=[
                                MatchCase(
                                    pattern="success",
                                    body=ReturnStmt(
                                        value=Literal(value=1, literal_type="int"),
                                    ),
                                ),
                                MatchCase(
                                    pattern="error",
                                    body=ReturnStmt(
                                        value=Literal(value=0, literal_type="int"),
                                    ),
                                ),
                            ],
                            else_body=ReturnStmt(
                                value=Literal(value=-1, literal_type="int"),
                            ),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "match " in code
        assert "case 'success'" in code
        assert "case 'error'" in code
        assert "case _:" in code


# =============================================================================
# CodeGenerator Tests - Expressions
# =============================================================================


class TestCodeGeneratorExpressions:
    """Test code generation for expressions."""

    def test_generate_literal_int(self) -> None:
        """Generate code for integer literal."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value=42, literal_type="int")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Return stores value in context since flow is async generator
        assert "ctx.vars['_return_value'] = 42" in code
        assert "return" in code

    def test_generate_literal_string(self) -> None:
        """Generate code for string literal."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(value=Literal(value="hello", literal_type="string")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Return stores value in context since flow is async generator
        assert 'ctx.vars[\'_return_value\'] = "hello"' in code
        assert "return" in code

    def test_generate_binary_operation(self) -> None:
        """Generate code for binary operation."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(
                            value=BinaryOp(
                                op=">",
                                left=VarRef(name="x"),
                                right=Literal(value=10, literal_type="int"),
                            ),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "ctx.vars['x'] > 10" in code

    def test_generate_property_access(self) -> None:
        """Generate code for property access."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        ReturnStmt(
                            value=PropertyAccess(
                                base=VarRef(name="invoice"),
                                properties=["amount"],
                            ),
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Property access should be generated as dict access or attribute access
        assert "['amount']" in code or ".amount" in code

    def test_generate_push_statement(self) -> None:
        """Generate code for push statement."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        Assignment(
                            target="results",
                            value=Literal(value=[], literal_type="list"),
                        ),
                        PushStmt(
                            value=Literal(value=42, literal_type="int"),
                            target="results",
                        ),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert ".append(" in code


# =============================================================================
# CodeGenerator Tests - Source Mappings
# =============================================================================


class TestCodeGeneratorSourceMappings:
    """Test that code generator produces source mappings."""

    def test_generates_source_mappings(self) -> None:
        """Generated code includes source mappings."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        Assignment(
                            target="x",
                            value=Literal(value=42, literal_type="int"),
                            meta=SourcePosition(line=5, column=4),
                        ),
                    ],
                    meta=SourcePosition(line=3, column=0),
                ),
            ],
        )

        generator = CodeGenerator()
        _code, mappings = generator.generate(ast, "test.sr")

        # Should have mappings for the flow and assignment
        assert len(mappings) > 0

    def test_source_comments_in_generated_code(self) -> None:
        """Generated code includes source file comments."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                FlowDef(
                    name="main",
                    params=[],
                    body=[
                        Assignment(
                            target="x",
                            value=Literal(value=42, literal_type="int"),
                            meta=SourcePosition(line=5, column=4),
                        ),
                    ],
                    meta=SourcePosition(line=3, column=0),
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should include source file comments
        assert "# test.sr:" in code


# =============================================================================
# CodeGenerator Tests - Complete Workflow Class
# =============================================================================


class TestCodeGeneratorWorkflowClass:
    """Test complete workflow class generation."""

    def test_generates_valid_python(self) -> None:
        """Generated code should be valid Python syntax."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                PromptDef(name="greeting", body="Hello"),
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

        # Verify the code can be compiled
        compile(code, "<generated>", "exec")

    def test_generates_class_structure(self) -> None:
        """Generated code has proper class structure."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "class " in code
        assert "DslAgentWorkflow" in code

    def test_generates_imports(self) -> None:
        """Generated code includes necessary imports."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "import" in code or "from" in code


# =============================================================================
# CodeGenerator Tests - Tool Definitions
# =============================================================================


class TestCodeGeneratorToolDefinitions:
    """Test code generation for tool definitions."""

    def test_generate_mcp_tool_with_auth(self) -> None:
        """Generate code for MCP tool with auth configuration."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(
                    name="github",
                    tool_type="mcp",
                    url="https://api.github.com/mcp",
                    auth_type="bearer",
                    auth_value="${GITHUB_TOKEN}",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "_tools = {" in code
        assert "'github'" in code
        assert "'type': 'mcp'" in code
        assert "'url': 'https://api.github.com/mcp'" in code
        assert "'auth': {" in code
        assert "'type': 'bearer'" in code
        assert "'value': '${GITHUB_TOKEN}'" in code

    def test_generate_mcp_tool_with_headers(self) -> None:
        """Generate code for MCP tool with explicit headers."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(
                    name="custom_api",
                    tool_type="mcp",
                    url="https://api.example.com/mcp",
                    headers={"X-API-Key": "secret"},
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'headers': {'X-API-Key': 'secret'}" in code

    def test_generate_builtin_tool(self) -> None:
        """Generate code for builtin tool."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(
                    name="fs",
                    tool_type="builtin",
                    builtin_ref="streetrace.fs",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "'fs'" in code
        assert "'type': 'builtin'" in code
        assert "'builtin_ref': 'streetrace.fs'" in code

    def test_generated_tools_code_compiles(self) -> None:
        """Generated tool code should be valid Python syntax."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(
                    name="github",
                    tool_type="mcp",
                    url="https://api.github.com/mcp",
                    auth_type="bearer",
                    auth_value="${GITHUB_TOKEN}",
                ),
                ToolDef(
                    name="fs",
                    tool_type="builtin",
                    builtin_ref="streetrace.fs",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Verify the code can be compiled
        compile(code, "<generated>", "exec")
