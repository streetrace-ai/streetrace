"""Semantic analyzer for Streetrace DSL.

Validate AST nodes for semantic correctness including reference
resolution, variable scoping, and type checking.
"""

from dataclasses import dataclass, field

from streetrace.dsl.ast.nodes import (
    AgentDef,
    Assignment,
    BinaryOp,
    CallStmt,
    DslFile,
    EventHandler,
    FlowDef,
    ForLoop,
    FunctionCall,
    IfBlock,
    ListLiteral,
    MatchBlock,
    ModelDef,
    ObjectLiteral,
    ParallelBlock,
    PromptDef,
    PropertyAccess,
    PushStmt,
    RetryPolicyDef,
    ReturnStmt,
    RunStmt,
    SchemaDef,
    TimeoutPolicyDef,
    ToolDef,
    UnaryOp,
    VarRef,
)
from streetrace.dsl.semantic.errors import SemanticError
from streetrace.dsl.semantic.scope import Scope, ScopeType, SymbolKind
from streetrace.log import get_logger

logger = get_logger(__name__)


# Built-in variables available in all scopes
BUILTIN_VARIABLES = frozenset({
    "input_prompt",
    "conversation",
    "current_agent",
    "session_id",
    "turn_count",
})


@dataclass
class SymbolTable:
    """Collected symbol information from analysis."""

    models: dict[str, ModelDef] = field(default_factory=dict)
    schemas: dict[str, SchemaDef] = field(default_factory=dict)
    tools: dict[str, ToolDef] = field(default_factory=dict)
    prompts: dict[str, PromptDef] = field(default_factory=dict)
    agents: dict[str, AgentDef] = field(default_factory=dict)
    flows: dict[str, FlowDef] = field(default_factory=dict)
    retry_policies: dict[str, RetryPolicyDef] = field(default_factory=dict)
    timeout_policies: dict[str, TimeoutPolicyDef] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Result of semantic analysis."""

    is_valid: bool
    """Whether the AST passed semantic validation."""

    errors: list[SemanticError] = field(default_factory=list)
    """List of semantic errors found."""

    symbols: SymbolTable = field(default_factory=SymbolTable)
    """Collected symbol information."""


class SemanticAnalyzer:
    """Semantic analyzer for Streetrace DSL AST.

    Perform semantic validation including:
    - Reference validation (models, tools, prompts, agents)
    - Variable scoping (global, flow-local, handler-local)
    - Type checking for expressions
    - Duplicate detection
    """

    def __init__(self) -> None:
        """Initialize the semantic analyzer."""
        self._errors: list[SemanticError] = []
        self._symbols = SymbolTable()
        self._global_scope: Scope | None = None
        self._current_scope: Scope | None = None

    def analyze(self, ast: DslFile) -> AnalysisResult:
        """Analyze a DSL file AST for semantic correctness.

        Args:
            ast: The DslFile AST node to analyze.

        Returns:
            AnalysisResult with validation status and any errors.

        """
        self._errors = []
        self._symbols = SymbolTable()
        self._global_scope = Scope(scope_type=ScopeType.GLOBAL)
        self._current_scope = self._global_scope

        # Define built-in variables in global scope
        self._define_builtins()

        # First pass: collect all top-level definitions
        self._collect_definitions(ast)

        # Second pass: validate references and scoping
        self._validate_references(ast)

        return AnalysisResult(
            is_valid=len(self._errors) == 0,
            errors=self._errors,
            symbols=self._symbols,
        )

    def _define_builtins(self) -> None:
        """Define built-in variables in global scope."""
        if self._global_scope is None:
            return

        for name in BUILTIN_VARIABLES:
            self._global_scope.define(
                name=name,
                kind=SymbolKind.VARIABLE,
                type_info="builtin",
            )

    def _collect_definitions(self, ast: DslFile) -> None:
        """Collect all top-level definitions from the AST.

        Args:
            ast: The DslFile AST node.

        """
        for stmt in ast.statements:
            self._collect_definition(stmt)

    def _collect_definition(self, stmt: object) -> None:
        """Collect a single top-level definition.

        Args:
            stmt: The statement to collect.

        """
        if isinstance(stmt, ModelDef):
            self._collect_model(stmt)
        elif isinstance(stmt, SchemaDef):
            self._collect_schema(stmt)
        elif isinstance(stmt, ToolDef):
            self._collect_tool(stmt)
        elif isinstance(stmt, PromptDef):
            self._collect_prompt(stmt)
        elif isinstance(stmt, AgentDef):
            self._collect_agent(stmt)
        elif isinstance(stmt, (FlowDef, RetryPolicyDef, TimeoutPolicyDef)):
            self._collect_flow_or_policy(stmt)

    def _collect_model(self, model: ModelDef) -> None:
        """Collect a model definition."""
        if model.name in self._symbols.models:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="model",
                    name=model.name,
                    position=model.meta,
                ),
            )
            return
        self._symbols.models[model.name] = model
        if self._global_scope is not None:
            self._global_scope.define(
                name=model.name,
                kind=SymbolKind.MODEL,
                node=model,
            )

    def _collect_schema(self, schema: SchemaDef) -> None:
        """Collect a schema definition."""
        if schema.name in self._symbols.schemas:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="schema",
                    name=schema.name,
                    position=schema.meta,
                ),
            )
            return
        self._symbols.schemas[schema.name] = schema
        if self._global_scope is not None:
            self._global_scope.define(
                name=schema.name,
                kind=SymbolKind.SCHEMA,
                node=schema,
            )

    def _collect_tool(self, tool: ToolDef) -> None:
        """Collect a tool definition."""
        if tool.name in self._symbols.tools:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="tool",
                    name=tool.name,
                    position=tool.meta,
                ),
            )
            return
        self._symbols.tools[tool.name] = tool
        if self._global_scope is not None:
            self._global_scope.define(
                name=tool.name,
                kind=SymbolKind.TOOL,
                node=tool,
            )

    def _collect_prompt(self, prompt: PromptDef) -> None:
        """Collect a prompt definition."""
        if prompt.name in self._symbols.prompts:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="prompt",
                    name=prompt.name,
                    position=prompt.meta,
                ),
            )
            return
        self._symbols.prompts[prompt.name] = prompt
        if self._global_scope is not None:
            self._global_scope.define(
                name=prompt.name,
                kind=SymbolKind.PROMPT,
                node=prompt,
            )

    def _collect_agent(self, agent: AgentDef) -> None:
        """Collect an agent definition."""
        name = agent.name or "default"
        if name in self._symbols.agents:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="agent",
                    name=name,
                    position=agent.meta,
                ),
            )
            return
        self._symbols.agents[name] = agent
        if self._global_scope is not None:
            self._global_scope.define(
                name=name,
                kind=SymbolKind.AGENT,
                node=agent,
            )

    def _collect_flow_or_policy(
        self,
        stmt: FlowDef | RetryPolicyDef | TimeoutPolicyDef,
    ) -> None:
        """Collect a flow or policy definition.

        Args:
            stmt: Flow or policy definition to collect.

        """
        if isinstance(stmt, FlowDef):
            self._collect_flow(stmt)
        elif isinstance(stmt, RetryPolicyDef):
            self._collect_retry_policy(stmt)
        elif isinstance(stmt, TimeoutPolicyDef):
            self._collect_timeout_policy(stmt)

    def _collect_flow(self, flow: FlowDef) -> None:
        """Collect a flow definition."""
        if flow.name in self._symbols.flows:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="flow",
                    name=flow.name,
                    position=flow.meta,
                ),
            )
            return
        self._symbols.flows[flow.name] = flow
        if self._global_scope is not None:
            self._global_scope.define(
                name=flow.name,
                kind=SymbolKind.FLOW,
                node=flow,
            )

    def _collect_retry_policy(self, policy: RetryPolicyDef) -> None:
        """Collect a retry policy definition."""
        if policy.name in self._symbols.retry_policies:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="retry policy",
                    name=policy.name,
                    position=policy.meta,
                ),
            )
            return
        self._symbols.retry_policies[policy.name] = policy
        if self._global_scope is not None:
            self._global_scope.define(
                name=policy.name,
                kind=SymbolKind.RETRY_POLICY,
                node=policy,
            )

    def _collect_timeout_policy(self, policy: TimeoutPolicyDef) -> None:
        """Collect a timeout policy definition."""
        if policy.name in self._symbols.timeout_policies:
            self._add_error(
                SemanticError.duplicate_definition(
                    kind="timeout policy",
                    name=policy.name,
                    position=policy.meta,
                ),
            )
            return
        self._symbols.timeout_policies[policy.name] = policy
        if self._global_scope is not None:
            self._global_scope.define(
                name=policy.name,
                kind=SymbolKind.TIMEOUT_POLICY,
                node=policy,
            )

    def _validate_references(self, ast: DslFile) -> None:
        """Validate all references in the AST.

        Args:
            ast: The DslFile AST node.

        """
        for stmt in ast.statements:
            if isinstance(stmt, PromptDef):
                self._validate_prompt_refs(stmt)
            elif isinstance(stmt, AgentDef):
                self._validate_agent_refs(stmt)
            elif isinstance(stmt, FlowDef):
                self._validate_flow(stmt)
            elif isinstance(stmt, EventHandler):
                self._validate_event_handler(stmt)

    def _validate_prompt_refs(self, prompt: PromptDef) -> None:
        """Validate references in a prompt definition."""
        # Check model reference if specified
        if prompt.model is not None and prompt.model not in self._symbols.models:
            self._add_error(
                SemanticError.undefined_reference(
                    kind="model",
                    name=prompt.model,
                    position=prompt.meta,
                    suggestion=self._suggest_similar("model", prompt.model),
                ),
            )

        # Check expecting (schema) reference if specified
        if (
            prompt.expecting is not None
            and prompt.expecting not in self._symbols.schemas
        ):
            self._add_error(
                SemanticError.undefined_reference(
                    kind="schema",
                    name=prompt.expecting,
                    position=prompt.meta,
                ),
            )

    def _validate_agent_refs(self, agent: AgentDef) -> None:
        """Validate references in an agent definition."""
        agent_name = agent.name or "default"

        # Check required instruction property
        if not agent.instruction:
            suggestion = (
                "add 'instruction <prompt_name>' to specify the agent's "
                "instruction prompt"
            )
            self._add_error(
                SemanticError.missing_required_property(
                    kind="agent",
                    name=agent_name,
                    prop="instruction",
                    position=agent.meta,
                    suggestion=suggestion,
                ),
            )

        # Check tool references
        for tool_name in agent.tools:
            if tool_name not in self._symbols.tools:
                self._add_error(
                    SemanticError.undefined_reference(
                        kind="tool",
                        name=tool_name,
                        position=agent.meta,
                        suggestion=self._suggest_similar("tool", tool_name),
                    ),
                )

        # Check retry policy reference
        if agent.retry is not None and agent.retry not in self._symbols.retry_policies:
            self._add_error(
                SemanticError.undefined_reference(
                    kind="retry policy",
                    name=agent.retry,
                    position=agent.meta,
                ),
            )

        # Check timeout policy reference
        if (
            agent.timeout_ref is not None
            and agent.timeout_ref not in self._symbols.timeout_policies
        ):
            self._add_error(
                SemanticError.undefined_reference(
                    kind="timeout policy",
                    name=agent.timeout_ref,
                    position=agent.meta,
                ),
            )

    def _validate_flow(self, flow: FlowDef) -> None:
        """Validate a flow definition including scoping."""
        # Create flow scope
        flow_scope = Scope(
            scope_type=ScopeType.FLOW,
            parent=self._global_scope,
        )

        # Define parameters in flow scope
        # Strip $ prefix for consistency with VarRef which uses name without $
        for param in flow.params:
            param_name = param.lstrip("$")
            flow_scope.define(name=param_name, kind=SymbolKind.PARAMETER)

        # Validate flow body with flow scope
        self._validate_statements(flow.body, flow_scope)

    def _validate_event_handler(self, handler: EventHandler) -> None:
        """Validate an event handler."""
        # Check if this is an "on start" handler - defines global vars
        is_start_handler = handler.timing == "on" and handler.event_type == "start"

        if is_start_handler:
            # Variables defined in on start are global
            scope = self._global_scope
        else:
            # Create handler scope
            scope = Scope(
                scope_type=ScopeType.HANDLER,
                parent=self._global_scope,
            )

        if scope is not None:
            self._validate_statements(handler.body, scope)

    def _validate_statements(self, stmts: list[object], scope: Scope) -> None:
        """Validate a list of statements with given scope.

        Args:
            stmts: List of AST statement nodes.
            scope: Current scope for variable resolution.

        """
        for stmt in stmts:
            self._validate_statement(stmt, scope)

    def _validate_statement(self, stmt: object, scope: Scope) -> None:
        """Validate a single statement.

        Args:
            stmt: AST statement node.
            scope: Current scope for variable resolution.

        """
        if isinstance(stmt, Assignment):
            self._validate_assignment(stmt, scope)
        elif isinstance(stmt, RunStmt):
            self._validate_run_stmt(stmt, scope)
        elif isinstance(stmt, CallStmt):
            self._validate_call_stmt(stmt, scope)
        elif isinstance(stmt, (ReturnStmt, PushStmt)):
            self._validate_return_or_push(stmt, scope)
        elif isinstance(stmt, (ForLoop, IfBlock, MatchBlock, ParallelBlock)):
            self._validate_control_flow(stmt, scope)
        # Guardrail actions and other statements don't need special handling

    def _validate_assignment(self, stmt: Assignment, scope: Scope) -> None:
        """Validate an assignment statement."""
        self._validate_expression(stmt.value, scope)
        # Strip $ prefix for consistency with VarRef which uses name without $
        var_name = stmt.target.lstrip("$")
        scope.define(name=var_name, kind=SymbolKind.VARIABLE)

    def _validate_run_stmt(self, stmt: RunStmt, scope: Scope) -> None:
        """Validate a run statement for agents or flows."""
        if stmt.is_flow:
            # Validate flow call
            if stmt.agent not in self._symbols.flows:
                self._add_error(
                    SemanticError.undefined_reference(
                        kind="flow",
                        name=stmt.agent,
                        position=stmt.meta,
                        suggestion=self._suggest_similar("flow", stmt.agent),
                    ),
                )
        elif stmt.agent not in self._symbols.agents:
            # Validate agent call
            self._add_error(
                SemanticError.undefined_reference(
                    kind="agent",
                    name=stmt.agent,
                    position=stmt.meta,
                    suggestion=self._suggest_similar("agent", stmt.agent),
                ),
            )
        for arg in stmt.args:
            self._validate_expression(arg, scope)
        if stmt.target is not None:
            # Strip $ prefix for consistency with VarRef which uses name without $
            var_name = stmt.target.lstrip("$")
            scope.define(name=var_name, kind=SymbolKind.VARIABLE)

    def _validate_call_stmt(self, stmt: CallStmt, scope: Scope) -> None:
        """Validate a call LLM statement."""
        if stmt.prompt not in self._symbols.prompts:
            self._add_error(
                SemanticError.undefined_reference(
                    kind="prompt",
                    name=stmt.prompt,
                    position=stmt.meta,
                    suggestion=self._suggest_similar("prompt", stmt.prompt),
                ),
            )
        if stmt.model is not None and stmt.model not in self._symbols.models:
            self._add_error(
                SemanticError.undefined_reference(
                    kind="model",
                    name=stmt.model,
                    position=stmt.meta,
                ),
            )
        for arg in stmt.args:
            self._validate_expression(arg, scope)
        if stmt.target is not None:
            # Strip $ prefix for consistency with VarRef which uses name without $
            var_name = stmt.target.lstrip("$")
            scope.define(name=var_name, kind=SymbolKind.VARIABLE)

    def _validate_return_or_push(
        self,
        stmt: ReturnStmt | PushStmt,
        scope: Scope,
    ) -> None:
        """Validate return or push statements."""
        if isinstance(stmt, ReturnStmt):
            self._validate_expression(stmt.value, scope)
        elif isinstance(stmt, PushStmt):
            self._validate_expression(stmt.value, scope)
            # Strip $ prefix for consistency with VarRef which uses name without $
            var_name = stmt.target.lstrip("$")
            if scope.lookup(var_name) is None:
                self._add_error(
                    SemanticError.undefined_variable(
                        name=stmt.target,
                        position=stmt.meta,
                    ),
                )

    def _validate_control_flow(
        self,
        stmt: ForLoop | IfBlock | MatchBlock | ParallelBlock,
        scope: Scope,
    ) -> None:
        """Validate control flow statements."""
        if isinstance(stmt, ForLoop):
            self._validate_for_loop(stmt, scope)
        elif isinstance(stmt, IfBlock):
            self._validate_if_block(stmt, scope)
        elif isinstance(stmt, MatchBlock):
            self._validate_match_block(stmt, scope)
        elif isinstance(stmt, ParallelBlock):
            self._validate_statements(stmt.body, scope)

    def _validate_for_loop(self, stmt: ForLoop, scope: Scope) -> None:
        """Validate a for loop statement."""
        block_scope = Scope(scope_type=ScopeType.BLOCK, parent=scope)
        # Strip $ prefix for consistency with VarRef which uses name without $
        var_name = stmt.variable.lstrip("$")
        block_scope.define(name=var_name, kind=SymbolKind.VARIABLE)
        self._validate_expression(stmt.iterable, scope)
        self._validate_statements(stmt.body, block_scope)

    def _validate_if_block(self, stmt: IfBlock, scope: Scope) -> None:
        """Validate an if block statement."""
        self._validate_expression(stmt.condition, scope)
        block_scope = Scope(scope_type=ScopeType.BLOCK, parent=scope)
        self._validate_statements(stmt.body, block_scope)

    def _validate_match_block(self, stmt: MatchBlock, scope: Scope) -> None:
        """Validate a match block statement."""
        self._validate_expression(stmt.expression, scope)
        for case in stmt.cases:
            case_scope = Scope(scope_type=ScopeType.BLOCK, parent=scope)
            if hasattr(case, "body") and isinstance(case.body, list):
                self._validate_statements(case.body, case_scope)
        if stmt.else_body is not None:
            else_scope = Scope(scope_type=ScopeType.BLOCK, parent=scope)
            if isinstance(stmt.else_body, list):
                self._validate_statements(stmt.else_body, else_scope)

    def _validate_expression(self, expr: object, scope: Scope) -> None:
        """Validate an expression.

        Args:
            expr: AST expression node.
            scope: Current scope for variable resolution.

        """
        if isinstance(expr, VarRef):
            self._validate_var_ref(expr, scope)
        elif isinstance(expr, PropertyAccess):
            self._validate_expression(expr.base, scope)
        elif isinstance(expr, (BinaryOp, UnaryOp)):
            self._validate_binary_or_unary(expr, scope)
        elif isinstance(expr, (FunctionCall, ListLiteral, ObjectLiteral)):
            self._validate_compound_expr(expr, scope)
        # Literals are always valid - no validation needed

    def _validate_var_ref(self, expr: VarRef, scope: Scope) -> None:
        """Validate a variable reference."""
        if scope.lookup(expr.name) is None:
            self._add_error(
                SemanticError.undefined_variable(
                    name=expr.name,
                    position=expr.meta,
                ),
            )

    def _validate_binary_or_unary(
        self,
        expr: BinaryOp | UnaryOp,
        scope: Scope,
    ) -> None:
        """Validate binary or unary operations."""
        if isinstance(expr, BinaryOp):
            self._validate_expression(expr.left, scope)
            self._validate_expression(expr.right, scope)
        elif isinstance(expr, UnaryOp):
            self._validate_expression(expr.operand, scope)

    def _validate_compound_expr(
        self,
        expr: FunctionCall | ListLiteral | ObjectLiteral,
        scope: Scope,
    ) -> None:
        """Validate compound expressions with child elements."""
        if isinstance(expr, FunctionCall):
            for arg in expr.args:
                self._validate_expression(arg, scope)
        elif isinstance(expr, ListLiteral):
            for elem in expr.elements:
                self._validate_expression(elem, scope)
        elif isinstance(expr, ObjectLiteral):
            for value in expr.entries.values():
                self._validate_expression(value, scope)

    def _add_error(self, error: SemanticError) -> None:
        """Add an error to the error list.

        Args:
            error: The semantic error to add.

        """
        self._errors.append(error)
        logger.debug("Semantic error: %s", error.message)

    def _suggest_similar(self, kind: str, name: str) -> str | None:
        """Suggest similar names for an undefined reference.

        Args:
            kind: Kind of reference (model, tool, etc.).
            name: Name that was not found.

        Returns:
            Suggestion string or None.

        """
        candidates: list[str] = []
        if kind == "model":
            candidates = list(self._symbols.models.keys())
        elif kind == "tool":
            candidates = list(self._symbols.tools.keys())
        elif kind == "prompt":
            candidates = list(self._symbols.prompts.keys())
        elif kind == "agent":
            candidates = list(self._symbols.agents.keys())
        elif kind == "flow":
            candidates = list(self._symbols.flows.keys())

        if not candidates:
            return None

        # Simple similarity check - could be improved with Levenshtein
        for candidate in candidates:
            if candidate.lower().startswith(name.lower()[:3]):
                return f"did you mean '{candidate}'?"

        if candidates:
            return f"defined {kind}s are: {', '.join(candidates)}"

        return None
