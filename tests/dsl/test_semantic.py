"""Tests for semantic analysis of Streetrace DSL.

Test the semantic analyzer's ability to validate AST nodes,
resolve references, check scoping rules, and detect errors.
"""


from streetrace.dsl.ast import (
    AgentDef,
    Assignment,
    BinaryOp,
    CallStmt,
    DslFile,
    EventHandler,
    FlowDef,
    Literal,
    MaskAction,
    ModelDef,
    PromptDef,
    ReturnStmt,
    RunStmt,
    SchemaDef,
    SchemaField,
    ToolDef,
    TypeExpr,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.scope import Scope, ScopeType, Symbol, SymbolKind

# =============================================================================
# Symbol Table Tests
# =============================================================================


class TestSymbol:
    """Test Symbol dataclass."""

    def test_create_symbol(self) -> None:
        """Create a symbol with all fields."""
        symbol = Symbol(
            name="my_model",
            kind=SymbolKind.MODEL,
            defined_at=None,
        )
        assert symbol.name == "my_model"
        assert symbol.kind == SymbolKind.MODEL
        assert symbol.defined_at is None

    def test_symbol_with_node(self) -> None:
        """Create a symbol with associated AST node."""
        model = ModelDef(name="main", provider_model="anthropic/claude-sonnet")
        symbol = Symbol(
            name="main",
            kind=SymbolKind.MODEL,
            defined_at=model,
        )
        assert symbol.defined_at is model


class TestScope:
    """Test Scope class for variable and symbol tracking."""

    def test_create_global_scope(self) -> None:
        """Create a global scope."""
        scope = Scope(scope_type=ScopeType.GLOBAL)
        assert scope.scope_type == ScopeType.GLOBAL
        assert scope.parent is None

    def test_create_child_scope(self) -> None:
        """Create a child scope with parent."""
        global_scope = Scope(scope_type=ScopeType.GLOBAL)
        flow_scope = Scope(scope_type=ScopeType.FLOW, parent=global_scope)
        assert flow_scope.parent is global_scope
        assert flow_scope.scope_type == ScopeType.FLOW

    def test_define_symbol(self) -> None:
        """Define a symbol in scope."""
        scope = Scope(scope_type=ScopeType.GLOBAL)
        model = ModelDef(name="main", provider_model="anthropic/claude-sonnet")
        scope.define(
            name="main",
            kind=SymbolKind.MODEL,
            node=model,
        )
        assert scope.lookup("main") is not None
        assert scope.lookup("main").kind == SymbolKind.MODEL

    def test_lookup_symbol_in_parent(self) -> None:
        """Lookup symbol from parent scope."""
        global_scope = Scope(scope_type=ScopeType.GLOBAL)
        global_scope.define(name="my_model", kind=SymbolKind.MODEL)

        flow_scope = Scope(scope_type=ScopeType.FLOW, parent=global_scope)
        symbol = flow_scope.lookup("my_model")
        assert symbol is not None
        assert symbol.name == "my_model"

    def test_lookup_undefined_symbol(self) -> None:
        """Lookup returns None for undefined symbol."""
        scope = Scope(scope_type=ScopeType.GLOBAL)
        assert scope.lookup("undefined") is None

    def test_define_variable(self) -> None:
        """Define a variable in scope."""
        scope = Scope(scope_type=ScopeType.FLOW)
        scope.define(name="result", kind=SymbolKind.VARIABLE)
        assert scope.lookup("result") is not None
        assert scope.lookup("result").kind == SymbolKind.VARIABLE

    def test_local_scope_shadows_parent(self) -> None:
        """Local scope can shadow parent symbols."""
        global_scope = Scope(scope_type=ScopeType.GLOBAL)
        global_scope.define(name="x", kind=SymbolKind.VARIABLE)

        flow_scope = Scope(scope_type=ScopeType.FLOW, parent=global_scope)
        flow_scope.define(name="x", kind=SymbolKind.VARIABLE)

        # Local lookup finds local symbol
        assert flow_scope.lookup_local("x") is not None

    def test_lookup_local_only(self) -> None:
        """Lookup local only does not search parent."""
        global_scope = Scope(scope_type=ScopeType.GLOBAL)
        global_scope.define(name="x", kind=SymbolKind.VARIABLE)

        flow_scope = Scope(scope_type=ScopeType.FLOW, parent=global_scope)
        # Local lookup doesn't find parent symbol
        assert flow_scope.lookup_local("x") is None

    def test_is_defined_locally(self) -> None:
        """Check if symbol is defined in current scope only."""
        global_scope = Scope(scope_type=ScopeType.GLOBAL)
        global_scope.define(name="x", kind=SymbolKind.VARIABLE)

        flow_scope = Scope(scope_type=ScopeType.FLOW, parent=global_scope)
        assert not flow_scope.is_defined_locally("x")
        flow_scope.define(name="y", kind=SymbolKind.VARIABLE)
        assert flow_scope.is_defined_locally("y")


# =============================================================================
# Semantic Analyzer Tests - Symbol Resolution
# =============================================================================


class TestSemanticAnalyzerModels:
    """Test semantic analysis of model definitions."""

    def test_valid_model_definition(self) -> None:
        """Valid model definition is accepted."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid
        assert "main" in result.symbols.models

    def test_duplicate_model_definition(self) -> None:
        """Duplicate model name produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ModelDef(name="main", provider_model="anthropic/claude-sonnet"),
                ModelDef(name="main", provider_model="openai/gpt-4o"),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("duplicate" in e.message.lower() for e in result.errors)


class TestSemanticAnalyzerSchemas:
    """Test semantic analysis of schema definitions."""

    def test_valid_schema_definition(self) -> None:
        """Valid schema definition is accepted."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                SchemaDef(
                    name="Invoice",
                    fields=[
                        SchemaField(
                            name="amount",
                            type_expr=TypeExpr(base_type="float"),
                        ),
                        SchemaField(
                            name="vendor",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid
        assert "Invoice" in result.symbols.schemas


class TestSemanticAnalyzerTools:
    """Test semantic analysis of tool definitions."""

    def test_valid_tool_definition(self) -> None:
        """Valid tool definition is accepted."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(
                    name="github",
                    tool_type="mcp",
                    url="https://api.github.com/mcp",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid
        assert "github" in result.symbols.tools


class TestSemanticAnalyzerPrompts:
    """Test semantic analysis of prompt definitions."""

    def test_valid_prompt_definition(self) -> None:
        """Valid prompt definition is accepted."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="analyze",
                    body="Analyze the following text: $input",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid
        assert "analyze" in result.symbols.prompts

    def test_prompt_with_model_reference(self) -> None:
        """Prompt referencing defined model is valid."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ModelDef(name="fast", provider_model="anthropic/claude-haiku"),
                PromptDef(
                    name="analyze",
                    body="Analyze the text",
                    model="fast",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_prompt_with_undefined_model(self) -> None:
        """Prompt referencing undefined model produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="analyze",
                    body="Analyze the text",
                    model="undefined_model",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_model" in e.message for e in result.errors)


class TestSemanticAnalyzerAgents:
    """Test semantic analysis of agent definitions."""

    def test_valid_agent_definition(self) -> None:
        """Valid agent definition is accepted."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="my_instruction", body="Help the user with files"),
                AgentDef(
                    name="file_helper",
                    tools=["fs"],
                    instruction="my_instruction",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid
        assert "file_helper" in result.symbols.agents

    def test_agent_with_undefined_tool(self) -> None:
        """Agent referencing undefined tool produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="my_instruction", body="Help the user"),
                AgentDef(
                    name="helper",
                    tools=["undefined_tool"],
                    instruction="my_instruction",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_tool" in e.message for e in result.errors)


# =============================================================================
# Semantic Analyzer Tests - Variable Scoping
# =============================================================================


class TestSemanticAnalyzerScoping:
    """Test variable scoping rules in semantic analysis."""

    def test_variable_defined_before_use(self) -> None:
        """Variable used after definition is valid."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="my_flow",
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
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_variable_used_before_definition(self) -> None:
        """Variable used before definition produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="my_flow",
                    params=[],
                    body=[
                        ReturnStmt(value=VarRef(name="undefined_var")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_var" in e.message for e in result.errors)

    def test_flow_parameters_are_in_scope(self) -> None:
        """Flow parameters are available as variables."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="my_flow",
                    params=["input"],
                    body=[
                        ReturnStmt(value=VarRef(name="input")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_global_variable_from_on_start(self) -> None:
        """Variable defined in on start is global."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
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
                FlowDef(
                    name="my_flow",
                    params=[],
                    body=[
                        # Should be able to access global $config
                        ReturnStmt(value=VarRef(name="config")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_builtin_variables_available(self) -> None:
        """Built-in variables like $input_prompt are available."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="my_flow",
                    params=[],
                    body=[
                        ReturnStmt(value=VarRef(name="input_prompt")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_flow_local_variable_not_visible_outside(self) -> None:
        """Variable defined in flow is not visible in another flow."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="flow_a",
                    params=[],
                    body=[
                        Assignment(
                            target="local_var",
                            value=Literal(value=42, literal_type="int"),
                        ),
                    ],
                ),
                FlowDef(
                    name="flow_b",
                    params=[],
                    body=[
                        # Should NOT be able to access flow_a's $local_var
                        ReturnStmt(value=VarRef(name="local_var")),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("local_var" in e.message for e in result.errors)


# =============================================================================
# Semantic Analyzer Tests - Type Checking
# =============================================================================


class TestSemanticAnalyzerTypeChecking:
    """Test type checking in expressions."""

    def test_comparison_operators(self) -> None:
        """Comparison operators produce boolean results."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="my_flow",
                    params=[],
                    body=[
                        Assignment(
                            target="result",
                            value=BinaryOp(
                                op=">",
                                left=Literal(value=10, literal_type="int"),
                                right=Literal(value=5, literal_type="int"),
                            ),
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid


# =============================================================================
# Semantic Analyzer Tests - Reference Resolution
# =============================================================================


class TestSemanticAnalyzerReferences:
    """Test reference resolution in run/call statements."""

    def test_run_agent_with_valid_reference(self) -> None:
        """Run statement with valid agent reference."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with files"),
                AgentDef(
                    name="file_helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="main_flow",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="file_helper",
                            args=[VarRef(name="input_prompt")],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_run_agent_with_undefined_reference(self) -> None:
        """Run statement with undefined agent produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="main_flow",
                    params=[],
                    body=[
                        RunStmt(
                            target="result",
                            agent="undefined_agent",
                            args=[VarRef(name="input_prompt")],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_agent" in e.message for e in result.errors)

    def test_call_with_valid_prompt(self) -> None:
        """Call statement with valid prompt reference."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(name="analyze_prompt", body="Analyze: $input"),
                FlowDef(
                    name="main_flow",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="analyze_prompt",
                            args=[VarRef(name="input_prompt")],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid

    def test_call_with_undefined_prompt(self) -> None:
        """Call statement with undefined prompt produces error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                FlowDef(
                    name="main_flow",
                    params=[],
                    body=[
                        CallStmt(
                            target="result",
                            prompt="undefined_prompt",
                            args=[VarRef(name="input_prompt")],
                        ),
                    ],
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert any("undefined_prompt" in e.message for e in result.errors)


# =============================================================================
# Semantic Analyzer Tests - Event Handlers
# =============================================================================


class TestSemanticAnalyzerEventHandlers:
    """Test semantic analysis of event handlers."""

    def test_valid_event_handler(self) -> None:
        """Valid event handler is accepted."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
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
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert result.is_valid


# =============================================================================
# Semantic Analyzer Tests - Error Collection
# =============================================================================


class TestSemanticAnalyzerErrorCollection:
    """Test error collection and reporting."""

    def test_multiple_errors_collected(self) -> None:
        """Multiple errors are collected in single pass."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                # Error 1: undefined model in prompt
                PromptDef(
                    name="p1",
                    body="text",
                    model="undefined_model_1",
                ),
                # Error 2: another undefined model
                PromptDef(
                    name="p2",
                    body="text",
                    model="undefined_model_2",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        assert len(result.errors) >= 2

    def test_error_has_location_info(self) -> None:
        """Errors include source location when available."""
        from streetrace.dsl.ast.nodes import SourcePosition

        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                PromptDef(
                    name="p1",
                    body="text",
                    model="undefined",
                    meta=SourcePosition(line=5, column=10),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)
        assert not result.is_valid
        # Error should have position info
        assert result.errors[0].position is not None
        assert result.errors[0].position.line == 5
