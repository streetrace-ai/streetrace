# app/interaction_manager.py
"""This module contains the InteractionManager class and auxiliary data classes to manage the stateful,
reliable interaction with LLM APIs and tool execution in a conversational state machine.
Implements client-facing glue code for StreetRace🚗💨 UI and LLM wrappers.
"""

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import (
    ContentPart,
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    ContentPartUsage,
    History,
    Message,
    Role,
    ToolCallResult,
)
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_EMPTY_RESPONSE_MAX_RETRIES = 3  # Specific retry limit for empty responses
_EMPTY_RESPONSE_WAIT_SEC = 10  # Wait time for empty response retry


class InteractionState(Enum):
    """Defines states of the interaction manager's state machine loop.
    Helps control conversational and tool execution flow.
    """

    STARTING_TURN = auto()
    GENERATING = auto()
    PROCESSING_GENERATION_RESULT = auto()
    EXECUTING_TOOLS = auto()
    PROCESSING_TOOL_RESULTS = auto()
    UPDATING_HISTORY = auto()
    HANDLING_API_RETRY = auto()
    HANDLING_EMPTY_RETRY = auto()
    FINISHED = auto()
    FAILED = auto()
    INTERRUPTED = auto()


@dataclass
class TurnData:
    """Transient data for a single turn within the interaction loop.
    Tracks all received/generated content and tool info for that turn.
    """

    assistant_text_parts: list[str] = field(default_factory=list)  # Text chunks
    buffered_tool_calls: list[ContentPartToolCall] = field(
        default_factory=list,
    )  # Tools from LLM
    turn_finish_reason: str | None = None
    prompt_tokens: int = 0
    response_tokens: int = 0
    generation_exception: Exception | None = None  # Generation phase error

    executed_tool_calls: list[ContentPartToolCall] = field(
        default_factory=list,
    )  # Actually executed tools
    executed_tool_results: list[ContentPartToolResult] = field(
        default_factory=list,
    )  # Their results
    tool_execution_exception: Exception | None = None  # Tool execution phase error

    def has_buffered_tools(self) -> bool:
        """Returns True if there are unprocessed (buffered) tool calls."""
        return bool(self.buffered_tool_calls)

    def has_executed_tools(self) -> bool:
        """True if any tools were executed in this turn."""
        return bool(self.executed_tool_results)

    def has_text_content(self) -> bool:
        """True if any assistant text was collected from the LLM for this turn."""
        return bool(self.assistant_text_parts)

    def has_any_content(self) -> bool:
        """Returns True if the turn produced any assistant text or buffered tool calls.
        Executed tool calls may be cleared on error and should not be checked alone for this.
        """
        return self.has_text_content() or self.has_buffered_tools()

    def reset(self) -> None:
        """Resets the main turn content for a new turn or retry, leaving exceptions for inspection."""
        self.assistant_text_parts = []
        self.buffered_tool_calls = []
        self.turn_finish_reason = None
        self.prompt_tokens = 0
        self.response_tokens = 0
        self.executed_tool_calls = []
        self.executed_tool_results = []
        # Keep .generation_exception and .tool_execution_exception for debug/retry logic.


@dataclass
class ConversationData:
    """Summary state and counters for a full conversation loop execution.
    The TurnData is held as .turn and reset in each STARTING_TURN phase.
    """

    state: InteractionState = InteractionState.STARTING_TURN
    turn: TurnData = field(default_factory=TurnData)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0  # Incremented before each LLM API call attempt
    final_reason: str | None = None
    api_retry_count: int = 0
    empty_response_retry_count: int = 0


@dataclass
class GenerationOutcome:
    """Result (success/failure and error status) for _call_llm_api method."""

    success: bool = False
    is_retriable: bool = False
    error: Exception | None = None


@dataclass
class ToolExecutionOutcome:
    """Result (success/failure and error info) for _execute_tools method."""

    success: bool = True
    error: Exception | None = None


class ThinkingResult:
    """Describes the result of one interactive loop session: reason, tokens, requests."""

    def __init__(
        self,
        finish_reason: str | None,
        input_tokens: int,
        output_tokens: int,
        request_count: int,
    ) -> None:
        """Initialize a ThinkingResult with final statistics and finish reason."""
        self.finish_reason = finish_reason
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.request_count = request_count

    def __repr__(self) -> str:
        return (
            f"ThinkingResult(finish_reason={self.finish_reason!r}, "
            f"input_tokens={self.input_tokens}, output_tokens={self.output_tokens}, "
            f"request_count={self.request_count})"
        )


class InteractionManager:
    """Handles the main interaction state machine for LLM chat and tool-augmented code generation.

    - Orchestrates prompt/response with the model, tool execution, error/retry logic,
      token/timing tracking, and stateful user feedback.
    - Uses fail-fast for internal errors, gracefully degrades and logs extensively for UI and tool phases.
    """

    def __init__(
        self,
        provider: LLMAPI,
        model_name: str | None,
        tools: ToolCall,
        ui: ConsoleUI,
        sleeper: Callable[[int | float], None] = time.sleep,
    ) -> None:
        """Construct an InteractionManager for a specific LLM provider, model, tool set, and UI.

        Args:
            provider: LLMAPI (implementation of backend, e.g. OpenAI, Claude)
            model_name: Name of model to use for LLM backend (provider-specific string)
            tools: ToolCall delegator (handles dispatch to actual code tools)
            ui: ConsoleUI for all user/output interaction, feedback etc.
            sleeper: Function used for sleeping between retries (overridable for tests)

        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools
        self.ui = ui
        self.sleeper = sleeper
        logger.info(
            f"InteractionManager initialized for provider: {type(provider).__name__}",
        )

    def _call_llm_api(
        self,
        client: Any,
        system_message: str,
        provider_history: list[Any],
        provider_tools: list[Any],
        turn: TurnData,
    ) -> GenerationOutcome:
        """Calls the LLM API, processes the stream, and updates TurnData.

        Args:
            client: The initialized LLM client.
            system_message: The system message to be included in the prompt.
            provider_history: The history formatted for the specific provider.
            provider_tools: The tools formatted for the specific provider.
            turn: The TurnData object to populate. Reset before calling.

        Returns:
            GenerationOutcome indicating success, retriable error, or fatal error.

        """
        try:
            logger.debug("Calling LLM API...")
            stream: Iterable[ContentPart] = self.provider.generate(
                client,
                self.model_name,
                system_message,
                provider_history,
                provider_tools,
            )
            for chunk in stream:
                match chunk:
                    case ContentPartText():
                        self.ui.display_ai_response_chunk(chunk.text)
                        turn.assistant_text_parts.append(chunk.text)
                    case ContentPartToolCall():
                        turn.buffered_tool_calls.append(chunk)
                    case ContentPartFinishReason():
                        turn.turn_finish_reason = chunk.finish_reason
                        logger.debug(f"Received finish reason: {chunk.finish_reason}")
                    case ContentPartUsage():
                        turn.prompt_tokens += chunk.prompt_tokens
                        turn.response_tokens += chunk.response_tokens
                    case _:
                        logger.warning(f"Unhandled content part type: {type(chunk)}")
            logger.debug("LLM API call finished.")
            return GenerationOutcome(success=True)
        except RetriableError as retry_err:
            logger.warning(
                f"Retriable error during generation: {retry_err}",
                exc_info=False,
            )
            turn.generation_exception = retry_err
            return GenerationOutcome(success=False, is_retriable=True, error=retry_err)
        except Exception as e:
            logger.error(f"Non-retriable error during generation: {e}", exc_info=True)
            turn.generation_exception = e
            return GenerationOutcome(success=False, is_retriable=False, error=e)

    def _execute_tools(self, turn: TurnData) -> ToolExecutionOutcome:
        """Executes all tool calls currently buffered. Updates execution lists/results."""
        logger.debug(f"Executing {len(turn.buffered_tool_calls)} tool calls...")
        turn.executed_tool_calls = []
        turn.executed_tool_results = []
        turn.tool_execution_exception = None
        if not turn.buffered_tool_calls:
            return ToolExecutionOutcome(success=True)
        try:
            for tool_call in turn.buffered_tool_calls:
                self.ui.display_tool_call(tool_call)
                logger.info(
                    f"Tool call: {tool_call.name} with args: {tool_call.arguments}",
                )
                tool_result: ToolCallResult = self.tools.call_tool(tool_call)
                tool_result_part = ContentPartToolResult(
                    id=tool_call.id,
                    name=tool_call.name,
                    content=tool_result,
                )
                if tool_result.success:
                    self.ui.display_tool_result(tool_result_part)
                    logger.info(
                        f"Tool '{tool_call.name}' result: {tool_result.output.content}",
                    )
                else:
                    self.ui.display_tool_error(tool_result_part)
                    logger.error(
                        f"Tool '{tool_call.name}' error: {tool_result.output.content}",
                    )
                turn.executed_tool_calls.append(tool_call)
                turn.executed_tool_results.append(tool_result_part)
            assert len(turn.executed_tool_calls) == len(
                turn.executed_tool_results,
            ), "Mismatched tool calls and results after execution"
            logger.debug("Tool execution finished.")
            return ToolExecutionOutcome(success=True)
        except Exception as e:
            logger.error(f"Error during tool execution phase: {e}", exc_info=True)
            turn.tool_execution_exception = e
            turn.executed_tool_calls = []
            turn.executed_tool_results = []
            return ToolExecutionOutcome(success=False, error=e)

    def _update_histories(
        self,
        history: History,
        provider_history: list[Any],
        turn: TurnData,
    ) -> list[Message]:
        """Update the user-facing and provider-facing chat histories after each turn.
        Appends generated text/tool-calls, tool results as messages, and
        synchronizes with provider's internal format.

        Returns:
            List of messages added to logical history in this turn.

        """
        new_messages: list[Message] = []
        assistant_content: list[ContentPart] = []
        if turn.has_text_content():
            assistant_content.append(
                ContentPartText(text="".join(turn.assistant_text_parts)),
            )
        assistant_content.extend(turn.executed_tool_calls)
        if assistant_content:
            model_message = history.add_message(Role.MODEL, assistant_content)
            if model_message:
                new_messages.append(model_message)
        if turn.has_executed_tools():
            tool_message = history.add_message(Role.TOOL, turn.executed_tool_results)
            if tool_message:
                new_messages.append(tool_message)
        if new_messages:
            self.provider.append_history(provider_history, new_messages)
            logger.debug(f"Appended {len(new_messages)} messages to histories.")
        return new_messages

    def process_prompt(self, history: History) -> ThinkingResult:
        """Runs a chat prompt through the full state machine loop: generates, dispatches tools,
        retries as needed, and updates both visible user and provider history.
        Returns a ThinkingResult giving the final status.
        """
        client = self.provider.initialize_client()
        provider_history = self.provider.transform_history(history)
        provider_tools = self.provider.transform_tools(self.tools.tools)
        conv = ConversationData()
        with self.ui.status("Working...") as status:
            while conv.state not in (
                InteractionState.FINISHED,
                InteractionState.FAILED,
                InteractionState.INTERRUPTED,
            ):
                try:
                    logger.debug(f"Current state: {conv.state.name}")
                    if conv.state == InteractionState.STARTING_TURN:
                        conv.turn.reset()
                        conv.state = InteractionState.GENERATING
                    elif conv.state == InteractionState.GENERATING:
                        conv.total_requests += 1
                        logger.info(
                            f"Starting request {conv.total_requests} with {len(provider_history)} history items.",
                        )
                        logger.debug(
                            "Provider history for generation:\n%s",
                            provider_history,
                        )
                        logger.debug("System Message: %s", history.system_message)
                        status.update(
                            f"Working, io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                        )
                        outcome = self._call_llm_api(
                            client,
                            history.system_message,
                            provider_history,
                            provider_tools,
                            conv.turn,
                        )
                        conv.total_input_tokens += conv.turn.prompt_tokens
                        conv.total_output_tokens += conv.turn.response_tokens
                        if conv.total_input_tokens > 0 or conv.total_output_tokens > 0:
                            status.update(
                                f"Working, io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                            )
                        else:
                            status.update(
                                f"Working, total requests: {conv.total_requests}...",
                            )
                        if outcome.success:
                            conv.state = InteractionState.PROCESSING_GENERATION_RESULT
                            conv.api_retry_count = 0
                        elif outcome.is_retriable:
                            conv.state = InteractionState.HANDLING_API_RETRY
                        else:
                            conv.final_reason = (
                                str(outcome.error) or type(outcome.error).__name__
                            )
                            conv.state = (
                                InteractionState.INTERRUPTED
                                if isinstance(outcome.error, KeyboardInterrupt)
                                else InteractionState.FAILED
                            )
                    elif conv.state == InteractionState.PROCESSING_GENERATION_RESULT:
                        if conv.turn.has_buffered_tools():
                            conv.state = InteractionState.EXECUTING_TOOLS
                        elif (
                            conv.turn.has_any_content() or conv.turn.turn_finish_reason
                        ):
                            conv.state = InteractionState.UPDATING_HISTORY
                            conv.empty_response_retry_count = 0
                        else:
                            conv.state = InteractionState.HANDLING_EMPTY_RETRY
                    elif conv.state == InteractionState.EXECUTING_TOOLS:
                        outcome = self._execute_tools(conv.turn)
                        if outcome.success:
                            conv.state = InteractionState.PROCESSING_TOOL_RESULTS
                        else:
                            conv.final_reason = (
                                str(outcome.error) or type(outcome.error).__name__
                            )
                            conv.state = (
                                InteractionState.INTERRUPTED
                                if isinstance(outcome.error, KeyboardInterrupt)
                                else InteractionState.FAILED
                            )
                    elif conv.state == InteractionState.PROCESSING_TOOL_RESULTS:
                        conv.state = InteractionState.UPDATING_HISTORY
                    elif conv.state == InteractionState.UPDATING_HISTORY:
                        _ = self._update_histories(history, provider_history, conv.turn)
                        if conv.turn.has_executed_tools():
                            conv.state = InteractionState.STARTING_TURN
                        elif conv.turn.turn_finish_reason:
                            conv.final_reason = conv.turn.turn_finish_reason
                            conv.state = InteractionState.FINISHED
                        elif conv.turn.has_text_content():
                            logger.info(
                                "Continuing generation as no finish reason was received.",
                            )
                            conv.state = InteractionState.STARTING_TURN
                        else:
                            logger.warning(
                                "History update completed but turn yielded no content and no finish reason.",
                            )
                            conv.state = InteractionState.HANDLING_EMPTY_RETRY
                    elif conv.state == InteractionState.HANDLING_API_RETRY:
                        error = conv.turn.generation_exception
                        assert isinstance(error, RetriableError)
                        self.ui.display_warning(error)
                        max_retries = error.max_retries or _DEFAULT_MAX_RETRIES
                        if conv.api_retry_count < max_retries:
                            conv.api_retry_count += 1
                            wait_time = error.wait_time(conv.api_retry_count)
                            logger.info(
                                f"Retrying API call in {wait_time} seconds... (Attempt {conv.api_retry_count+1}/{max_retries})",
                            )
                            self.ui.display_info(
                                f"Retrying API call in {wait_time} seconds...",
                            )
                            status.update(
                                f"Retrying ({conv.api_retry_count}/{max_retries}), io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                            )
                            self.sleeper(wait_time)
                            conv.state = InteractionState.GENERATING
                        else:
                            logger.error("API retry limit exceeded.")
                            conv.final_reason = "Retry attempts exceeded"
                            conv.state = InteractionState.FAILED
                    elif conv.state == InteractionState.HANDLING_EMPTY_RETRY:
                        logger.debug("Handling potentially empty response.")
                        if (
                            conv.empty_response_retry_count
                            < _EMPTY_RESPONSE_MAX_RETRIES
                        ):
                            conv.empty_response_retry_count += 1
                            wait_time = _EMPTY_RESPONSE_WAIT_SEC
                            logger.info(
                                f"Empty response detected. Retrying in {wait_time} seconds... (Attempt {conv.empty_response_retry_count}/{_EMPTY_RESPONSE_MAX_RETRIES})",
                            )
                            self.ui.display_warning(
                                "No output generated by provider, retrying.",
                            )
                            status.update(
                                f"Empty response retry ({conv.empty_response_retry_count}/{_EMPTY_RESPONSE_MAX_RETRIES}), io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                            )
                            self.sleeper(wait_time)
                            conv.state = InteractionState.GENERATING
                        else:
                            logger.error("Empty response retry limit exceeded.")
                            conv.final_reason = "No result"
                            conv.state = InteractionState.FAILED
                except KeyboardInterrupt:
                    logger.warning(
                        "KeyboardInterrupt detected (outside inner try/except).",
                    )
                    conv.final_reason = "User interrupted"
                    conv.state = InteractionState.INTERRUPTED
                except Exception as e:
                    logger.error(
                        f"Unexpected error in state machine: {e}",
                        exc_info=True,
                    )
                    conv.final_reason = f"Internal error: {e}"
                    conv.state = InteractionState.FAILED
        if conv.state == InteractionState.FINISHED:
            self.ui.display_info(f"Finished: {conv.final_reason or 'Empty reason'}")
        if conv.state == InteractionState.INTERRUPTED:
            self.ui.display_info(f"Interrupted: {conv.final_reason or 'Empty reason'}")
        if conv.state == InteractionState.FAILED:
            self.ui.display_error(f"Failed: {conv.final_reason or 'Empty reason'}")
        return ThinkingResult(
            finish_reason=conv.final_reason,
            input_tokens=conv.total_input_tokens,
            output_tokens=conv.total_output_tokens,
            request_count=conv.total_requests,
        )
