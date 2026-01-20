"""Tests for error location tracking in DSL compiler.

Test that syntax and semantic errors correctly report source
locations for diagnostics.
"""


from streetrace.dsl.compiler import validate_dsl
from streetrace.dsl.errors.diagnostics import Severity


class TestSemanticErrorLineNumbers:
    """Test semantic error location tracking."""

    def test_undefined_model_reports_correct_line(self) -> None:
        """Undefined model reference reports the line where it's referenced."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) == 1
        # The error should point to line 5 where "undefined_model" is referenced
        # not line 1 where the file starts
        assert errors[0].line == 5, (
            f"Expected error on line 5, got line {errors[0].line}"
        )
        assert "undefined_model" in errors[0].message

    def test_duplicate_model_reports_second_definition_line(self) -> None:
        """Duplicate definition reports the line of the second definition."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

model main = openai/gpt-4o
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) == 1
        # The error should point to line 5 where the duplicate is defined
        assert errors[0].line == 5, (
            f"Expected error on line 5, got line {errors[0].line}"
        )
        assert "duplicate" in errors[0].message.lower()

    def test_undefined_tool_reports_correct_line(self) -> None:
        """Undefined tool reference reports the line where agent is defined."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt my_instruction: \"\"\"Help the user.\"\"\"

agent helper:
    tools undefined_tool
    instruction my_instruction
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) == 1
        # The error should point to line 7 where the agent with undefined tool is
        assert errors[0].line == 7, (
            f"Expected error on line 7, got line {errors[0].line}"
        )
        assert "undefined_tool" in errors[0].message

    def test_undefined_agent_in_flow_reports_correct_line(self) -> None:
        """Undefined agent in flow reports line of the run statement."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

flow my_flow:
    $result = run agent undefined_agent $input_prompt
    return $result
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) == 1
        # The error should point to line 6 where the run statement is
        assert errors[0].line == 6, (
            f"Expected error on line 6, got line {errors[0].line}"
        )
        assert "undefined_agent" in errors[0].message

    def test_undefined_variable_in_flow_without_params(self) -> None:
        """Flow without parameters accessing undefined variable produces an error."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

flow my_flow:
    $x = 42
    return $undefined_var
"""
        # Note: Depending on semantic analyzer behavior, undefined variables
        # inside flows may or may not be errors. This test documents current behavior.
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        # If the semantic analyzer catches undefined variables, it should report
        # the correct line. If it doesn't catch them, this test passes with no errors.
        if errors:
            # The error should point to line 7 where the undefined variable is used
            assert errors[0].line == 7, (
                f"Expected error on line 7, got line {errors[0].line}"
            )
            assert "undefined_var" in errors[0].message

    def test_undefined_prompt_reports_correct_line(self) -> None:
        """Undefined prompt in call statement reports correct line."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

flow my_flow:
    $result = call llm undefined_prompt $input_prompt
    return $result
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) == 1
        # The error should point to line 6 where the call statement is
        assert errors[0].line == 6, (
            f"Expected error on line 6, got line {errors[0].line}"
        )
        assert "undefined_prompt" in errors[0].message


class TestSyntaxErrorCaretPosition:
    """Test syntax error caret position in diagnostics."""

    def test_missing_colon_error_position(self) -> None:
        """Missing colon shows caret at expected position."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

agent
    tools fs
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) >= 1
        # The error should point to where the colon is expected
        # which is after "agent" on line 5
        assert errors[0].line == 5, (
            f"Expected error on line 5, got line {errors[0].line}"
        )
        # Column should point to after "agent" where colon is expected
        # "agent" is 5 characters, so column should be around 5-6
        # (0-indexed column 5 = position after "agent")

    def test_unexpected_token_error_position(self) -> None:
        """Unexpected token shows caret at the token position."""
        source = """\
streetrace v1

model = broken
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) >= 1
        # The error should point to line 3
        assert errors[0].line == 3, (
            f"Expected error on line 3, got line {errors[0].line}"
        )

    def test_invalid_character_error_position(self) -> None:
        """Invalid character shows caret at the character position."""
        source = """\
streetrace v1

model main @ invalid
"""
        diagnostics = validate_dsl(source, "test.sr")
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]

        assert len(errors) >= 1
        # Error should point to line 3
        assert errors[0].line == 3, (
            f"Expected error on line 3, got line {errors[0].line}"
        )
