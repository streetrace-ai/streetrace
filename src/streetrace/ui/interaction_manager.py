# app/interaction_manager.py
import logging
import time
from typing import List, Optional, Union

from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import ContentPart, ContentPartFinishReason, ContentPartText, ContentPartToolCall, ContentPartToolResult, ContentPartUsage, History, Message, Role, ToolCallResult, ToolOutput
from streetrace.tools.tools import ToolCall

# Assuming these are accessible
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3

class ThinkingStatus:
    """
    Encapsulates the outcome of a thinking session, including finish reason and token usage stats.
    """
    def __init__(self, finish_reason: Optional[Union[str, None]], input_tokens: int, output_tokens: int, request_count: int):
        self.finish_reason = finish_reason
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.request_count = request_count

    def __repr__(self):
        return (f"ThinkingStatus(finish_reason={self.finish_reason!r}, "
                f"input_tokens={self.input_tokens}, output_tokens={self.output_tokens}, "
                f"request_count={self.request_count})")


class InteractionManager:
    """
    Handles the core interaction with the AI model via generate_with_tools.

    Encapsulates the provider, model, tools, tool callback, and error handling
    for the AI generation process.
    """

    def __init__(
        self,
        provider: LLMAPI,
        model_name: Optional[str],
        tools: ToolCall,
        ui: ConsoleUI,
    ):
        """
        Initializes the InteractionManager.

        Args:
            provider: The initialized AI provider instance (e.g., ClaudeProvider).
            model_name: The specific model name to use (or None for provider default).
            tools: Tool call implementaiton that defines tools provided to the AI.
            tool_callback: The function to execute tool calls requested by the AI.
                           Expected signature: tool_callback(tool_name, args, original_call) -> result_dict
            ui: The ConsoleUI instance for displaying errors.
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools
        self.ui = ui
        logger.info(
            f"InteractionManager initialized for provider: {type(provider).__name__}"
        )

    def process_prompt(self, history: History) -> ThinkingStatus:
        """
        Processes the prompt by calling the AI with the provided history.

        Handles potential exceptions during the AI generation call and displays
        errors using the ConsoleUI. Modifies the history object in place.

        Args:
            history: The conversation History object containing the context and prompt.

        Returns:
            ThinkingStatus: Object containing finish reason, I/O token stats, and request count.
        """
        client = self.provider.initialize_client()
        provider_history = self.provider.transform_history(history)
        provider_tools = self.provider.transform_tools(self.tools.tools)

        consecutive_retries_count = 0
        request_count = 0        # total requests in this thinking session
        input_tokens = 0         # total input tokens in this thinking session
        output_tokens = 0        # total output tokens in this thinking session

        has_tool_calls = False   # always continue thining if there are tool calls
        reason_to_finish = None  # always continue thining if there is no reason to finish
        retry = False            # always continue thining if retry is requested
        retry_wait_time = 0      # time to wait before retrying a request

        render_final_reason = True   # render the reason_to_finish in the UI
        update_history = True        # update history with the new conversation turn
        is_keyboard_interrupt = False # flag to indicate if a keyboard interrupt occurred

        # <!-- thining session start -->
        with self.ui.status("Working...") as status:
            while not is_keyboard_interrupt and (has_tool_calls or not reason_to_finish or retry):
                # Ensure history fits the context window
                # if not self.provider.manage_conversation_history(provider_history):
                #     raise ValueError(
                #         "Conversation history exceeds the model's context window."
                #     )
                retry = False
                retry_wait_time = 0
                has_tool_calls = False
                reason_to_finish = None
                update_history = False
                is_keyboard_interrupt = False
                request_count += 1
                logging.info(
                    f"Starting request {request_count} with {len(provider_history)} message items."
                )
                logging.debug(
                    "Messages for generation:\n%s",
                    self.provider.pretty_print(provider_history),
                )
                logging.debug(
                    "Messages for generation:\n%s",
                    provider_history,
                )

                buffer_assistant_text: list[str] = []                 # all text retrieved in this request
                buffer_tool_calls: list[ContentPartToolCall] = []     # all tool calls retrieved in this request
                buffer_tool_results: list[ContentPartToolResult] = [] # all tool responses to be sent in the next request
                try:
                    # request to process current provider history and process the
                    # response for the new conversation turn
                    for chunk in self.provider.generate(
                        client,
                        self.model_name,
                        history.system_message,
                        provider_history,
                        provider_tools,
                    ):
                        match chunk:
                            case ContentPartText():
                                self.ui.display_ai_response_chunk(chunk.text)
                                buffer_assistant_text.append(chunk.text)

                            case ContentPartToolCall():
                                self.ui.display_tool_call(chunk)
                                logging.info(
                                    f"Tool call: {chunk.name} with args: {chunk.arguments}"
                                )
                                tool_result = self.tools.call_tool(chunk)
                                tool_result_part = ContentPartToolResult(
                                        id=chunk.id,
                                        name=chunk.name,
                                        content=tool_result,
                                    )
                                if tool_result.success:
                                    self.ui.display_tool_result(tool_result_part)
                                    logging.info(
                                        f"Tool '{chunk.name}' result: {tool_result.output.content}'"
                                    )
                                else:
                                    self.ui.display_tool_error(tool_result_part)
                                    logging.error(tool_result.output.content)
                                # add tool calls and results in adjacent lines to avoid
                                # adding calls without results
                                buffer_tool_calls.append(chunk)
                                buffer_tool_results.append(tool_result_part)
                                has_tool_calls = True

                            case ContentPartFinishReason():
                                reason_to_finish = chunk.finish_reason

                            case ContentPartUsage():
                                input_tokens += chunk.prompt_tokens
                                output_tokens += chunk.response_tokens

                        if input_tokens + output_tokens > 0:
                            status.update(f"Working, io tokens: {input_tokens}/{output_tokens}, total requests: {request_count}...")
                        else:
                            status.update(f"Working, total requests: {request_count}...")

                    assert len(buffer_tool_calls) == len(buffer_tool_results), "Mismatched tool calls and results"
                    consecutive_retries_count = 0
                    update_history = True

                except RetriableError as retry_err:
                    # provider reports an error and the request can be retried
                    # provider_history has to stay as before the last request
                    logger.exception(retry_err)
                    self.ui.display_warning(retry_err)
                    if consecutive_retries_count < (retry_err.max_retries or _DEFAULT_MAX_RETRIES):
                        consecutive_retries_count += 1
                        retry = True
                        retry_wait_time = retry_err.wait_time(consecutive_retries_count)
                    else:
                        retry = False
                        retry_wait_time = 0
                        reason_to_finish = "Retry attempts exceeded"
                    render_final_reason = False
                except KeyboardInterrupt:
                    # User pressed Ctrl+C, we need to exit the thinking loop after updating the history.
                    # When updating common history, we need to be careful not to add tool calls without
                    # the corresponding tool results.
                    logger.info("User interrupted.")
                    reason_to_finish = "User interrupted"
                    is_keyboard_interrupt = True
                    self.ui.display_info("\nExiting the working loop, press Ctrl+C again to quit.")
                    render_final_reason = False
                except Exception as fail_err:
                    # general error, we need to exit the thinking loop without updating the history
                    logger.exception(fail_err)
                    reason_to_finish = str(fail_err)
                    self.ui.display_error(fail_err)
                    render_final_reason = False

                assistant_messages: List[ContentPart] = []
                if buffer_assistant_text:
                    assistant_messages.append(ContentPartText(text="".join(buffer_assistant_text)))
                assistant_messages += buffer_tool_calls

                # conditions involved:      update_history, is_keyboard_interrupt, turn, consecutive_retries_count, retry
                # update history            True            ANY                    True  ANY                        False
                # continue thinking loop    ANY             False                  ANY   < _DEFAULT_MAX_RETRIES     or True
                # display a message
                # write to the log
                # report the finish reason

                if update_history and not retry:
                    turn: List[Message] = []
                    if assistant_messages:
                        new_message = history.add_message(Role.MODEL, assistant_messages)
                        if new_message:
                            turn.append(new_message)
                    if buffer_tool_results:
                        new_message = history.add_message(Role.TOOL, buffer_tool_results)
                        if new_message:
                            turn.append(new_message)
                    if turn:
                        self.provider.append_history(provider_history, turn)

                    if not turn and not reason_to_finish:
                        if consecutive_retries_count < _DEFAULT_MAX_RETRIES:
                            consecutive_retries_count += 1
                            self.ui.display_warning("No output generated by provider, retrying.")
                            retry = True
                            retry_wait_time = 10 # sec
                        else:
                            self.ui.display_warning("No output generated by provider, retry attempts exceeded.")

                if retry:
                    assert retry_wait_time > 0
                    logger.info(f"Retrying in {retry_wait_time} seconds...")
                    self.ui.display_info(f"Retrying in {retry_wait_time} seconds...")
                    time.sleep(retry_wait_time)

                retry_wait_time = 0


        # <!-- thining session end -->

        if render_final_reason:
            self.ui.display_info(reason_to_finish)

        return ThinkingStatus(
            finish_reason=reason_to_finish,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_count=request_count
        )
