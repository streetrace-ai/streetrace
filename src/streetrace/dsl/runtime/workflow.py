"""Base workflow class for Streetrace DSL.

Provide the base class that all generated workflows extend.
"""

from typing import ClassVar

from streetrace.dsl.runtime.context import WorkflowContext
from streetrace.log import get_logger

logger = get_logger(__name__)


class DslAgentWorkflow:
    """Base class for generated DSL workflows.

    Generated workflows extend this class and override
    the class attributes and event handler methods.
    """

    _models: ClassVar[dict[str, str]] = {}
    """Model definitions for this workflow."""

    _prompts: ClassVar[dict[str, object]] = {}
    """Prompt definitions for this workflow."""

    _tools: ClassVar[dict[str, dict[str, object]]] = {}
    """Tool definitions for this workflow."""

    _agents: ClassVar[dict[str, dict[str, object]]] = {}
    """Agent definitions for this workflow."""

    def __init__(self) -> None:
        """Initialize the workflow."""
        self._context: WorkflowContext | None = None
        logger.debug("Created %s", self.__class__.__name__)

    def create_context(self) -> WorkflowContext:
        """Create a new workflow context.

        Returns:
            A fresh WorkflowContext for execution.

        """
        ctx = WorkflowContext()
        ctx.set_models(self._models)
        ctx.set_prompts(self._prompts)
        ctx.set_agents(self._agents)
        self._context = ctx
        return ctx

    async def on_start(self, ctx: WorkflowContext) -> None:
        """Handle workflow start event.

        Override this method to initialize global variables.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_input(self, ctx: WorkflowContext) -> None:
        """Handle input event.

        Override this method to process/guard input.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_output(self, ctx: WorkflowContext) -> None:
        """Handle output event.

        Override this method to process/guard output.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_tool_call(self, ctx: WorkflowContext) -> None:
        """Handle tool call event.

        Override this method to intercept tool calls.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def on_tool_result(self, ctx: WorkflowContext) -> None:
        """Handle tool result event.

        Override this method to process tool results.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_start(self, ctx: WorkflowContext) -> None:
        """Handle after start event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_input(self, ctx: WorkflowContext) -> None:
        """Handle after input event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_output(self, ctx: WorkflowContext) -> None:
        """Handle after output event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_tool_call(self, ctx: WorkflowContext) -> None:
        """Handle after tool call event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use

    async def after_tool_result(self, ctx: WorkflowContext) -> None:
        """Handle after tool result event.

        Args:
            ctx: Workflow context.

        """
        _ = ctx  # Available for subclass use
