"""Tests for schema code generation.

Test that schema definitions are properly emitted as Pydantic create_model()
calls and that prompts with expecting clauses are linked to schemas.
"""

from streetrace.dsl.ast import (
    AgentDef,
    DslFile,
    FlowDef,
    Literal,
    PromptDef,
    ReturnStmt,
    SchemaDef,
    SchemaField,
    TypeExpr,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator


class TestSchemaEmission:
    """Test schema definitions are emitted correctly."""

    def test_simple_schema_generates_create_model(self) -> None:
        """Schema with simple fields generates create_model call."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="Result",
                    fields=[
                        SchemaField(
                            name="approved",
                            type_expr=TypeExpr(base_type="bool"),
                        ),
                        SchemaField(
                            name="message",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "create_model(" in code
        assert '"Result"' in code
        assert "approved=(bool, ...)" in code
        assert "message=(str, ...)" in code

    def test_schema_with_all_basic_types(self) -> None:
        """Schema emits correct Python types for all DSL types."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="AllTypes",
                    fields=[
                        SchemaField(
                            name="text",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                        SchemaField(
                            name="count",
                            type_expr=TypeExpr(base_type="int"),
                        ),
                        SchemaField(
                            name="score",
                            type_expr=TypeExpr(base_type="float"),
                        ),
                        SchemaField(
                            name="active",
                            type_expr=TypeExpr(base_type="bool"),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "text=(str, ...)" in code
        assert "count=(int, ...)" in code
        assert "score=(float, ...)" in code
        assert "active=(bool, ...)" in code

    def test_schema_with_list_type(self) -> None:
        """Schema emits list types correctly."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="ListResult",
                    fields=[
                        SchemaField(
                            name="items",
                            type_expr=TypeExpr(base_type="string", is_list=True),
                        ),
                        SchemaField(
                            name="counts",
                            type_expr=TypeExpr(base_type="int", is_list=True),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "items=(list[str], ...)" in code
        assert "counts=(list[int], ...)" in code

    def test_schema_with_optional_type(self) -> None:
        """Schema emits optional types correctly."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="OptionalResult",
                    fields=[
                        SchemaField(
                            name="maybe_text",
                            type_expr=TypeExpr(base_type="string", is_optional=True),
                        ),
                        SchemaField(
                            name="required_text",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Optional field uses None as default
        assert "maybe_text=(str | None, None)" in code
        # Required field uses ... (Ellipsis)
        assert "required_text=(str, ...)" in code

    def test_schema_with_optional_list_type(self) -> None:
        """Schema emits optional list types correctly."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="OptionalListResult",
                    fields=[
                        SchemaField(
                            name="maybe_items",
                            type_expr=TypeExpr(
                                base_type="string",
                                is_list=True,
                                is_optional=True,
                            ),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "maybe_items=(list[str] | None, None)" in code


class TestSchemasClassAttribute:
    """Test _schemas class attribute is generated correctly."""

    def test_schemas_dict_generated(self) -> None:
        """Schema generates _schemas class attribute."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="Result",
                    fields=[
                        SchemaField(
                            name="value",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "_schemas: dict[str, type[BaseModel]] = {" in code
        assert '"Result": Result,' in code

    def test_multiple_schemas_in_dict(self) -> None:
        """Multiple schemas are all included in _schemas dict."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="FirstResult",
                    fields=[
                        SchemaField(
                            name="value",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                SchemaDef(
                    name="SecondResult",
                    fields=[
                        SchemaField(
                            name="count",
                            type_expr=TypeExpr(base_type="int"),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert '"FirstResult": FirstResult,' in code
        assert '"SecondResult": SecondResult,' in code

    def test_empty_schemas_dict_when_no_schemas(self) -> None:
        """Empty _schemas dict when no schemas defined."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Uses generic dict type when no schemas to avoid importing BaseModel
        assert "_schemas: dict[str, type] = {}" in code


class TestPromptSchemaLinking:
    """Test prompts with expecting clause are linked to schemas."""

    def test_prompt_with_expecting_includes_schema(self) -> None:
        """Prompt with expecting generates PromptSpec with schema."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="ReviewResult",
                    fields=[
                        SchemaField(
                            name="approved",
                            type_expr=TypeExpr(base_type="bool"),
                        ),
                    ],
                ),
                PromptDef(
                    name="review",
                    body="Review the code",
                    expecting="ReviewResult",
                ),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="review",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # PromptSpec should include schema reference
        assert "schema='ReviewResult'" in code

    def test_prompt_without_expecting_no_schema(self) -> None:
        """Prompt without expecting does not include schema."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(
                    name="simple",
                    body="Simple prompt",
                ),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="simple",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should not have schema in PromptSpec
        assert "schema=" not in code


class TestPydanticImports:
    """Test Pydantic imports are added when schemas are present."""

    def test_pydantic_imports_when_schemas_present(self) -> None:
        """Pydantic imports added when schemas are defined."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="Result",
                    fields=[
                        SchemaField(
                            name="value",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        assert "from pydantic import BaseModel, create_model" in code

    def test_no_pydantic_imports_when_no_schemas(self) -> None:
        """No Pydantic imports when no schemas defined."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                PromptDef(name="test_prompt", body="Test"),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="test_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should not import create_model when no schemas
        assert "create_model" not in code


class TestGeneratedCodeCompilation:
    """Test generated code with schemas compiles successfully."""

    def test_schema_code_compiles(self) -> None:
        """Generated code with schemas compiles without errors."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="CodeReviewResult",
                    fields=[
                        SchemaField(
                            name="approved",
                            type_expr=TypeExpr(base_type="bool"),
                        ),
                        SchemaField(
                            name="severity",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                        SchemaField(
                            name="issues",
                            type_expr=TypeExpr(base_type="string", is_list=True),
                        ),
                        SchemaField(
                            name="confidence",
                            type_expr=TypeExpr(base_type="float"),
                        ),
                    ],
                ),
                PromptDef(
                    name="review_code",
                    body="Review the code",
                    expecting="CodeReviewResult",
                ),
                AgentDef(
                    name="code_reviewer",
                    tools=[],
                    instruction="review_code",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should compile without syntax errors
        compile(code, "<generated>", "exec")

    def test_multiple_schemas_compile(self) -> None:
        """Generated code with multiple schemas compiles."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="FirstResult",
                    fields=[
                        SchemaField(
                            name="text",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                SchemaDef(
                    name="SecondResult",
                    fields=[
                        SchemaField(
                            name="count",
                            type_expr=TypeExpr(base_type="int"),
                        ),
                        SchemaField(
                            name="items",
                            type_expr=TypeExpr(base_type="string", is_list=True),
                        ),
                    ],
                ),
                PromptDef(
                    name="first_prompt",
                    body="First prompt",
                    expecting="FirstResult",
                ),
                PromptDef(
                    name="second_prompt",
                    body="Second prompt",
                    expecting="SecondResult",
                ),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="first_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_optional_and_list_types_compile(self) -> None:
        """Generated code with optional and list types compiles."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="ComplexResult",
                    fields=[
                        SchemaField(
                            name="required_text",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                        SchemaField(
                            name="optional_text",
                            type_expr=TypeExpr(base_type="string", is_optional=True),
                        ),
                        SchemaField(
                            name="items",
                            type_expr=TypeExpr(base_type="string", is_list=True),
                        ),
                        SchemaField(
                            name="optional_items",
                            type_expr=TypeExpr(
                                base_type="int",
                                is_list=True,
                                is_optional=True,
                            ),
                        ),
                    ],
                ),
                PromptDef(
                    name="complex_prompt",
                    body="Complex prompt",
                    expecting="ComplexResult",
                ),
                AgentDef(
                    name="default",
                    tools=[],
                    instruction="complex_prompt",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        compile(code, "<generated>", "exec")

    def test_schema_with_flow_compiles(self) -> None:
        """Generated code with schemas and flows compiles."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="Result",
                    fields=[
                        SchemaField(
                            name="value",
                            type_expr=TypeExpr(base_type="string"),
                        ),
                    ],
                ),
                PromptDef(
                    name="test_prompt",
                    body="Test",
                    expecting="Result",
                ),
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

        compile(code, "<generated>", "exec")


class TestSchemaExampleFile:
    """Test schema.sr example file generates correct code."""

    def test_schema_sr_example_patterns(self) -> None:
        """Generated code matches expected patterns from schema.sr."""
        # Simplified version of schema.sr structure
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                SchemaDef(
                    name="CodeReviewResult",
                    fields=[
                        SchemaField(
                            name="approved",
                            type_expr=TypeExpr(base_type="bool"),
                        ),
                        SchemaField(
                            name="severity",
                            type_expr=TypeExpr(base_type="string"),
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
                            name="confidence",
                            type_expr=TypeExpr(base_type="float"),
                        ),
                    ],
                ),
                PromptDef(
                    name="review_code",
                    body="You are an expert code reviewer.",
                    expecting="CodeReviewResult",
                ),
                AgentDef(
                    name="code_reviewer",
                    tools=[],
                    instruction="review_code",
                    description="Reviews code and provides structured feedback",
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "schema.sr")

        # Verify schema definition
        assert "CodeReviewResult = create_model(" in code
        assert '"CodeReviewResult",' in code
        assert "approved=(bool, ...)" in code
        assert "issues=(list[str], ...)" in code
        assert "suggestions=(list[str], ...)" in code
        assert "confidence=(float, ...)" in code

        # Verify _schemas dict
        assert '"CodeReviewResult": CodeReviewResult,' in code

        # Verify prompt-schema linking
        assert "schema='CodeReviewResult'" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")
