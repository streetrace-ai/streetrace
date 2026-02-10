"""Integration tests for DSL compiler.

Test the full compile-to-run pipeline including compilation,
workflow creation, and error handling.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from streetrace.dsl import (
    DslAgentWorkflow,
    DslSemanticError,
    DslSyntaxError,
    compile_dsl,
    validate_dsl,
)
from streetrace.dsl.runtime import WorkflowContext

if TYPE_CHECKING:
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.llm.model_factory import ModelFactory
    from streetrace.system_context import SystemContext
    from streetrace.tools.tool_provider import ToolProvider


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

# =============================================================================
# Test DSL Sources
# =============================================================================

MINIMAL_AGENT_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt my_prompt: \"\"\"You are a helpful assistant.\"\"\"

tool github = mcp "https://api.github.com/mcp/"

agent:
    tools github
    instruction my_prompt
"""

AGENT_WITH_HANDLER_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

on input do
    mask pii
end

on output do
    mask pii
end
"""

AGENT_WITH_FLOW_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt task_prompt: \"\"\"Process the input.\"\"\"

tool fs = builtin streetrace.filesystem

agent processor:
    tools fs
    instruction task_prompt

flow process_items:
    $result = run agent processor with $input_prompt
    return $result
"""

AGENT_WITH_PARALLEL_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt task_prompt: \"\"\"Do task.\"\"\"

tool fs = builtin streetrace.filesystem

agent task_a:
    tools fs
    instruction task_prompt

agent task_b:
    tools fs
    instruction task_prompt

flow parallel_flow:
    parallel do
        $result_a = run agent task_a
        $result_b = run agent task_b
    end
    return $result_a
"""

AGENT_WITH_MATCH_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt process_prompt: \"\"\"Process.\"\"\"

tool fs = builtin streetrace.filesystem

agent standard_processor:
    tools fs
    instruction process_prompt

flow handle_type:
    $result = run agent standard_processor
    return $result
"""

AGENT_WITH_GUARDRAILS_SOURCE = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting: \"\"\"Hello!\"\"\"

on input do
    mask pii
    block if jailbreak
end

on tool-result do
    mask pii
end

on output do
    warn if sensitive
end
"""


def _execute_bytecode(bytecode: object) -> type[DslAgentWorkflow]:
    """Run bytecode and extract workflow class.

    Args:
        bytecode: Compiled Python bytecode.

    Returns:
        The generated workflow class.

    """
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
# Compilation Integration Tests
# =============================================================================


class TestCompilationPipeline:
    """Test the full compilation pipeline."""

    def test_minimal_agent_compiles(self) -> None:
        """Compile a minimal agent and verify bytecode is produced."""
        bytecode, source_map = compile_dsl(MINIMAL_AGENT_SOURCE, "test.sr")

        assert bytecode is not None
        # Source map may be empty depending on the file
        assert source_map is not None

    def test_compilation_produces_runnable_bytecode(self) -> None:
        """Compiled bytecode should be runnable."""
        bytecode, source_map = compile_dsl(MINIMAL_AGENT_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        assert workflow_class is not None
        assert issubclass(workflow_class, DslAgentWorkflow)

    def test_workflow_can_be_instantiated(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Compiled workflow class should be instantiable."""
        bytecode, _ = compile_dsl(MINIMAL_AGENT_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        assert isinstance(instance, DslAgentWorkflow)

    def test_workflow_creates_context(
        self,
        mock_model_factory: "ModelFactory",
        mock_tool_provider: "ToolProvider",
        mock_system_context: "SystemContext",
        mock_session_service: "BaseSessionService",
    ) -> None:
        """Workflow should create valid context."""
        bytecode, _ = compile_dsl(MINIMAL_AGENT_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        instance = workflow_class(
            model_factory=mock_model_factory,
            tool_provider=mock_tool_provider,
            system_context=mock_system_context,
            session_service=mock_session_service,
        )
        ctx = instance.create_context()

        assert isinstance(ctx, WorkflowContext)
        assert hasattr(ctx, "vars")
        assert hasattr(ctx, "guardrails")


# =============================================================================
# Event Handler Tests
# =============================================================================


class TestEventHandlerGeneration:
    """Test event handler generation and methods."""

    def test_on_input_handler_generates_method(self) -> None:
        """On input handler should generate on_input method."""
        bytecode, _ = compile_dsl(AGENT_WITH_HANDLER_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        # Check that on_input is overridden
        assert hasattr(workflow_class, "on_input")
        # The method should be async
        import inspect

        assert inspect.iscoroutinefunction(workflow_class.on_input)

    def test_on_output_handler_generates_method(self) -> None:
        """On output handler should generate on_output method."""
        bytecode, _ = compile_dsl(AGENT_WITH_HANDLER_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        assert hasattr(workflow_class, "on_output")


# =============================================================================
# Flow Generation Tests
# =============================================================================


class TestFlowGeneration:
    """Test flow generation produces correct methods."""

    def test_flow_generates_method(self) -> None:
        """Flow definition should generate flow method."""
        bytecode, _ = compile_dsl(AGENT_WITH_FLOW_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        # Flow should be named flow_<name>
        assert hasattr(workflow_class, "flow_process_items")

    def test_parallel_block_compiles(self) -> None:
        """Parallel block should compile successfully."""
        bytecode, _ = compile_dsl(AGENT_WITH_PARALLEL_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        assert hasattr(workflow_class, "flow_parallel_flow")

    def test_simple_flow_compiles(self) -> None:
        """Simple flow with run agent should compile successfully."""
        bytecode, _ = compile_dsl(AGENT_WITH_MATCH_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        assert hasattr(workflow_class, "flow_handle_type")


# =============================================================================
# Guardrail Generation Tests
# =============================================================================


class TestGuardrailGeneration:
    """Test guardrail action generation."""

    def test_guardrail_actions_compile(self) -> None:
        """Guardrail actions should compile without errors."""
        bytecode, _ = compile_dsl(AGENT_WITH_GUARDRAILS_SOURCE, "test.sr")

        workflow_class = _execute_bytecode(bytecode)

        assert workflow_class is not None


# =============================================================================
# Source Map Tests
# =============================================================================


class TestSourceMapGeneration:
    """Test source map generation and accuracy."""

    def test_source_map_covers_key_constructs(self) -> None:
        """Source map should cover key DSL constructs."""
        _, source_map = compile_dsl(AGENT_WITH_FLOW_SOURCE, "test.sr")

        # Source map is generated for tracking
        assert source_map is not None

        # If there are mappings, check that source lines are reasonable
        if source_map:
            source_lines = {m.source_line for m in source_map}
            assert all(line >= 1 for line in source_lines)

    def test_source_map_file_reference(self) -> None:
        """Source mappings should reference correct file."""
        # Disable cache to ensure this test gets correct filename in mappings
        _, source_map = compile_dsl(
            MINIMAL_AGENT_SOURCE, "my_agent.sr", use_cache=False,
        )

        for mapping in source_map:
            assert mapping.source_file == "my_agent.sr"


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Test DSL validation without compilation."""

    def test_validate_valid_source_no_errors(self) -> None:
        """Valid source should produce no error diagnostics."""
        diagnostics = validate_dsl(MINIMAL_AGENT_SOURCE, "test.sr")

        errors = [d for d in diagnostics if d.severity.name.lower() == "error"]
        assert not errors

    def test_validate_syntax_error(self) -> None:
        """Syntax errors should be reported as diagnostics."""
        bad_source = "model = broken"

        diagnostics = validate_dsl(bad_source, "test.sr")

        assert len(diagnostics) > 0

    def test_validate_semantic_error(self) -> None:
        """Semantic errors should be reported as diagnostics."""
        bad_source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""
        diagnostics = validate_dsl(bad_source, "test.sr")

        errors = [d for d in diagnostics if d.severity.name.lower() == "error"]
        assert len(errors) > 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling during compilation."""

    def test_syntax_error_raises_dsl_syntax_error(self) -> None:
        """Syntax errors should raise DslSyntaxError."""
        bad_source = "model = broken"

        with pytest.raises(DslSyntaxError):
            compile_dsl(bad_source, "test.sr")

    def test_semantic_error_raises_dsl_semantic_error(self) -> None:
        """Semantic errors should raise DslSemanticError."""
        bad_source = """\
streetrace v1

model main = anthropic/claude-sonnet

prompt greeting using model "undefined_model": \"\"\"Hello!\"\"\"
"""
        with pytest.raises(DslSemanticError):
            compile_dsl(bad_source, "test.sr")


# =============================================================================
# Caching Tests
# =============================================================================


class TestCaching:
    """Test bytecode caching functionality."""

    def test_cached_compilation_returns_same_bytecode(self) -> None:
        """Second compilation should return cached bytecode."""
        import time

        source = MINIMAL_AGENT_SOURCE

        # First compilation
        start1 = time.perf_counter()
        bytecode1, _ = compile_dsl(source, "test.sr", use_cache=True)
        time1 = time.perf_counter() - start1

        # Second compilation (should be cached)
        start2 = time.perf_counter()
        bytecode2, _ = compile_dsl(source, "test.sr", use_cache=True)
        time2 = time.perf_counter() - start2

        # Bytecode should be identical (same object from cache)
        assert bytecode1 is bytecode2

        # Second should be faster (cache hit)
        assert time2 < time1

    def test_different_source_not_cached(self) -> None:
        """Different sources should not share cache entries."""
        source1 = MINIMAL_AGENT_SOURCE
        source2 = AGENT_WITH_HANDLER_SOURCE

        bytecode1, _ = compile_dsl(source1, "test1.sr", use_cache=True)
        bytecode2, _ = compile_dsl(source2, "test2.sr", use_cache=True)

        # Should be different bytecode objects
        assert bytecode1 is not bytecode2
