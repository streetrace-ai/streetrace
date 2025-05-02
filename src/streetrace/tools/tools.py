"""Provide tools for AI models to interact with the file system and execute commands.

This module contains tools that allow AI models to perform operations such as
reading and writing files, executing commands, and more.
"""

import inspect
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from litellm import ChatCompletionMessageToolCall

from streetrace.tools.tool_call_result import ToolCallResult

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

    def call_tool(self, tool_call: ChatCompletionMessageToolCall) -> ToolCallResult:
        """Execute the appropriate tool function based on the tool name and arguments.

        Args:
            tool_call: Object containing the tool name and arguments to execute
            original_call: The original function call object from the model (for reference)

        Returns:
            ToolCallResult: An object containing the execution result (success or error)
                           with both raw output and display-formatted output

        """
        if tool_call.function.name not in self.tools_impl:
            # Handle tool not found errors
            error_msg = f"Tool not found: {tool_call.function.name}"
            return ToolCallResult.error(error_msg)

        tool_func = self.tools_impl[tool_call.function.name]

        # Check if the tool function is callable
        if not callable(tool_func):
            msg = f"Tool function '{tool_call.function.name}' is not callable."
            return ToolCallResult.error(msg)

        args = tool_call.function.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError as e:
                msg = f"Tool call arguments are not valid dict: {args}\n{e!s}"
                return ToolCallResult.error(msg)
        if not isinstance(args, dict) or not all(
            isinstance(name, str) for name in args
        ):
            # In the current litellm (1.67.5) this condition cannot be met b/c all arg names are converted to str
            msg = f"Tool call arguments must be a dict[str, Any], got {type(tool_call.function.arguments)}"  # pragma: no cover
            return ToolCallResult.error(msg)  # pragma: no cover

        return self._execute_tool_function(tool_call.function.name, tool_func, args)

    def _execute_tool_function(
        self,
        tool_name: str,
        tool_func: Callable,
        args: dict[str, Any],
    ) -> ToolCallResult:
        """Execute the tool function with the provided arguments.

        Args:
            tool_name: The name of the tool being executed
            tool_func: The tool function to execute
            args: The tool call arguments
        Returns:
            ToolCallResult: An object containing the execution result (success or error)

        """
        # Inspect and call tool function, handling work_dir injection
        sig = inspect.signature(tool_func)
        tool_params = sig.parameters
        if "work_dir" in tool_params:
            args = {
                **args,
                "work_dir": self.abs_work_dir,
            }
        try:
            tool_result, result_view = tool_func(**args)
        except Exception as e:
            # Handle tool execution errors
            error_msg = f"Error executing tool '{tool_name}': {e!s}"
            logger.exception("Error executing tool")
            return ToolCallResult.error(error_msg)
        else:
            try:
                # Verify result is JSON serializable
                json.dumps(tool_result)
            except TypeError as json_err:
                logger.warning(
                    "Tool '%s' result is not fully JSON serializable: %s. Returning string representation within result.",
                    tool_name,
                    json_err,
                )
                return ToolCallResult.ok(str(tool_result), result_view)
            else:
                return ToolCallResult.ok(tool_result, result_view)
