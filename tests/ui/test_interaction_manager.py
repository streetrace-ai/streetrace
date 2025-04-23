import logging
import pytest
from unittest.mock import MagicMock, call, patch

# Imports from the project
from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import (
    ContentPart, ContentPartFinishReason, ContentPartText,
    ContentPartToolCall, ContentPartToolResult, ContentPartUsage,
    History, Message, Role, ToolCallResult, ToolOutput
)
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.interaction_manager import InteractionManager, ThinkingStatus, _DEFAULT_MAX_RETRIES

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Fixtures ---

@pytest.fixture
def mock_provider():
    """Provides a mock LLMAPI provider."""
    provider = MagicMock(spec=LLMAPI)
    provider.transform_history.side_effect = lambda history: list(history.conversation) # Simple pass-through for testing
    provider.transform_tools.side_effect = lambda tools: tools # Simple pass-through
    provider.append_history.side_effect = lambda provider_history, turn: provider_history.extend(turn)
    provider.generate.return_value = iter([]) # Default: generates nothing
    return provider

@pytest.fixture
def mock_tools():
    """Provides a mock ToolCall instance."""
    tools = MagicMock(spec=ToolCall)
    tools.tools = [{"name": "mock_tool"}] # Example tool definition
    # Default successful tool call
    tools.call_tool.return_value = ToolCallResult(
        success=True,
        output=ToolOutput(type="text", content="Tool Success Result")
    )
    return tools

@pytest.fixture
def mock_ui():
    """Provides a mock ConsoleUI."""
    ui = MagicMock(spec=ConsoleUI)
    # Mock the status context manager
    status_mock = MagicMock()
    status_mock.__enter__.return_value = status_mock # Return self for context manager
    status_mock.__exit__.return_value = None
    ui.status.return_value = status_mock
    return ui

@pytest.fixture
def interaction_manager(mock_provider, mock_tools, mock_ui):
    """Provides an InteractionManager instance with mocked dependencies."""
    return InteractionManager(
        provider=mock_provider,
        model_name="test-model",
        tools=mock_tools,
        ui=mock_ui,
    )

@pytest.fixture
def sample_history():
    """Provides a sample History object."""
    history = History(system_message="System prompt")
    # history.add_message(Role.USER, [ContentPartText(text="Initial user prompt")])
    return history

# --- Test Cases ---

def test_process_prompt_normal_finish(interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Ground Rule 1: Test normal finish with text response.
    Provider yields text and a finish reason.
    Expect ThinkingStatus with reason, stats, and history updated.
    """
    logger.info("--- Test: Normal Finish ---")
    # Arrange
    provider_response = [
        ContentPartText(text="Hello!"),
        ContentPartUsage(prompt_tokens=10, response_tokens=5),
        ContentPartFinishReason(finish_reason="stop"),
    ]
    mock_provider.generate.return_value = iter(provider_response)
    initial_history_len = len(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == "stop"
    assert status.input_tokens == 10
    assert status.output_tokens == 5
    assert status.request_count == 1
    mock_provider.generate.assert_called_once()
    # History should have the new assistant message
    assert len(sample_history.conversation) == initial_history_len + 1
    assert sample_history.conversation[-1].role == Role.MODEL
    assert isinstance(sample_history.conversation[-1].content[0], ContentPartText)
    assert sample_history.conversation[-1].content[0].text == "Hello!"
    mock_ui.display_ai_response_chunk.assert_called_once_with("Hello!")
    mock_ui.display_info.assert_any_call("stop") # Check if finish reason was displayed

def test_process_prompt_tool_call_then_finish(interaction_manager, mock_provider, mock_tools, sample_history, mock_ui):
    """
    Ground Rule 4 & 10: Test interaction with a tool call, followed by a final text response.
    Provider yields tool call -> manager calls tool -> provider yields text and finish.
    Expect loop to run twice, history updated correctly, correct final status.
    """
    logger.info("--- Test: Tool Call then Finish ---")
    # Arrange
    tool_call_id = "tool_abc123"
    tool_name = "mock_tool"
    tool_args = {"arg1": "value1"}
    tool_result_content = "Tool Success Result"

    # First call to generate: yield a tool call
    provider_response_1 = [
        ContentPartToolCall(id=tool_call_id, name=tool_name, arguments=tool_args),
        ContentPartUsage(prompt_tokens=20, response_tokens=15),
        # No finish reason here, implies tool_calls follow
    ]
    # Second call to generate: yield final text response
    provider_response_2 = [
        ContentPartText(text="Okay, did the tool thing."),
        ContentPartUsage(prompt_tokens=30, response_tokens=25), # Tokens from second call
        ContentPartFinishReason(finish_reason="stop"),
    ]
    mock_provider.generate.side_effect = [
        iter(provider_response_1),
        iter(provider_response_2),
    ]
    mock_tools.call_tool.return_value = ToolCallResult(
        success=True, output=ToolOutput(type="text", content=tool_result_content)
    )
    initial_history_len = len(sample_history.conversation)
    initial_provider_history = list(sample_history.conversation) # Copy for assertion

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == "stop"
    assert status.input_tokens == 20 + 30 # Sum of both requests
    assert status.output_tokens == 15 + 25 # Sum of both requests
    assert status.request_count == 2

    # Check generate calls
    assert mock_provider.generate.call_count == 2
    # First call args (simplified check)
    mock_provider.generate.assert_any_call(
        interaction_manager.provider.initialize_client(),
        interaction_manager.model_name,
        sample_history.system_message,
        initial_provider_history, # History before first call
        mock_tools.tools
    )
    # Second call args (check history includes first turn's model and tool messages)
    history_after_first_turn = initial_provider_history + [
        Message(role=Role.MODEL, content=[ContentPartToolCall(id=tool_call_id, name=tool_name, arguments=tool_args)]),
        Message(role=Role.TOOL, content=[ContentPartToolResult(id=tool_call_id, name=tool_name, content=ToolCallResult(success=True, output=ToolOutput(type="text", content=tool_result_content)))])
    ]
    # We need to check the actual call argument list
    second_call_args = mock_provider.generate.call_args_list[1]
    # print(f"Second call args: {second_call_args}") # Debugging history
    assert second_call_args[0][3] == history_after_first_turn # Check history passed to second call


    # Check tool call
    mock_tools.call_tool.assert_called_once()
    call_args, call_kwargs = mock_tools.call_tool.call_args
    assert isinstance(call_args[0], ContentPartToolCall)
    assert call_args[0].id == tool_call_id
    assert call_args[0].name == tool_name
    assert call_args[0].arguments == tool_args

    # Check final history
    assert len(sample_history.conversation) == initial_history_len + 3 # model(tool_call) + tool(result) + model(text)
    assert sample_history.conversation[-3].role == Role.MODEL
    assert isinstance(sample_history.conversation[-3].content[0], ContentPartToolCall)
    assert sample_history.conversation[-2].role == Role.TOOL
    assert isinstance(sample_history.conversation[-2].content[0], ContentPartToolResult)
    assert sample_history.conversation[-1].role == Role.MODEL
    assert isinstance(sample_history.conversation[-1].content[0], ContentPartText)
    assert sample_history.conversation[-1].content[0].text == "Okay, did the tool thing."

    # Check UI calls
    mock_ui.display_tool_call.assert_called_once()
    mock_ui.display_tool_result.assert_called_once()
    mock_ui.display_ai_response_chunk.assert_called_once_with("Okay, did the tool thing.")
    mock_ui.display_info.assert_any_call("stop")

@patch('time.sleep', return_value=None) # Mock time.sleep - Restored decorator
def test_process_prompt_retriable_error_max_retries(mock_sleep, interaction_manager, mock_provider, sample_history, mock_ui): # Added mock_sleep arg
    """
    Ground Rule 2 & 9: Test RetriableError handling reaches max retries.
    Provider throws RetriableError multiple times, then loop exits.
    Check retry count, wait calls, final status, and history state.
    Use default max_retries first.
    """
    logger.info("--- Test: Retriable Error Max Retries (Default) ---")
    # Arrange
    max_retries = _DEFAULT_MAX_RETRIES
    # Use a RetriableError that returns a non-zero wait time
    retry_error = RetriableError("Temporary issue", max_retries=None, wait_seconds=1) # Use default retries, specify base wait
    mock_provider.generate.side_effect = [retry_error] * max_retries # Throw error max_retries times

    initial_history_len = len(sample_history.conversation)
    initial_provider_history = list(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == "Retry attempts exceeded"
    assert status.input_tokens == 0 # No successful calls
    assert status.output_tokens == 0
    assert status.request_count == max_retries # Called max_retries times

    # Check generate calls
    assert mock_provider.generate.call_count == max_retries
    for i in range(max_retries):
         # Check history was the same for all calls
        call_args = mock_provider.generate.call_args_list[i]
        assert call_args[0][3] == initial_provider_history

    # Check sleep calls (wait time logic might vary, check count and times)
    assert mock_sleep.call_count == max_retries # Sleep is called *before* each retry attempt
    expected_wait_times = [retry_error.wait_time(i + 1) for i in range(max_retries)] # wait_time called before each retry
    actual_wait_times = [args[0][0] for args in mock_sleep.call_args_list]
    assert actual_wait_times == expected_wait_times

    # Check history (should be unchanged)
    assert len(sample_history.conversation) == initial_history_len

    # Check UI calls
    assert mock_ui.display_warning.call_count == max_retries
    mock_ui.display_info.assert_has_calls([call(f"Retrying in {wait_time} seconds...") for wait_time in expected_wait_times])
    # No final "reason" display because render_final_reason is false on retry exit
    assert not any(args[0][0] == "Retry attempts exceeded" for args, kwargs in mock_ui.display_info.call_args_list if args)


@patch('time.sleep', return_value=None) # Mock time.sleep
def test_process_prompt_retriable_error_specific_retries(mock_sleep, interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Ground Rule 2: Test RetriableError handling with specific max_retries.
    Provider throws RetriableError with specific max_retries.
    """
    logger.info("--- Test: Retriable Error Specific Retries ---")
    # Arrange
    max_retries = 2
    wait_seconds = 3
    retry_error = RetriableError("Specific issue", max_retries=max_retries, wait_seconds=wait_seconds)
    mock_provider.generate.side_effect = [retry_error] * max_retries

    initial_history_len = len(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert status.finish_reason == "Retry attempts exceeded"
    assert status.request_count == max_retries
    assert mock_provider.generate.call_count == max_retries
    assert mock_sleep.call_count == max_retries # Sleep is called before each retry
    expected_wait_times = [retry_error.wait_time(i + 1) for i in range(max_retries)]
    actual_wait_times = [args[0][0] for args in mock_sleep.call_args_list]
    assert actual_wait_times == expected_wait_times
    assert len(sample_history.conversation) == initial_history_len
    assert mock_ui.display_warning.call_count == max_retries

def test_process_prompt_non_retriable_error_during_generate(interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Ground Rule 7 & 8: Test non-retriable error during provider.generate.
    Expect loop termination, error reason in status, and unchanged history.
    """
    logger.info("--- Test: Non-Retriable Error during Generate ---")
    # Arrange
    error_message = "Fatal generation error!"
    mock_provider.generate.side_effect = ValueError(error_message) # Any non-RetriableError
    initial_history_len = len(sample_history.conversation)
    initial_provider_history = list(sample_history.conversation) # Copy

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == error_message
    assert status.input_tokens == 0
    assert status.output_tokens == 0
    assert status.request_count == 1 # Failed on the first request

    # Check generate call
    mock_provider.generate.assert_called_once()
    call_args = mock_provider.generate.call_args_list[0]
    assert call_args[0][3] == initial_provider_history # Check history passed to call

    # Check history (should be unchanged)
    assert len(sample_history.conversation) == initial_history_len

    # Check UI calls
    mock_ui.display_error.assert_called_once()
    # Extract the error instance from the call_args
    displayed_error = mock_ui.display_error.call_args[0][0]
    assert isinstance(displayed_error, ValueError)
    assert str(displayed_error) == error_message
    # No final "reason" display because render_final_reason is false on general exception
    assert not any(args[0][0] == error_message for args, kwargs in mock_ui.display_info.call_args_list if args)


def test_process_prompt_non_retriable_error_during_tool_call(interaction_manager, mock_provider, mock_tools, sample_history, mock_ui):
    """
    Ground Rule 7, 8 & 11: Test non-retriable error during tools.call_tool.
    Provider yields a tool call, but tool execution fails.
    Expect loop termination, error reason in status, and history *before* the failed tool call.
    """
    logger.info("--- Test: Non-Retriable Error during Tool Call ---")
    # Arrange
    tool_call_id = "tool_fail"
    tool_name = "failing_tool"
    tool_args = {}
    error_message = "Tool execution failed!"

    provider_response = [
        ContentPartToolCall(id=tool_call_id, name=tool_name, arguments=tool_args),
        ContentPartUsage(prompt_tokens=5, response_tokens=3),
        # No finish reason, expects tool result next
    ]
    mock_provider.generate.return_value = iter(provider_response)
    mock_tools.call_tool.side_effect = RuntimeError(error_message) # Tool fails

    initial_history_len = len(sample_history.conversation)
    initial_provider_history = list(sample_history.conversation) # Copy

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == error_message
    # Tokens from the first (and only) successful generate call should be recorded
    assert status.input_tokens == 5
    assert status.output_tokens == 3
    assert status.request_count == 1 # The request yielding the tool call succeeded, the failure was after

    # Check generate call
    mock_provider.generate.assert_called_once()
    call_args = mock_provider.generate.call_args_list[0]
    assert call_args[0][3] == initial_provider_history

    # Check tool call attempt
    mock_tools.call_tool.assert_called_once()

    # --- FIX: Check history (should be unchanged) ---
    assert len(sample_history.conversation) == initial_history_len # History should not be updated on error
    # --- FIX: Provider history should not be updated either ---
    mock_provider.append_history.assert_not_called()


    # Check UI calls
    mock_ui.display_tool_call.assert_called_once()
    mock_ui.display_tool_result.assert_not_called() # Tool failed
    mock_ui.display_tool_error.assert_not_called() # Tool failed *before* result could be formatted
    mock_ui.display_error.assert_called_once()
    # Extract the error instance from the call_args
    displayed_error = mock_ui.display_error.call_args[0][0]
    assert isinstance(displayed_error, RuntimeError)
    assert str(displayed_error) == error_message
    # No final "reason" display because render_final_reason is false on general exception
    assert not any(args[0][0] == error_message for args, kwargs in mock_ui.display_info.call_args_list if args)

@patch('time.sleep', return_value=None) # Mock time.sleep
def test_process_prompt_no_finish_reason_or_tool_calls_retries(mock_sleep, interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Ground Rule 5 & 6: Test loop continues if no finish reason or tool calls are provided.
    Provider yields only text or usage, then nothing for several calls.
    Expect loop to retry _DEFAULT_MAX_RETRIES times after the first empty response, then exit.
    History should contain text accumulated before retries began.
    """
    logger.info("--- Test: No Finish Reason/Tool Call Retries ---")
    # Arrange
    max_empty_retries = _DEFAULT_MAX_RETRIES
    response_1 = [
        ContentPartText(text="Thinking..."),
        ContentPartUsage(prompt_tokens=10, response_tokens=5),
        # No finish reason or tool call
    ]
    response_2 = [
        ContentPartText(text=" still thinking..."), # More text
        ContentPartUsage(prompt_tokens=10, response_tokens=8),
        # No finish reason or tool call
    ]
    # Subsequent responses are empty or only usage (won't trigger continuation)
    response_empty = [
        ContentPartUsage(prompt_tokens=5, response_tokens=0),
         # No finish reason or tool call
    ]

    mock_provider.generate.side_effect = [
        iter(response_1),
        iter(response_2),
    ] + [iter(response_empty)] * max_empty_retries

    initial_history_len = len(sample_history.conversation)
    initial_provider_history = list(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    # The loop should exit because max_empty_retries was reached *after* getting no results
    assert status.finish_reason == "Empty response retries exceeded" # Check the specific reason set in the code fix
    assert status.input_tokens == 10 + 10 + (5 * max_empty_retries)
    assert status.output_tokens == 5 + 8 + (0 * max_empty_retries)
    assert status.request_count == 2 + max_empty_retries # 2 good responses + retries

    # Check generate calls
    assert mock_provider.generate.call_count == 2 + max_empty_retries

    # Check sleep calls (should be called during the empty response retries)
    assert mock_sleep.call_count == max_empty_retries # Sleep is called *before* each empty retry
    expected_wait_time = 10 # Hardcoded in the retry logic for empty response
    actual_wait_times = [args[0][0] for args in mock_sleep.call_args_list]
    assert all(t == expected_wait_time for t in actual_wait_times)


    # Check history (should contain the accumulated text from the first two calls)
    assert len(sample_history.conversation) == initial_history_len + 2 # Two assistant messages were added
    assert sample_history.conversation[-2].role == Role.MODEL
    assert sample_history.conversation[-2].content[0].text == "Thinking..."
    assert sample_history.conversation[-1].role == Role.MODEL
    # Text is concatenated within a turn, so second message combines text parts
    assert sample_history.conversation[-1].content[0].text == " still thinking..."


    # Check UI calls
    assert mock_ui.display_ai_response_chunk.call_count == 2
    mock_ui.display_ai_response_chunk.assert_any_call("Thinking...")
    mock_ui.display_ai_response_chunk.assert_any_call(" still thinking...")
    # Check warnings for empty retries
    assert mock_ui.display_warning.call_count == max_empty_retries
    mock_ui.display_warning.assert_any_call("No output generated by provider, retrying.")
    mock_ui.display_warning.assert_any_call("No output generated by provider, retry attempts exceeded.")
    mock_ui.display_info.assert_has_calls([call(f"Retrying in {expected_wait_time} seconds...")] * max_empty_retries)
    # No final "reason" display because render_final_reason is false on empty retry exit
    assert not any(args[0][0] == "Empty response retries exceeded" for args, kwargs in mock_ui.display_info.call_args_list if args)


def test_process_prompt_keyboard_interrupt(interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Ground Rule 12: Test KeyboardInterrupt during provider.generate.
    Simulate interrupt after some content has been yielded.
    Expect loop termination, specific reason, and history updated *partially*.
    """
    logger.info("--- Test: Keyboard Interrupt ---")
    # Arrange
    tool_call_id = "tool_int"
    tool_name = "interrupted_tool"
    tool_args = {"a": 1}

    def generate_with_interrupt():
        yield ContentPartText(text="Starting...")
        yield ContentPartUsage(prompt_tokens=5, response_tokens=2)
        yield ContentPartToolCall(id=tool_call_id, name=tool_name, arguments=tool_args)
        # Simulate Ctrl+C happening here, before the tool call is processed by manager
        raise KeyboardInterrupt()
        # These should not be yielded or processed
        # yield ContentPartFinishReason(finish_reason="stop")

    mock_provider.generate.side_effect = generate_with_interrupt
    # Tool should not be called
    mock_tools = interaction_manager.tools = MagicMock()

    initial_history_len = len(sample_history.conversation)
    initial_provider_history = list(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == "User interrupted"
    # Tokens yielded before interrupt should be counted
    assert status.input_tokens == 5
    assert status.output_tokens == 2
    assert status.request_count == 1 # Interrupt happened during the first request

    # Check generate call
    mock_provider.generate.assert_called_once()

    # Check tool call attempt (should NOT have happened)
    mock_tools.call_tool.assert_not_called()

    # --- FIX: Check history (should be unchanged) ---
    assert len(sample_history.conversation) == initial_history_len # History should not be updated on interrupt
    # --- FIX: Provider history should not be updated either ---
    mock_provider.append_history.assert_not_called()


    # Check UI calls
    mock_ui.display_ai_response_chunk.assert_called_once_with("Starting...")
    mock_ui.display_tool_call.assert_called_once() # Display happens as it's yielded
    mock_ui.display_tool_result.assert_not_called()
    mock_ui.display_tool_error.assert_not_called()
    mock_ui.display_error.assert_not_called()
    mock_ui.display_info.assert_any_call("\nExiting the working loop, press Ctrl+C again to quit.")
    # No final "reason" display because render_final_reason is false on interrupt
    assert not any(args[0][0] == "User interrupted" for args, kwargs in mock_ui.display_info.call_args_list if args)


def test_process_prompt_provider_yields_only_finish_reason(interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Added Scenario: Provider yields only a finish reason immediately.
    """
    logger.info("--- Test: Provider Yields Only Finish Reason ---")
    # Arrange
    provider_response = [
        ContentPartUsage(prompt_tokens=2, response_tokens=0),
        ContentPartFinishReason(finish_reason="completed"),
    ]
    mock_provider.generate.return_value = iter(provider_response)
    initial_history_len = len(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == "completed"
    assert status.input_tokens == 2
    assert status.output_tokens == 0
    assert status.request_count == 1
    mock_provider.generate.assert_called_once()
    # History should be unchanged as no assistant message was generated
    assert len(sample_history.conversation) == initial_history_len
    mock_ui.display_ai_response_chunk.assert_not_called()
    mock_ui.display_tool_call.assert_not_called()
    mock_ui.display_info.assert_any_call("completed")


def test_process_prompt_provider_yields_only_text_then_finish(interaction_manager, mock_provider, sample_history, mock_ui):
    """
    Added Scenario: Provider yields only text and then a finish reason.
    (Similar to normal finish, but explicit test)
    """
    logger.info("--- Test: Provider Yields Only Text and Finish ---")
    # Arrange
    provider_response = [
        ContentPartText(text="Just text."),
        ContentPartUsage(prompt_tokens=7, response_tokens=3),
        ContentPartFinishReason(finish_reason="done"),
    ]
    mock_provider.generate.return_value = iter(provider_response)
    initial_history_len = len(sample_history.conversation)

    # Act
    status = interaction_manager.process_prompt(sample_history)

    # Assert
    assert isinstance(status, ThinkingStatus)
    assert status.finish_reason == "done"
    assert status.input_tokens == 7
    assert status.output_tokens == 3
    assert status.request_count == 1
    mock_provider.generate.assert_called_once()
    # History should have the new assistant message
    assert len(sample_history.conversation) == initial_history_len + 1
    assert sample_history.conversation[-1].role == Role.MODEL
    assert sample_history.conversation[-1].content[0].text == "Just text."
    mock_ui.display_ai_response_chunk.assert_called_once_with("Just text.")
    mock_ui.display_info.assert_any_call("done")

