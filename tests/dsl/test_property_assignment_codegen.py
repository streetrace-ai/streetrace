"""Tests for property assignment code generation.

Test coverage for code generation of property assignment statements.
"""

from streetrace.dsl.ast.nodes import (
    AgentDef,
    DslFile,
    FlowDef,
    Literal,
    PromptDef,
    PropertyAccess,
    PropertyAssignment,
    ReturnStmt,
    ToolDef,
    VarRef,
    VersionDecl,
)
from streetrace.dsl.codegen.generator import CodeGenerator


class TestPropertyAssignmentCodegen:
    """Test code generation for property assignment statements."""

    def test_generates_simple_property_assignment(self) -> None:
        """Generate code for simple property assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="test_flow",
                    params=[],
                    body=[
                        PropertyAssignment(
                            target=PropertyAccess(
                                base=VarRef(name="review"),
                                properties=["findings"],
                            ),
                            value=VarRef(name="filtered"),
                        ),
                        ReturnStmt(value=VarRef(name="review")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate nested dict assignment
        assert "ctx.vars['review']['findings'] = ctx.vars['filtered']" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_nested_property_assignment(self) -> None:
        """Generate code for nested property assignment."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="test_flow",
                    params=[],
                    body=[
                        PropertyAssignment(
                            target=PropertyAccess(
                                base=VarRef(name="data"),
                                properties=["nested", "deep"],
                            ),
                            value=Literal(value="value", literal_type="string"),
                        ),
                        ReturnStmt(value=VarRef(name="data")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate nested dict assignment with multiple levels
        assert "ctx.vars['data']['nested']['deep'] = \"value\"" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_property_assignment_with_integer(self) -> None:
        """Generate code for property assignment with integer value."""
        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="test_flow",
                    params=[],
                    body=[
                        PropertyAssignment(
                            target=PropertyAccess(
                                base=VarRef(name="data"),
                                properties=["count"],
                            ),
                            value=Literal(value=0, literal_type="int"),
                        ),
                        ReturnStmt(value=VarRef(name="data")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate assignment with integer value
        assert "ctx.vars['data']['count'] = 0" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_generates_property_assignment_with_list(self) -> None:
        """Generate code for property assignment with empty list."""
        from streetrace.dsl.ast.nodes import ListLiteral

        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="test_flow",
                    params=[],
                    body=[
                        PropertyAssignment(
                            target=PropertyAccess(
                                base=VarRef(name="review"),
                                properties=["issues"],
                            ),
                            value=ListLiteral(elements=[]),
                        ),
                        ReturnStmt(value=VarRef(name="review")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should generate assignment with empty list
        assert "ctx.vars['review']['issues'] = []" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")

    def test_backward_compat_simple_assignment(self) -> None:
        """Backward compat - simple assignment still works."""
        from streetrace.dsl.ast.nodes import Assignment

        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="test_flow",
                    params=[],
                    body=[
                        Assignment(
                            target="result",
                            value=Literal(value="value", literal_type="string"),
                        ),
                        ReturnStmt(value=VarRef(name="result")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should use simple ctx.vars assignment
        assert "ctx.vars['result'] = \"value\"" in code
        # Should NOT have nested dict access for simple assignment
        assert "ctx.vars['result']['']" not in code

        # Verify code compiles
        compile(code, "<generated>", "exec")


class TestPropertyAssignmentIntegration:
    """Integration tests for property assignment end-to-end."""

    def test_complete_flow_with_property_assignment(self) -> None:
        """Test complete flow using property assignment."""
        from streetrace.dsl.ast.nodes import Assignment, ObjectLiteral

        ast = DslFile(
            version=VersionDecl(version="v1"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help with tasks"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
                FlowDef(
                    name="test_flow",
                    params=[],
                    body=[
                        # Initialize object
                        Assignment(
                            target="review",
                            value=ObjectLiteral(
                                entries={
                                    "findings": VarRef(name="input"),
                                    "score": Literal(value=0, literal_type="int"),
                                },
                            ),
                        ),
                        # Modify property
                        PropertyAssignment(
                            target=PropertyAccess(
                                base=VarRef(name="review"),
                                properties=["score"],
                            ),
                            value=Literal(value=100, literal_type="int"),
                        ),
                        # Return modified object
                        ReturnStmt(value=VarRef(name="review")),
                    ],
                ),
            ],
        )

        generator = CodeGenerator()
        code, _mappings = generator.generate(ast, "test.sr")

        # Should have both assignment types
        assert "ctx.vars['review'] = {" in code
        assert "ctx.vars['review']['score'] = 100" in code

        # Verify code compiles
        compile(code, "<generated>", "exec")
