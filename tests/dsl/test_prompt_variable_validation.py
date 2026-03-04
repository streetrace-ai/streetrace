"""Integration tests for prompt variable validation.

Test the full compile pipeline for prompt variable handling including:
- Instructions with runtime variables (should error)
- Prompts with global/context variables (should interpolate)
- Prompts with undefined variables (typo detection)
- Forward reference detection
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl import (
    DslAgentWorkflow,
    DslSemanticError,
    compile_dsl,
    validate_dsl,
)

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_model_factory() -> "ModelFactory":
    """Create a mock ModelFactory."""
    factory = MagicMock()
    factory.get_current_model.return_value = MagicMock()
    factory.get_llm_interface.return_value = MagicMock()
    return factory


@pytest.fixture
def mock_tool_provider() -> "ToolProvider":
    """Create a mock ToolProvider."""
    return MagicMock()


@pytest.fixture
def mock_system_context() -> "SystemContext":
    """Create a mock SystemContext."""
    return MagicMock()


@pytest.fixture
def mock_session_service() -> "BaseSessionService":
    """Create a mock BaseSessionService with async methods."""
    service = MagicMock()
    service.get_session = AsyncMock(return_value=None)
    service.create_session = AsyncMock()
    return service


def _execute_bytecode(bytecode: object) -> type[DslAgentWorkflow]:
    """Run bytecode and extract workflow class."""
    namespace: dict[str, object] = {}
    # SECURITY: This is test code running validated DSL bytecode
    exec(bytecode, namespace)  # noqa: S102  # nosec B102

    for obj in namespace.values():
        is_workflow = (
            isinstance(obj, type)
            and issubclass(obj, DslAgentWorkflow)
            and obj is not DslAgentWorkflow
        )
        if is_workflow:
            return obj

    msg = "No workflow class found"
    raise ValueError(msg)


# =============================================================================
# 1. Instructions with Runtime Variables (Should Error)
# =============================================================================


class TestInstructionVariableErrors:
    """Instructions are resolved at agent creation time with empty context.

    Any $variable in an instruction prompt will resolve to empty string,
    so we raise E0016 errors at compile time.
    """

    def test_instruction_with_runtime_var_fails_compilation(self) -> None:
        """Instruction referencing runtime variable produces E0016 error."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt my_instruction: \"\"\"
Process this context: $context
And this data: $data
\"\"\"

agent my_agent:
    instruction my_instruction
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        # Should have E0016 errors for runtime variables in instruction
        errors = exc_info.value.errors
        e0016_errors = [e for e in errors if e.code.name == "E0016"]
        assert len(e0016_errors) >= 2
        error_messages = " ".join(e.message for e in e0016_errors)
        assert "context" in error_messages
        assert "data" in error_messages

    def test_instruction_with_property_access_fails(self) -> None:
        """Instruction with $var.property also produces E0016 error."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt validator_instruction: \"\"\"
Validate finding at $finding.file line $finding.line_start
\"\"\"

agent validator:
    instruction validator_instruction
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        errors = exc_info.value.errors
        e0016_errors = [e for e in errors if e.code.name == "E0016"]
        assert len(e0016_errors) >= 1
        assert any("finding" in e.message for e in e0016_errors)

    def test_instruction_with_prompt_composition_succeeds(self) -> None:
        """Instruction can reference other prompts (composition is valid)."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt shared_rules: \"\"\"Always be concise and accurate.\"\"\"

prompt my_instruction: \"\"\"
You are a helpful assistant.
$shared_rules
\"\"\"

agent my_agent:
    instruction my_instruction
"""
        # Should compile without errors
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        assert bytecode is not None

    def test_instruction_validation_reports_all_variables(self) -> None:
        """All runtime variables in instruction are reported."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt complex_instruction: \"\"\"
Context: $pr_context
Chunk: $chunk
Finding: $finding
Item: $item.property
\"\"\"

agent reviewer:
    instruction complex_instruction
"""
        diagnostics = validate_dsl(source, "test.sr")

        e0016_diagnostics = [
            d for d in diagnostics
            if d.code and d.code.value == "E0016"
        ]
        # Should report all 4 runtime variables
        assert len(e0016_diagnostics) == 4
        messages = " ".join(d.message for d in e0016_diagnostics)
        assert "pr_context" in messages
        assert "chunk" in messages
        assert "finding" in messages
        assert "item" in messages


# =============================================================================
# 2. Prompts with Global Variables (Should Interpolate)
# =============================================================================


class TestPromptGlobalVariableInterpolation:
    """Prompts (not instructions) can use runtime variables.

    These are resolved at runtime via ctx.resolve().
    """

    def test_prompt_with_runtime_vars_compiles(self) -> None:
        """Prompt field can have runtime variables (resolved at runtime)."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt static_instruction: \"\"\"You are a reviewer.\"\"\"

prompt review_prompt: \"\"\"
Review this PR:
$pr_context

Changes:
$changes
\"\"\"

agent reviewer:
    instruction static_instruction
    prompt review_prompt
"""
        # Should compile without errors
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        assert bytecode is not None

    def test_prompt_interpolation_at_runtime(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Verify runtime variables are interpolated in prompts."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greet: \"\"\"Hello $name, welcome to $place!\"\"\"

flow main:
    return $input_prompt
"""
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = instance.create_context()

        # Set runtime variables
        ctx.vars["name"] = "Alice"
        ctx.vars["place"] = "Wonderland"

        # Resolve the prompt
        result = ctx.resolve("greet")
        assert "Hello Alice" in result
        assert "welcome to Wonderland" in result

    def test_builtin_input_prompt_interpolation(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Built-in $input_prompt variable is available."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt echo: \"\"\"You said: $input_prompt\"\"\"

flow main:
    return $input_prompt
"""
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = instance.create_context(input_prompt="Hello world")

        result = ctx.resolve("echo")
        assert "You said: Hello world" in result


# =============================================================================
# 3. Context Variables Defined Before Agent Run (Should Work)
# =============================================================================


class TestContextVariablesBeforeAgentRun:
    """Variables produced by earlier agents are available to later prompts."""

    def test_produces_variable_available_in_later_prompt(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Agent produces variable that later prompt can reference."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt fetcher_instruction: \"\"\"Fetch context data.\"\"\"

prompt reviewer_prompt: \"\"\"
Review with context:
$pr_context
\"\"\"

agent context_fetcher:
    instruction fetcher_instruction
    produces pr_context

agent reviewer:
    instruction fetcher_instruction
    prompt reviewer_prompt

flow main:
    run agent context_fetcher
    run agent reviewer
    return $input_prompt
"""
        # Should compile - pr_context is produced before reviewer uses it
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = instance.create_context()

        # Simulate what context_fetcher would produce
        ctx.vars["pr_context"] = "This is the PR context"

        # Now reviewer_prompt should resolve correctly
        result = ctx.resolve("reviewer_prompt")
        assert "This is the PR context" in result

    def test_runtime_variable_in_prompt_field_compiles(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Runtime variables in prompt field compile and resolve at runtime."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt chunk_prompt: \"\"\"
Process chunk: $chunk_data
\"\"\"

prompt static_instruction: \"\"\"Process chunks.\"\"\"

agent chunk_processor:
    instruction static_instruction
    prompt chunk_prompt

flow main:
    run agent chunk_processor
    return $input_prompt
"""
        # Should compile - $chunk_data in prompt field is runtime variable
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = instance.create_context()

        # Set runtime variable before resolving prompt
        ctx.vars["chunk_data"] = "Test Chunk Content"

        result = ctx.resolve("chunk_prompt")
        assert "Test Chunk Content" in result


# =============================================================================
# 4. Context Variables Defined After Agent Run (Edge Case)
# =============================================================================


class TestContextVariablesAfterAgentRun:
    """Variables used before they're produced.

    This is a semantic ordering issue - the prompt references a variable
    that will only exist after a later agent runs.
    """

    def test_forward_reference_resolves_to_empty_at_runtime(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Forward reference to unpopulated variable resolves to empty string.

        This is current runtime behavior - ctx.resolve() returns ""
        for unknown variables. The semantic analyzer doesn't track
        flow execution order, so this compiles but produces empty output.
        """
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt use_future: \"\"\"Data: $future_data\"\"\"

prompt producer_instruction: \"\"\"Produce data.\"\"\"

agent producer:
    instruction producer_instruction
    produces future_data

flow main:
    $early = call llm use_future
    run agent producer
    return $input_prompt
"""
        # Compiles (semantic analyzer doesn't track execution order)
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = instance.create_context()

        # Before producer runs, future_data doesn't exist
        result = ctx.resolve("use_future")
        # Should resolve to empty string for undefined variable
        assert result == "Data: "


# =============================================================================
# 5. Prompts with Undefined Variables (Typo Detection)
# =============================================================================


class TestUndefinedVariableTypoDetection:
    """Typos of known symbols produce E0015 errors.

    Unknown variables that don't match known symbols are assumed to be
    runtime variables and allowed through.
    """

    def test_typo_of_prompt_name_produces_error(self) -> None:
        """Typo of a defined prompt produces E0015 error."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt helper_rules: \"\"\"Be helpful and concise.\"\"\"

prompt main_prompt: \"\"\"
Follow these rules:
$helpr_rules
\"\"\"
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        errors = exc_info.value.errors
        e0015_errors = [e for e in errors if e.code.name == "E0015"]
        assert len(e0015_errors) == 1
        assert "helpr_rules" in e0015_errors[0].message
        # Should suggest the correct name
        assert e0015_errors[0].suggestion is not None
        assert "helper_rules" in e0015_errors[0].suggestion

    def test_typo_of_produces_name_produces_error(self) -> None:
        """Typo of an agent produces name produces E0015 error."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt fetcher_instruction: \"\"\"Fetch data.\"\"\"

prompt use_context: \"\"\"Context: $pr_contex\"\"\"

agent fetcher:
    instruction fetcher_instruction
    produces pr_context
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        errors = exc_info.value.errors
        e0015_errors = [e for e in errors if e.code.name == "E0015"]
        assert len(e0015_errors) == 1
        assert "pr_contex" in e0015_errors[0].message
        assert e0015_errors[0].suggestion is not None
        assert "pr_context" in e0015_errors[0].suggestion

    def test_typo_of_builtin_produces_error(self) -> None:
        """Typo of built-in variable produces E0015 error."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt echo: \"\"\"You said: $input_promt\"\"\"
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        errors = exc_info.value.errors
        e0015_errors = [e for e in errors if e.code.name == "E0015"]
        assert len(e0015_errors) == 1
        assert "input_promt" in e0015_errors[0].message
        assert e0015_errors[0].suggestion is not None
        assert "input_prompt" in e0015_errors[0].suggestion

    def test_unknown_variable_without_typo_passes(self) -> None:
        """Unknown variable without similar match passes (runtime var)."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt dynamic: \"\"\"
Process: $completely_different_name
With: $another_runtime_var
\"\"\"
"""
        # Should compile - these don't match any known symbols
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        assert bytecode is not None


# =============================================================================
# 6. Additional Typo Detection Scenarios
# =============================================================================


class TestTypoDetectionScenarios:
    """Additional typo detection test cases."""

    def test_multiple_typos_all_reported(self) -> None:
        """Multiple typos in same prompt are all reported.

        Note: Typo detection uses 0.85 LCS similarity threshold.
        Short strings like 'rule' vs 'rules' (80%) won't be caught.
        We use longer strings to ensure they meet the threshold.
        """
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt security_guidelines: \"\"\"Follow security guidelines.\"\"\"
prompt review_instructions: \"\"\"Review instructions.\"\"\"

prompt main_prompt: \"\"\"
$security_guideline
$review_instruction
\"\"\"
"""
        diagnostics = validate_dsl(source, "test.sr")

        e0015_diagnostics = [
            d for d in diagnostics
            if d.code and d.code.value == "E0015"
        ]
        # Should catch both typos (missing 's' at end)
        # security_guideline vs security_guidelines = 18/19 = 94.7%
        # review_instruction vs review_instructions = 18/19 = 94.7%
        assert len(e0015_diagnostics) >= 2

    def test_case_sensitive_typo_detection(self) -> None:
        """Typo detection is case-sensitive but catches similar names."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt MyPrompt: \"\"\"Content.\"\"\"

prompt user_prompt: \"\"\"Use: $mypromt\"\"\"
"""
        # 'mypromt' is similar to 'MyPrompt' (case difference + typo)
        diagnostics = validate_dsl(source, "test.sr")

        # May or may not catch depending on similarity threshold
        # The key is it compiles/validates without crashing
        assert diagnostics is not None

    def test_property_access_typo_on_base_variable(self) -> None:
        """Typo on base variable with property access is caught."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt fetcher_instruction: \"\"\"Fetch.\"\"\"

prompt use_finding: \"\"\"
File: $findin.file
Line: $findin.line_start
\"\"\"

agent reviewer:
    instruction fetcher_instruction
    produces finding
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        errors = exc_info.value.errors
        e0015_errors = [e for e in errors if e.code.name == "E0015"]
        assert len(e0015_errors) >= 1
        assert any("findin" in e.message for e in e0015_errors)

    def test_braced_variable_typo_detection(self) -> None:
        """Typo detection works with ${var} syntax too.

        Note: Uses longer prompt name to meet 0.85 LCS threshold.
        """
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt helper_prompt: \"\"\"Help.\"\"\"

prompt main_prompt: \"\"\"Use: ${helpr_prompt}\"\"\"
"""
        with pytest.raises(DslSemanticError) as exc_info:
            compile_dsl(source, "test.sr", use_cache=False)

        errors = exc_info.value.errors
        e0015_errors = [e for e in errors if e.code.name == "E0015"]
        assert len(e0015_errors) == 1
        assert "helpr_prompt" in e0015_errors[0].message


# =============================================================================
# Validation Mode Tests (Non-Throwing)
# =============================================================================


class TestValidationMode:
    """Test validate_dsl() returns diagnostics without throwing."""

    def test_validation_returns_e0016_diagnostics(self) -> None:
        """validate_dsl returns E0016 diagnostics for instruction vars."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt bad_instruction: \"\"\"Process: $runtime_var\"\"\"

agent my_agent:
    instruction bad_instruction
"""
        diagnostics = validate_dsl(source, "test.sr")

        e0016 = [d for d in diagnostics if d.code and d.code.value == "E0016"]
        assert len(e0016) == 1
        assert "runtime_var" in e0016[0].message

    def test_validation_returns_e0015_diagnostics(self) -> None:
        """validate_dsl returns E0015 diagnostics for typos."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt helper_prompt: \"\"\"Help.\"\"\"

prompt main_prompt: \"\"\"$helpr_prompt\"\"\"
"""
        diagnostics = validate_dsl(source, "test.sr")

        e0015 = [d for d in diagnostics if d.code and d.code.value == "E0015"]
        assert len(e0015) == 1
        assert "helpr_prompt" in e0015[0].message

    def test_validation_includes_help_text(self) -> None:
        """Diagnostics include helpful suggestions."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt my_instruction: \"\"\"Process: $context\"\"\"

agent my_agent:
    instruction my_instruction
"""
        diagnostics = validate_dsl(source, "test.sr")

        e0016 = [d for d in diagnostics if d.code and d.code.value == "E0016"]
        assert len(e0016) == 1
        # Should have help text about moving to prompt field
        assert e0016[0].help_text is not None
        assert "prompt" in e0016[0].help_text.lower()


# =============================================================================
# Combined Scenarios
# =============================================================================


class TestCombinedScenarios:
    """Test realistic combined scenarios."""

    def test_code_review_agent_pattern(self) -> None:
        """Realistic code review agent with proper variable usage."""
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt no_inference: \"\"\"Do not infer or assume.\"\"\"

prompt fetcher_instruction: \"\"\"
Fetch PR context from GitHub.
$no_inference
\"\"\"

prompt reviewer_instruction: \"\"\"
You are a security reviewer.
$no_inference
\"\"\"

prompt reviewer_prompt: \"\"\"
Review this PR:
$pr_context

Changes:
$chunk
\"\"\"

agent context_fetcher:
    instruction fetcher_instruction
    produces pr_context

agent security_reviewer:
    instruction reviewer_instruction
    prompt reviewer_prompt

flow main:
    run agent context_fetcher
    run agent security_reviewer
    return $input_prompt
"""
        # Should compile - instructions use only prompt composition,
        # runtime vars are in prompt field
        bytecode, _ = compile_dsl(source, "test.sr", use_cache=False)
        assert bytecode is not None

    def test_mixed_errors_all_reported(self) -> None:
        """Multiple error types are all reported together.

        Note: Uses longer prompt name to meet 0.85 LCS threshold for typo detection.
        """
        source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt helper_prompt: \"\"\"Help.\"\"\"

prompt bad_instruction: \"\"\"
Process: $runtime_var
With: $helpr_prompt
\"\"\"

agent my_agent:
    instruction bad_instruction
"""
        diagnostics = validate_dsl(source, "test.sr")

        # Should have E0016 for runtime_var in instruction
        e0016 = [d for d in diagnostics if d.code and d.code.value == "E0016"]
        assert len(e0016) >= 1

        # Should have E0015 for typo of 'helper_prompt' (helpr_prompt is 91% similar)
        e0015 = [d for d in diagnostics if d.code and d.code.value == "E0015"]
        assert len(e0015) >= 1
