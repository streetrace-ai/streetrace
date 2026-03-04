"""Unit tests for schema factory.

Test conversion of DSL SchemaDef AST nodes to Pydantic models.
"""

import pytest
from pydantic import BaseModel, ValidationError

from streetrace.dsl.ast.nodes import SchemaDef, SchemaField, TypeExpr
from streetrace.dsl.runtime.schema_factory import (
    DSL_TYPE_MAP,
    schema_to_pydantic,
    type_expr_to_python_type,
)


class TestDslTypeMap:
    """Test the DSL type mapping constant."""

    def test_string_type_maps_to_str(self):
        """Test that 'string' maps to Python str."""
        assert DSL_TYPE_MAP["string"] is str

    def test_int_type_maps_to_int(self):
        """Test that 'int' maps to Python int."""
        assert DSL_TYPE_MAP["int"] is int

    def test_float_type_maps_to_float(self):
        """Test that 'float' maps to Python float."""
        assert DSL_TYPE_MAP["float"] is float

    def test_bool_type_maps_to_bool(self):
        """Test that 'bool' maps to Python bool."""
        assert DSL_TYPE_MAP["bool"] is bool

    def test_all_basic_types_present(self):
        """Test that all four basic DSL types are in the map."""
        expected_types = {"string", "int", "float", "bool"}
        assert set(DSL_TYPE_MAP.keys()) == expected_types


class TestTypeExprToPythonType:
    """Test conversion of TypeExpr to Python type annotations."""

    def test_simple_string_type(self):
        """Test conversion of simple string type."""
        type_expr = TypeExpr(base_type="string")
        result = type_expr_to_python_type(type_expr)
        assert result is str

    def test_simple_int_type(self):
        """Test conversion of simple int type."""
        type_expr = TypeExpr(base_type="int")
        result = type_expr_to_python_type(type_expr)
        assert result is int

    def test_simple_float_type(self):
        """Test conversion of simple float type."""
        type_expr = TypeExpr(base_type="float")
        result = type_expr_to_python_type(type_expr)
        assert result is float

    def test_simple_bool_type(self):
        """Test conversion of simple bool type."""
        type_expr = TypeExpr(base_type="bool")
        result = type_expr_to_python_type(type_expr)
        assert result is bool

    def test_list_of_string(self):
        """Test conversion of list[string] type."""
        type_expr = TypeExpr(base_type="string", is_list=True)
        result = type_expr_to_python_type(type_expr)
        assert result == list[str]

    def test_list_of_int(self):
        """Test conversion of list[int] type."""
        type_expr = TypeExpr(base_type="int", is_list=True)
        result = type_expr_to_python_type(type_expr)
        assert result == list[int]

    def test_list_of_float(self):
        """Test conversion of list[float] type."""
        type_expr = TypeExpr(base_type="float", is_list=True)
        result = type_expr_to_python_type(type_expr)
        assert result == list[float]

    def test_list_of_bool(self):
        """Test conversion of list[bool] type."""
        type_expr = TypeExpr(base_type="bool", is_list=True)
        result = type_expr_to_python_type(type_expr)
        assert result == list[bool]

    def test_optional_string(self):
        """Test conversion of optional string type (string?)."""
        type_expr = TypeExpr(base_type="string", is_optional=True)
        result = type_expr_to_python_type(type_expr)
        assert result == str | None

    def test_optional_int(self):
        """Test conversion of optional int type (int?)."""
        type_expr = TypeExpr(base_type="int", is_optional=True)
        result = type_expr_to_python_type(type_expr)
        assert result == int | None

    def test_optional_float(self):
        """Test conversion of optional float type (float?)."""
        type_expr = TypeExpr(base_type="float", is_optional=True)
        result = type_expr_to_python_type(type_expr)
        assert result == float | None

    def test_optional_bool(self):
        """Test conversion of optional bool type (bool?)."""
        type_expr = TypeExpr(base_type="bool", is_optional=True)
        result = type_expr_to_python_type(type_expr)
        assert result == bool | None

    def test_optional_list_of_string(self):
        """Test conversion of optional list type (list[string]?)."""
        type_expr = TypeExpr(base_type="string", is_list=True, is_optional=True)
        result = type_expr_to_python_type(type_expr)
        assert result == list[str] | None

    def test_optional_list_of_int(self):
        """Test conversion of optional list type (list[int]?)."""
        type_expr = TypeExpr(base_type="int", is_list=True, is_optional=True)
        result = type_expr_to_python_type(type_expr)
        assert result == list[int] | None

    def test_unknown_type_defaults_to_str(self):
        """Test that unknown types default to str."""
        type_expr = TypeExpr(base_type="unknown_custom_type")
        result = type_expr_to_python_type(type_expr)
        assert result is str


class TestSchemaToPydantic:
    """Test conversion of SchemaDef to Pydantic models."""

    def test_empty_schema(self):
        """Test conversion of schema with no fields."""
        schema_def = SchemaDef(name="EmptySchema", fields=[])
        model = schema_to_pydantic(schema_def)

        assert issubclass(model, BaseModel)
        assert model.__name__ == "EmptySchema"

    def test_simple_schema_with_string_field(self):
        """Test schema with a single string field."""
        schema_def = SchemaDef(
            name="SimpleSchema",
            fields=[
                SchemaField(
                    name="title",
                    type_expr=TypeExpr(base_type="string"),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        assert issubclass(model, BaseModel)
        assert model.__name__ == "SimpleSchema"

        # Validate that the model works
        instance = model(title="Test Title")
        assert instance.title == "Test Title"

    def test_schema_with_multiple_fields(self):
        """Test schema with multiple fields of different types."""
        schema_def = SchemaDef(
            name="MultiFieldSchema",
            fields=[
                SchemaField(name="name", type_expr=TypeExpr(base_type="string")),
                SchemaField(name="age", type_expr=TypeExpr(base_type="int")),
                SchemaField(name="score", type_expr=TypeExpr(base_type="float")),
                SchemaField(name="active", type_expr=TypeExpr(base_type="bool")),
            ],
        )
        model = schema_to_pydantic(schema_def)

        instance = model(name="Alice", age=30, score=95.5, active=True)
        assert instance.name == "Alice"
        assert instance.age == 30
        assert instance.score == 95.5
        assert instance.active is True

    def test_schema_with_list_field(self):
        """Test schema with a list field."""
        schema_def = SchemaDef(
            name="ListSchema",
            fields=[
                SchemaField(
                    name="tags",
                    type_expr=TypeExpr(base_type="string", is_list=True),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        instance = model(tags=["python", "testing"])
        assert instance.tags == ["python", "testing"]

    def test_schema_with_optional_field(self):
        """Test schema with an optional field."""
        schema_def = SchemaDef(
            name="OptionalSchema",
            fields=[
                SchemaField(
                    name="required_name",
                    type_expr=TypeExpr(base_type="string"),
                ),
                SchemaField(
                    name="optional_note",
                    type_expr=TypeExpr(base_type="string", is_optional=True),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        # Should work with optional field omitted
        instance = model(required_name="Test")
        assert instance.required_name == "Test"
        assert instance.optional_note is None

        # Should work with optional field provided
        instance_with_note = model(required_name="Test", optional_note="A note")
        assert instance_with_note.optional_note == "A note"

    def test_schema_with_optional_list_field(self):
        """Test schema with an optional list field."""
        schema_def = SchemaDef(
            name="OptionalListSchema",
            fields=[
                SchemaField(
                    name="items",
                    type_expr=TypeExpr(
                        base_type="string", is_list=True, is_optional=True,
                    ),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        # Should work with optional list omitted
        instance = model()
        assert instance.items is None

        # Should work with optional list provided
        instance_with_items = model(items=["a", "b"])
        assert instance_with_items.items == ["a", "b"]

    def test_code_review_result_schema(self):
        """Test the CodeReviewResult schema from the example DSL file."""
        schema_def = SchemaDef(
            name="CodeReviewResult",
            fields=[
                SchemaField(
                    name="approved", type_expr=TypeExpr(base_type="bool"),
                ),
                SchemaField(
                    name="severity", type_expr=TypeExpr(base_type="string"),
                ),
                SchemaField(
                    name="issues",
                    type_expr=TypeExpr(base_type="string", is_list=True),
                ),
                SchemaField(
                    name="suggestions",
                    type_expr=TypeExpr(base_type="string", is_list=True),
                ),
                SchemaField(
                    name="confidence", type_expr=TypeExpr(base_type="float"),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        instance = model(
            approved=True,
            severity="low",
            issues=["minor typo"],
            suggestions=["add docstring"],
            confidence=0.95,
        )
        assert instance.approved is True
        assert instance.severity == "low"
        assert instance.issues == ["minor typo"]
        assert instance.suggestions == ["add docstring"]
        assert instance.confidence == 0.95

    def test_model_rejects_missing_required_field(self):
        """Test that created model rejects missing required fields."""
        schema_def = SchemaDef(
            name="RequiredFieldSchema",
            fields=[
                SchemaField(
                    name="required_field",
                    type_expr=TypeExpr(base_type="string"),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        with pytest.raises(ValidationError):
            model()  # Missing required_field

    def test_model_rejects_wrong_type(self):
        """Test that created model rejects wrong field type."""
        schema_def = SchemaDef(
            name="IntSchema",
            fields=[
                SchemaField(name="count", type_expr=TypeExpr(base_type="int")),
            ],
        )
        model = schema_to_pydantic(schema_def)

        with pytest.raises(ValidationError):
            model(count="not an int")

    def test_model_rejects_wrong_list_item_type(self):
        """Test that created model rejects wrong list item type."""
        schema_def = SchemaDef(
            name="IntListSchema",
            fields=[
                SchemaField(
                    name="numbers", type_expr=TypeExpr(base_type="int", is_list=True),
                ),
            ],
        )
        model = schema_to_pydantic(schema_def)

        with pytest.raises(ValidationError):
            model(numbers=["one", "two"])

    def test_model_dump_returns_dict(self):
        """Test that model_dump() returns a dictionary."""
        schema_def = SchemaDef(
            name="DumpSchema",
            fields=[
                SchemaField(name="value", type_expr=TypeExpr(base_type="string")),
            ],
        )
        model = schema_to_pydantic(schema_def)

        instance = model(value="test")
        dumped = instance.model_dump()

        assert isinstance(dumped, dict)
        assert dumped == {"value": "test"}

    def test_model_json_schema_available(self):
        """Test that model_json_schema() is available for prompt enrichment."""
        schema_def = SchemaDef(
            name="JsonSchemaTest",
            fields=[
                SchemaField(name="name", type_expr=TypeExpr(base_type="string")),
                SchemaField(name="count", type_expr=TypeExpr(base_type="int")),
            ],
        )
        model = schema_to_pydantic(schema_def)

        json_schema = model.model_json_schema()

        assert isinstance(json_schema, dict)
        assert json_schema.get("title") == "JsonSchemaTest"
        assert "properties" in json_schema
        assert "name" in json_schema["properties"]
        assert "count" in json_schema["properties"]

    def test_model_validate_from_dict(self):
        """Test that model_validate() can create instance from dict."""
        schema_def = SchemaDef(
            name="ValidateSchema",
            fields=[
                SchemaField(name="value", type_expr=TypeExpr(base_type="string")),
            ],
        )
        model = schema_to_pydantic(schema_def)

        instance = model.model_validate({"value": "from dict"})
        assert instance.value == "from dict"
