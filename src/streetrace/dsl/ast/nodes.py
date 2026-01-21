"""AST node dataclasses for Streetrace DSL.

Define typed AST nodes with source position metadata for all DSL constructs.
Each node is a frozen dataclass that can be used for semantic analysis and
code generation.
"""

from dataclasses import dataclass
from typing import Any

from streetrace.log import get_logger

logger = get_logger(__name__)


# =============================================================================
# Base Types and Type Aliases
# =============================================================================


@dataclass
class SourcePosition:
    """Source position information for error reporting."""

    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None


# Type alias for any AST node
AstNode = Any  # Will be refined with Protocol in future


# =============================================================================
# Expression Nodes
# =============================================================================


@dataclass
class VarRef:
    """Variable reference node (e.g., $input, $result)."""

    name: str
    meta: SourcePosition | None = None


@dataclass
class PropertyAccess:
    """Property access node (e.g., $item.value.first)."""

    base: "VarRef | PropertyAccess | NameRef"
    properties: list[str]
    meta: SourcePosition | None = None


@dataclass
class Literal:
    """Literal value node (string, int, float, bool, null)."""

    value: str | int | float | bool | None
    literal_type: str  # "string", "int", "float", "bool", "null"
    meta: SourcePosition | None = None


@dataclass
class BinaryOp:
    """Binary operation node (e.g., $score > 0.5)."""

    op: str  # ">", "<", ">=", "<=", "==", "!=", "and", "or", "contains", "+", "-", etc.
    left: AstNode
    right: AstNode
    meta: SourcePosition | None = None


@dataclass
class UnaryOp:
    """Unary operation node (e.g., not $flag, -$value)."""

    op: str  # "not", "-"
    operand: AstNode
    meta: SourcePosition | None = None


@dataclass
class FunctionCall:
    """Function call node (e.g., lib.convert($item))."""

    name: str
    args: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class ListLiteral:
    """List literal node (e.g., [1, 2, 3])."""

    elements: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class ObjectLiteral:
    """Object literal node (e.g., { success: true, count: 42 })."""

    entries: dict[str, AstNode]
    meta: SourcePosition | None = None


@dataclass
class NameRef:
    """Name reference node for identifiers that aren't variables."""

    name: str
    meta: SourcePosition | None = None


# =============================================================================
# Statement Nodes
# =============================================================================


@dataclass
class Assignment:
    """Assignment statement node (e.g., $x = 42)."""

    target: str
    value: AstNode
    meta: SourcePosition | None = None


@dataclass
class RunStmt:
    """Run statement node for agents and flows.

    Examples:
    - $result = run agent fetch_data $input  (agent call)
    - $goal = run get_agent_goal  (flow call, is_flow=True)
    - run my_workflow  (flow call without assignment)

    """

    target: str | None  # None if no assignment
    agent: str  # Agent or flow name
    args: list[AstNode]
    meta: SourcePosition | None = None
    is_flow: bool = False  # True for flow calls, False for agent calls


@dataclass
class CallStmt:
    """Call LLM statement node (e.g., $goal = call llm analyze_prompt $input)."""

    target: str | None  # None if no assignment
    prompt: str
    args: list[AstNode]
    model: str | None = None  # Optional model override
    meta: SourcePosition | None = None


@dataclass
class ReturnStmt:
    """Return statement node."""

    value: AstNode
    meta: SourcePosition | None = None


@dataclass
class PushStmt:
    """Push statement node (e.g., push $item to $results)."""

    value: AstNode
    target: str
    meta: SourcePosition | None = None


@dataclass
class EscalateStmt:
    """Escalate to human statement node."""

    message: str | None = None
    meta: SourcePosition | None = None


@dataclass
class LogStmt:
    """Log statement node."""

    message: str
    meta: SourcePosition | None = None


@dataclass
class NotifyStmt:
    """Notify statement node."""

    message: str
    meta: SourcePosition | None = None


@dataclass
class ContinueStmt:
    """Continue statement node."""

    meta: SourcePosition | None = None


@dataclass
class AbortStmt:
    """Abort statement node."""

    meta: SourcePosition | None = None


@dataclass
class RetryStepStmt:
    """Retry step statement node."""

    message: AstNode
    meta: SourcePosition | None = None


# =============================================================================
# Control Flow Nodes
# =============================================================================


@dataclass
class ForLoop:
    """For loop node."""

    variable: str
    iterable: AstNode
    body: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class ParallelBlock:
    """Parallel execution block node."""

    body: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class LoopBlock:
    """Loop block for iterative refinement pattern.

    Used to execute a body of statements repeatedly until a condition
    is met or maximum iterations are reached.
    """

    max_iterations: int | None  # None means unbounded loop
    body: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class MatchCase:
    """Match case node (e.g., when "standard" -> ...)."""

    pattern: str
    body: AstNode
    meta: SourcePosition | None = None


@dataclass
class MatchBlock:
    """Match block node."""

    expression: AstNode
    cases: list[MatchCase]
    else_body: AstNode | None = None
    meta: SourcePosition | None = None


@dataclass
class IfBlock:
    """If block node."""

    condition: AstNode
    body: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class FailureBlock:
    """On failure block node."""

    body: list[AstNode]
    meta: SourcePosition | None = None


# =============================================================================
# Guardrail Action Nodes
# =============================================================================


@dataclass
class MaskAction:
    """Mask guardrail action node (e.g., mask pii)."""

    guardrail: str
    meta: SourcePosition | None = None


@dataclass
class BlockAction:
    """Block guardrail action node (e.g., block if jailbreak)."""

    condition: AstNode
    meta: SourcePosition | None = None


@dataclass
class WarnAction:
    """Warn guardrail action node."""

    condition: AstNode | None = None
    message: str | None = None
    contains_expr: AstNode | None = None
    contains_pattern: str | None = None
    meta: SourcePosition | None = None


@dataclass
class RetryAction:
    """Retry guardrail action node (e.g., retry with $message if $condition)."""

    message: AstNode
    condition: AstNode
    meta: SourcePosition | None = None


# =============================================================================
# Type Expression Nodes
# =============================================================================


@dataclass
class TypeExpr:
    """Type expression node for schema fields."""

    base_type: str  # "string", "int", "float", "bool", or custom type name
    is_list: bool = False
    is_optional: bool = False
    meta: SourcePosition | None = None


# =============================================================================
# Top-Level Declaration Nodes
# =============================================================================


@dataclass
class VersionDecl:
    """Version declaration node (e.g., streetrace v1.0)."""

    version: str
    meta: SourcePosition | None = None


@dataclass
class ImportStmt:
    """Import statement node."""

    name: str | None  # None for bare imports like "import ./path.sr"
    source: str
    source_type: str  # "streetrace", "local", "pip", "mcp"
    meta: SourcePosition | None = None


@dataclass
class ModelDef:
    """Model definition node."""

    name: str
    provider_model: str | None = None  # Short form: "anthropic/claude-sonnet"
    properties: dict[str, Any] | None = None  # Long form properties
    meta: SourcePosition | None = None


@dataclass
class SchemaField:
    """Schema field node."""

    name: str
    type_expr: TypeExpr
    meta: SourcePosition | None = None


@dataclass
class SchemaDef:
    """Schema definition node."""

    name: str
    fields: list[SchemaField]
    meta: SourcePosition | None = None


@dataclass
class ToolDef:
    """Tool definition node."""

    name: str
    tool_type: str  # "mcp", "builtin", "ref"
    url: str | None = None
    auth_type: str | None = None  # "bearer", "basic"
    auth_value: str | None = None
    builtin_ref: str | None = None
    ref: str | None = None
    headers: dict[str, str] | None = None
    properties: dict[str, Any] | None = None  # For long form
    meta: SourcePosition | None = None


@dataclass
class AgentDef:
    """Agent definition node."""

    name: str | None  # None for unnamed/default agent
    tools: list[str]
    instruction: str
    retry: str | None = None
    timeout_ref: str | None = None  # Reference to timeout policy
    timeout_value: int | None = None  # Literal timeout value
    timeout_unit: str | None = None  # seconds, minutes, hours
    description: str | None = None
    delegate: list[str] | None = None  # Sub-agents for coordinator pattern
    use: list[str] | None = None  # AgentTool for hierarchical pattern
    meta: SourcePosition | None = None


@dataclass
class PromptDef:
    """Prompt definition node."""

    name: str
    body: str
    model: str | None = None  # using model modifier
    expecting: str | None = None  # expecting modifier (schema name)
    inherit: str | None = None  # inherit modifier (variable)
    meta: SourcePosition | None = None


@dataclass
class FlowDef:
    """Flow definition node."""

    name: str
    params: list[str]
    body: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class EventHandler:
    """Event handler node (on/after start/input/output/tool-call/tool-result)."""

    timing: str  # "on" or "after"
    event_type: str  # "start", "input", "output", "tool-call", "tool-result"
    body: list[AstNode]
    meta: SourcePosition | None = None


@dataclass
class RetryPolicyDef:
    """Retry policy definition node."""

    name: str
    times: int
    backoff_strategy: str | None = None  # "exponential", "linear", "fixed"
    meta: SourcePosition | None = None


@dataclass
class TimeoutPolicyDef:
    """Timeout policy definition node."""

    name: str
    value: int
    unit: str  # "seconds", "minutes", "hours"
    meta: SourcePosition | None = None


@dataclass
class PolicyTrigger:
    """Policy trigger condition."""

    variable: str
    op: str
    value: float | int
    meta: SourcePosition | None = None


@dataclass
class PolicyDef:
    """General policy definition node."""

    name: str
    properties: dict[str, Any]
    meta: SourcePosition | None = None


# =============================================================================
# Root Node
# =============================================================================


@dataclass
class DslFile:
    """Root AST node for a DSL file."""

    version: VersionDecl | None
    statements: list[AstNode]
    meta: SourcePosition | None = None
