"""Expression visitor for DSL code generation.

Generate Python expressions from DSL expression AST nodes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lark import Token

from streetrace.dsl.ast.nodes import (
    BinaryOp,
    FilterExpr,
    FunctionCall,
    ImplicitProperty,
    ListLiteral,
    Literal,
    NameRef,
    ObjectLiteral,
    PropertyAccess,
    UnaryOp,
    VarRef,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

# Map DSL operators to Python operators
OPERATOR_MAP = {
    "contains": "in",
}


class ExpressionVisitor:
    """Generate Python expressions from DSL AST nodes.

    Visit expression nodes and produce Python expression strings.
    """

    def __init__(self, *, use_resolve: bool = False) -> None:
        """Initialize the expression visitor.

        Args:
            use_resolve: If True, use ctx.resolve() for variables instead of
                ctx.vars access. This is needed for prompt interpolation.

        """
        self._use_resolve = use_resolve
        self._dispatch: dict[type, Callable[..., str]] = {
            VarRef: self._visit_var_ref,
            PropertyAccess: self._visit_property_access,
            Literal: self._visit_literal,
            BinaryOp: self._visit_binary_op,
            UnaryOp: self._visit_unary_op,
            FunctionCall: self._visit_function_call,
            ListLiteral: self._visit_list_literal,
            ObjectLiteral: self._visit_object_literal,
            NameRef: self._visit_name_ref,
            ImplicitProperty: self._visit_implicit_property,
            FilterExpr: self._visit_filter_expr,
        }

    def visit(self, node: object) -> str:
        """Visit an expression node and generate Python code.

        Args:
            node: The AST expression node to visit.

        Returns:
            Python expression string.

        Raises:
            ValueError: If a raw Token is encountered, indicating a transformer bug.

        """
        # Check for unhandled Token - this indicates a bug in the AST transformer
        if isinstance(node, Token):
            msg = (
                f"Unhandled Token in expression: type='{node.type}', "
                f"value='{node.value}', line={getattr(node, 'line', 'unknown')}. "
                f"The AST transformer should have converted this to a proper node."
            )
            raise ValueError(msg)  # noqa: TRY004

        visitor = self._dispatch.get(type(node))
        if visitor is not None:
            return visitor(node)

        # Fallback for unknown nodes
        logger.warning("Unknown expression node type: %s", type(node).__name__)
        return repr(node)

    def _visit_var_ref(self, node: VarRef) -> str:
        """Generate code for variable reference.

        Args:
            node: Variable reference node.

        Returns:
            Python code to access the variable via ctx.vars or ctx.resolve.

        """
        name = node.name.lstrip("$")
        if self._use_resolve:
            return f"ctx.resolve('{name}')"
        return f"ctx.vars['{name}']"

    def _visit_property_access(self, node: PropertyAccess) -> str:
        """Generate code for property access.

        Args:
            node: Property access node.

        Returns:
            Python code for accessing nested properties.

        """
        if self._use_resolve and isinstance(node.base, (VarRef, NameRef)):
            # If we're in resolve mode and base is a simple variable,
            # use resolve_property for the whole chain.
            base_name = node.base.name.lstrip("$")
            prop_args = ", ".join(f"'{p}'" for p in node.properties)
            return f"ctx.resolve_property('{base_name}', {prop_args})"

        base = self.visit(node.base)
        # Build chain of property accesses
        for prop in node.properties:
            base = f"{base}['{prop}']"
        return base

    def _visit_literal(self, node: Literal) -> str:
        """Generate code for literal value.

        Args:
            node: Literal value node.

        Returns:
            Python literal representation.

        """
        if node.literal_type == "string":
            return self._visit_string_literal(str(node.value))

        if node.literal_type == "bool":
            return "True" if node.value else "False"
        if node.literal_type == "null":
            return "None"
        if node.literal_type == "list":
            return "[]"
        return str(node.value)

    def _visit_string_literal(self, text: str) -> str:
        """Generate code for string literal with proper escaping.

        Args:
            text: String value to generate code for.

        Returns:
            Python string literal.

        """
        # If it has interpolation patterns or literal braces, we need f-string
        if "${" in text or "{" in text or "}" in text:
            return self._interpolate(text)

        # Multiline string
        if "\n" in text:
            # Escape backslashes first, then triple quotes
            escaped = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            return f'"""{escaped}"""'

        # Escape string properly
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _visit_binary_op(self, node: BinaryOp) -> str:
        """Generate code for binary operation.

        Args:
            node: Binary operation node.

        Returns:
            Python binary expression.

        """
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = node.op

        # Handle special operators
        if op == "contains":
            return f"({right} in {left})"

        # Handle normalized equals operator
        if op == "~":
            return f"normalized_equals({left}, {right})"

        # Use list_concat for + to handle mixed list/string operands
        if op == "+":
            return f"list_concat({left}, {right})"

        # Map operator if needed
        python_op = OPERATOR_MAP.get(op, op)

        return f"({left} {python_op} {right})"

    def _visit_unary_op(self, node: UnaryOp) -> str:
        """Generate code for unary operation.

        Args:
            node: Unary operation node.

        Returns:
            Python unary expression.

        """
        operand = self.visit(node.operand)

        if node.op == "not":
            return f"(not {operand})"
        if node.op == "-":
            return f"(-{operand})"

        return f"({node.op}{operand})"

    def _visit_function_call(self, node: FunctionCall) -> str:
        """Generate code for function call.

        Args:
            node: Function call node.

        Returns:
            Python function call expression.

        """
        args = ", ".join(self.visit(arg) for arg in node.args)

        # Handle built-in functions
        if node.name == "initial_user_prompt":
            return "ctx.vars['input_prompt']"
        if node.name == "process":
            return f"ctx.process({args})"

        # Library function calls (e.g., lib.convert)
        return f"{node.name}({args})"

    def _visit_list_literal(self, node: ListLiteral) -> str:
        """Generate code for list literal.

        Args:
            node: List literal node.

        Returns:
            Python list literal.

        """
        elements = ", ".join(self.visit(elem) for elem in node.elements)
        return f"[{elements}]"

    def _visit_object_literal(self, node: ObjectLiteral) -> str:
        """Generate code for object literal.

        Args:
            node: Object literal node.

        Returns:
            Python dict literal.

        """
        entries = ", ".join(
            f'"{key}": {self.visit(value)}' for key, value in node.entries.items()
        )
        return f"{{{entries}}}"

    def _visit_name_ref(self, node: NameRef) -> str:
        """Generate code for name reference.

        Bare names in DSL expressions are context variables, same
        as explicit $-prefixed references.

        Args:
            node: Name reference node.

        Returns:
            Python code to access the variable via ctx.vars or ctx.resolve.

        """
        if self._use_resolve:
            return f"ctx.resolve('{node.name}')"
        return f"ctx.vars['{node.name}']"

    def _visit_implicit_property(self, node: ImplicitProperty) -> str:
        """Generate code for implicit property access.

        Args:
            node: Implicit property node.

        Returns:
            Python code accessing properties on _item.

        Example:
            .confidence -> _item['confidence']
            .nested.prop -> _item['nested']['prop']

        """
        base = "_item"
        for prop in node.properties:
            base = f"{base}['{prop}']"
        return base

    def _visit_filter_expr(self, node: FilterExpr) -> str:
        """Generate code for filter expression.

        Args:
            node: Filter expression node.

        Returns:
            Python list comprehension that filters the list.

        Example:
            filter $findings where .confidence >= 80
            -> [_item for _item in ctx.vars['findings'] if _item['confidence'] >= 80]

        """
        list_code = self.visit(node.list_expr)
        condition_code = self.visit(node.condition)
        return f"[_item for _item in {list_code} if {condition_code}]"

    def _interpolate(self, text: str) -> str:
        """Build an f-string expression from interpolated text.

        Escape literal braces so they survive the f-string wrapper,
        then replace ``${expr}`` patterns with Python expressions.

        Args:
            text: String containing ${...} interpolation patterns.

        Returns:
            Python f-string expression.

        """
        # Sentinel-based approach: protect ${expr} before escaping braces
        sentinel_prefix = "\x00SR_EXPR:"
        sentinel_suffix = "\x00"
        placeholders: list[str] = []

        pattern = r"\$\{([^}]+)\}"

        def capture_expr(match: re.Match[str]) -> str:
            expr = match.group(1).strip()
            replacement = "{" + self._convert_dsl_expr_to_python(expr) + "}"
            idx = len(placeholders)
            placeholders.append(replacement)
            return f"{sentinel_prefix}{idx}{sentinel_suffix}"

        processed = re.sub(pattern, capture_expr, text)

        # Escape literal braces
        processed = processed.replace("{", "{{")
        processed = processed.replace("}", "}}")

        # Restore sentinels
        for idx, replacement in enumerate(placeholders):
            processed = processed.replace(
                f"{sentinel_prefix}{idx}{sentinel_suffix}",
                replacement,
            )

        # Use triple-quoted f-string for multiline strings
        if "\n" in processed:
            # Escape backslashes first, then triple quotes
            processed = processed.replace("\\", "\\\\")
            processed = processed.replace('"""', '\\"\\"\\"')
            return f'f"""{processed}"""'

        # Single line - use regular f-string
        processed = processed.replace("\\", "\\\\")
        processed = processed.replace('"', '\\"')
        return f'f"{processed}"'

    def _convert_dsl_expr_to_python(self, expr: str) -> str:
        """Convert a DSL expression inside ${...} to Python code.

        Handles:
        - Simple variables: diff_chunks -> ctx.vars['diff_chunks']
        - Dotted access: chunk.title -> ctx.vars['chunk']['title']
        - Function calls: len(var) -> len(ctx.vars['var'])
        - Nested: len(chunk.items) -> len(ctx.vars['chunk']['items'])

        Args:
            expr: DSL expression string.

        Returns:
            Python expression string.

        """
        # Match function call pattern: func(arg) or func(arg.prop.prop)
        func_match = re.match(r"(\w+)\(([^)]+)\)", expr)
        if func_match:
            func_name = func_match.group(1)
            arg = func_match.group(2).strip()
            python_arg = self._convert_var_to_python(arg)
            return f"{func_name}({python_arg})"

        # Otherwise, treat as variable or dotted access
        return self._convert_var_to_python(expr)

    def _convert_var_to_python(self, var_expr: str) -> str:
        """Convert a variable expression to Python accessor.

        Args:
            var_expr: Variable expression (e.g., 'chunk' or 'chunk.title').

        Returns:
            Python code to access the variable.

        """
        parts = var_expr.split(".")
        base = parts[0].strip().lstrip("$")

        if self._use_resolve:
            if len(parts) == 1:
                return f"ctx.resolve('{base}')"
            prop_args = ", ".join(f"'{p.strip()}'" for p in parts[1:])
            return f"ctx.resolve_property('{base}', {prop_args})"

        result = f"ctx.vars['{base}']"

        for prop in parts[1:]:
            result = f"{result}['{prop.strip()}']"

        return result
