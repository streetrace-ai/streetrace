import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from streetrace.llm.wrapper import ContentPartToolCall, ToolCallResult

logger = logging.getLogger(__name__)


class ToolCall:
    """Manages the execution of tool functions requested by the AI model.

    This class handles the routing of tool calls to the appropriate implementation,
    manages arguments, handles errors, and ensures results are properly formatted.
    """

    def __init__(
        self,
        tools: dict[str, Any],
        tools_impl: dict[str, Callable],
        abs_work_dir: Path,
    ) -> None:
        """Initialize the ToolCall manager.

        Args:
            tools: Dictionary mapping tool names to their schema definitions
            tools_impl: Dictionary mapping tool names to their implementation functions
            abs_work_dir: Absolute path to the working directory for file operations

        """
        self.tools = tools
        self.tools_impl = tools_impl
        self.abs_work_dir = abs_work_dir

    def call_tool(self, tool_call: ContentPartToolCall) -> ToolCallResult:
        """Executes the appropriate tool function based on the tool name and arguments.

        Args:
            tool_call: Object containing the tool name and arguments to execute
            original_call: The original function call object from the model (for reference)

        Returns:
            ToolCallResult: An object containing the execution result (success or error)
                           with both raw output and display-formatted output

        """
        if tool_call.name in self.tools_impl:
            tool_func = self.tools_impl[tool_call.name]
            try:
                # Inspect and call tool function, handling work_dir injection
                import inspect

                sig = inspect.signature(tool_func)
                tool_params = sig.parameters
                if "work_dir" in tool_params:
                    args_with_workdir = {
                        **tool_call.arguments,
                        "work_dir": self.abs_work_dir,
                    }
                    tool_result, result_view = tool_func(**args_with_workdir)
                else:
                    tool_result, result_view = tool_func(**tool_call.arguments)

                try:
                    # Verify result is JSON serializable
                    json.dumps(tool_result)
                    return ToolCallResult.ok(tool_result, result_view)
                except TypeError as json_err:
                    logger.warning(
                        f"Tool '{tool_call.name}' result is not fully JSON serializable: {json_err}. Returning string representation within result.",
                    )
                    return ToolCallResult.ok(str(tool_result), result_view)

            except Exception as e:
                # Handle tool execution errors
                error_msg = f"Error executing tool '{tool_call.name}': {e!s}"
                logger.exception(e)
                return ToolCallResult.error(error_msg)
        else:
            # Handle tool not found errors
            error_msg = f"Tool not found: {tool_call.name}"
            return ToolCallResult.error(error_msg)
