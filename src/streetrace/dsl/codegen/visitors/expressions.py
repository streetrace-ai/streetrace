"""Expression visitor for DSL code generation.

Generate Python expressions from DSL expression AST nodes.
"""

from __future__ import annotations

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

    def __init__(self) -> None:
        """Initialize the expression visitor."""
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
            Python code to access the variable via ctx.vars.

        """
        name = node.name.lstrip("$")
        return f"ctx.vars['{name}']"

    def _visit_property_access(self, node: PropertyAccess) -> str:
        """Generate code for property access.

        Args:
            node: Property access node.

        Returns:
            Python code for accessing nested properties.

        """
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
            # Escape string properly
            escaped = str(node.value).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        if node.literal_type == "bool":
            return "True" if node.value else "False"
        if node.literal_type == "null":
            return "None"
        if node.literal_type == "list":
            return "[]"
        return str(node.value)

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
            Python code to access the variable via ctx.vars.

        """
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
