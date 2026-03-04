"""Convert DSL SchemaDef AST nodes to Pydantic models.

Provide factory functions to transform DSL schema definitions into
dynamically-created Pydantic model classes for structured output validation.
"""

from typing import Any

from pydantic import BaseModel, create_model

from streetrace.dsl.ast.nodes import SchemaDef, TypeExpr

DSL_TYPE_MAP: dict[str, type] = {
    "string": str,
    "int": int,
    "float": float,
    "bool": bool,
}
"""Map DSL type names to Python built-in types."""


def type_expr_to_python_type(type_expr: TypeExpr) -> Any:  # noqa: ANN401
    """Convert DSL TypeExpr to Python type annotation.

    Args:
        type_expr: DSL type expression node.

    Returns:
        Python type annotation (e.g., str, list[str], str | None).

    Note:
        Returns Any to satisfy mypy as dynamic type construction
        (list[base] where base is a runtime value) is not statically
        analyzable. The actual runtime values are always valid types.

    """
    base = DSL_TYPE_MAP.get(type_expr.base_type, str)

    # Dynamic type construction - mypy cannot verify list[base]
    # when base is a runtime value
    if type_expr.is_list:
        result: Any = list[base]  # type: ignore[valid-type]
    else:
        result = base

    if type_expr.is_optional:
        result = result | None

    return result


def schema_to_pydantic(schema_def: SchemaDef) -> type[BaseModel]:
    """Convert DSL SchemaDef to a Pydantic model class.

    Args:
        schema_def: DSL schema definition node.

    Returns:
        Dynamically-created Pydantic model class.

    """
    field_definitions: dict[str, Any] = {}

    for field in schema_def.fields:
        python_type = type_expr_to_python_type(field.type_expr)

        if field.type_expr.is_optional:
            field_definitions[field.name] = (python_type, None)
        else:
            field_definitions[field.name] = (python_type, ...)

    return create_model(schema_def.name, **field_definitions)
