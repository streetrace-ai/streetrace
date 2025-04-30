import unittest
from unittest.mock import MagicMock, call

from streetrace.interaction_manager import (
    _DEFAULT_MAX_RETRIES,
    _EMPTY_RESPONSE_MAX_RETRIES,
    InteractionManager,
    ThinkingResult,
)

# Assuming these imports work based on project structure
from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import (
    ContentPartFinishReason,
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    ContentPartUsage,
    History,
    Message,
    Role,
    ToolCallResult,
    ToolOutput,
)

# Removed ToolDescription from this import
from streetrace.ui.console_ui import ConsoleUI


# Helper function to create RetriableError with wait_time logic
def _create_retriable_error(max_retries=None, base_wait_time=1):
    error = RetriableError("Simulated retriable error", max_retries=max_retries)
    # Simple exponential backoff for testing
    error.wait_time = lambda attempt: base_wait_time * (2 ** (attempt - 1))
    return error


class TestInteractionManager(unittest.TestCase):

    def setUp(self) -> None:
        """Set up test fixtures, mock dependencies."""
        self.mock_provider = MagicMock(spec=LLMAPI)
        # ToolCall needs 'tools' and 'tools_impl' attributes in the spec
        # We can mock the spec_set to include these, or just mock the instance directly
        # Mocking the instance is simpler here as we don't need strict spec checking for the mock itself.
        self.mock_tools = MagicMock()  # Removed spec=ToolCall
        self.mock_tools.tools = (
            []
        )  # Provide the 'tools' attribute expected by InteractionManager
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.mock_sleeper = MagicMock()
        self.mock_status = MagicMock()
        self.mock_ui.status.return_value.__enter__.return_value = (
            self.mock_status
        )  # Mock the context manager

        # Mock provider methods to return sensible defaults or iterables
        self.mock_provider.initialize_client.return_value = "mock_client"
        # Corrected: History uses 'conversation', not 'messages'
        self.mock_provider.transform_history.side_effect = lambda h: h.conversation
        self.mock_provider.transform_tools.return_value = (
            []
        )  # Default to no tools transformed
        self.mock_provider.generate.return_value = iter(
            [],
        )  # Default to empty generator
        self.mock_provider.append_history.return_value = None
        self.mock_provider.pretty_print.return_value = "pretty_history"

        self.manager = InteractionManager(
            provider=self.mock_provider,
            model_name="test_model",
            tools=self.mock_tools,
            ui=self.mock_ui,
            sleeper=self.mock_sleeper,  # Inject the mock sleeper
        )

        self.history = History(system_message="System Prompt")
        # Add initial user message to the history's conversation list
        self.history.conversation.append(
            Message(role=Role.USER, content=[ContentPartText(text="User Prompt")]),
        )

    def test_system_message_is_processed(self) -> None:
        """Test that a successful run returns a ThinkingResult with correct stats."""
        # Arrange
        self.mock_provider.generate.return_value = iter(
            [
                ContentPartText(text="Response text"),
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                ContentPartFinishReason(finish_reason="stop"),
            ],
        )

        # Act
        _ = self.manager.process_prompt(self.history)

        self.mock_provider.generate.assert_called_once_with(
            "mock_client",
            "test_model",
            "System Prompt",
            self.history.conversation,
            [],
        )

    def test_successful_completion_returns_thinking_result(self) -> None:
        """Test that a successful run returns a ThinkingResult with correct stats."""
        # Arrange
        self.mock_provider.generate.return_value = iter(
            [
                ContentPartText(text="Response text"),
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                ContentPartFinishReason(finish_reason="stop"),
            ],
        )

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert isinstance(result, ThinkingResult)
        assert result.finish_reason == "stop"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.request_count == 1
        self.mock_provider.generate.assert_called_once()
        self.mock_sleeper.assert_not_called()  # No retries, no sleep
        # Check history update
        self.mock_provider.append_history.assert_called_once()
        provider_history_arg = self.mock_provider.append_history.call_args[0][0]
        turn_arg = self.mock_provider.append_history.call_args[0][1]
        # Provider history passed to append_history is the transformed history
        assert provider_history_arg == self.history.conversation
        assert len(turn_arg) == 1  # Only model message added
        assert turn_arg[0].role == Role.MODEL
        assert len(turn_arg[0].content) == 1
        assert isinstance(turn_arg[0].content[0], ContentPartText)
        assert turn_arg[0].content[0].text == "Response text"

    def test_retriable_error_retries_and_waits(self) -> None:
        """Test RetriableError leads to retries with correct waits, then succeeds."""
        # Arrange
        max_retries = 2
        wait_times = [1, 2]  # 1 * (2**(1-1)), 1 * (2**(2-1))
        retriable_error = _create_retriable_error(
            max_retries=max_retries,
            base_wait_time=1,
        )

        # Simulate: Error -> Error -> Success
        self.mock_provider.generate.side_effect = [
            retriable_error,
            retriable_error,
            iter(
                [
                    ContentPartText(text="Success finally!"),
                    ContentPartUsage(prompt_tokens=5, response_tokens=3),
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 3
        assert result.finish_reason == "stop"  # Should eventually succeed
        assert result.input_tokens == 5  # Only tokens from the successful call
        assert result.output_tokens == 3
        assert result.request_count == 3  # 2 failed + 1 successful request
        self.mock_sleeper.assert_has_calls([call(wait_times[0]), call(wait_times[1])])
        assert self.mock_sleeper.call_count == max_retries
        # Check history update (only the successful turn)
        self.mock_provider.append_history.assert_called_once()
        turn_arg = self.mock_provider.append_history.call_args[0][1]
        assert len(turn_arg) == 1
        assert isinstance(turn_arg[0].content[0], ContentPartText)
        assert turn_arg[0].content[0].text == "Success finally!"
        # Check that the warning was displayed for each retriable error
        self.mock_ui.display_warning.assert_has_calls(
            [call(retriable_error), call(retriable_error)],
        )
        assert self.mock_ui.display_warning.call_count == 2

    def test_retriable_error_exceeds_max_retries(self) -> None:
        """Test RetriableError exits after max_retries with correct reason."""
        # Arrange
        max_retries = 2
        wait_times = [1, 2]
        retriable_error = _create_retriable_error(
            max_retries=max_retries,
            base_wait_time=1,
        )

        # Simulate: Error -> Error -> Error (exceeds max_retries)
        # We need generate to raise the error 3 times
        self.mock_provider.generate.side_effect = [retriable_error] * (max_retries + 1)

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == max_retries + 1
        assert result.finish_reason == "Retry attempts exceeded"
        assert result.input_tokens == 0  # No successful call
        assert result.output_tokens == 0
        assert result.request_count == max_retries + 1
        self.mock_sleeper.assert_has_calls([call(wait_times[0]), call(wait_times[1])])
        assert self.mock_sleeper.call_count == max_retries
        self.mock_provider.append_history.assert_not_called()  # History should not be updated on failure
        # Check warnings: 3 errors raised -> 3 error warnings displayed.
        # Then 1 final warning about exceeding retries.
        expected_warnings = [call(retriable_error)] * (max_retries + 1)
        self.mock_ui.display_warning.assert_has_calls(
            expected_warnings,
            any_order=False,
        )
        assert self.mock_ui.display_warning.call_count == max_retries + 1
        self.mock_ui.display_error.assert_has_calls(
            [call("Failed: Retry attempts exceeded")],
            any_order=False,
        )
        assert self.mock_ui.display_error.call_count == 1

    def test_retriable_error_uses_default_retries(self) -> None:
        """Test RetriableError uses _DEFAULT_MAX_RETRIES when max_retries is None."""
        # Arrange
        wait_times = [1, 2, 4]  # Assuming base_wait_time=1
        retriable_error = _create_retriable_error(
            max_retries=None,
            base_wait_time=1,
        )  # No max_retries specified
        num_attempts = _DEFAULT_MAX_RETRIES + 1

        # Simulate: Error * (_DEFAULT_MAX_RETRIES + 1) # noqa: ERA001
        self.mock_provider.generate.side_effect = [retriable_error] * num_attempts

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == num_attempts
        assert result.finish_reason == "Retry attempts exceeded"
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.request_count == num_attempts
        self.mock_sleeper.assert_has_calls([call(w) for w in wait_times])
        assert self.mock_sleeper.call_count == _DEFAULT_MAX_RETRIES
        self.mock_provider.append_history.assert_not_called()
        # Check warnings: num_attempts errors raised -> num_attempts error warnings displayed.
        # Then 1 final warning about exceeding retries.
        expected_warnings = [call(retriable_error)] * num_attempts
        self.mock_ui.display_warning.assert_has_calls(
            expected_warnings,
            any_order=False,
        )
        assert self.mock_ui.display_warning.call_count == num_attempts
        self.mock_ui.display_error.assert_has_calls(
            [call("Failed: Retry attempts exceeded")],
            any_order=False,
        )
        assert self.mock_ui.display_error.call_count == 1

    def test_tool_call_displays_success(self) -> None:
        """Test that a successful tool call displays the result correctly."""
        # Arrange
        tool_result_content = ToolCallResult(
            success=True,
            output=ToolOutput(type="text", content="Sunny"),
        )
        self.mock_tools.call_tool.return_value = (
            tool_result_content  # Mock the tool execution
        )
        tool_call = ContentPartToolCall(
            tool_id="tool1",
            name="get_weather",
            arguments={"location": "London"},
        )
        tool_result_part = ContentPartToolResult(
            tool_id="tool1",
            name="get_weather",
            content=tool_result_content,
        )

        # Simulate: LLM calls tool, then finishes
        self.mock_provider.generate.side_effect = [
            iter(
                [  # First call: returns tool call
                    tool_call,
                    ContentPartUsage(prompt_tokens=10, response_tokens=5),
                    # No finish reason yet
                ],
            ),
            iter(
                [  # Second call: finishes
                    ContentPartText(text="Final Answer"),
                    ContentPartUsage(prompt_tokens=15, response_tokens=3),
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.mock_ui.display_tool_call.assert_called_once_with(tool_call)
        self.mock_ui.display_tool_result.assert_called_once_with(tool_result_part)
        self.mock_ui.display_tool_error.assert_not_called()
        assert result.input_tokens == 10 + 15
        assert result.output_tokens == 5 + 3

    def test_tool_call_with_finish_reason_continues_the_loop(self) -> None:
        """Test that a successful tool call displays the result correctly."""
        # Arrange
        tool_result_content = ToolCallResult(
            success=True,
            output=ToolOutput(type="text", content="Sunny"),
        )
        self.mock_tools.call_tool.return_value = (
            tool_result_content  # Mock the tool execution
        )
        tool_call = ContentPartToolCall(
            tool_id="tool1",
            name="get_weather",
            arguments={"location": "London"},
        )

        # Simulate: LLM calls tool, then finishes
        self.mock_provider.generate.side_effect = [
            iter(
                [  # First call: returns tool call
                    tool_call,
                    ContentPartUsage(prompt_tokens=10, response_tokens=5),
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
            iter(
                [  # Second call: finishes
                    ContentPartText(text="Final Answer"),
                    ContentPartUsage(prompt_tokens=15, response_tokens=3),
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.mock_ui.display_tool_call.assert_called_once_with(tool_call)
        assert result.input_tokens == 10 + 15
        assert result.output_tokens == 5 + 3

    def test_tool_call_displays_failure(self) -> None:
        """Test that a failed tool call displays the error correctly."""
        # Arrange
        tool_error_output = ToolOutput(type="error", content="API Key Invalid")
        tool_result_content = ToolCallResult(
            success=False,  # Changed to failure=False, assuming success=False is the indicator
            output=tool_error_output,
        )
        self.mock_tools.call_tool.return_value = tool_result_content
        tool_call = ContentPartToolCall(
            tool_id="tool1",
            name="get_weather",
            arguments={"location": "InvalidCity"},
        )
        tool_result_part = ContentPartToolResult(
            tool_id="tool1",
            name="get_weather",
            content=tool_result_content,
        )

        # Simulate: LLM calls tool (which fails), then finishes based on the error
        self.mock_provider.generate.side_effect = [
            iter(
                [  # First call: returns tool call
                    tool_call,
                    ContentPartUsage(prompt_tokens=10, response_tokens=5),
                    # No finish reason yet
                ],
            ),
            iter(
                [  # Second call: finishes (maybe AI reports the error)
                    ContentPartText(text="Tool failed: API Key Invalid"),
                    ContentPartUsage(prompt_tokens=15, response_tokens=6),
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.mock_ui.display_tool_call.assert_called_once_with(tool_call)
        self.mock_ui.display_tool_error.assert_called_once_with(tool_result_part)
        self.mock_ui.display_tool_result.assert_not_called()
        assert result.input_tokens == 10 + 15  # Sum of tokens from both calls
        assert result.output_tokens == 5 + 6  # Sum of tokens from both calls

    def test_tool_call_continues_thinking(self) -> None:
        """Test that a tool call triggers another generate cycle."""
        # Arrange
        tool_call = ContentPartToolCall(
            tool_id="tool1",
            name="get_weather",
            arguments={"location": "London"},
        )
        tool_output = ToolOutput(type="text", content="Sunny")
        tool_result_content = ToolCallResult(success=True, output=tool_output)
        tool_result_part = ContentPartToolResult(
            tool_id="tool1",
            name="get_weather",
            content=tool_result_content,
        )

        # Simulate: Tool Call -> Tool Result Sent -> Final Text Response
        self.mock_provider.generate.side_effect = [
            # First call: returns tool call and usage
            iter(
                [
                    tool_call,
                    ContentPartUsage(prompt_tokens=10, response_tokens=5),
                    # NO finish reason initially
                ],
            ),
            # Second call: returns final text and finish reason
            iter(
                [
                    ContentPartText(text="The weather is Sunny."),
                    ContentPartUsage(
                        prompt_tokens=20,
                        response_tokens=8,
                    ),  # Tokens from second call
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
        ]
        self.mock_tools.call_tool.return_value = (
            tool_result_content  # Mock the tool execution
        )

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 2
        self.mock_tools.call_tool.assert_called_once_with(tool_call)
        assert result.finish_reason == "stop"
        assert result.input_tokens == 10 + 20  # Sum of tokens from both calls
        assert result.output_tokens == 5 + 8
        assert result.request_count == 2
        self.mock_sleeper.assert_not_called()  # No errors, no sleep
        # Check history updates (two turns added)
        assert self.mock_provider.append_history.call_count == 2
        # Call 1: Model (tool call), Tool (result)
        provider_history_arg1, turn1 = self.mock_provider.append_history.call_args_list[
            0
        ][0]
        assert len(turn1) == 2
        assert turn1[0].role == Role.MODEL
        assert turn1[0].content == [tool_call]
        assert turn1[1].role == Role.TOOL
        assert turn1[1].content == [tool_result_part]  # Check the wrapper part
        # Call 2: Model (text)
        provider_history_arg2, turn2 = self.mock_provider.append_history.call_args_list[
            1
        ][0]
        assert len(turn2) == 1
        assert turn2[0].role == Role.MODEL
        assert isinstance(turn2[0].content[0], ContentPartText)
        assert turn2[0].content[0].text == "The weather is Sunny."

    def test_no_finish_reason_continues_thinking(self) -> None:
        """Test that lack of finish reason triggers another generate cycle."""
        # Arrange
        # Simulate: Text -> Text (no finish reason) -> Text + Finish Reason
        self.mock_provider.generate.side_effect = [
            iter(
                [
                    ContentPartText(text="Thinking..."),
                    ContentPartUsage(prompt_tokens=5, response_tokens=2),
                    # NO finish reason
                ],
            ),
            iter(
                [
                    ContentPartText(text="Still thinking..."),
                    ContentPartUsage(prompt_tokens=6, response_tokens=3),
                    # NO finish reason
                ],
            ),
            iter(
                [
                    ContentPartText(text="Done."),
                    ContentPartUsage(prompt_tokens=7, response_tokens=4),
                    ContentPartFinishReason(finish_reason="stop"),
                ],
            ),
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 3
        assert result.finish_reason == "stop"
        assert result.input_tokens == 5 + 6 + 7
        assert result.output_tokens == 2 + 3 + 4
        assert result.request_count == 3
        self.mock_sleeper.assert_not_called()
        # Check history updates (three turns added)
        assert self.mock_provider.append_history.call_count == 3
        # Ensure history is appended correctly across turns
        # Turn 1
        _, turn1_messages = self.mock_provider.append_history.call_args_list[0][0]
        assert len(turn1_messages) == 1
        assert turn1_messages[0].role == Role.MODEL
        assert turn1_messages[0].content[0].text == "Thinking..."
        # Turn 2
        _, turn2_messages = self.mock_provider.append_history.call_args_list[1][0]
        assert len(turn2_messages) == 1
        assert turn2_messages[0].role == Role.MODEL
        assert turn2_messages[0].content[0].text == "Still thinking..."
        # Turn 3
        _, turn3_messages = self.mock_provider.append_history.call_args_list[2][0]
        assert len(turn3_messages) == 1
        assert turn3_messages[0].role == Role.MODEL
        assert turn3_messages[0].content[0].text == "Done."

    def test_no_output_or_finish_reason_retries_default_times(self) -> None:
        """Test empty response with no reason retries _DEFAULT_MAX_RETRIES times."""
        # Arrange
        num_attempts = _EMPTY_RESPONSE_MAX_RETRIES + 1
        # Simulate: Empty -> Empty -> Empty -> Empty (exceeds default retries)
        self.mock_provider.generate.side_effect = [iter([])] * num_attempts

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == num_attempts
        assert result.finish_reason == "No result"
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.request_count == num_attempts
        # Expect sleeps with the hardcoded wait time
        self.mock_sleeper.assert_has_calls([call(10)] * _EMPTY_RESPONSE_MAX_RETRIES)
        assert self.mock_sleeper.call_count == _EMPTY_RESPONSE_MAX_RETRIES
        self.mock_provider.append_history.assert_not_called()  # No content generated, no history update
        # Check warnings: _EMPTY_RESPONSE_MAX_RETRIES for retrying, one for exceeding retries
        expected_warnings = [
            call("No output generated by provider, retrying."),
        ] * _EMPTY_RESPONSE_MAX_RETRIES
        self.mock_ui.display_warning.assert_has_calls(expected_warnings)
        assert self.mock_ui.display_warning.call_count == _EMPTY_RESPONSE_MAX_RETRIES
        expected_errors = [call("Failed: No result")]
        self.mock_ui.display_error.assert_has_calls(expected_errors)
        assert self.mock_ui.display_error.call_count == 1

    def test_no_output_but_text_then_retry_saves_text(self) -> None:
        """Test text is saved even if a retry happens due to no finish reason later."""
        # Arrange
        # Simulate: Text (no finish) -> Empty -> Empty -> Empty -> Empty (failure)
        num_empty_attempts = _EMPTY_RESPONSE_MAX_RETRIES + 1
        # We need enough iterables for the initial text call + all empty attempts
        side_effects = [
            iter(
                [
                    ContentPartText(text="Some text"),
                    ContentPartUsage(prompt_tokens=1, response_tokens=1),
                ],
            ),  # Call 1: Text, no finish
        ]
        side_effects.extend(
            [iter([])] * num_empty_attempts,
        )  # Add empty iterators for subsequent calls

        self.mock_provider.generate.side_effect = side_effects

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        # Expected calls: 1 (text) + num_empty_attempts = 1 + 4 = 5
        total_calls = 1 + num_empty_attempts
        assert self.mock_provider.generate.call_count == total_calls

        assert (
            result.finish_reason == "No result"
        )  # Exits due to retry limit for empty responses
        assert result.input_tokens == 1  # Tokens from first call only
        assert result.output_tokens == 1
        assert result.request_count == total_calls  # 5 requests total
        # Check history update - only the first message should be appended
        self.mock_provider.append_history.assert_called_once()
        _, turn1 = self.mock_provider.append_history.call_args[0]
        assert len(turn1) == 1
        assert turn1[0].role == Role.MODEL
        assert isinstance(turn1[0].content[0], ContentPartText)
        assert turn1[0].content[0].text == "Some text"
        # Check sleeps for empty responses
        self.mock_sleeper.assert_has_calls([call(10)] * _EMPTY_RESPONSE_MAX_RETRIES)
        assert self.mock_sleeper.call_count == _EMPTY_RESPONSE_MAX_RETRIES
        # Check warnings
        expected_warnings = [
            call("No output generated by provider, retrying."),
        ] * _EMPTY_RESPONSE_MAX_RETRIES
        self.mock_ui.display_warning.assert_has_calls(expected_warnings)
        assert self.mock_ui.display_warning.call_count == _EMPTY_RESPONSE_MAX_RETRIES
        # Check errors
        expected_errors = [call("Failed: No result")]
        self.mock_ui.display_error.assert_has_calls(expected_errors)
        assert self.mock_ui.display_error.call_count == len(expected_errors)

    def test_keyboard_interrupt_during_generation(self) -> None:
        """Test KeyboardInterrupt during LLM generation."""
        # Arrange
        the_error = KeyboardInterrupt()
        # Simulate interrupt after partial text
        self.mock_provider.generate.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 1
        assert result.finish_reason == "User interrupted"
        assert result.input_tokens == 0  # No usage info received before interrupt
        assert result.output_tokens == 0
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        # History should NOT be updated as the generation turn didn't complete successfully
        self.mock_provider.append_history.assert_not_called()
        self.mock_ui.display_info.assert_called_once_with(
            "Interrupted: User interrupted",
        )

    def test_keyboard_interrupt_during_tool_execution(self) -> None:
        """Test KeyboardInterrupt during the tool execution loop."""
        # Arrange
        the_error = KeyboardInterrupt()
        tool_call = ContentPartToolCall(
            tool_id="tool1",
            name="long_running_tool",
            arguments={},
        )
        # Simulate: Generate returns tool call -> tool call execution raises interrupt
        self.mock_provider.generate.return_value = iter(
            [
                tool_call,
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                # No finish reason, expecting tool execution
            ],
        )
        self.mock_tools.call_tool.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 1
        self.mock_tools.call_tool.assert_called_once_with(tool_call)
        assert result.finish_reason == "User interrupted"
        # Tokens from the generate call *before* the interrupt occurred are counted
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        # History should NOT be updated as the tool execution turn didn't complete
        self.mock_provider.append_history.assert_not_called()
        self.mock_ui.display_info.assert_called_once_with(
            "Interrupted: User interrupted",
        )

    def test_non_retriable_error_in_generate_stops_thinking(self) -> None:
        """Test that a non-RetriableError during generate stops the loop."""
        # Arrange
        error_message = "Fatal generation error!"
        the_error = ValueError(error_message)
        self.mock_provider.generate.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 1
        assert result.finish_reason == error_message
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        self.mock_provider.append_history.assert_not_called()  # Failed turn not added
        self.mock_ui.display_error.assert_called_once_with(f"Failed: {error_message}")

    def test_non_retriable_error_in_tool_call_stops_thinking(self) -> None:
        """Test that a non-RetriableError during tool call stops the loop."""
        # Arrange
        error_message = "Fatal tool error!"
        the_error = ValueError(error_message)
        tool_call = ContentPartToolCall(tool_id="tool1", name="bad_tool", arguments={})
        # Simulate: Generate returns tool call -> tool call raises error
        self.mock_provider.generate.return_value = iter(
            [
                tool_call,
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                # No finish reason here, tool call implies continuation
            ],
        )
        self.mock_tools.call_tool.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert self.mock_provider.generate.call_count == 1
        self.mock_tools.call_tool.assert_called_once_with(tool_call)
        assert result.finish_reason == error_message
        # Tokens from the generate call *before* the tool error occurred are still counted
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        # History should not be updated because the turn (tool call + result) failed mid-way
        self.mock_provider.append_history.assert_not_called()
        self.mock_ui.display_error.assert_called_once_with(f"Failed: {error_message}")

    def test_error_after_successful_turn_preserves_history(self) -> None:
        """Test history is preserved from successful turns before a failure."""
        # Arrange
        error_message = "Failed on second turn"
        the_error = ValueError(error_message)

        # Simulate: Success (no finish reason) -> Error
        self.mock_provider.generate.side_effect = [
            iter(
                [
                    ContentPartText(text="First turn success."),
                    ContentPartUsage(prompt_tokens=10, response_tokens=5),
                    # NO finish reason - forces loop continuation
                ],
            ),
            the_error,
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        assert (
            self.mock_provider.generate.call_count == 2
        )  # First success, second error
        assert result.finish_reason == error_message
        assert result.input_tokens == 10  # Tokens from the first successful call
        assert result.output_tokens == 5
        assert result.request_count == 2  # One success, one failure
        self.mock_sleeper.assert_not_called()
        # Check history: Only the first successful turn should be appended
        self.mock_provider.append_history.assert_called_once()
        _, turn_arg = self.mock_provider.append_history.call_args[0]
        assert len(turn_arg) == 1
        assert turn_arg[0].role == Role.MODEL
        assert isinstance(turn_arg[0].content[0], ContentPartText)
        assert turn_arg[0].content[0].text == "First turn success."
        self.mock_ui.display_error.assert_called_once_with(f"Failed: {the_error}")


if __name__ == "__main__":
    unittest.main()
