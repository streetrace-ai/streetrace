"""ReAct Agent implementation. See https://arxiv.org/abs/2210.03629.

The basic intuition is that this module can be replaced with several lines of langchain and
ultimately with one line of `create_react_agent`. But when doing so, most part of this module
will need to stay to allow managing conversation state, usage, history, etc.

I.e., process_prompt could look something like this:

```python
def process_prompt(self, history: History) -> ThinkingResult:
    config = {"configurable": {"thread_id": "1"}}

    client = self.provider.initialize_client()
    provider_history = self.provider.transform_history(history)
    provider_tools = self.provider.transform_tools(self.tools.tools).as_langchain_tools()
    llm = client.as_langchain_bind_tools(provider_tools)

    def stream_graph_updates(provider_history: list[dict[str, Any]]):
        for event in graph.stream(
            {"messages": provider_history},
            config,
            stream_mode="values",
        ):
            self._update_histories(history, provider_history, event)

    def chatbot(provider_history: ProviderHistory):
        global llm_i
        return {"messages": [llm.invoke(provider_history["messages"])]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools=tools))
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")
    graph = graph_builder.compile(checkpointer=memory)
    print(graph.get_graph().draw_ascii())

    while True:
        stream_graph_updates(provider_history)
        ... etc
```

Which immediately shows that history and error management needs to be implemented anyway, which
most of this module does. But there is still a strong advantage, mostly coming from the community
tools db, which would allow users to build agents with any existing tools easily. Overall pros and
cons of migrating to langchain:

Downsides:
- while removing some complexity, it adds complexity where it's not needed
- linear and graph aproaches are a fundamental limitations for real agentic workflows <- this is
    probably the main one. As StreetRace grows, I don't know if it will stay in this form of a
    simple looping ReAct agent, or will change into a more event driven dynamic graph space, in
    which case langgraph will not be an option.
Advantages:
- quick and easy
- lots of community contributions

I'll need to re-asses migrating this module to langchain after first migrating to litellm as
the llm gateway, which will reduce a lot of boilerplate code (if it works). Ideally, what I want
is to implement an Actors model for all agents and tools, where agents and tools are interchangeable
terms from the architecture standpoint (inputs+outputs, who cares?), while allowing to use langchain
community tools and other libraries. This is a long term goal, but I think it's worth it.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, NoReturn

import litellm
from rich.status import Status
from tenacity import (
    TryAgain,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_incrementing,
)

from streetrace.history import (
    History,
    Role,
)
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI

if TYPE_CHECKING:

    from streetrace.tools.tool_call_result import ToolCallResult

logger = logging.getLogger(__name__)

_EMPTY_RESPONSE_MAX_RETRIES = 3  # Specific retry limit for empty responses
_EMPTY_RESPONSE_WAIT_SEC = 10  # Wait time for empty response retry
_MAX_RETRIES = 7


class _InteractionState(Enum):
    """Define states of the interaction manager's state machine loop.

    Helps control conversational and tool execution flow.
    """

    STARTING_TURN = auto()
    GENERATING = auto()
    PROCESSING_GENERATION_RESULT = auto()
    EXECUTING_TOOLS = auto()
    PROCESSING_TOOL_RESULTS = auto()
    UPDATING_HISTORY = auto()
    HANDLING_EMPTY_RETRY = auto()
    FINISHED = auto()
    FAILED = auto()
    INTERRUPTED = auto()


@dataclass
class _TurnData:
    """Store transient data for a single turn within the interaction loop.

    Tracks all received/generated content and tool info for that turn.
    """

    assistant_messages: list[litellm.Message] = field(
        default_factory=list,
    )  # Messages from LLM
    tool_results: list[litellm.Message] = field(
        default_factory=list,
    )  # Their results
    turn_finish_reason: str | None = None
    usage: litellm.Usage | None = None  # Token usage from LLM
    generation_exception: Exception | None = None  # Generation phase error

    def has_buffered_tool_calls(self) -> bool:
        """Check if there are unprocessed (buffered) tool calls."""
        return bool(self.buffered_tool_calls())

    def buffered_tool_calls(self) -> list[litellm.ChatCompletionMessageToolCall]:
        """Check if there are unprocessed (buffered) tool calls."""
        tool_calls = []
        for message in self.assistant_messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls.extend(message.tool_calls.copy())
        return tool_calls

    def has_executed_tools(self) -> bool:
        """Check if any tools were executed in this turn."""
        return bool(self.tool_results)

    def has_text_content(self) -> bool:
        """Check if any assistant text was collected from the LLM for this turn."""
        return any(bool(m.content) for m in self.assistant_messages)

    def has_any_content(self) -> bool:
        """Check if the turn produced any assistant text or buffered tool calls.

        Executed tool calls may be cleared on error and should not be checked alone for this.
        """
        return (
            self.has_text_content()
            or self.has_buffered_tool_calls()
            or self.turn_finish_reason
        )

    def reset(self) -> None:
        """Reset the main turn content for a new turn or retry, leaving exceptions for inspection."""
        self.assistant_messages = []
        self.tool_results = []
        self.turn_finish_reason = None
        self.usage = None
        # Keep .generation_exception for debug/retry logic.


@dataclass
class _ConversationData:
    """Track summary state and counters for a full conversation loop execution.

    The _TurnData is held as .turn and reset in each STARTING_TURN phase.
    """

    state: _InteractionState = _InteractionState.STARTING_TURN
    turn: _TurnData = field(default_factory=_TurnData)
    usage: list[litellm.Usage] = field(default_factory=list)  # List of usage objects
    total_requests: int = 0  # Incremented before each LLM API call attempt
    final_reason: str | None = None
    api_retry_count: int = 0
    empty_response_retry_count: int = 0

    def add_usage(self, usage: litellm.Usage | None) -> None:
        """Add a usage object to the conversation's token usage."""
        if usage:
            self.usage.append(usage)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens for the conversation."""
        return sum(u.prompt_tokens for u in self.usage if u.prompt_tokens is not None)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens for the conversation."""
        return sum(
            u.completion_tokens for u in self.usage if u.completion_tokens is not None
        )


@dataclass
class _GenerationOutcome:
    """Result (success/failure and error status) for _call_llm method."""

    success: bool = False
    error: Exception | None = None


@dataclass
class _ToolExecutionOutcome:
    """Result (success/failure and error info) for _execute_tools method."""

    success: bool = True
    error: Exception | None = None


class ThinkingResult:
    """Describe the result of one interactive loop session: reason, tokens, requests."""

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
        """Return string representation of ThinkingResult."""
        return (
            f"ThinkingResult(finish_reason={self.finish_reason!r}, "
            f"input_tokens={self.input_tokens}, output_tokens={self.output_tokens}, "
            f"request_count={self.request_count})"
        )


class InteractionManager:
    """Handle the main interaction state machine for LLM chat and tool-augmented code generation.

    - Orchestrates prompt/response with the model, tool execution, error/retry logic,
      token/timing tracking, and stateful user feedback.
    - Uses fail-fast for internal errors, gracefully degrades and logs extensively for UI and tool phases.
    """

    def __init__(
        self,
        ui: ConsoleUI,
        sleeper: Callable[[int | float], None] = time.sleep,
    ) -> None:
        """Construct an InteractionManager for a specific LLM provider, model, tool set, and UI.

        Args:
            provider: LLMAPI (implementation of backend, e.g. OpenAI, Anthropic)
            model_name: Name of model to use for LLM backend (provider-specific string)
            tools: ToolCall delegator (handles dispatch to actual code tools)
            ui: ConsoleUI for all user/output interaction, feedback etc.
            sleeper: Function used for sleeping between retries (overridable for tests)

        """
        self.ui = ui
        self.sleeper = sleeper

    def _raise_mismatch_error(self, msg: str) -> NoReturn:
        """Raise a runtime error for mismatched tool calls and results."""
        logger.error(msg)
        raise RuntimeError(msg)

    def _raise_type_error(self, msg: str) -> NoReturn:
        """Raise a type error for incorrect error type."""
        logger.error(msg)
        raise TypeError(msg)

    # Only retry on specific LiteLLM exceptions that indicate a potentially
    # transient issue (like rate limiting). Do not retry on general errors.
    @retry(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_incrementing(start=30, increment=30, max=10 * 60),
        retry=retry_if_exception_type(litellm.exceptions.RateLimitError),
        reraise=True,
    )
    def _call_llm_with_retry(
        self,
        model: str,
        history: History,
        tools: ToolCall,
        conv: _ConversationData,
        status: Status,
    ) -> litellm.ModelResponse:
        logger.debug("Calling LLM API...")
        try:
            completion = litellm.completion(
                model=model,
                messages=[m.to_dict() for m in history.get_all_messages()],
                stream=False,
                tools=tools.tools,
                num_retries=0,  # Let tenacity handle retries
            )
        except litellm.exceptions.RateLimitError as rate_limit_err:
            # Log and increment count for the specific retry handler
            conv.api_retry_count += 1
            self.ui.display_warning(f"Rate limit exceeded: {rate_limit_err}")
            logger.warning(
                "Retrying API call due to RateLimitError... (Attempt %d)",
                conv.api_retry_count,
            )
            status.update(
                f"Retrying (Rate Limit {conv.api_retry_count}/{_MAX_RETRIES}), io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
            )
            # Reraise TryAgain explicitly to signal tenacity to retry
            raise TryAgain from rate_limit_err
        except litellm.exceptions.InternalServerError as server_error:
            # Log and increment count for the specific retry handler
            conv.api_retry_count += 1
            self.ui.display_error(f"Server error exceeded: {server_error}")
            logger.exception(
                "Retrying API call due to RateLimitError... (Attempt %d)",
                conv.api_retry_count,
            )
            status.update(
                f"Retrying (Rate Limit {conv.api_retry_count}/{_MAX_RETRIES}), io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
            )
            # Reraise TryAgain explicitly to signal tenacity to retry
            raise TryAgain from server_error
        except Exception as e:
            # For any other exception, log it and let tenacity's reraise=True handle it
            # (i.e., it will stop retrying and raise the original exception)
            logger.exception(
                "LLM call failed with non-retried exception: %s",
                type(e).__name__,
            )
            raise  # Reraises the original exception 'e'
        else:
            conv.api_retry_count = 0
            return completion

    def _call_llm(
        self,
        model: str,
        history: History,
        tools: ToolCall,
        conv: _ConversationData,
        status: Status,
    ) -> _GenerationOutcome:
        """Call the LLM API, process the stream, and update _TurnData.

        Args:
            model: The model name.
            history: The conversation history.
            tools: The tools.
            conv: The state of this conversation session. Reset conv.turn before calling.
            status: UI status object to update the user on progress.

        Returns:
            _GenerationOutcome indicating success or error.

        """
        outcome: _GenerationOutcome
        try:
            # Reset the retry counter before calling the retry loop
            model_response = self._call_llm_with_retry(
                model,
                history,
                tools,
                conv,
                status,
            )
        except Exception as e:
            # This catches errors that tenacity decided not to retry or that exceeded retries
            logger.exception(
                "Non-retriable error or retry limit exceeded during generation",
            )
            conv.turn.generation_exception = e
            outcome = _GenerationOutcome(success=False, error=e)
        else:
            # Successful call (possibly after retries)
            if hasattr(model_response, "choices") and model_response.choices:
                message: litellm.Message = model_response.choices[0].message

                if message.content:
                    self.ui.display_ai_response_chunk(message.content)

                if hasattr(model_response.choices[0], "finish_reason"):
                    conv.turn.turn_finish_reason = model_response.choices[
                        0
                    ].finish_reason
                    logger.debug(
                        "Received finish reason: %s",
                        conv.turn.turn_finish_reason,
                    )

                conv.turn.assistant_messages.append(message)

            if hasattr(model_response, "usage"):
                conv.add_usage(model_response.usage)

            logger.debug("LLM API call finished successfully.")
            outcome = _GenerationOutcome(success=True)

        return outcome

    def _execute_tools(self, turn: _TurnData, tools: ToolCall) -> _ToolExecutionOutcome:
        """Execute all tool calls currently buffered. Updates execution lists/results."""
        logger.debug("Executing %d tool calls...", len(turn.buffered_tool_calls()))
        turn.tool_results = []
        if not turn.has_buffered_tool_calls():
            return _ToolExecutionOutcome(success=True)
        try:
            for tool_call in turn.buffered_tool_calls():
                self.ui.display_tool_call(tool_call)
                logger.info(
                    "Tool call: %s with args: %s",
                    tool_call.function.name,
                    tool_call.function.arguments,
                )
                tool_result: ToolCallResult = tools.call_tool(tool_call)
                if tool_result.success:
                    self.ui.display_tool_result(tool_call.function.name, tool_result)
                    logger.info(
                        "Tool '%s' result: %s",
                        tool_call.function.name,
                        tool_result.output.content,
                    )
                else:
                    self.ui.display_tool_error(tool_call.function.name, tool_result)
                    logger.error(
                        "Tool '%s' error: %s",
                        tool_call.function.name,
                        tool_result.output.content,
                    )
                tool_result_message = litellm.Message(
                    role=Role.TOOL.value,
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    content=tool_result.model_dump_json(exclude_none=True),
                )
                turn.tool_results.append(tool_result_message)

            # Check tool calls and results match
            if len(turn.buffered_tool_calls()) != len(turn.tool_results):
                self._raise_mismatch_error(
                    "Mismatched tool calls and results after execution",
                )

            logger.debug("Tool execution finished.")
            return _ToolExecutionOutcome(success=True)
        except Exception as e:
            logger.exception("Error during tool execution")
            turn.assistant_messages = []
            turn.tool_results = []
            return _ToolExecutionOutcome(success=False, error=e)

    def _update_histories(
        self,
        history: History,
        turn: _TurnData,
    ) -> None:
        """Update chat history after each turn.

        Appends generated text/tool-calls, tool results as messages, and
        synchronizes with provider's internal format.

        """
        history.messages.extend(turn.assistant_messages)
        history.messages.extend(turn.tool_results)

    # The process_prompt method is deliberately complex as it implements a complete
    # state machine with multiple pathways. Refactoring attempts have been made but didn't
    # show better readability.
    def process_prompt(  # noqa: C901, PLR0912, PLR0915 See note above
        self,
        model: str,
        history: History,
        tools: ToolCall,
    ) -> ThinkingResult:
        """Run a chat prompt through the full state machine loop.

        Generates responses, dispatches tools, retries as needed, and updates
        both visible user and provider history.
        Returns a ThinkingResult giving the final status.
        """
        conv = _ConversationData()
        with self.ui.status("Working...") as status:
            while conv.state not in (
                _InteractionState.FINISHED,
                _InteractionState.FAILED,
                _InteractionState.INTERRUPTED,
            ):
                try:
                    logger.debug("Current state: %s", conv.state.name)
                    if conv.state == _InteractionState.STARTING_TURN:
                        conv.turn.reset()
                        conv.state = _InteractionState.GENERATING
                    elif conv.state == _InteractionState.GENERATING:
                        conv.total_requests += 1
                        logger.info(
                            "Starting request %d with %d history items.",
                            conv.total_requests,
                            len(history.messages),
                        )
                        logger.debug(
                            "Provider history for generation:",
                            extra={"history": [m.to_dict() for m in history.messages]},
                        )
                        logger.debug("System Message: %s", history.system_message)
                        status.update(
                            f"Working, io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                        )
                        outcome = self._call_llm(model, history, tools, conv, status)
                        if conv.total_input_tokens > 0 or conv.total_output_tokens > 0:
                            status.update(
                                f"Working, io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                            )
                        else:
                            status.update(
                                f"Working, total requests: {conv.total_requests}...",
                            )
                        if outcome.success:
                            conv.state = _InteractionState.PROCESSING_GENERATION_RESULT
                            # Reset API retry count after success
                        else:
                            conv.final_reason = (
                                str(outcome.error) or type(outcome.error).__name__
                            )
                            conv.state = (
                                _InteractionState.INTERRUPTED
                                if isinstance(outcome.error, KeyboardInterrupt)
                                else _InteractionState.FAILED
                            )
                    elif conv.state == _InteractionState.PROCESSING_GENERATION_RESULT:
                        if conv.turn.has_buffered_tool_calls():
                            conv.state = _InteractionState.EXECUTING_TOOLS
                        elif conv.turn.has_any_content():
                            conv.state = _InteractionState.UPDATING_HISTORY
                            conv.empty_response_retry_count = 0
                        else:
                            conv.state = _InteractionState.HANDLING_EMPTY_RETRY
                    elif conv.state == _InteractionState.EXECUTING_TOOLS:
                        outcome = self._execute_tools(conv.turn, tools)
                        if outcome.success:
                            conv.state = _InteractionState.PROCESSING_TOOL_RESULTS
                        else:
                            conv.final_reason = (
                                str(outcome.error) or type(outcome.error).__name__
                            )
                            conv.state = (
                                _InteractionState.INTERRUPTED
                                if isinstance(outcome.error, KeyboardInterrupt)
                                else _InteractionState.FAILED
                            )
                    elif conv.state == _InteractionState.PROCESSING_TOOL_RESULTS:
                        conv.state = _InteractionState.UPDATING_HISTORY
                    elif conv.state == _InteractionState.UPDATING_HISTORY:
                        self._update_histories(history, conv.turn)
                        if conv.turn.has_executed_tools():
                            conv.state = _InteractionState.STARTING_TURN
                        elif conv.turn.turn_finish_reason:
                            conv.final_reason = conv.turn.turn_finish_reason
                            conv.state = _InteractionState.FINISHED
                        elif conv.turn.has_text_content():
                            logger.info(
                                "Continuing generation as no finish reason was received.",
                            )
                            conv.state = _InteractionState.STARTING_TURN
                        else:
                            logger.warning(
                                "History update completed but turn yielded no content and no finish reason.",
                            )
                            conv.state = _InteractionState.HANDLING_EMPTY_RETRY
                    elif conv.state == _InteractionState.HANDLING_EMPTY_RETRY:
                        logger.debug("Handling potentially empty response.")
                        if (
                            conv.empty_response_retry_count
                            < _EMPTY_RESPONSE_MAX_RETRIES
                        ):
                            conv.empty_response_retry_count += 1
                            wait_time = _EMPTY_RESPONSE_WAIT_SEC
                            logger.info(
                                "Empty response detected. Retrying in %d seconds... (Attempt %d/%d)",
                                wait_time,
                                conv.empty_response_retry_count,
                                _EMPTY_RESPONSE_MAX_RETRIES,
                            )
                            self.ui.display_warning(
                                "No output generated by provider, retrying.",
                            )
                            status.update(
                                f"Empty response retry ({conv.empty_response_retry_count}/{_EMPTY_RESPONSE_MAX_RETRIES}), io tokens: {conv.total_input_tokens}/{conv.total_output_tokens}, total requests: {conv.total_requests}...",
                            )
                            self.sleeper(wait_time)
                            conv.state = _InteractionState.GENERATING
                        else:
                            logger.error("Empty response retry limit exceeded.")
                            conv.final_reason = "No result"
                            conv.state = _InteractionState.FAILED
                except KeyboardInterrupt:
                    logger.warning(
                        "KeyboardInterrupt detected (outside inner try/except).",
                    )
                    conv.final_reason = "User interrupted"
                    conv.state = _InteractionState.INTERRUPTED
                except Exception as e:
                    logger.exception("Unexpected error in state machine")
                    conv.final_reason = f"Internal error: {e}"
                    conv.state = _InteractionState.FAILED
        if conv.state == _InteractionState.FINISHED:
            self.ui.display_info(f"Finished: {conv.final_reason or 'Empty reason'}")
        if conv.state == _InteractionState.INTERRUPTED:
            self.ui.display_info(f"Interrupted: {conv.final_reason or 'Empty reason'}")
        if conv.state == _InteractionState.FAILED:
            self.ui.display_error(f"Failed: {conv.final_reason or 'Empty reason'}")
        return ThinkingResult(
            finish_reason=conv.final_reason,
            input_tokens=conv.total_input_tokens,
            output_tokens=conv.total_output_tokens,
            request_count=conv.total_requests,
        )
