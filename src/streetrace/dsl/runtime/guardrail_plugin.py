"""ADK plugin that bridges DSL event handlers to data flows.

Connect the ``on_input``, ``on_output``, ``on_tool_call``, and
``on_tool_result`` handlers defined in generated DSL workflows to the
ADK plugin callback system so guardrail logic actually executes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.adk.plugins import BasePlugin

from streetrace.dsl.runtime.errors import BlockedInputError
from streetrace.dsl.runtime.guardrail_provider import (
    ToolCallContent,
    ToolResultContent,
)
from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.tool_context import ToolContext
    from google.genai import types as genai_types

    from streetrace.dsl.runtime.context import WorkflowContext
    from streetrace.dsl.runtime.workflow import DslAgentWorkflow

logger = get_logger(__name__)

BLOCKED_MESSAGE = "Request blocked by guardrail policy."
"""Default message returned when a guardrail blocks a request."""

_HANDLER_NAMES = (
    "on_input",
    "after_input",
    "on_output",
    "after_output",
    "on_tool_call",
    "after_tool_call",
    "on_tool_result",
    "after_tool_result",
)
"""Event handler method names that may be overridden by generated workflows."""


class GuardrailPlugin(BasePlugin):
    """Bridge DSL event handlers to ADK plugin callbacks.

    Only call handlers that the generated subclass actually overrides,
    avoiding unnecessary context creation for no-op base methods.
    """

    def __init__(self, *, workflow: DslAgentWorkflow) -> None:
        """Initialize with a reference to the DSL workflow.

        Args:
            workflow: The DslAgentWorkflow instance whose handlers to invoke.

        """
        super().__init__(name="streetrace_guardrails")
        self._workflow = workflow

    # -- handler existence check ------------------------------------------

    def _has_handler(self, name: str) -> bool:
        """Check if the workflow subclass overrides a handler.

        Args:
            name: Handler method name (e.g. ``on_input``).

        Returns:
            True if the subclass provides its own implementation.

        """
        from streetrace.dsl.runtime.workflow import DslAgentWorkflow

        subclass_method = getattr(type(self._workflow), name, None)
        base_method = getattr(DslAgentWorkflow, name, None)
        return subclass_method is not base_method

    def has_any_handler(self) -> bool:
        """Check if the workflow has any overridden event handlers.

        Returns:
            True if at least one handler is overridden.

        """
        return any(self._has_handler(name) for name in _HANDLER_NAMES)

    # -- context helpers --------------------------------------------------

    def _get_or_create_context(self) -> WorkflowContext:
        """Get the workflow's current context, creating one if needed.

        Returns:
            The active WorkflowContext.

        """
        ctx = self._workflow._context  # noqa: SLF001
        if ctx is None:
            ctx = self._workflow.create_context()
        return ctx

    # -- ADK plugin callbacks ---------------------------------------------

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,  # noqa: ARG002
        user_message: genai_types.Content,
    ) -> genai_types.Content | None:
        """Dispatch user message to on_input handler.

        Args:
            invocation_context: ADK invocation context (unused).
            user_message: The incoming user message.

        Returns:
            Modified Content if message changed or blocked, None otherwise.

        """
        if not self._has_handler("on_input"):
            return None

        text = _extract_text(user_message)
        if not text:
            return None

        ctx = self._get_or_create_context()
        ctx.event_phase = "input"
        ctx.message = text

        try:
            await self._workflow.on_input(ctx)
        except BlockedInputError:
            logger.warning("Input blocked by on_input guardrail")
            return _make_content(BLOCKED_MESSAGE, role="model")

        if ctx.message != text:
            return _make_content(ctx.message, role="user")

        return None

    async def before_model_callback(
        self,
        *,
        callback_context: CallbackContext,  # noqa: ARG002
        llm_request: LlmRequest,
    ) -> LlmResponse | None:
        """Dispatch to after_input handler before model call.

        Args:
            callback_context: ADK callback context (unused).
            llm_request: The LLM request about to be sent.

        Returns:
            LlmResponse to short-circuit, or None to proceed.

        """
        if not self._has_handler("after_input"):
            return None

        text = _extract_last_user_text(llm_request)
        if not text:
            return None

        ctx = self._get_or_create_context()
        ctx.event_phase = "input"
        ctx.message = text

        try:
            await self._workflow.after_input(ctx)
        except BlockedInputError:
            logger.warning("Input blocked by after_input guardrail")
            return _make_llm_response(BLOCKED_MESSAGE)

        if ctx.message != text:
            _update_last_user_text(llm_request, ctx.message)

        return None

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,  # noqa: ARG002
        llm_response: LlmResponse,
    ) -> LlmResponse | None:
        """Dispatch to on_output and after_output after model call.

        Args:
            callback_context: ADK callback context (unused).
            llm_response: The LLM response received.

        Returns:
            Modified LlmResponse if text changed, None otherwise.

        """
        has_on = self._has_handler("on_output")
        has_after = self._has_handler("after_output")
        if not has_on and not has_after:
            return None

        text = _extract_llm_response_text(llm_response)
        if not text:
            return None

        ctx = self._get_or_create_context()
        ctx.event_phase = "output"
        ctx.message = text

        if has_on:
            await self._workflow.on_output(ctx)
        if has_after:
            await self._workflow.after_output(ctx)

        if ctx.message != text:
            return _make_llm_response(ctx.message)

        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,  # noqa: ARG002
        tool_args: dict[str, object],
        tool_context: ToolContext,  # noqa: ARG002
    ) -> dict[str, object] | None:
        """Dispatch to on_tool_call and after_tool_call before tool execution.

        Args:
            tool: The tool about to be called (unused).
            tool_args: Arguments about to be passed to the tool.
            tool_context: ADK tool context (unused).

        Returns:
            Dict with error key if blocked, None otherwise.

        """
        has_on = self._has_handler("on_tool_call")
        has_after = self._has_handler("after_tool_call")
        if not has_on and not has_after:
            return None

        ctx = self._get_or_create_context()
        ctx.event_phase = "tool_call"
        ctx.message = ToolCallContent(data=tool_args)

        try:
            if has_on:
                await self._workflow.on_tool_call(ctx)
            if has_after:
                await self._workflow.after_tool_call(ctx)
        except BlockedInputError:
            logger.warning("Tool call blocked by guardrail")
            return {"error": BLOCKED_MESSAGE}

        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,  # noqa: ARG002
        tool_args: dict[str, object],  # noqa: ARG002
        tool_context: ToolContext,  # noqa: ARG002
        result: dict[str, object],
    ) -> dict[str, object] | None:
        """Dispatch to on_tool_result and after_tool_result after tool.

        Args:
            tool: The tool that was called (unused).
            tool_args: Arguments passed to the tool (unused).
            tool_context: ADK tool context (unused).
            result: The tool's return value.

        Returns:
            Modified result dict if changed, None otherwise.

        """
        has_on = self._has_handler("on_tool_result")
        has_after = self._has_handler("after_tool_result")
        if not has_on and not has_after:
            return None

        if result is None:
            # Side-effect tools like transfer_to_agent return None
            return None

        original = ToolResultContent(data=dict(result))
        ctx = self._get_or_create_context()
        ctx.event_phase = "tool_result"
        ctx.message = original

        if has_on:
            await self._workflow.on_tool_result(ctx)
        if has_after:
            await self._workflow.after_tool_result(ctx)

        if ctx.message is not original and ctx.message != original:
            if isinstance(ctx.message, ToolResultContent):
                return ctx.message.data
            if isinstance(ctx.message, str):
                return {"result": ctx.message}

        return None


# -- module-level helper functions ----------------------------------------


def _extract_text(content: genai_types.Content) -> str:
    """Extract concatenated text from Content parts.

    Args:
        content: ADK Content object.

    Returns:
        Concatenated text from all text parts.

    """
    if not content or not content.parts:
        return ""
    return " ".join(
        part.text for part in content.parts if hasattr(part, "text") and part.text
    )


def _extract_last_user_text(llm_request: LlmRequest) -> str:
    """Extract text from the last user message in an LLM request.

    Args:
        llm_request: ADK LlmRequest with ``contents`` attribute.

    Returns:
        Text from the last user-role content, or empty string.

    """
    contents = getattr(llm_request, "contents", None)
    if not contents:
        return ""
    for content in reversed(contents):
        if getattr(content, "role", None) == "user" and content.parts:
            texts = [
                part.text
                for part in content.parts
                if hasattr(part, "text") and part.text
            ]
            if texts:
                return " ".join(texts)
    return ""


def _update_last_user_text(
    llm_request: LlmRequest,
    new_text: str,
) -> None:
    """Replace text in the last user message of an LLM request.

    Args:
        llm_request: ADK LlmRequest with ``contents`` attribute.
        new_text: Replacement text.

    """
    from google.genai import types as genai_types

    contents = getattr(llm_request, "contents", None)
    if not contents:
        return
    for content in reversed(contents):
        if getattr(content, "role", None) == "user" and content.parts:
            content.parts = [genai_types.Part.from_text(text=new_text)]
            return


def _extract_llm_response_text(llm_response: LlmResponse) -> str:
    """Extract text from an LLM response.

    Args:
        llm_response: ADK LlmResponse object.

    Returns:
        Concatenated text from response content parts.

    """
    content = getattr(llm_response, "content", None)
    if not content:
        return ""
    parts = getattr(content, "parts", None)
    if not parts:
        return ""
    return " ".join(
        part.text for part in parts if hasattr(part, "text") and part.text
    )


def _make_content(
    text: str,
    *,
    role: str = "user",
) -> genai_types.Content:
    """Build an ADK Content with a single text part.

    Args:
        text: The text content.
        role: Content role (default ``user``).

    Returns:
        New Content instance.

    """
    from google.genai import types as genai_types

    return genai_types.Content(
        role=role,
        parts=[genai_types.Part.from_text(text=text)],
    )


def _make_llm_response(text: str) -> LlmResponse:
    """Build an ADK LlmResponse with a single text part.

    Args:
        text: The response text.

    Returns:
        New LlmResponse instance.

    """
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types as genai_types

    content = genai_types.Content(
        role="model",
        parts=[genai_types.Part.from_text(text=text)],
    )
    return LlmResponse(content=content)
