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
    LoopBlock,
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
        self._loop_depth: int = 0

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
        self._loop_depth = 0

        # Define built-in variables in global scope
        self._define_builtins()

        # First pass: collect all top-level definitions (prompts are merged)
        self._collect_definitions(ast)

        # Validate merged prompts have bodies
        self._validate_prompts_have_bodies()

        # Second pass: validate references and scoping
        self._validate_references(ast)

        # Validation passes if there are no actual errors (warnings don't fail)
        actual_errors = [e for e in self._errors if not e.is_warning]
        return AnalysisResult(
            is_valid=len(actual_errors) == 0,
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
        """Collect a prompt definition, merging with existing definition if present.

        Support the override pattern where prompts can be defined multiple times:
        - Declarations (no body) define metadata at top of file
        - Full definitions (with body) define prompt text at bottom
        - Multiple definitions are merged following these rules:
          - body: later non-empty body overwrites
          - model, expecting, inherit: fill if not set, error if conflicting
          - escalation_condition: later non-None overwrites
        """
        if prompt.name not in self._symbols.prompts:
            # First definition - store as-is
            self._symbols.prompts[prompt.name] = prompt
            if self._global_scope is not None:
                self._global_scope.define(
                    name=prompt.name,
                    kind=SymbolKind.PROMPT,
                    node=prompt,
                )
            return

        # Merge with existing definition
        existing = self._symbols.prompts[prompt.name]
        merged = self._merge_prompts(existing, prompt)
        if merged is not None:
            self._symbols.prompts[prompt.name] = merged
            # Update scope node reference
            if self._global_scope is not None:
                self._global_scope.define(
                    name=prompt.name,
                    kind=SymbolKind.PROMPT,
                    node=merged,
                )

    def _merge_prompts(
        self,
        existing: PromptDef,
        new: PromptDef,
    ) -> PromptDef | None:
        """Merge two prompt definitions.

        Args:
            existing: The existing prompt definition.
            new: The new prompt definition to merge.

        Returns:
            Merged PromptDef, or None if merge failed due to conflicts.

        """
        # Check for modifier conflicts
        if not self._check_prompt_modifier_conflict(
            existing, new, "model", existing.model, new.model,
        ):
            return None
        if not self._check_prompt_modifier_conflict(
            existing, new, "expecting", existing.expecting, new.expecting,
        ):
            return None
        if not self._check_prompt_modifier_conflict(
            existing, new, "inherit", existing.inherit, new.inherit,
        ):
            return None

        # Merge: later non-empty values overwrite
        merged_body = new.body if new.body else existing.body
        merged_model = new.model if new.model else existing.model
        merged_expecting = new.expecting if new.expecting else existing.expecting
        merged_inherit = new.inherit if new.inherit else existing.inherit
        merged_escalation = (
            new.escalation_condition
            if new.escalation_condition
            else existing.escalation_condition
        )

        # Use the position of the definition with body, or the later one
        merged_meta = new.meta if new.body else existing.meta

        return PromptDef(
            name=existing.name,
            body=merged_body,
            model=merged_model,
            expecting=merged_expecting,
            inherit=merged_inherit,
            escalation_condition=merged_escalation,
            meta=merged_meta,
        )

    def _check_prompt_modifier_conflict(
        self,
        _existing: PromptDef,
        new: PromptDef,
        modifier_name: str,
        existing_value: str | None,
        new_value: str | None,
    ) -> bool:
        """Check if two prompt modifier values conflict.

        Args:
            _existing: The existing prompt definition (unused, for context).
            new: The new prompt definition.
            modifier_name: Name of the modifier being checked.
            existing_value: Value from existing definition.
            new_value: Value from new definition.

        Returns:
            True if no conflict, False if conflict (error added).

        """
        if existing_value and new_value and existing_value != new_value:
            self._add_error(
                SemanticError.conflicting_prompt_modifier(
                    name=new.name,
                    modifier=modifier_name,
                    first=existing_value,
                    second=new_value,
                    position=new.meta,
                ),
            )
            return False
        return True

    def _validate_prompts_have_bodies(self) -> None:
        """Validate that all prompts have bodies after merging.

        Report E0013 error for any prompt that has no body definition.
        This catches cases where only declarations exist without a full definition.
        """
        for name, prompt in self._symbols.prompts.items():
            if not prompt.body:
                self._add_error(
                    SemanticError.prompt_missing_body(
                        name=name,
                        position=prompt.meta,
                    ),
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

        # After validating all individual references, detect circular references
        self._detect_circular_agent_refs()

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
        # Strip [] suffix for array types before validating schema reference
        if prompt.expecting is not None:
            schema_name = prompt.expecting.rstrip("[]")
            if schema_name not in self._symbols.schemas:
                self._add_error(
                    SemanticError.undefined_reference(
                        kind="schema",
                        name=schema_name,
                        position=prompt.meta,
                    ),
                )

    def _validate_agent_refs(self, agent: AgentDef) -> None:
        """Validate references in an agent definition."""
        agent_name = agent.name or "default"

        self._validate_agent_instruction(agent, agent_name)
        self._validate_agent_prompt_ref(agent)
        self._validate_agent_tool_refs(agent)
        self._validate_agent_policy_refs(agent)
        self._validate_agent_delegate_refs(agent, agent_name)

    def _validate_agent_instruction(
        self,
        agent: AgentDef,
        agent_name: str,
    ) -> None:
        """Validate agent instruction property."""
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

    def _validate_agent_prompt_ref(self, agent: AgentDef) -> None:
        """Validate agent prompt field references a defined prompt or variable.

        The agent prompt field is resolved at runtime via ctx.resolve(),
        which checks ctx.vars first then prompt definitions. Accept:
        - Defined prompt names
        - Built-in variables (e.g. input_prompt)
        - Produces names from other agents (become variables at runtime)
        """
        if agent.prompt is None:
            return
        if agent.prompt in self._symbols.prompts:
            return
        if agent.prompt in BUILTIN_VARIABLES:
            return
        if self._is_known_produces_name(agent.prompt):
            return
        self._add_error(
            SemanticError.undefined_reference(
                kind="prompt or variable",
                name=agent.prompt,
                position=agent.prompt_meta or agent.meta,
                suggestion=self._suggest_prompt_or_variable(agent.prompt),
            ),
        )

    def _validate_agent_tool_refs(self, agent: AgentDef) -> None:
        """Validate agent tool references."""
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

    def _validate_agent_policy_refs(self, agent: AgentDef) -> None:
        """Validate agent retry and timeout policy references."""
        if agent.retry is not None and agent.retry not in self._symbols.retry_policies:
            self._add_error(
                SemanticError.undefined_reference(
                    kind="retry policy",
                    name=agent.retry,
                    position=agent.meta,
                ),
            )

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

    def _validate_agent_delegate_refs(
        self,
        agent: AgentDef,
        agent_name: str,
    ) -> None:
        """Validate agent delegate and use references."""
        # Check delegate references
        if agent.delegate:
            for delegate_name in agent.delegate:
                if delegate_name not in self._symbols.agents:
                    self._add_error(
                        SemanticError.undefined_reference(
                            kind="agent",
                            name=delegate_name,
                            position=agent.meta,
                            suggestion=self._suggest_similar("agent", delegate_name),
                        ),
                    )

        # Check use references
        if agent.use:
            for use_name in agent.use:
                if use_name not in self._symbols.agents:
                    self._add_error(
                        SemanticError.undefined_reference(
                            kind="agent",
                            name=use_name,
                            position=agent.meta,
                            suggestion=self._suggest_similar("agent", use_name),
                        ),
                    )

        # Warn if agent has both delegate and use
        if agent.delegate and agent.use:
            self._add_error(
                SemanticError.agent_has_both_delegate_and_use(
                    name=agent_name,
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

        # Flows read from ambient context (ctx.vars) -- no parameter scope
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
        elif isinstance(stmt, (ForLoop, IfBlock, MatchBlock, ParallelBlock, LoopBlock)):
            self._validate_control_flow(stmt, scope)
        # Guardrail actions and other statements don't need special handling

    def _validate_assignment(self, stmt: Assignment, scope: Scope) -> None:
        """Validate an assignment statement."""
        self._validate_expression(stmt.value, scope)
        scope.define(name=stmt.target, kind=SymbolKind.VARIABLE)

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
        if stmt.input is not None:
            self._validate_expression(stmt.input, scope)
        if stmt.target is not None:
            scope.define(name=stmt.target, kind=SymbolKind.VARIABLE)
        elif not stmt.is_flow:
            # Auto-define produces variable when agent has produces field
            agent_def = self._symbols.agents.get(stmt.agent)
            if agent_def and agent_def.produces:
                scope.define(name=agent_def.produces, kind=SymbolKind.VARIABLE)
        # Validate escalation handler context
        self._validate_escalation_handler(stmt)

    def _validate_escalation_handler(self, stmt: RunStmt) -> None:
        """Validate escalation handler context for run statements.

        Check that 'on escalate continue' is only used inside a loop context.

        Args:
            stmt: RunStmt node with potential escalation handler.

        """
        if stmt.escalation_handler is None:
            return

        handler = stmt.escalation_handler
        if handler.action == "continue" and self._loop_depth == 0:
            # Get position from handler if available, otherwise from statement
            position = handler.meta if handler.meta else stmt.meta
            self._add_error(
                SemanticError.continue_outside_loop(position=position),
            )

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
        if stmt.input is not None:
            self._validate_expression(stmt.input, scope)
        if stmt.target is not None:
            scope.define(name=stmt.target, kind=SymbolKind.VARIABLE)

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
            if scope.lookup(stmt.target) is None:
                self._add_error(
                    SemanticError.undefined_variable(
                        name=stmt.target,
                        position=stmt.meta,
                    ),
                )

    def _validate_control_flow(
        self,
        stmt: ForLoop | IfBlock | MatchBlock | ParallelBlock | LoopBlock,
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
        elif isinstance(stmt, LoopBlock):
            self._validate_loop_block(stmt, scope)

    def _validate_for_loop(self, stmt: ForLoop, scope: Scope) -> None:
        """Validate a for loop statement."""
        block_scope = Scope(scope_type=ScopeType.BLOCK, parent=scope)
        block_scope.define(name=stmt.variable, kind=SymbolKind.VARIABLE)
        self._validate_expression(stmt.iterable, scope)
        self._loop_depth += 1
        try:
            self._validate_statements(stmt.body, block_scope)
        finally:
            self._loop_depth -= 1

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

    def _validate_loop_block(self, stmt: LoopBlock, scope: Scope) -> None:
        """Validate a loop block statement.

        Args:
            stmt: LoopBlock AST node.
            scope: Current scope for variable resolution.

        """
        block_scope = Scope(scope_type=ScopeType.BLOCK, parent=scope)
        self._loop_depth += 1
        try:
            self._validate_statements(stmt.body, block_scope)
        finally:
            self._loop_depth -= 1

    def _detect_circular_agent_refs(self) -> None:
        """Detect circular references in agent delegate/use relationships.

        Build a directed graph of agent relationships and use DFS to detect
        cycles. Report E0011 error for any circular agent references found.
        """
        graph = self._build_agent_graph()
        cycle = self._find_cycle_in_graph(graph)
        if cycle is not None:
            first_agent = self._symbols.agents.get(cycle[0])
            position = first_agent.meta if first_agent else None
            self._add_error(
                SemanticError.circular_agent_reference(
                    agents=cycle,
                    position=position,
                ),
            )

    def _build_agent_graph(self) -> dict[str, list[str]]:
        """Build adjacency list for agent delegate/use relationships.

        Self-references via ``use`` are filtered out because the ``use``
        pattern wraps an agent as an AgentTool — the LLM chooses when to
        call it, providing natural recursion termination.  Self-references
        via ``delegate`` remain in the graph because delegate transfers
        control unconditionally and is harder to bound.

        Returns:
            Dictionary mapping agent names to their referenced agents.

        """
        graph: dict[str, list[str]] = {}
        for agent_name, agent in self._symbols.agents.items():
            neighbors: list[str] = []
            if agent.delegate:
                neighbors.extend(agent.delegate)
            if agent.use:
                neighbors.extend(
                    name for name in agent.use if name != agent_name
                )
            graph[agent_name] = neighbors
        return graph

    def _find_cycle_in_graph(
        self,
        graph: dict[str, list[str]],
    ) -> list[str] | None:
        """Find a cycle in the agent dependency graph using DFS.

        Args:
            graph: Adjacency list of agent relationships.

        Returns:
            List of agents forming a cycle, or None if no cycle found.

        """
        visited: set[str] = set()
        rec_stack: set[str] = set()

        for agent_name in self._symbols.agents:
            if agent_name not in visited:
                cycle = self._dfs_find_cycle(
                    agent_name,
                    graph,
                    visited,
                    rec_stack,
                    [],
                )
                if cycle is not None:
                    return cycle
        return None

    def _dfs_find_cycle(
        self,
        node: str,
        graph: dict[str, list[str]],
        visited: set[str],
        rec_stack: set[str],
        path: list[str],
    ) -> list[str] | None:
        """DFS helper to find cycles in agent graph.

        Args:
            node: Current node being visited.
            graph: Adjacency list of agent relationships.
            visited: Set of fully visited nodes.
            rec_stack: Set of nodes in current recursion stack.
            path: Current path from root.

        Returns:
            List of agents forming a cycle, or None if no cycle found.

        """
        if node in rec_stack:
            cycle_start = path.index(node)
            return [*path[cycle_start:], node]

        if node in visited:
            return None

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor in self._symbols.agents:
                cycle = self._dfs_find_cycle(
                    neighbor,
                    graph,
                    visited,
                    rec_stack,
                    path,
                )
                if cycle is not None:
                    return cycle

        path.pop()
        rec_stack.remove(node)
        return None

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

    def _is_known_produces_name(self, name: str) -> bool:
        """Check if a name matches any agent's produces field.

        Args:
            name: Name to check.

        Returns:
            True if any agent produces this name.

        """
        return any(
            a.produces == name
            for a in self._symbols.agents.values()
        )

    def _suggest_prompt_or_variable(self, name: str) -> str | None:
        """Suggest similar prompts or variable names.

        Combine prompt names, built-in variables, and produces names
        as candidates for suggestions.

        Args:
            name: Name that was not found.

        Returns:
            Suggestion string or None.

        """
        candidates = list(self._symbols.prompts.keys())
        candidates.extend(BUILTIN_VARIABLES)
        candidates.extend(
            a.produces for a in self._symbols.agents.values() if a.produces
        )
        for candidate in candidates:
            if candidate.lower().startswith(name.lower()[:3]):
                return f"did you mean '{candidate}'?"
        if candidates:
            return (
                f"defined prompts are: "
                f"{', '.join(self._symbols.prompts.keys())}"
            )
        return None
