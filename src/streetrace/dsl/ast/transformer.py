"""AST transformer for Streetrace DSL.

Transform Lark parse trees into typed AST node structures.
"""

# mypy: disable-error-code="type-arg,no-any-return"
# Note: Lark transformers receive heterogeneous children, making strict typing
# impractical. The type-arg and no-any-return errors are suppressed for this file.

from typing import Any

from lark import Token, Transformer, Tree, v_args

from streetrace.dsl.ast.nodes import (
    AgentDef,
    Assignment,
    BinaryOp,
    BlockAction,
    CallStmt,
    DslFile,
    EscalateStmt,
    EscalationCondition,
    EscalationHandler,
    EventHandler,
    FailureBlock,
    FilterExpr,
    FlowDef,
    ForLoop,
    FunctionCall,
    IfBlock,
    ImplicitProperty,
    ImportStmt,
    ListLiteral,
    Literal,
    LogStmt,
    LoopBlock,
    MaskAction,
    MatchBlock,
    MatchCase,
    ModelDef,
    NameRef,
    NotifyStmt,
    ObjectLiteral,
    ParallelBlock,
    PolicyDef,
    PromptDef,
    PropertyAccess,
    PropertyAssignment,
    PushStmt,
    RetryAction,
    RetryPolicyDef,
    ReturnStmt,
    RunStmt,
    SchemaDef,
    SchemaField,
    SourcePosition,
    TimeoutPolicyDef,
    ToolDef,
    TypeExpr,
    UnaryOp,
    VarRef,
    VersionDecl,
    WarnAction,
)
from streetrace.log import get_logger

logger = get_logger(__name__)


def _get_meta(tree: Tree[Token]) -> SourcePosition | None:
    """Extract source position from Lark tree metadata."""
    if tree.meta and tree.meta.line is not None:
        return SourcePosition(
            line=tree.meta.line,
            column=tree.meta.column,
            end_line=tree.meta.end_line,
            end_column=tree.meta.end_column,
        )
    return None


def _meta_to_position(meta: object) -> SourcePosition | None:
    """Convert Lark meta object to SourcePosition.

    Args:
        meta: Lark meta object with line/column attributes.

    Returns:
        SourcePosition or None if meta has no line info.

    """
    line = getattr(meta, "line", None)
    if meta is not None and line is not None:
        return SourcePosition(
            line=line,
            column=getattr(meta, "column", 0),
            end_line=getattr(meta, "end_line", None),
            end_column=getattr(meta, "end_column", None),
        )
    return None


def _extract_string(value: str | Token) -> str:
    """Extract string value, removing quotes if present."""
    s = str(value)
    # Handle triple-quoted strings FIRST (before single quotes check)
    if s.startswith('"""') and s.endswith('"""'):
        return s[3:-3]
    if s.startswith("'''") and s.endswith("'''"):
        return s[3:-3]
    # Then handle single-quoted strings
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1]
    return s


TUPLE_PAIR_LENGTH = 2
"""Expected length for key-value tuple pairs."""

BINARY_OP_LENGTH = 3
"""Expected number of items in a binary operation (left, op, right)."""

PROMPT_BODY_MIN_LENGTH = 50
"""Minimum length to consider a string as prompt body rather than name."""

# Type alias for transformer pass-through return type
AstNode = object
"""Type alias for any AST node returned from transformer methods."""

# Type alias for transformer method items parameter
# Using Any because Lark transformers receive heterogeneous children
TransformerItems = list[Any]
"""Type alias for transformer method input items list."""

# Tokens to ignore when extracting meaningful children
NOISE_TOKENS = frozenset(
    {
        "_NL",
        "_INDENT",
        "_DEDENT",
        "COLON",
        "LPAR",
        "RPAR",
        "LSQB",
        "RSQB",
        "LBRACE",
        "RBRACE",
        "COMMA",
        "EQUAL",
        "ARROW",
        "DOLLAR",
        # Model property keywords that precede the actual value
        "PROVIDER",
        "TEMPERATURE",
        "MAX_TOKENS",
        # Question mark for optional types
        "QMARK",
    },
)


def _filter_children(items: TransformerItems) -> list:
    """Filter out noise tokens from children list."""
    result = []
    for item in items:
        if isinstance(item, Token):
            if item.type in NOISE_TOKENS:
                continue
            # Also skip anonymous literal tokens for keywords
            if item.type.startswith("__ANON"):
                # Keep the value, these are typically type names
                result.append(str(item))
                continue
            # Skip keyword tokens that were kept but are just syntax
            if item.type in {
                "SCHEMA",
                "MODEL",
                "TOOL",
                "AGENT",
                "FLOW",
                "PROMPT",
                "POLICY",
                "RETRY",
                "TIMEOUT",
                "IMPORT",
                "FROM",
                "ON",
                "AFTER",
                "DO",
                "END",
                "IF",
                "FOR",
                "IN",
                "PARALLEL",
                "MATCH",
                "WHEN",
                "ELSE",
                "RETURN",
                "PUSH",
                "TO",
                "RUN",
                "CALL",
                "LLM",
                "BLOCK",
                "MASK",
                "WARN",
                "WITH",
                "AUTH",
                "BEARER",
                "BASIC",
                "BUILTIN",
                "MCP",
                "USING",
                "EXPECTING",
                "INHERIT",
                "TIMES",
                "BACKOFF",
                "EXPONENTIAL",
                "LINEAR",
                "FIXED",
                "SECONDS",
                "MINUTES",
                "HOURS",
                "TRIGGER",
                "STRATEGY",
                "PRESERVE",
                "LAST",
                "MESSAGES",
                "RESULTS",
                "ESCALATE",
                "HUMAN",
                "LOG",
                "NOTIFY",
                "CONTINUE",
                "ABORT",
                "STEP",
                "FAILURE",
                "INITIAL",
                "USER",
                "DETECT",
                "GET",
                "GOAL",
                "PROCESS",
                "AND",
                "OR",
                "NOT",
                "CONTAINS",
                "TRUE",
                "FALSE",
                "NULL",
                "STREETRACE",
                "DESCRIPTION",
                "TOOLS",
                "INSTRUCTION",
                "PRODUCES",
                "FILTER",
                "WHERE",
            }:
                continue
        result.append(item)
    return result


def _get_token_value(token: Token | str) -> str:
    """Get the string value from a token."""
    if isinstance(token, Token):
        return str(token.value)
    return str(token)


class AstTransformer(Transformer):
    """Transform Lark parse tree to AST nodes."""

    # =========================================================================
    # Terminals
    # =========================================================================

    def NAME(self, token: Token) -> str:  # noqa: N802
        """Transform NAME token."""
        return str(token)

    def STRING(self, token: Token) -> str:  # noqa: N802
        """Transform STRING token, removing quotes."""
        return _extract_string(token)

    def INT(self, token: Token) -> int:  # noqa: N802
        """Transform INT token."""
        return int(token)

    def NUMBER(self, token: Token) -> float:  # noqa: N802
        """Transform NUMBER token."""
        return float(token)

    def VERSION(self, token: Token) -> str:  # noqa: N802
        """Transform VERSION token."""
        return str(token)

    def PROVIDER_MODEL(self, token: Token) -> str:  # noqa: N802
        """Transform PROVIDER_MODEL token."""
        return str(token)

    def DOTTED_NAME(self, token: Token) -> str:  # noqa: N802
        """Transform DOTTED_NAME token."""
        return str(token)

    def TRIPLE_QUOTED_STRING(self, token: Token) -> str:  # noqa: N802
        """Transform TRIPLE_QUOTED_STRING token."""
        return _extract_string(token)

    def LOCAL_PATH(self, token: Token) -> str:  # noqa: N802
        """Transform LOCAL_PATH token."""
        return str(token)

    def PIP_URI(self, token: Token) -> str:  # noqa: N802
        """Transform PIP_URI token."""
        return str(token)

    def MCP_URI(self, token: Token) -> str:  # noqa: N802
        """Transform MCP_URI token."""
        return str(token)

    def INTERPOLATED_STRING(self, token: Token) -> str:  # noqa: N802
        """Transform INTERPOLATED_STRING token."""
        return _extract_string(token)

    # =========================================================================
    # Start rule
    # =========================================================================

    def start(self, items: TransformerItems) -> DslFile:
        """Transform start rule."""
        filtered = _filter_children(items)
        version = None
        statements = []

        for item in filtered:
            if item is None:
                continue
            if isinstance(item, VersionDecl):
                version = item
            elif not isinstance(item, (str, Token)):
                statements.append(item)

        return DslFile(version=version, statements=statements)

    # =========================================================================
    # Version
    # =========================================================================

    def version_decl(self, items: TransformerItems) -> VersionDecl:
        """Transform version_decl rule."""
        filtered = _filter_children(items)
        version = "v1"
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            # Look for version pattern like v1, v1.2
            if val.startswith("v") and any(c.isdigit() for c in val):
                version = val
                break
        return VersionDecl(version=version)

    # =========================================================================
    # Statements / Top-level constructs
    # =========================================================================

    def statement(self, items: TransformerItems) -> AstNode:
        """Transform statement rule - pass through child."""
        return items[0] if items else None

    # =========================================================================
    # Imports
    # =========================================================================

    def import_stmt(self, items: TransformerItems) -> ImportStmt:
        """Transform import_stmt rule."""
        filtered = _filter_children(items)
        name = None
        source_info = None

        for item in filtered:
            if isinstance(item, dict):
                source_info = item
            elif isinstance(item, str):
                name = item
            elif isinstance(item, Token):
                name = _get_token_value(item)

        if source_info is None:
            # No source found, use name as source (bare import)
            return ImportStmt(
                name=None,
                source=name or "",
                source_type="local",
            )

        return ImportStmt(
            name=name,
            source=source_info["source"],
            source_type=source_info["type"],
        )

    def import_streetrace(self, _items: TransformerItems) -> dict:
        """Transform import_streetrace rule."""
        return {"source": "streetrace", "type": "streetrace"}

    def import_local(self, items: TransformerItems) -> dict:
        """Transform import_local rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"source": item, "type": "local"}
            if isinstance(item, Token):
                return {"source": _get_token_value(item), "type": "local"}
        return {"source": "", "type": "local"}

    def import_pip(self, items: TransformerItems) -> dict:
        """Transform import_pip rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"source": item, "type": "pip"}
            if isinstance(item, Token):
                return {"source": _get_token_value(item), "type": "pip"}
        return {"source": "", "type": "pip"}

    def import_mcp(self, items: TransformerItems) -> dict:
        """Transform import_mcp rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"source": item, "type": "mcp"}
            if isinstance(item, Token):
                return {"source": _get_token_value(item), "type": "mcp"}
        return {"source": "", "type": "mcp"}

    # =========================================================================
    # Models
    # =========================================================================

    @v_args(meta=True)
    def model_short(self, meta: object, items: TransformerItems) -> ModelDef:
        """Transform model_short rule."""
        filtered = _filter_children(items)
        name = None
        model_ref = None
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if "/" in val:  # Provider/model format
                model_ref = val
            elif name is None:
                name = val
        return ModelDef(
            name=name or "",
            provider_model=model_ref,
            meta=_meta_to_position(meta),
        )

    @v_args(meta=True)
    def model_long(self, meta: object, items: TransformerItems) -> ModelDef:
        """Transform model_long rule."""
        filtered = _filter_children(items)
        name = None
        properties = {}
        for item in filtered:
            if isinstance(item, dict):
                properties = item
            elif isinstance(item, (str, Token)):
                val = _get_token_value(item) if isinstance(item, Token) else item
                if name is None and val:
                    name = val
        return ModelDef(
            name=name or "",
            properties=properties,
            meta=_meta_to_position(meta),
        )

    def model_ref(self, items: TransformerItems) -> str:
        """Transform model_ref rule."""
        filtered = _filter_children(items)
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if val:
                return val
        return ""

    def model_body(self, items: TransformerItems) -> dict:
        """Transform model_body rule."""
        props = {}
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, dict):
                props.update(item)
        return props

    def model_provider(self, items: TransformerItems) -> dict:
        """Transform model_provider rule."""
        filtered = _filter_children(items)
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if val:
                return {"provider": val}
        return {}

    def model_name(self, items: TransformerItems) -> dict:
        """Transform model_name rule."""
        filtered = _filter_children(items)
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if val:
                return {"name": val}
        return {}

    def model_temperature(self, items: TransformerItems) -> dict:
        """Transform model_temperature rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, (int, float)):
                return {"temperature": item}
            if isinstance(item, Token):
                try:
                    return {"temperature": float(item)}
                except ValueError:
                    continue
        return {}

    def model_max_tokens(self, items: TransformerItems) -> dict:
        """Transform model_max_tokens rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, int):
                return {"max_tokens": item}
            if isinstance(item, Token):
                try:
                    return {"max_tokens": int(item)}
                except ValueError:
                    continue
        return {}

    # =========================================================================
    # Schemas
    # =========================================================================

    @v_args(meta=True)
    def schema_def(self, meta: object, items: TransformerItems) -> SchemaDef:
        """Transform schema_def rule."""
        filtered = _filter_children(items)
        name = None
        fields = []
        for item in filtered:
            if isinstance(item, list):
                fields = [f for f in item if isinstance(f, SchemaField)]
            elif isinstance(item, (str, Token)):
                val = _get_token_value(item) if isinstance(item, Token) else item
                if name is None and val:
                    name = val
        return SchemaDef(name=name or "", fields=fields, meta=_meta_to_position(meta))

    def schema_body(self, items: TransformerItems) -> list[SchemaField]:
        """Transform schema_body rule."""
        filtered = _filter_children(items)
        return [item for item in filtered if isinstance(item, SchemaField)]

    def schema_field(self, items: TransformerItems) -> SchemaField:
        """Transform schema_field rule."""
        filtered = _filter_children(items)
        field_name = None
        type_expr = None
        for item in filtered:
            if isinstance(item, TypeExpr):
                type_expr = item
            elif isinstance(item, (str, Token)):
                val = _get_token_value(item) if isinstance(item, Token) else item
                if field_name is None and val:
                    field_name = val
        return SchemaField(
            name=field_name or "",
            type_expr=type_expr or TypeExpr(base_type="unknown"),
        )

    def field_name(self, items: TransformerItems) -> str:
        """Transform field_name rule."""
        filtered = _filter_children(items)
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if val:
                return val
        return ""

    def type_expr(self, items: TransformerItems) -> TypeExpr:
        """Transform type_expr rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, TypeExpr):
                return item
        return TypeExpr(base_type="unknown")

    def simple_type(self, items: TransformerItems) -> TypeExpr:
        """Transform simple_type rule."""
        # Items contain the type token (BOOL, STRING, etc. or NAME for custom types)
        for item in items:
            if isinstance(item, Token):
                # The token value is the type name (bool, string, int, etc.)
                return TypeExpr(base_type=str(item))
            if isinstance(item, str):
                return TypeExpr(base_type=item)
        return TypeExpr(base_type="unknown")

    def list_type(self, items: TransformerItems) -> TypeExpr:
        """Transform list_type rule."""
        filtered = _filter_children(items)
        inner_type = None
        for item in filtered:
            if isinstance(item, TypeExpr):
                inner_type = item
                break
        if inner_type is None:
            inner_type = TypeExpr(base_type="unknown")
        return TypeExpr(
            base_type=inner_type.base_type,
            is_list=True,
            is_optional=inner_type.is_optional,
        )

    def optional_type(self, items: TransformerItems) -> TypeExpr:
        """Transform optional_type rule."""
        filtered = _filter_children(items)
        inner_type = None
        for item in filtered:
            if isinstance(item, TypeExpr):
                inner_type = item
                break
        if inner_type is None:
            inner_type = TypeExpr(base_type="unknown")
        return TypeExpr(
            base_type=inner_type.base_type,
            is_list=inner_type.is_list,
            is_optional=True,
        )

    # =========================================================================
    # Tools
    # =========================================================================

    @v_args(meta=True)
    def tool_short(self, meta: object, items: TransformerItems) -> ToolDef:
        """Transform tool_short rule."""
        filtered = _filter_children(items)
        name = None
        tool_info = {}
        for item in filtered:
            if isinstance(item, dict):
                tool_info = item
            elif isinstance(item, str):
                name = item
            elif isinstance(item, Token):
                name = _get_token_value(item)
        return ToolDef(name=name or "", meta=_meta_to_position(meta), **tool_info)

    @v_args(meta=True)
    def tool_long(self, meta: object, items: TransformerItems) -> ToolDef:
        """Transform tool_long rule."""
        filtered = _filter_children(items)
        name = None
        properties = {}
        for item in filtered:
            if isinstance(item, dict):
                properties = item
            elif isinstance(item, str):
                name = item
            elif isinstance(item, Token):
                name = _get_token_value(item)
        return ToolDef(
            name=name or "",
            tool_type=properties.get("type", "mcp"),
            url=properties.get("url"),
            headers=properties.get("headers"),
            properties=properties,
            meta=_meta_to_position(meta),
        )

    def tool_short_expr(self, items: TransformerItems) -> AstNode:
        """Transform tool_short_expr rule - pass through."""
        return items[0]

    def tool_mcp(self, items: TransformerItems) -> dict:
        """Transform tool_mcp rule."""
        filtered = _filter_children(items)
        url = None
        options = {}
        for item in filtered:
            if isinstance(item, dict):
                options = item
            elif isinstance(item, str):
                url = item
            elif isinstance(item, Token):
                url = _get_token_value(item)
        return {
            "tool_type": "mcp",
            "url": url,
            "auth_type": options.get("auth_type"),
            "auth_value": options.get("auth_value"),
        }

    def tool_builtin(self, items: TransformerItems) -> dict:
        """Transform tool_builtin rule."""
        filtered = _filter_children(items)
        ref = None
        for item in filtered:
            if isinstance(item, str):
                ref = item
            elif isinstance(item, Token):
                ref = _get_token_value(item)
        return {"tool_type": "builtin", "builtin_ref": ref}

    def tool_ref(self, items: TransformerItems) -> dict:
        """Transform tool_ref rule."""
        filtered = _filter_children(items)
        ref = None
        for item in filtered:
            if isinstance(item, str):
                ref = item
            elif isinstance(item, Token):
                ref = _get_token_value(item)
        return {"tool_type": "ref", "ref": ref}

    def tool_options(self, items: TransformerItems) -> dict:
        """Transform tool_options rule."""
        result = {}
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, dict):
                result.update(item)
        return result

    def tool_option(self, items: TransformerItems) -> AstNode:
        """Transform tool_option rule - pass through."""
        filtered = _filter_children(items)
        return filtered[0] if filtered else {}

    def tool_auth_bearer(self, items: TransformerItems) -> dict:
        """Transform tool_auth_bearer rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"auth_type": "bearer", "auth_value": item}
            if isinstance(item, Token):
                return {"auth_type": "bearer", "auth_value": _get_token_value(item)}
        return {"auth_type": "bearer", "auth_value": ""}

    def tool_auth_basic(self, items: TransformerItems) -> dict:
        """Transform tool_auth_basic rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"auth_type": "basic", "auth_value": item}
            if isinstance(item, Token):
                return {"auth_type": "basic", "auth_value": _get_token_value(item)}
        return {"auth_type": "basic", "auth_value": ""}

    def tool_custom_option(self, items: TransformerItems) -> dict:
        """Transform tool_custom_option rule."""
        return {items[0]: items[1]}

    def tool_body(self, items: TransformerItems) -> dict:
        """Transform tool_body rule."""
        result = {}
        for item in items:
            if item:
                result.update(item)
        return result

    def tool_property(self, items: TransformerItems) -> AstNode:
        """Transform tool_property rule - pass through."""
        return items[0]

    def tool_type(self, items: TransformerItems) -> dict:
        """Transform tool_type rule."""
        return {"type": items[0]}

    def tool_url(self, items: TransformerItems) -> dict:
        """Transform tool_url rule."""
        return {"url": items[0]}

    def tool_headers(self, items: TransformerItems) -> dict:
        """Transform tool_headers rule."""
        return {"headers": items[0]}

    def tool_type_name(self, items: TransformerItems) -> str:
        """Transform tool_type_name rule."""
        return items[0]

    def header_list(self, items: TransformerItems) -> dict:
        """Transform header_list rule."""
        headers = {}
        for item in items:
            if isinstance(item, dict):
                headers.update(item)
        return headers

    def header_entry(self, items: TransformerItems) -> dict:
        """Transform header_entry rule."""
        return {items[0]: items[1]}

    # =========================================================================
    # Retry and Timeout Policies
    # =========================================================================

    def retry_policy_def(self, items: TransformerItems) -> RetryPolicyDef:
        """Transform retry_policy_def rule."""
        filtered = _filter_children(items)
        name = None
        times = None
        backoff = None

        for item in filtered:
            if isinstance(item, int):
                times = item
            elif isinstance(item, str):
                # Backoff strategy
                if item in {"exponential", "linear", "fixed"}:
                    backoff = item
                elif name is None:
                    name = item
            elif isinstance(item, Token):
                val = _get_token_value(item)
                if name is None:
                    name = val

        return RetryPolicyDef(
            name=name or "",
            times=times or 1,
            backoff_strategy=backoff,
        )

    def backoff_exponential(self, _items: TransformerItems) -> str:
        """Transform backoff_exponential rule."""
        return "exponential"

    def backoff_linear(self, _items: TransformerItems) -> str:
        """Transform backoff_linear rule."""
        return "linear"

    def backoff_fixed(self, _items: TransformerItems) -> str:
        """Transform backoff_fixed rule."""
        return "fixed"

    def timeout_policy_def(self, items: TransformerItems) -> TimeoutPolicyDef:
        """Transform timeout_policy_def rule."""
        filtered = _filter_children(items)
        name = None
        value = None
        unit = "seconds"

        for item in filtered:
            if isinstance(item, int):
                value = item
            elif isinstance(item, str):
                # Time unit
                if item in {"seconds", "minutes", "hours"}:
                    unit = item
                elif name is None:
                    name = item
            elif isinstance(item, Token):
                val = _get_token_value(item)
                if name is None:
                    name = val

        return TimeoutPolicyDef(
            name=name or "",
            value=value or 0,
            unit=unit,
        )

    def time_unit(self, items: TransformerItems) -> str:
        """Transform time_unit rule."""
        # The time unit is a keyword token like SECONDS, MINUTES, HOURS
        for item in items:
            if isinstance(item, Token):
                return str(item).lower()
            if isinstance(item, str):
                return item.lower()
        return "seconds"  # Default

    # =========================================================================
    # Policies
    # =========================================================================

    def policy_def(self, items: TransformerItems) -> PolicyDef:
        """Transform policy_def rule."""
        filtered = _filter_children(items)
        name = None
        body: dict = {}

        for item in filtered:
            if isinstance(item, str) and name is None:
                name = item
            elif isinstance(item, dict):
                body = item

        return PolicyDef(name=name or "", properties=body)

    def policy_body(self, items: TransformerItems) -> dict:
        """Transform policy_body rule."""
        props = {}
        for item in items:
            if item:
                props.update(item)
        return props

    def policy_property(self, items: TransformerItems) -> dict:
        """Transform policy_property rule.

        Handle the different policy property alternatives:
        - trigger: policy_trigger
        - strategy: identifier
        - preserve: preserve_list
        - use model: interpolated_string
        """
        # First, identify the property type from tokens BEFORE filtering
        property_type = self._identify_policy_property_type(items)

        # Now filter the children
        filtered = _filter_children(items)
        if not filtered:
            return {}

        # Find the value based on property type
        return self._extract_policy_property_value(filtered, property_type)

    def _identify_policy_property_type(self, items: TransformerItems) -> str | None:
        """Identify the policy property type from tokens.

        Args:
            items: Raw transformer items before filtering.

        Returns:
            The property type string or None if not recognized.

        """
        # Map token types to property names
        token_to_property = {
            "TRIGGER": "trigger",
            "STRATEGY": "strategy",
            "PRESERVE": "preserve",
        }
        # USE token maps to use_model property (not a password)
        use_model_token = "USE"  # noqa: S105  # nosec B105

        for item in items:
            if isinstance(item, Token):
                token_type = item.type
                if token_type in token_to_property:
                    return token_to_property[token_type]
                if token_type == use_model_token:
                    return "use_model"
        return None

    def _extract_policy_property_value(
        self,
        filtered: list,
        property_type: str | None,
    ) -> dict:
        """Extract the property value from filtered items.

        Args:
            filtered: Filtered list of children.
            property_type: The identified property type or None.

        Returns:
            Dictionary with the property type as key and value.

        """
        for item in filtered:
            if isinstance(item, dict):
                # Already a dict (from policy_trigger or preserve_list)
                return item
            if isinstance(item, str) and property_type:
                # This is the value for the identified property type
                return {property_type: item}

        # Fallback for unrecognized property types
        strings = [x for x in filtered if isinstance(x, str)]
        min_strings_for_key_value = 2
        if len(strings) >= min_strings_for_key_value:
            return {strings[0]: strings[1]}
        if strings:
            return {"value": strings[0]}

        return {}

    def policy_custom(self, items: TransformerItems) -> dict:
        """Transform policy_custom rule."""
        return {items[0]: items[1]}

    def policy_trigger(self, items: TransformerItems) -> dict:
        """Transform policy_trigger rule."""
        var = items[0]
        op = items[1]
        value = items[2]
        return {"trigger": {"var": var, "op": op, "value": value}}

    def preserve_list(self, items: TransformerItems) -> dict:
        """Transform preserve_list rule.

        Filter out syntax tokens (brackets, commas) and keep only
        the actual preserve items.
        """
        filtered = _filter_children(items)
        result = [item for item in filtered if item is not None]
        return {"preserve": result}

    def preserve_item(self, items: TransformerItems) -> str | VarRef | dict:
        """Transform preserve_item rule.

        Handle different preserve item types:
        - variable ($goal)
        - last N messages
        - tool results
        - string literal
        """
        filtered = _filter_children(items)
        if not filtered:
            return {}

        # Check for "last N messages" pattern
        has_last = any(
            isinstance(item, Token) and item.type == "LAST" for item in items
        )
        has_messages = any(
            isinstance(item, Token) and item.type == "MESSAGES" for item in items
        )
        if has_last and has_messages:
            # Extract the number
            for item in filtered:
                if isinstance(item, (int, float)):
                    return {"last_messages": int(item)}
            return {"last_messages": 5}  # Default

        # Check for "tool results" pattern
        has_tool = any(
            isinstance(item, Token) and item.type == "TOOL" for item in items
        )
        has_results = any(
            isinstance(item, Token) and item.type == "RESULTS" for item in items
        )
        if has_tool and has_results:
            return {"tool_results": True}

        # Return first item (VarRef or string)
        return filtered[0] if filtered else {}

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def event_handler(self, items: TransformerItems) -> EventHandler:
        """Transform event_handler rule."""
        filtered = _filter_children(items)
        timing = None
        event_type = None
        body = []

        for item in filtered:
            if isinstance(item, str):
                # timing or event_type
                if item in {"on", "after"}:
                    timing = item
                elif item in {"start", "input", "output", "tool-call", "tool-result"}:
                    event_type = item
            elif isinstance(item, list):
                body = item
            elif isinstance(item, (MaskAction, BlockAction, WarnAction, RetryAction)):
                body.append(item)

        return EventHandler(
            timing=timing or "on",
            event_type=event_type or "input",
            body=body,
        )

    def timing_on(self, _items: TransformerItems) -> str:
        """Transform timing_on rule."""
        return "on"

    def timing_after(self, _items: TransformerItems) -> str:
        """Transform timing_after rule."""
        return "after"

    def event_start(self, _items: TransformerItems) -> str:
        """Transform event_start rule."""
        return "start"

    def event_input(self, _items: TransformerItems) -> str:
        """Transform event_input rule."""
        return "input"

    def event_output(self, _items: TransformerItems) -> str:
        """Transform event_output rule."""
        return "output"

    def event_tool_call(self, _items: TransformerItems) -> str:
        """Transform event_tool_call rule."""
        return "tool-call"

    def event_tool_result(self, _items: TransformerItems) -> str:
        """Transform event_tool_result rule."""
        return "tool-result"

    def handler_body(self, items: TransformerItems) -> list:
        """Transform handler_body rule."""
        return [item for item in items if item is not None]

    def handler_statement(self, items: TransformerItems) -> AstNode:
        """Transform handler_statement rule - pass through."""
        return items[0] if items else None

    # =========================================================================
    # Guardrail Actions
    # =========================================================================

    def guardrail_action(self, items: TransformerItems) -> AstNode:
        """Transform guardrail_action rule - pass through."""
        return items[0]

    def mask_action(self, items: TransformerItems) -> MaskAction:
        """Transform mask_action rule."""
        return MaskAction(guardrail=items[0])

    def block_action(self, items: TransformerItems) -> BlockAction:
        """Transform block_action rule.

        Handle the form: "block" "if" condition
        The first items may be the BLOCK and IF tokens due to keep_all_tokens=True.
        """
        filtered = _filter_children(items)
        # After filtering, we should have the condition expression
        condition = filtered[0] if filtered else None
        return BlockAction(condition=condition)

    def warn_action(self, items: TransformerItems) -> WarnAction:
        """Transform warn_action rule.

        Handle the form: "warn" "if" condition
        The first items may be the WARN and IF tokens due to keep_all_tokens=True.
        """
        filtered = _filter_children(items)
        # Check what we have after filtering tokens
        if len(filtered) == 1:
            item = filtered[0]
            if isinstance(item, str):
                return WarnAction(message=item)
            return WarnAction(condition=item)
        # "warn if expr contains string" case
        if len(filtered) == TUPLE_PAIR_LENGTH:
            return WarnAction(contains_expr=filtered[0], contains_pattern=filtered[1])
        return WarnAction(condition=filtered[0] if filtered else None)

    def retry_action(self, items: TransformerItems) -> RetryAction:
        """Transform retry_action rule."""
        if len(items) >= TUPLE_PAIR_LENGTH:
            return RetryAction(message=items[0], condition=items[1])
        return RetryAction(message=items[0], condition=None)

    # =========================================================================
    # Flows
    # =========================================================================

    @v_args(meta=True)
    def flow_def(self, meta: object, items: TransformerItems) -> FlowDef:
        """Transform flow_def rule."""
        filtered = _filter_children(items)
        name, body = self._extract_flow_components(filtered)
        return FlowDef(
            name=name or "",
            body=body,
            meta=_meta_to_position(meta),
        )

    def _extract_flow_components(
        self,
        filtered: list,
    ) -> tuple[str | None, list]:
        """Extract name and body from flow_def children."""
        name = None
        body: list = []

        for item in filtered:
            if isinstance(item, (str, Token)):
                if name is None:
                    name = _get_token_value(item) if isinstance(item, Token) else item
            elif isinstance(item, list):
                body = item
            elif item not in body:
                body.append(item)

        return name, body

    def flow_name(self, items: TransformerItems) -> str:
        """Transform flow_name rule."""
        return " ".join(str(item) for item in items)

    def flow_body(self, items: TransformerItems) -> list:
        """Transform flow_body rule."""
        return [item for item in items if item is not None]

    def flow_statement(self, items: TransformerItems) -> AstNode:
        """Transform flow_statement rule - pass through."""
        return items[0] if items else None

    def expression_stmt(self, items: TransformerItems) -> AstNode:
        """Transform expression_stmt rule - pass through."""
        return items[0] if items else None

    # =========================================================================
    # Agents
    # =========================================================================

    @v_args(meta=True)
    def agent_def(self, meta: object, items: TransformerItems) -> AgentDef:
        """Transform agent_def rule."""
        filtered = _filter_children(items)
        name = None
        body = {}

        for item in filtered:
            if isinstance(item, dict):
                body = item
            elif isinstance(item, (str, Token)) and not isinstance(item, dict):
                # This could be the agent name
                val = _get_token_value(item) if isinstance(item, Token) else item
                if val not in {"agent", ":", ""}:
                    name = val

        return AgentDef(
            name=name,
            tools=body.get("tools", []),
            instruction=body.get("instruction", ""),
            retry=body.get("retry"),
            timeout_ref=body.get("timeout_ref"),
            timeout_value=body.get("timeout_value"),
            timeout_unit=body.get("timeout_unit"),
            description=body.get("description"),
            delegate=body.get("delegate"),
            use=body.get("use"),
            prompt=body.get("prompt"),
            prompt_meta=body.get("prompt_meta"),
            produces=body.get("produces"),
            meta=_meta_to_position(meta),
        )

    def agent_body(self, items: TransformerItems) -> dict:
        """Transform agent_body rule."""
        result = {}
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, dict):
                result.update(item)
        return result

    def agent_property(self, items: TransformerItems) -> AstNode:
        """Transform agent_property rule - pass through."""
        filtered = _filter_children(items)
        return filtered[0] if filtered else {}

    def agent_tools(self, items: TransformerItems) -> dict:
        """Transform agent_tools rule."""
        filtered = _filter_children(items)
        tools = []
        for item in filtered:
            if isinstance(item, list):
                tools = item
            elif isinstance(item, (str, Token)):
                val = _get_token_value(item) if isinstance(item, Token) else item
                if val:
                    tools.append(val)
        return {"tools": tools}

    def agent_instruction(self, items: TransformerItems) -> dict:
        """Transform agent_instruction rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"instruction": item}
            if isinstance(item, Token):
                return {"instruction": _get_token_value(item)}
        return {"instruction": ""}

    @v_args(meta=True)
    def agent_prompt(self, meta: object, items: TransformerItems) -> dict:
        """Transform agent_prompt rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"prompt": item, "prompt_meta": _meta_to_position(meta)}
            if isinstance(item, Token):
                return {
                    "prompt": _get_token_value(item),
                    "prompt_meta": _meta_to_position(meta),
                }
        return {}

    def agent_produces(self, items: TransformerItems) -> dict:
        """Transform agent_produces rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"produces": item}
            if isinstance(item, Token):
                return {"produces": _get_token_value(item)}
        return {}

    def agent_retry(self, items: TransformerItems) -> dict:
        """Transform agent_retry rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"retry": item}
            if isinstance(item, Token):
                return {"retry": _get_token_value(item)}
        return {}

    def agent_timeout(self, items: TransformerItems) -> dict:
        """Transform agent_timeout rule."""
        filtered = _filter_children(items)
        return filtered[0] if filtered and isinstance(filtered[0], dict) else {}

    def agent_description(self, items: TransformerItems) -> dict:
        """Transform agent_description rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"description": item}
            if isinstance(item, Token):
                return {"description": _get_token_value(item)}
        return {}

    def agent_delegate(self, items: TransformerItems) -> dict:
        """Transform agent_delegate rule.

        Extract list of sub-agent names for the coordinator pattern.
        """
        filtered = _filter_children(items)
        delegate = []
        for item in filtered:
            if isinstance(item, list):
                delegate = item
            elif isinstance(item, (str, Token)):
                val = _get_token_value(item) if isinstance(item, Token) else item
                if val:
                    delegate.append(val)
        return {"delegate": delegate}

    def agent_use(self, items: TransformerItems) -> dict:
        """Transform agent_use rule.

        Extract list of agent names for hierarchical pattern (AgentTool).
        """
        filtered = _filter_children(items)
        use = []
        for item in filtered:
            if isinstance(item, list):
                use = item
            elif isinstance(item, (str, Token)):
                val = _get_token_value(item) if isinstance(item, Token) else item
                if val:
                    use.append(val)
        return {"use": use}

    def timeout_ref(self, items: TransformerItems) -> dict:
        """Transform timeout_ref rule."""
        return {"timeout_ref": items[0]}

    def timeout_literal(self, items: TransformerItems) -> dict:
        """Transform timeout_literal rule."""
        return {"timeout_value": items[0], "timeout_unit": items[1]}

    def name_list(self, items: TransformerItems) -> list[str]:
        """Transform name_list rule.

        Filter out comma tokens from the list, keeping only actual tool names.
        """
        filtered = _filter_children(items)
        result = []
        for item in filtered:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, Token):
                # Token objects that made it past _filter_children are tool names
                result.append(_get_token_value(item))
        return result

    def tool_name(self, items: TransformerItems) -> str:
        """Transform tool_name rule."""
        return items[0]

    # =========================================================================
    # Prompts
    # =========================================================================

    @v_args(meta=True)
    def prompt_decl(self, meta: object, items: TransformerItems) -> PromptDef:
        """Transform prompt_decl rule (declaration without body).

        Creates a PromptDef with empty body for forward declarations.
        Multiple definitions of the same prompt are merged during semantic analysis.
        """
        return self._create_prompt_def(meta, items)

    @v_args(meta=True)
    def prompt_full(self, meta: object, items: TransformerItems) -> PromptDef:
        """Transform prompt_full rule (full definition with body).

        Creates a PromptDef with body text for complete definitions.
        """
        return self._create_prompt_def(meta, items)

    def _create_prompt_def(self, meta: object, items: TransformerItems) -> PromptDef:
        """Create a PromptDef from parsed items.

        Shared implementation for both prompt_decl and prompt_full rules.
        """
        filtered = _filter_children(items)
        name, body, modifiers, escalation = self._extract_prompt_components(filtered)

        return PromptDef(
            name=name or "",
            body=body.strip() if body else "",
            model=modifiers.get("model"),
            expecting=modifiers.get("expecting"),
            inherit=modifiers.get("inherit"),
            escalation_condition=escalation,
            meta=_meta_to_position(meta),
        )

    def _extract_prompt_components(
        self,
        filtered: list,
    ) -> tuple[str | None, str | None, dict, EscalationCondition | None]:
        """Extract name, body, modifiers, and escalation from prompt_def children."""
        name = None
        body = None
        modifiers: dict = {}
        escalation: EscalationCondition | None = None

        for item in filtered:
            if isinstance(item, str):
                name, body = self._categorize_prompt_string(item, name, body)
            elif isinstance(item, Token):
                if name is None:
                    name = _get_token_value(item)
            elif isinstance(item, dict):
                modifiers.update(item)
            elif isinstance(item, EscalationCondition):
                escalation = item

        return name, body, modifiers, escalation

    def _categorize_prompt_string(
        self,
        item: str,
        name: str | None,
        body: str | None,
    ) -> tuple[str | None, str | None]:
        """Categorize a string as either name or body."""
        # If string has newlines or is long, it's definitely a body
        if "\n" in item or len(item) > PROMPT_BODY_MIN_LENGTH:
            return name, item.strip()
        # If we don't have a name yet, this is the name
        if name is None:
            return item, body
        # If we already have a name and no body, this is the body
        if body is None:
            return name, item.strip()
        return name, body

    def prompt_modifiers(self, items: TransformerItems) -> dict:
        """Transform prompt_modifiers rule."""
        result = {}
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, dict):
                result.update(item)
        return result

    def prompt_modifier(self, items: TransformerItems) -> AstNode:
        """Transform prompt_modifier rule - pass through."""
        filtered = _filter_children(items)
        return filtered[0] if filtered else {}

    def prompt_using_model(self, items: TransformerItems) -> dict:
        """Transform prompt_using_model rule."""
        filtered = _filter_children(items)
        for item in filtered:
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if val:
                return {"model": val}
        return {}

    def prompt_expecting(self, items: TransformerItems) -> dict:
        """Transform prompt_expecting rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return {"expecting": item}
            val = _get_token_value(item) if isinstance(item, Token) else str(item)
            if val:
                return {"expecting": val}
        return {}

    def expecting_single(self, items: TransformerItems) -> str:
        """Transform expecting_single rule (e.g., Finding)."""
        filtered = _filter_children(items)
        return str(filtered[0])

    def expecting_array(self, items: TransformerItems) -> str:
        """Transform expecting_array rule (e.g., Finding[])."""
        filtered = _filter_children(items)
        return f"{filtered[0]}[]"

    def prompt_inherit(self, items: TransformerItems) -> dict:
        """Transform prompt_inherit rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, VarRef):
                return {"inherit": f"${item.name}"}
            if isinstance(item, str):
                return {"inherit": item if item.startswith("$") else f"${item}"}
            if isinstance(item, Token):
                val = _get_token_value(item)
                return {"inherit": val if val.startswith("$") else f"${val}"}
        return {}

    def prompt_body(self, items: TransformerItems) -> str:
        """Transform prompt_body rule."""
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, str):
                return item
            if isinstance(item, Token):
                return _get_token_value(item)
        return ""

    # =========================================================================
    # Escalation
    # =========================================================================

    def escalation_clause(self, items: TransformerItems) -> EscalationCondition:
        """Transform escalation_clause rule.

        Returns the EscalationCondition from the escalation_condition child.
        """
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, EscalationCondition):
                return item
        msg = "escalation_clause must contain an EscalationCondition"
        raise ValueError(msg)

    def normalized_escalation(self, items: TransformerItems) -> EscalationCondition:
        """Transform normalized_escalation rule (~ operator).

        Items: [~, STRING] - the operator and the string value.
        """
        filtered = _filter_children(items)
        # Find the string value (skip the operator token)
        value = ""
        for item in filtered:
            if isinstance(item, str) and item not in {"~", "==", "!=", "contains"}:
                value = item
                break
            if isinstance(item, Token):
                token_val = _get_token_value(item)
                if token_val not in {"~", "==", "!=", "contains"}:
                    value = token_val
                    break
        return EscalationCondition(op="~", value=value)

    def exact_escalation(self, items: TransformerItems) -> EscalationCondition:
        """Transform exact_escalation rule (== operator).

        Items: [==, STRING] - the operator and the string value.
        """
        filtered = _filter_children(items)
        # Find the string value (skip the operator token)
        value = ""
        for item in filtered:
            if isinstance(item, str) and item not in {"~", "==", "!=", "contains"}:
                value = item
                break
            if isinstance(item, Token):
                token_val = _get_token_value(item)
                if token_val not in {"~", "==", "!=", "contains"}:
                    value = token_val
                    break
        return EscalationCondition(op="==", value=value)

    def not_equal_escalation(self, items: TransformerItems) -> EscalationCondition:
        """Transform not_equal_escalation rule (!= operator).

        Items: [!=, STRING] - the operator and the string value.
        """
        filtered = _filter_children(items)
        # Find the string value (skip the operator token)
        value = ""
        for item in filtered:
            if isinstance(item, str) and item not in {"~", "==", "!=", "contains"}:
                value = item
                break
            if isinstance(item, Token):
                token_val = _get_token_value(item)
                if token_val not in {"~", "==", "!=", "contains"}:
                    value = token_val
                    break
        return EscalationCondition(op="!=", value=value)

    def contains_escalation(self, items: TransformerItems) -> EscalationCondition:
        """Transform contains_escalation rule.

        Items: [contains, STRING] - the keyword and the string value.
        """
        filtered = _filter_children(items)
        # Find the string value (skip the keyword token)
        value = ""
        for item in filtered:
            if isinstance(item, str) and item not in {"~", "==", "!=", "contains"}:
                value = item
                break
            if isinstance(item, Token):
                token_val = _get_token_value(item)
                if token_val not in {"~", "==", "!=", "contains"}:
                    value = token_val
                    break
        return EscalationCondition(op="contains", value=value)

    def escalation_handler(self, items: TransformerItems) -> EscalationHandler:
        """Transform escalation_handler rule.

        Returns the EscalationHandler from the escalation_action child.
        """
        filtered = _filter_children(items)
        for item in filtered:
            if isinstance(item, EscalationHandler):
                return item
        msg = "escalation_handler must contain an EscalationHandler"
        raise ValueError(msg)

    def escalation_return(self, items: TransformerItems) -> EscalationHandler:
        """Transform escalation_return rule."""
        filtered = _filter_children(items)
        value = filtered[0] if filtered else None
        return EscalationHandler(action="return", value=value)

    def escalation_continue(self, _items: TransformerItems) -> EscalationHandler:
        """Transform escalation_continue rule."""
        return EscalationHandler(action="continue")

    def escalation_abort(self, _items: TransformerItems) -> EscalationHandler:
        """Transform escalation_abort rule."""
        return EscalationHandler(action="abort")

    # =========================================================================
    # Control Flow
    # =========================================================================

    def for_loop(self, items: TransformerItems) -> ForLoop:
        """Transform for_loop rule."""
        filtered = _filter_children(items)
        var = None
        iterable = None
        body = []

        for item in filtered:
            if isinstance(item, VarRef):
                if var is None:
                    var = item.name
                elif iterable is None:
                    iterable = item
            elif isinstance(item, list):
                body = item
            elif not isinstance(item, (str, Token)):
                if iterable is None:
                    iterable = item
                else:
                    body.append(item)

        return ForLoop(variable=var or "", iterable=iterable, body=body)

    def parallel_block(self, items: TransformerItems) -> ParallelBlock:
        """Transform parallel_block rule."""
        filtered = _filter_children(items)
        body = []

        for item in filtered:
            if isinstance(item, list):
                body = item
            elif not isinstance(item, (str, Token)):
                body.append(item)

        return ParallelBlock(body=body)

    @v_args(meta=True)
    def loop_block(self, meta: object, items: TransformerItems) -> LoopBlock:
        """Transform loop_block rule.

        Handle loop with max iterations: loop max 5 do ... end
        Handle unbounded loop: loop do ... end
        """
        filtered = _filter_children(items)
        max_iterations = None
        body: list = []

        for item in filtered:
            if isinstance(item, int):
                max_iterations = item
            elif isinstance(item, list):
                body = item
            elif not isinstance(item, (str, Token)):
                body.append(item)

        return LoopBlock(
            max_iterations=max_iterations,
            body=body,
            meta=_meta_to_position(meta),
        )

    def match_block(self, items: TransformerItems) -> MatchBlock:
        """Transform match_block rule."""
        filtered = _filter_children(items)
        expr = None
        cases = []
        else_body = None

        for item in filtered:
            if isinstance(item, tuple) and len(item) == TUPLE_PAIR_LENGTH:
                # (cases_list, else_body) from match_cases
                cases, else_body = item
            elif isinstance(item, MatchCase):
                cases.append(item)
            elif isinstance(item, list):
                # Could be a list of cases
                for sub in item:
                    if isinstance(sub, MatchCase):
                        cases.append(sub)
            elif expr is None and not isinstance(item, (str, Token)):
                # First AST node is the expression
                expr = item

        return MatchBlock(expression=expr, cases=cases, else_body=else_body)

    def match_cases(
        self,
        items: TransformerItems,
    ) -> tuple[list[MatchCase], object | None]:
        """Transform match_cases rule."""
        cases = []
        else_body = None
        for item in items:
            if isinstance(item, MatchCase):
                cases.append(item)
            else:
                else_body = item
        return cases, else_body

    def match_case(self, items: TransformerItems) -> MatchCase:
        """Transform match_case rule."""
        filtered = _filter_children(items)
        pattern = None
        body = None

        for item in filtered:
            if isinstance(item, str):
                if pattern is None:
                    pattern = item
            elif isinstance(item, Token):
                val = _get_token_value(item)
                if pattern is None:
                    pattern = val
            elif body is None:
                body = item

        return MatchCase(pattern=pattern or "", body=body)

    def match_else(self, items: TransformerItems) -> AstNode:
        """Transform match_else rule.

        The grammar is: match_else: "else" "->" flow_statement
        So items[0] is "else" token, items[1] is "->" token, items[2] is flow_statement.
        """
        # The flow_statement is the last item (after "else" and "->")
        filtered = _filter_children(items)
        # Return the first non-token item (the flow statement)
        for item in filtered:
            if not isinstance(item, (str, Token)):
                return item
        # Fallback to last item if no statement found
        return items[-1] if items else None

    def if_block(self, items: TransformerItems) -> IfBlock:
        """Transform if_block rule.

        Grammar: if_block: "if" condition ":" _NL _INDENT flow_body _DEDENT _NL?
        Items received: [Token('IF'), condition, Token(':'), ..., body, ...]
        """
        # Filter out tokens to get condition and body
        filtered = [item for item in items if not isinstance(item, Token)]
        condition = filtered[0] if filtered else None
        body = filtered[1] if len(filtered) > 1 else []
        return IfBlock(condition=condition, body=body)

    def if_stmt(self, items: TransformerItems) -> IfBlock:
        """Transform if_stmt rule (inline if).

        Grammar: if_stmt: "if" condition ":" statement_body
        Items received: [Token('IF'), condition, Token(':'), body]
        """
        # Filter out tokens to get condition and body
        filtered = [item for item in items if not isinstance(item, Token)]
        condition = filtered[0] if filtered else None
        body = [filtered[1]] if len(filtered) > 1 else []
        return IfBlock(condition=condition, body=body)

    def flow_control(self, items: TransformerItems) -> AstNode:
        """Transform flow_control rule - pass through."""
        return items[0] if items else None

    def failure_block(self, items: TransformerItems) -> FailureBlock:
        """Transform failure_block rule."""
        body = items[0] if items else []
        return FailureBlock(body=body)

    def failure_body(self, items: TransformerItems) -> list:
        """Transform failure_body rule."""
        return [item for item in items if item is not None]

    def statement_body(self, items: TransformerItems) -> AstNode:
        """Transform statement_body rule - pass through."""
        return items[0] if items else None

    # =========================================================================
    # Statements
    # =========================================================================

    def assignment(
        self,
        items: TransformerItems,
    ) -> Assignment | PropertyAssignment:
        """Transform assignment rule.

        Return PropertyAssignment for property access targets like $obj.prop,
        or Assignment for simple variable targets like $var.
        """
        filtered = _filter_children(items)
        var = filtered[0]
        value = filtered[1]

        # If target is a PropertyAccess, create PropertyAssignment
        if isinstance(var, PropertyAccess):
            return PropertyAssignment(target=var, value=value)

        # Otherwise, create standard Assignment
        # VarRef.name is already normalized (no $ prefix)
        var_str = var.name if isinstance(var, VarRef) else str(var)
        return Assignment(target=var_str, value=value)

    @v_args(meta=True)
    def run_stmt(self, meta: object, items: TransformerItems) -> RunStmt:  # noqa: C901, PLR0912
        """Transform run_stmt rule.

        Handle run statement forms:
        - variable "=" "run" "agent" identifier ("with" expression)? escalation_handler?
        - "run" "agent" identifier ("with" expression)? escalation_handler?
        """
        target = None
        agent = None
        input_expr: AstNode | None = None
        escalation: EscalationHandler | None = None

        # Keywords to skip (Lark tokens that should not be treated as identifiers)
        skip_tokens = {"=", "run", "agent", "with"}

        for i, item in enumerate(items):
            if isinstance(item, EscalationHandler):
                escalation = item
            elif isinstance(item, VarRef) and target is None and i == 0:
                target = item.name
            elif isinstance(item, NameRef):
                if agent is None:
                    agent = item.name
                else:
                    input_expr = item
            elif isinstance(item, Token):
                # Skip keyword tokens
                if str(item) in skip_tokens:
                    continue
                # Non-keyword tokens are identifiers
                if agent is None:
                    agent = str(item)
                else:
                    input_expr = NameRef(name=str(item))
            elif isinstance(item, str) and item not in skip_tokens:
                if agent is None:
                    agent = item
                else:
                    input_expr = NameRef(name=item)
            elif agent is not None and not isinstance(item, Token):
                input_expr = item

        if agent is None and target:
            # run identifier form
            agent = target.lstrip("$")
            target = None

        return RunStmt(
            target=target,
            agent=agent or "",
            input=input_expr,
            meta=_meta_to_position(meta),
            escalation_handler=escalation,
        )

    @v_args(meta=True)
    def run_flow_assign(  # noqa: C901, PLR0912
        self,
        meta: object,
        items: TransformerItems,
    ) -> RunStmt:
        """Transform run_flow_assign rule.

        Handle: variable "=" "run" identifier ("with" expression)? escalation_handler?
        This is for calling user-defined flows with assignment.
        """
        target = None
        flow_name = None
        input_expr: AstNode | None = None
        escalation: EscalationHandler | None = None

        skip_tokens = {"=", "run", "with"}

        for i, item in enumerate(items):
            if isinstance(item, EscalationHandler):
                escalation = item
            elif isinstance(item, VarRef) and target is None and i == 0:
                target = item.name
            elif isinstance(item, NameRef):
                if flow_name is None:
                    flow_name = item.name
                else:
                    input_expr = item
            elif isinstance(item, Token):
                if str(item) in skip_tokens:
                    continue
                if flow_name is None:
                    flow_name = str(item)
                else:
                    input_expr = NameRef(name=str(item))
            elif isinstance(item, str) and item not in skip_tokens:
                if flow_name is None:
                    flow_name = item
                else:
                    input_expr = NameRef(name=item)
            elif flow_name is not None and not isinstance(item, Token):
                input_expr = item

        return RunStmt(
            target=target,
            agent=flow_name or "",
            input=input_expr,
            meta=_meta_to_position(meta),
            is_flow=True,
            escalation_handler=escalation,
        )

    @v_args(meta=True)
    def run_flow(  # noqa: C901, PLR0912
        self,
        meta: object,
        items: TransformerItems,
    ) -> RunStmt:
        """Transform run_flow rule.

        Handle: "run" identifier ("with" expression)? escalation_handler?
        This is for calling user-defined flows without assignment.
        """
        flow_name = None
        input_expr: AstNode | None = None
        escalation: EscalationHandler | None = None

        skip_tokens = {"run", "with"}

        for item in items:
            if isinstance(item, EscalationHandler):
                escalation = item
            elif isinstance(item, NameRef):
                if flow_name is None:
                    flow_name = item.name
                else:
                    input_expr = item
            elif isinstance(item, Token):
                if str(item) in skip_tokens:
                    continue
                if flow_name is None:
                    flow_name = str(item)
                else:
                    input_expr = NameRef(name=str(item))
            elif isinstance(item, str) and item not in skip_tokens:
                if flow_name is None:
                    flow_name = item
                else:
                    input_expr = NameRef(name=item)
            elif flow_name is not None and not isinstance(item, Token):
                input_expr = item

        return RunStmt(
            target=None,
            agent=flow_name or "",
            input=input_expr,
            meta=_meta_to_position(meta),
            is_flow=True,
            escalation_handler=escalation,
        )

    @v_args(meta=True)
    def call_stmt(self, meta: object, items: TransformerItems) -> CallStmt:  # noqa: C901
        """Transform call_stmt rule.

        Handle call statement forms:
        - variable "=" "call" "llm" identifier ("with" expression)? call_modifiers?
        - "call" "llm" identifier ("with" expression)? call_modifiers?
        """
        target = None
        prompt = None
        input_expr: AstNode | None = None
        model = None

        # Keywords to skip
        skip_tokens = {"=", "call", "llm", "with"}

        for i, item in enumerate(items):
            if isinstance(item, VarRef) and target is None and i == 0:
                target = item.name
            elif isinstance(item, NameRef):
                if prompt is None:
                    prompt = item.name
                else:
                    input_expr = item
            elif isinstance(item, Token):
                # Skip keyword tokens
                if str(item) in skip_tokens:
                    continue
                # Non-keyword tokens are identifiers
                if prompt is None:
                    prompt = str(item)
            elif isinstance(item, str) and item not in skip_tokens:
                if prompt is None:
                    prompt = item
            elif isinstance(item, dict) and "model" in item:
                model = item["model"]
            elif prompt is not None and not isinstance(item, Token):
                input_expr = item

        return CallStmt(
            target=target,
            prompt=prompt or "",
            input=input_expr,
            model=model,
            meta=_meta_to_position(meta),
        )

    def call_modifiers(self, items: TransformerItems) -> dict:
        """Transform call_modifiers rule."""
        return {"model": items[0]}

    @v_args(meta=True)
    def return_stmt(self, meta: object, items: TransformerItems) -> ReturnStmt:
        """Transform return_stmt rule.

        Handle the return statement form: "return" expression
        The first item may be the RETURN keyword token due to keep_all_tokens=True.
        """
        filtered = _filter_children(items)
        # After filtering, we should have the expression value
        value = filtered[0] if filtered else None
        return ReturnStmt(value=value, meta=_meta_to_position(meta))

    def push_stmt(self, items: TransformerItems) -> PushStmt:
        """Transform push_stmt rule.

        Grammar: push_stmt: "push" expression "to" variable
        With keep_all_tokens, items include keyword tokens.
        """
        filtered = _filter_children(items)
        value = filtered[0]
        target_var = filtered[1]
        target_str = (
            target_var.name if isinstance(target_var, VarRef) else str(target_var)
        )
        return PushStmt(value=value, target=target_str)

    def escalate_stmt(self, items: TransformerItems) -> EscalateStmt:
        """Transform escalate_stmt rule."""
        message = items[0] if items else None
        return EscalateStmt(message=message)

    @v_args(meta=True)
    def log_stmt(self, meta: object, items: TransformerItems) -> LogStmt:
        """Transform log_stmt rule.

        Grammar: log_stmt: "log" expression
        The first item may be the LOG keyword token due to keep_all_tokens=True.
        """
        filtered = _filter_children(items)
        message = filtered[0] if filtered else Literal(value="", literal_type="string")
        return LogStmt(message=message, meta=_meta_to_position(meta))

    @v_args(meta=True)
    def notify_stmt(self, meta: object, items: TransformerItems) -> NotifyStmt:
        """Transform notify_stmt rule.

        Grammar: notify_stmt: "notify" expression
        The first item may be the NOTIFY keyword token due to keep_all_tokens=True.
        """
        filtered = _filter_children(items)
        message = filtered[0] if filtered else Literal(value="", literal_type="string")
        return NotifyStmt(message=message, meta=_meta_to_position(meta))

    # =========================================================================
    # Expressions
    # =========================================================================

    def or_expr(self, items: TransformerItems) -> AstNode:
        """Transform or_expr rule."""
        if len(items) == 1:
            return items[0]
        result = items[0]
        for i in range(1, len(items)):
            result = BinaryOp(op="or", left=result, right=items[i])
        return result

    def and_expr(self, items: TransformerItems) -> AstNode:
        """Transform and_expr rule."""
        if len(items) == 1:
            return items[0]
        result = items[0]
        for i in range(1, len(items)):
            result = BinaryOp(op="and", left=result, right=items[i])
        return result

    def not_op(self, items: TransformerItems) -> UnaryOp:
        """Transform not_op rule."""
        return UnaryOp(op="not", operand=items[0])

    def comparison(self, items: TransformerItems) -> AstNode:
        """Transform comparison rule."""
        if len(items) == 1:
            return items[0]
        if len(items) == BINARY_OP_LENGTH:
            return BinaryOp(op=items[1], left=items[0], right=items[2])
        return items[0]

    def comparison_op(self, items: TransformerItems) -> str:
        """Transform comparison_op rule."""
        return str(items[0])

    def additive(self, items: TransformerItems) -> AstNode:
        """Transform additive rule."""
        if len(items) == 1:
            return items[0]
        result = items[0]
        i = 1
        while i < len(items):
            op = str(items[i])  # Convert Token to string
            right = items[i + 1]
            result = BinaryOp(op=op, left=result, right=right)
            i += TUPLE_PAIR_LENGTH
        return result

    def multiplicative(self, items: TransformerItems) -> AstNode:
        """Transform multiplicative rule."""
        if len(items) == 1:
            return items[0]
        result = items[0]
        i = 1
        while i < len(items):
            op = str(items[i])  # Convert Token to string
            right = items[i + 1]
            result = BinaryOp(op=op, left=result, right=right)
            i += TUPLE_PAIR_LENGTH
        return result

    def neg(self, items: TransformerItems) -> UnaryOp:
        """Transform neg rule."""
        return UnaryOp(op="-", operand=items[0])

    def atom(self, items: TransformerItems) -> AstNode:
        """Transform atom rule - pass through."""
        return items[0]

    def literal(self, items: TransformerItems) -> AstNode:
        """Transform literal rule - pass through."""
        return items[0]

    def string_lit(self, items: TransformerItems) -> Literal:
        """Transform string_lit rule."""
        return Literal(value=items[0], literal_type="string")

    def number_lit(self, items: TransformerItems) -> Literal:
        """Transform number_lit rule."""
        return Literal(value=items[0], literal_type="float")

    def int_lit(self, items: TransformerItems) -> Literal:
        """Transform int_lit rule."""
        return Literal(value=items[0], literal_type="int")

    def true_lit(self, _items: TransformerItems) -> Literal:
        """Transform true_lit rule."""
        return Literal(value=True, literal_type="bool")

    def false_lit(self, _items: TransformerItems) -> Literal:
        """Transform false_lit rule."""
        return Literal(value=False, literal_type="bool")

    def null_lit(self, _items: TransformerItems) -> Literal:
        """Transform null_lit rule."""
        return Literal(value=None, literal_type="null")

    def initial_prompt(self, _items: TransformerItems) -> FunctionCall:
        """Transform initial_prompt rule."""
        return FunctionCall(name="initial_user_prompt", args=[])

    def list_literal(self, items: TransformerItems) -> ListLiteral:
        """Transform list_literal rule."""
        filtered = _filter_children(items)
        return ListLiteral(elements=filtered)

    def object_literal(self, items: TransformerItems) -> ObjectLiteral:
        """Transform object_literal rule."""
        entries = {}
        for item in items:
            if isinstance(item, tuple) and len(item) == TUPLE_PAIR_LENGTH:
                entries[item[0]] = item[1]
            elif isinstance(item, dict):
                entries.update(item)
        return ObjectLiteral(entries=entries)

    def object_entry(self, items: TransformerItems) -> tuple[str, object]:
        """Transform object_entry rule."""
        filtered = _filter_children(items)
        return (filtered[0], filtered[1])

    @v_args(meta=True)
    def var_ref(self, meta: object, items: TransformerItems) -> VarRef:
        """Transform var_ref rule."""
        filtered = _filter_children(items)
        name = None
        for item in filtered:
            if isinstance(item, str):
                name = item
            elif isinstance(item, Token):
                val = _get_token_value(item)
                # Skip the dollar sign token
                if val != "$":
                    name = val
        return VarRef(name=name or "", meta=_meta_to_position(meta))

    def var_dotted(self, items: TransformerItems) -> PropertyAccess:
        """Transform var_dotted rule (e.g., $var.prop.nested)."""
        filtered = _filter_children(items)
        dotted_name = filtered[0]
        parts = dotted_name.split(".")
        base = VarRef(name=parts[0])
        return PropertyAccess(base=base, properties=parts[1:])

    @v_args(meta=True)
    def var_bare(self, meta: object, items: TransformerItems) -> VarRef:
        """Transform var_bare rule (bare name without $ prefix)."""
        filtered = _filter_children(items)
        name = None
        for item in filtered:
            if isinstance(item, str):
                name = item
            elif isinstance(item, Token):
                name = _get_token_value(item)
        if name is None:
            msg = "var_bare has no name"
            raise ValueError(msg)
        return VarRef(name=name, meta=_meta_to_position(meta))

    def variable(self, items: TransformerItems) -> AstNode:
        """Transform variable rule - pass through."""
        return items[0]

    def var_name(self, items: TransformerItems) -> str:
        """Transform var_name rule."""
        return str(items[0])

    def identifier(self, items: TransformerItems) -> str:
        """Transform identifier rule."""
        return str(items[0])

    def contextual_keyword(self, items: TransformerItems) -> str:
        """Transform contextual_keyword rule."""
        return str(items[0])

    def contextual_name(self, items: TransformerItems) -> str:
        """Transform contextual_name rule."""
        return str(items[0])

    def property_access(self, items: TransformerItems) -> PropertyAccess:
        """Transform property_access rule.

        Handles three grammar alternatives:
        - NAME "." contextual_name ("." contextual_name)*
        - variable "." contextual_name ("." contextual_name)*
        - DOTTED_NAME (e.g., "result.valid" lexed as single token)
        """
        base = items[0]
        props = list(items[1:])
        if isinstance(base, str):
            # Could be NAME or DOTTED_NAME token
            if "." in base:
                # DOTTED_NAME: split into base + properties
                parts = base.split(".")
                base = NameRef(name=parts[0])
                props = parts[1:] + props
            else:
                base = NameRef(name=base)
        return PropertyAccess(base=base, properties=props)

    def function_call(self, items: TransformerItems) -> FunctionCall:
        """Transform function_call rule."""
        name = items[0]
        args = list(items[1:])
        return FunctionCall(name=name, args=args)

    def named_function_call(self, items: TransformerItems) -> FunctionCall:
        """Transform named_function_call rule."""
        name = items[0]
        args = list(items[1:])
        return FunctionCall(name=name, args=args)

    def bare_function_call(self, items: TransformerItems) -> FunctionCall:
        """Transform bare_function_call rule."""
        name = items[0]
        args = list(items[1:])
        return FunctionCall(name=name, args=args)

    def process_call(self, items: TransformerItems) -> FunctionCall:
        """Transform process_call rule."""
        return FunctionCall(name="process", args=list(items))

    def paren_expr(self, items: TransformerItems) -> AstNode:
        """Transform paren_expr rule - pass through."""
        return items[0]

    def name_ref(self, items: TransformerItems) -> NameRef:
        """Transform name_ref rule."""
        return NameRef(name=str(items[0]))

    def interpolated_string(self, items: TransformerItems) -> str:
        """Transform interpolated_string rule."""
        return str(items[0])

    # =========================================================================
    # Filter Expressions
    # =========================================================================

    def implicit_property(self, items: TransformerItems) -> ImplicitProperty:
        """Transform implicit_property rule (.prop or .nested.prop).

        Handle two forms:
        - "." contextual_name ("." contextual_name)* -> list of names
        - "." DOTTED_NAME -> single dotted name string to split
        """
        properties = []

        for item in items:
            # Skip DOT tokens
            if isinstance(item, Token):
                if item.type == "DOT":
                    continue
                val = _get_token_value(item)
                # Check if it's a DOTTED_NAME (contains dots)
                if "." in val:
                    properties.extend(val.split("."))
                elif val:  # Only add non-empty values
                    properties.append(val)
            elif isinstance(item, str):
                # Could be a dotted name string from contextual_name
                if "." in item:
                    properties.extend(item.split("."))
                elif item:  # Only add non-empty values
                    properties.append(item)

        return ImplicitProperty(properties=properties)

    def filter_expr(self, items: TransformerItems) -> FilterExpr:
        """Transform filter_expr rule (filter $list where .prop op val)."""
        filtered = _filter_children(items)
        # items[0] = list expression, items[1] = condition
        list_expr = filtered[0] if filtered else None
        condition = filtered[1] if len(filtered) > 1 else None
        return FilterExpr(list_expr=list_expr, condition=condition)


def transform(tree: Tree[Token]) -> DslFile:
    """Transform a Lark parse tree into an AST.

    Args:
        tree: Lark parse tree from parsing DSL source.

    Returns:
        Root DslFile AST node.

    """
    transformer = AstTransformer()
    return transformer.transform(tree)
