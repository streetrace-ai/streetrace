"""Tests for invocation context threading through GuardrailProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streetrace.dsl.runtime.guardrail_provider import GuardrailProvider


class TestSetInvocationContext:
    """Verify GuardrailProvider.set_invocation_context stores session info."""

    def test_set_and_read_session_id(self) -> None:
        provider = GuardrailProvider()
        provider.set_invocation_context(
            session_id="sess-123",
            session_state={"key": "val"},
        )
        assert provider.session_id == "sess-123"

    def test_set_and_read_session_state(self) -> None:
        provider = GuardrailProvider()
        state = {
            "streetrace.cognitive_monitor.hidden_state": [0.1, 0.2],
        }
        provider.set_invocation_context(
            session_id="sess-456",
            session_state=state,
        )
        assert provider.session_state is state

    def test_defaults_are_none(self) -> None:
        provider = GuardrailProvider()
        assert provider.session_id is None
        assert provider.session_state is None

    def test_overwrite_context(self) -> None:
        provider = GuardrailProvider()
        provider.set_invocation_context(
            session_id="first", session_state={},
        )
        provider.set_invocation_context(
            session_id="second", session_state={"new": True},
        )
        assert provider.session_id == "second"
        assert provider.session_state == {"new": True}

    def test_clear_context(self) -> None:
        provider = GuardrailProvider()
        provider.set_invocation_context(
            session_id="sess", session_state={"a": 1},
        )
        provider.clear_invocation_context()
        assert provider.session_id is None
        assert provider.session_state is None


class TestPluginThreadsContext:
    """Verify GuardrailPlugin passes session context to provider."""

    @pytest.fixture
    def mock_workflow(self) -> MagicMock:
        """Create a mock DslAgentWorkflow with overridden handlers."""
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        workflow = MagicMock(spec=DslAgentWorkflow)
        ctx = MagicMock()
        ctx.guardrails = GuardrailProvider()
        ctx.event_phase = ""
        ctx.message = ""
        workflow._context = ctx  # noqa: SLF001
        workflow.create_context.return_value = ctx
        return workflow

    @pytest.fixture
    def mock_callback_context(self) -> MagicMock:
        """Create a mock CallbackContext with session info."""
        cb_ctx = MagicMock()
        cb_ctx.session.id = "test-session-42"
        cb_ctx.state = {"some": "state"}
        return cb_ctx

    @pytest.mark.asyncio
    async def test_after_model_threads_session(
        self,
        mock_workflow: MagicMock,
        mock_callback_context: MagicMock,
    ) -> None:
        from streetrace.dsl.runtime.guardrail_plugin import (
            GuardrailPlugin,
        )

        mock_workflow.after_output = AsyncMock()

        plugin = GuardrailPlugin(workflow=mock_workflow)

        with patch.object(
            plugin, "_has_handler",
            side_effect=lambda n: n == "after_output",
        ):
            llm_response = MagicMock()
            llm_response.content.parts = [MagicMock(text="hello")]

            await plugin.after_model_callback(
                callback_context=mock_callback_context,
                llm_response=llm_response,
            )

            ctx = mock_workflow._context  # noqa: SLF001
            assert ctx.guardrails.session_id == "test-session-42"

    @pytest.mark.asyncio
    async def test_before_tool_threads_session(
        self,
        mock_workflow: MagicMock,
    ) -> None:
        from streetrace.dsl.runtime.guardrail_plugin import (
            GuardrailPlugin,
        )

        mock_workflow.on_tool_call = AsyncMock()

        plugin = GuardrailPlugin(workflow=mock_workflow)

        handler_match = lambda n: n == "on_tool_call"  # noqa: E731
        with patch.object(
            plugin, "_has_handler", side_effect=handler_match,
        ):
            tool = MagicMock()
            tool_context = MagicMock()
            tool_context.session.id = "tool-sess-99"
            tool_context.state = {"tool": "state"}

            await plugin.before_tool_callback(
                tool=tool,
                tool_args={"cmd": "ls"},
                tool_context=tool_context,
            )

            ctx = mock_workflow._context  # noqa: SLF001
            assert ctx.guardrails.session_id == "tool-sess-99"

    @pytest.mark.asyncio
    async def test_after_tool_threads_session(
        self,
        mock_workflow: MagicMock,
    ) -> None:
        from streetrace.dsl.runtime.guardrail_plugin import (
            GuardrailPlugin,
        )

        mock_workflow.on_tool_result = AsyncMock()

        plugin = GuardrailPlugin(workflow=mock_workflow)

        handler_match = lambda n: n == "on_tool_result"  # noqa: E731
        with patch.object(
            plugin, "_has_handler", side_effect=handler_match,
        ):
            tool = MagicMock()
            tool_context = MagicMock()
            tool_context.session.id = "result-sess-77"
            tool_context.state = {"result": "state"}

            await plugin.after_tool_callback(
                tool=tool,
                tool_args={},
                tool_context=tool_context,
                result={"output": "data"},
            )

            ctx = mock_workflow._context  # noqa: SLF001
            assert ctx.guardrails.session_id == "result-sess-77"
