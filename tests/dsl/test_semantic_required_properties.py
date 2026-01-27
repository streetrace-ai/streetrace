"""Tests for semantic validation of required properties.

Test that missing required properties trigger appropriate errors,
specifically E0010 for agents without instruction.
"""

from streetrace.dsl.ast import (
    AgentDef,
    DslFile,
    PromptDef,
    SourcePosition,
    ToolDef,
    VersionDecl,
)
from streetrace.dsl.semantic import SemanticAnalyzer
from streetrace.dsl.semantic.errors import ErrorCode


class TestAgentMissingInstruction:
    """Test E0010 error for agents missing required instruction property."""

    def test_agent_without_instruction_triggers_e0010(self) -> None:
        """Agent without instruction property triggers E0010 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="",  # Empty instruction
                    meta=SourcePosition(line=5, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid
        assert len(result.errors) >= 1

        # Find the E0010 error
        e0010_errors = [e for e in result.errors if e.code == ErrorCode.E0010]
        assert len(e0010_errors) == 1

        error = e0010_errors[0]
        assert "instruction" in error.message.lower()
        assert error.position is not None
        assert error.position.line == 5

    def test_agent_with_instruction_passes(self) -> None:
        """Agent with valid instruction property passes validation."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="helper_prompt", body="Help the user with files"),
                AgentDef(
                    name="helper",
                    tools=["fs"],
                    instruction="helper_prompt",
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_unnamed_agent_without_instruction_triggers_e0010(self) -> None:
        """Unnamed (default) agent without instruction triggers E0010 error."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                AgentDef(
                    name=None,  # Unnamed/default agent
                    tools=["fs"],
                    instruction="",  # Empty instruction
                    meta=SourcePosition(line=3, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid

        # Find the E0010 error
        e0010_errors = [e for e in result.errors if e.code == ErrorCode.E0010]
        assert len(e0010_errors) == 1

        error = e0010_errors[0]
        assert "instruction" in error.message.lower()
        # Error should indicate it's for the default agent
        assert "default" in error.message.lower() or "agent" in error.message.lower()

    def test_multiple_agents_one_missing_instruction(self) -> None:
        """Only the agent missing instruction triggers E0010."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                ToolDef(name="fs", tool_type="builtin", builtin_ref="filesystem"),
                PromptDef(name="valid_prompt", body="Valid instruction"),
                AgentDef(
                    name="valid_agent",
                    tools=["fs"],
                    instruction="valid_prompt",
                ),
                AgentDef(
                    name="invalid_agent",
                    tools=["fs"],
                    instruction="",  # Missing instruction
                    meta=SourcePosition(line=10, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid

        # Should have exactly one E0010 error
        e0010_errors = [e for e in result.errors if e.code == ErrorCode.E0010]
        assert len(e0010_errors) == 1
        assert "invalid_agent" in e0010_errors[0].message

    def test_agent_missing_instruction_has_helpful_suggestion(self) -> None:
        """E0010 error includes helpful suggestion for fixing."""
        ast = DslFile(
            version=VersionDecl(version="1.0"),
            statements=[
                AgentDef(
                    name="helper",
                    tools=[],
                    instruction="",
                    meta=SourcePosition(line=1, column=0),
                ),
            ],
        )
        analyzer = SemanticAnalyzer()
        result = analyzer.analyze(ast)

        assert not result.is_valid

        e0010_errors = [e for e in result.errors if e.code == ErrorCode.E0010]
        assert len(e0010_errors) == 1

        error = e0010_errors[0]
        # Error should have a helpful suggestion
        assert error.suggestion is not None
        assert "instruction" in error.suggestion.lower()
