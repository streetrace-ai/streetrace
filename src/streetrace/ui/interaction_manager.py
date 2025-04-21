# app/interaction_manager.py
import logging
import time
from typing import List, Optional

from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import ContentPart, ContentPartText, ContentPartToolCall, ContentPartToolResult, History, Message, Role
from streetrace.tools.tools import ToolCall

# Assuming these are accessible
from streetrace.ui.console_ui import ConsoleUI

logger = logging.getLogger(__name__)


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

    def process_prompt(self, history: History):
        """
        Processes the prompt by calling the AI with the provided history.

        Handles potential exceptions during the AI generation call and displays
        errors using the ConsoleUI. Modifies the history object in place.

        Args:
            history: The conversation History object containing the context and prompt.
        """
        client = self.provider.initialize_client()
        provider_history = self.provider.transform_history(history)
        provider_tools = self.provider.transform_tools(self.tools.tools)

        consecutive_retries_count = 0
        request_count = 0

        has_tool_calls = False   # always continue self-talk if there are tool calls
        reason_to_finish = None  # always continue self-talk if there is no reason to finish
        retry = False            # continue self-talk if retry is requested

        render_final_reason = True

        # <!-- Agent self-conversation loop start -->
        with self.ui.status("Working..."):
            while has_tool_calls or not reason_to_finish or retry:
                # Ensure history fits the context window
                # if not self.provider.manage_conversation_history(provider_history):
                #     raise ValueError(
                #         "Conversation history exceeds the model's context window."
                #     )
                retry = False
                has_tool_calls = False
                reason_to_finish = None
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

                buffer_assistant_text: list[str] = []
                buffer_tool_calls: list[ContentPartToolCall] = []
                buffer_tool_results: list[ContentPartToolResult] = []
                try:
                    for chunk in self.provider.generate(
                        client,
                        self.model_name,
                        history.system_message,
                        provider_history,
                        provider_tools,
                    ):
                        if chunk.get_finish_message():
                            reason_to_finish = chunk.get_finish_message()
                            # finish message has to be the last chunk of the response
                            break

                        text_part = chunk.get_text()
                        if text_part:
                            self.ui.display_ai_response_chunk(text_part)
                            buffer_assistant_text.append(text_part)
                        if chunk.get_tool_calls():
                            for tool_call in chunk.get_tool_calls():
                                self.ui.display_tool_call(tool_call)
                                buffer_tool_calls.append(tool_call)
                                logging.info(
                                    f"Tool call: {tool_call.name} with args: {tool_call.arguments}"
                                )
                                tool_result = self.tools.call_tool(tool_call, chunk.raw)
                                tool_result_part = ContentPartToolResult(
                                        id=tool_call.id,
                                        name=tool_call.name,
                                        content=tool_result,
                                    )
                                if tool_result.success:
                                    self.ui.display_tool_result(tool_result_part)
                                    logging.info(
                                        f"Tool '{tool_call.name}' result: {tool_result.output.content}'"
                                    )
                                else:
                                    self.ui.display_tool_error(tool_result_part)
                                    logging.error(tool_result.output.content)
                                buffer_tool_results.append(tool_result_part)
                                has_tool_calls = True

                except RetriableError as retry_err:
                    # retry means the provider_history has to stay unmodified for
                    # another similar request
                    logger.exception(retry_err)
                    if consecutive_retries_count < retry_err.max_retries:
                        consecutive_retries_count += 1
                        retry = True
                        self.ui.display_warning(retry_err)
                        wait_time = retry_err.wait_time(consecutive_retries_count)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        reason_to_finish = "Retry attempts exceeded"
                        self.ui.display_error(retry_err)
                    render_final_reason = False
                except Exception as fail_err:
                    # no retry means the provider_history has to be updated with
                    # the turn messages, and we need to exit the conversation loop
                    logger.exception(fail_err)
                    consecutive_retries_count = 0
                    reason_to_finish = str(fail_err)
                    self.ui.display_error(fail_err)
                    render_final_reason = False

                assistant_messages: List[ContentPart] = []
                if buffer_assistant_text:
                    assistant_messages.append(ContentPartText(text="".join(buffer_assistant_text)))
                assistant_messages += buffer_tool_calls
                turn: List[Message] = []
                if assistant_messages:
                    turn.append(history.add_message(Role.MODEL, assistant_messages))
                if buffer_tool_results:
                    turn.append(history.add_message(Role.TOOL, buffer_tool_results))
                # if this generation has completed successfully, update the history
                if not retry:
                    if turn:
                        self.provider.append_history(provider_history, turn)
                        consecutive_retries_count = 0
                    else:
                        # if it's not a retry due to error, and the turn is empty,
                        # the provider responded with an empty output (or we don't
                        # know how to handle the provided output)
                        if consecutive_retries_count < 3:
                            consecutive_retries_count += 1
                            retry = True
                            self.ui.display_warning(
                                "No output generated by provider. See logs for details in "
                                "case there is unsupported output. Retrying...")
                            wait_time = 10 # sec
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            reason_to_finish = "No output generated by provider after multiple retries."
                            self.ui.display_warning(
                                "No output generated by provider. See logs for details in "
                                "case there is unsupported output.")


        # <!-- Agent self-conversation loop end -->
        if render_final_reason:
            self.ui.display_info(reason_to_finish)
