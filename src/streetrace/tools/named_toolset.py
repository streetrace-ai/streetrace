"""ADK Toolset wrapper that assigns a name to the toolset for logging / debugging."""

import asyncio
from typing import TYPE_CHECKING

import httpx
from google.adk.tools.base_toolset import BaseToolset
from httpx import HTTPError

from streetrace.log import get_logger

ORIGINAL_HTTPX_INIT = httpx.HTTPError.__init__

logger = get_logger(__name__)

if TYPE_CHECKING:
    from google.adk.agents.readonly_context import ReadonlyContext
    from google.adk.tools.base_tool import BaseTool


class HttpErrorCapture:
    """Captures HTTP errors during specific operations using monkey patching.

    This is due to https://github.com/modelcontextprotocol/python-sdk/issues/915,
    so we can show meaningful error messages when toolset initialization fails due to
    network issues.
    """

    def __init__(self) -> None:
        """Initialize the error capture."""
        self.captured_errors: list[str] = []

    def start_capturing(self) -> None:
        """Start capturing HTTP errors by patching httpx constructors."""
        _capture = self

        def patched_init(self: HTTPError, message: str, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            """Patched constructor that captures the error message."""
            _capture.captured_errors.append(message)

            # Call original constructor
            ORIGINAL_HTTPX_INIT(self, message, *args, **kwargs)

        httpx.HTTPError.__init__ = patched_init  # type: ignore[method-assign]

    def stop_capturing(self) -> None:
        """Stop capturing HTTP errors by restoring original constructors."""
        httpx.HTTPError.__init__ = ORIGINAL_HTTPX_INIT  # type: ignore[method-assign]

    def get_recent_error(self) -> str | None:
        """Get the most recent captured HTTP error."""
        if self.captured_errors:
            return self.captured_errors[-1]
        return None


class ToolsetLifecycleError(Exception):
    """The original toolset failed to initialize or cleanup."""

    def __init__(self, name: str, message: str) -> None:
        """Initialize error with toolset name and message.

        Args:
            name: Name of the toolset that failed
            message: Error message describing the failure

        """
        self.name = name
        super().__init__(message)


class NamedToolset(BaseToolset):
    """Assigns a name to a toolset, and uses it to help logging / debugging."""

    def __init__(
        self,
        name: str,
        *,
        original_toolset: BaseToolset,
    ) -> None:
        """Initialize a named toolset that wraps the original toolset."""
        super().__init__(tool_filter=original_toolset.tool_filter)

        self.name = name
        self._original_toolset = original_toolset

    async def get_tools(
        self,
        readonly_context: "ReadonlyContext | None" = None,
    ) -> "list[BaseTool]":
        """Return all tools in the toolset based on the provided context.

        Args:
            readonly_context: Context used to filter tools available to the agent.
                If None, all tools in the toolset are returned.

        Returns:
            List[BaseTool]: A list of tools available under the specified context.

        """
        # Start capturing HTTP errors before attempting to get tools
        _error_capture = HttpErrorCapture()
        _error_capture.start_capturing()

        # Shield the toolset initialization from external cancellation.
        # This prevents cancel scope mismatches when MCP stdio transports
        # are initialized within nested agent contexts. The OpenTelemetry
        # MCP instrumentation wraps transports with async context managers
        # that can fail to clean up properly when cancelled from a different
        # async context (e.g., parent agent GeneratorExit).
        #
        # We use asyncio.shield with asyncio.wait_for instead of nested anyio
        # cancel scopes. Nested anyio CancelScope + fail_after can cause
        # "Attempted to exit a cancel scope that isn't the current task's
        # current cancel scope" errors when async context switches occur
        # during MCP transport initialization.
        #
        # We use a 60-second timeout to prevent indefinite blocking while
        # still allowing sufficient time for stdio servers to start (e.g.,
        # npx downloading packages on first run).
        toolset_init_timeout_seconds = 60.0
        tools: list[BaseTool] = []
        try:
            tools = await asyncio.wait_for(
                asyncio.shield(
                    self._original_toolset.get_tools(
                        readonly_context=readonly_context,
                    ),
                ),
                timeout=toolset_init_timeout_seconds,
            )
        except TimeoutError as te:
            msg = (
                f"Toolset '{self.name}' initialization timed out after "
                f"{toolset_init_timeout_seconds}s"
            )
            raise ToolsetLifecycleError(self.name, msg) from te
        except asyncio.CancelledError as ae:
            # Check for captured HTTP errors that might have caused the cancellation
            msg = f"Toolset '{self.name}': {ae}"
            network_error = _error_capture.get_recent_error()
            if network_error:
                msg = f"{msg}, potentially due to {network_error}"
            raise ToolsetLifecycleError(self.name, msg) from ae
        except Exception as e:
            e = e.exceptions[0] if isinstance(e, ExceptionGroup) else e
            msg = f"Error initializing toolset '{self.name}': {e}"
            raise ToolsetLifecycleError(self.name, msg) from e
        finally:
            # Always restore the original constructor
            _error_capture.stop_capturing()

        return tools

    async def close(self) -> None:
        """Cleanup and releases resources held by the toolset."""
        try:
            await self._original_toolset.close()
        except Exception as e:
            msg = f"Error closing toolset '{self.name}': {e}"
            raise ToolsetLifecycleError(self.name, msg) from e
