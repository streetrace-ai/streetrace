"""Tests for PromptResolutionContext.

Test that PromptResolutionContext provides a minimal context for
prompt evaluation without requiring a workflow reference.
"""



class TestPromptResolutionContextCreation:
    """Test PromptResolutionContext creation."""

    def test_can_create_without_arguments(self) -> None:
        """PromptResolutionContext can be created without any arguments."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert ctx is not None

    def test_has_vars_attribute(self) -> None:
        """PromptResolutionContext has vars attribute."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert hasattr(ctx, "vars")
        assert isinstance(ctx.vars, dict)

    def test_vars_is_empty_dict_by_default(self) -> None:
        """Vars attribute is empty dict by default."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert ctx.vars == {}

    def test_has_message_attribute(self) -> None:
        """PromptResolutionContext has message attribute."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert hasattr(ctx, "message")
        assert isinstance(ctx.message, str)

    def test_message_is_empty_string_by_default(self) -> None:
        """Message attribute is empty string by default."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert ctx.message == ""


class TestPromptResolutionContextUsage:
    """Test PromptResolutionContext usage for prompt evaluation."""

    def test_vars_can_be_modified(self) -> None:
        """Vars dict can be modified."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()
        ctx.vars["key"] = "value"

        assert ctx.vars["key"] == "value"

    def test_message_can_be_set(self) -> None:
        """Message can be set."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()
        ctx.message = "Hello, world!"

        assert ctx.message == "Hello, world!"

    def test_can_evaluate_prompt_lambda(self) -> None:
        """Can use context to evaluate prompt lambdas."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()
        ctx.vars["name"] = "Alice"

        # Simulating how prompt lambdas work in DSL
        def prompt_fn(c: PromptResolutionContext) -> str:
            return f"Hello, {c.vars.get('name', 'Unknown')}!"

        result = prompt_fn(ctx)

        assert result == "Hello, Alice!"


class TestNoWorkflowMethods:
    """Test that PromptResolutionContext has no workflow-related methods."""

    def test_no_run_agent_method(self) -> None:
        """PromptResolutionContext has no run_agent method."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert not hasattr(ctx, "run_agent")

    def test_no_run_flow_method(self) -> None:
        """PromptResolutionContext has no run_flow method."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert not hasattr(ctx, "run_flow")

    def test_no_workflow_reference(self) -> None:
        """PromptResolutionContext has no _workflow attribute."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        ctx = PromptResolutionContext()

        assert not hasattr(ctx, "_workflow")


class TestPromptResolutionContextDocumentation:
    """Test PromptResolutionContext documentation."""

    def test_has_docstring(self) -> None:
        """PromptResolutionContext class has a docstring."""
        from streetrace.dsl.runtime.prompt_context import PromptResolutionContext

        assert PromptResolutionContext.__doc__ is not None
        assert len(PromptResolutionContext.__doc__) > 0
        assert "prompt" in PromptResolutionContext.__doc__.lower()
