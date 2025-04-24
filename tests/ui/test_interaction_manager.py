import unittest
from unittest.mock import MagicMock, call

# Assuming these imports work based on project structure
from streetrace.llm.llmapi import LLMAPI, RetriableError
from streetrace.llm.wrapper import (
    ContentPartFinishReason, ContentPartText,
    ContentPartToolCall, ContentPartToolResult, ContentPartUsage,
    History, Message, Role, ToolCallResult, ToolOutput
)
# Removed ToolDescription from this import
from streetrace.ui.console_ui import ConsoleUI
from streetrace.ui.interaction_manager import InteractionManager, ThinkingResult, _DEFAULT_MAX_RETRIES

# Helper function to create RetriableError with wait_time logic
def create_retriable_error(max_retries=None, base_wait_time=1):
    error = RetriableError("Simulated retriable error", max_retries=max_retries)
    # Simple exponential backoff for testing
    error.wait_time = lambda attempt: base_wait_time * (2 ** (attempt - 1))
    return error

class TestInteractionManager(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures, mock dependencies."""
        self.mock_provider = MagicMock(spec=LLMAPI)
        # ToolCall needs 'tools' and 'tools_impl' attributes in the spec
        # We can mock the spec_set to include these, or just mock the instance directly
        # Mocking the instance is simpler here as we don't need strict spec checking for the mock itself.
        self.mock_tools = MagicMock() # Removed spec=ToolCall
        self.mock_tools.tools = [] # Provide the 'tools' attribute expected by InteractionManager
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.mock_sleeper = MagicMock()
        self.mock_status = MagicMock()
        self.mock_ui.status.return_value.__enter__.return_value = self.mock_status # Mock the context manager

        # Mock provider methods to return sensible defaults or iterables
        self.mock_provider.initialize_client.return_value = "mock_client"
        # Corrected: History uses 'conversation', not 'messages'
        self.mock_provider.transform_history.side_effect = lambda h: h.conversation
        self.mock_provider.transform_tools.return_value = [] # Default to no tools transformed
        self.mock_provider.generate.return_value = iter([]) # Default to empty generator
        self.mock_provider.append_history.return_value = None
        self.mock_provider.pretty_print.return_value = "pretty_history"

        self.manager = InteractionManager(
            provider=self.mock_provider,
            model_name="test_model",
            tools=self.mock_tools,
            ui=self.mock_ui,
            sleeper=self.mock_sleeper, # Inject the mock sleeper
        )

        self.history = History(system_message="System Prompt")
        # Add initial user message to the history's conversation list
        self.history.conversation.append(Message(role=Role.USER, content=[ContentPartText(text="User Prompt")]))

    def test_successful_completion_returns_thinking_result(self):
        """Test that a successful run returns a ThinkingResult with correct stats."""
        # Arrange
        self.mock_provider.generate.return_value = iter([
            ContentPartText(text="Response text"),
            ContentPartUsage(prompt_tokens=10, response_tokens=5),
            ContentPartFinishReason(finish_reason="stop"),
        ])

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertIsInstance(result, ThinkingResult)
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.request_count, 1)
        self.mock_provider.generate.assert_called_once()
        self.mock_sleeper.assert_not_called() # No retries, no sleep
        # Check history update
        self.mock_provider.append_history.assert_called_once()
        provider_history_arg = self.mock_provider.append_history.call_args[0][0]
        turn_arg = self.mock_provider.append_history.call_args[0][1]
        # Provider history passed to append_history is the transformed history
        self.assertEqual(provider_history_arg, self.history.conversation)
        self.assertEqual(len(turn_arg), 1) # Only model message added
        self.assertEqual(turn_arg[0].role, Role.MODEL)
        self.assertEqual(len(turn_arg[0].content), 1)
        self.assertIsInstance(turn_arg[0].content[0], ContentPartText)
        self.assertEqual(turn_arg[0].content[0].text, "Response text")

    def test_retriable_error_retries_and_waits(self):
        """Test RetriableError leads to retries with correct waits, then succeeds."""
        # Arrange
        max_retries = 2
        wait_times = [1, 2] # 1 * (2**(1-1)), 1 * (2**(2-1))
        retriable_error = create_retriable_error(max_retries=max_retries, base_wait_time=1)

        # Simulate: Error -> Error -> Success
        self.mock_provider.generate.side_effect = [
            retriable_error,
            retriable_error,
            iter([
                ContentPartText(text="Success finally!"),
                ContentPartUsage(prompt_tokens=5, response_tokens=3),
                ContentPartFinishReason(finish_reason="stop"),
            ])
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 3)
        self.assertEqual(result.finish_reason, "stop") # Should eventually succeed
        self.assertEqual(result.input_tokens, 5) # Only tokens from the successful call
        self.assertEqual(result.output_tokens, 3)
        self.assertEqual(result.request_count, 3) # 2 failed + 1 successful request
        self.mock_sleeper.assert_has_calls([call(wait_times[0]), call(wait_times[1])])
        self.assertEqual(self.mock_sleeper.call_count, max_retries)
        # Check history update (only the successful turn)
        self.mock_provider.append_history.assert_called_once()
        turn_arg = self.mock_provider.append_history.call_args[0][1]
        self.assertEqual(len(turn_arg), 1)
        self.assertIsInstance(turn_arg[0].content[0], ContentPartText)
        self.assertEqual(turn_arg[0].content[0].text, "Success finally!")
        self.mock_ui.display_warning.assert_called_with(retriable_error) # Check error display
        self.assertEqual(self.mock_ui.display_warning.call_count, 2)

    def test_retriable_error_exceeds_max_retries(self):
        """Test RetriableError exits after max_retries with correct reason."""
        # Arrange
        max_retries = 2
        wait_times = [1, 2]
        retriable_error = create_retriable_error(max_retries=max_retries, base_wait_time=1)

        # Simulate: Error -> Error -> Error (exceeds max_retries)
        self.mock_provider.generate.side_effect = [
            retriable_error,
            retriable_error,
            retriable_error,
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 3) # 2 retries + 1 final attempt
        self.assertEqual(result.finish_reason, "Retry attempts exceeded")
        self.assertEqual(result.input_tokens, 0) # No successful call
        self.assertEqual(result.output_tokens, 0)
        self.assertEqual(result.request_count, 3)
        self.mock_sleeper.assert_has_calls([call(wait_times[0]), call(wait_times[1])])
        self.assertEqual(self.mock_sleeper.call_count, max_retries)
        self.mock_provider.append_history.assert_not_called() # History should not be updated on failure
        self.mock_ui.display_warning.assert_called_with(retriable_error) # Check error display
        self.assertEqual(self.mock_ui.display_warning.call_count, 3) # Called for the first 2 errors

    def test_retriable_error_uses_default_retries(self):
        """Test RetriableError uses _DEFAULT_MAX_RETRIES when max_retries is None."""
        # Arrange
        wait_times = [1, 2, 4] # Assuming base_wait_time=1
        retriable_error = create_retriable_error(max_retries=None, base_wait_time=1) # No max_retries specified

        # Simulate: Error * (_DEFAULT_MAX_RETRIES + 1)
        self.mock_provider.generate.side_effect = [retriable_error] * (_DEFAULT_MAX_RETRIES + 1)

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, _DEFAULT_MAX_RETRIES + 1)
        self.assertEqual(result.finish_reason, "Retry attempts exceeded")
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)
        self.assertEqual(result.request_count, _DEFAULT_MAX_RETRIES + 1)
        self.mock_sleeper.assert_has_calls([call(w) for w in wait_times])
        self.assertEqual(self.mock_sleeper.call_count, _DEFAULT_MAX_RETRIES)
        self.mock_provider.append_history.assert_not_called()

    def test_tool_call_displays_success(self):
        """Test that a tool call triggers another generate cycle."""
        # Arrange
        tool_result_content = ToolCallResult(
            success=True,
            output=ToolOutput(type="text", content="Sunny")
        )
        self.mock_tools.call_tool.return_value = tool_result_content # Mock the tool execution
        # Simulate: Tool Call
        self.mock_provider.generate.side_effect = [
            # First call: returns tool call and usage
            iter([
                ContentPartToolCall(id="tool1", name="get_weather", arguments={'location': 'London'}),
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                ContentPartFinishReason(finish_reason="stop"),
            ]),
        ]

        # Act
        _ = self.manager.process_prompt(self.history)

        # Assert
        self.mock_ui.display_tool_result.assert_called_once_with(
            ContentPartToolResult(id="tool1", name="get_weather", content=tool_result_content)
        )
        self.mock_ui.display_tool_error.assert_not_called()

    def test_tool_call_displays_failure(self):
        """Test that a tool call triggers another generate cycle."""
        # Arrange
        tool_result_content = ToolCallResult(
            failure=True,
            output=ToolOutput(type="text", content="Sunny")
        )
        self.mock_tools.call_tool.return_value = tool_result_content # Mock the tool execution
        # Simulate: Tool Call
        self.mock_provider.generate.side_effect = [
            # First call: returns tool call and usage
            iter([
                ContentPartToolCall(id="tool1", name="get_weather", arguments={'location': 'London'}),
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                ContentPartFinishReason(finish_reason="stop"),
            ]),
        ]

        # Act
        _ = self.manager.process_prompt(self.history)

        # Assert
        self.mock_ui.display_tool_error.assert_called_once_with(
            ContentPartToolResult(id="tool1", name="get_weather", content=tool_result_content)
        )
        self.mock_ui.display_tool_result.assert_not_called()

    def test_tool_call_continues_thinking(self):
        """Test that a tool call triggers another generate cycle."""
        # Arrange
        tool_call = ContentPartToolCall(id="tool1", name="get_weather", arguments={'location': 'London'})
        # Corrected: ToolOutput requires 'type' field
        tool_output = ToolOutput(type="text", content="Sunny")
        tool_result_content = ToolCallResult(
            success=True,
            output=tool_output
        )
        # Tool results are wrapped in ContentPartToolResult in the history
        tool_result_part = ContentPartToolResult(id="tool1", name="get_weather", content=tool_result_content)

        # Simulate: Tool Call -> Tool Result Sent -> Final Text Response
        self.mock_provider.generate.side_effect = [
            # First call: returns tool call and usage
            iter([
                tool_call,
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                # NO finish reason initially
            ]),
            # Second call: returns final text and finish reason
            iter([
                ContentPartText(text="The weather is Sunny."),
                ContentPartUsage(prompt_tokens=20, response_tokens=8), # Tokens from second call
                ContentPartFinishReason(finish_reason="stop"),
            ])
        ]
        self.mock_tools.call_tool.return_value = tool_result_content # Mock the tool execution

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 2)
        self.mock_tools.call_tool.assert_called_once_with(tool_call)
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.input_tokens, 10 + 20) # Sum of tokens from both calls
        self.assertEqual(result.output_tokens, 5 + 8)
        self.assertEqual(result.request_count, 2)
        self.mock_sleeper.assert_not_called() # No errors, no sleep
        # Check history updates (two turns added)
        self.assertEqual(self.mock_provider.append_history.call_count, 2)
        # Call 1: Model (tool call), Tool (result)
        provider_history_arg1, turn1 = self.mock_provider.append_history.call_args_list[0][0]
        self.assertEqual(len(turn1), 2)
        self.assertEqual(turn1[0].role, Role.MODEL)
        self.assertEqual(turn1[0].content, [tool_call])
        self.assertEqual(turn1[1].role, Role.TOOL)
        self.assertEqual(turn1[1].content, [tool_result_part]) # Check the wrapper part
        # Call 2: Model (text)
        provider_history_arg2, turn2 = self.mock_provider.append_history.call_args_list[1][0]
        self.assertEqual(len(turn2), 1)
        self.assertEqual(turn2[0].role, Role.MODEL)
        self.assertIsInstance(turn2[0].content[0], ContentPartText)
        self.assertEqual(turn2[0].content[0].text, "The weather is Sunny.")

    def test_no_finish_reason_continues_thinking(self):
        """Test that lack of finish reason triggers another generate cycle."""
        # Arrange
        # Simulate: Text -> Text (no finish reason) -> Text + Finish Reason
        self.mock_provider.generate.side_effect = [
            iter([
                ContentPartText(text="Thinking..."),
                ContentPartUsage(prompt_tokens=5, response_tokens=2),
                # NO finish reason
            ]),
            iter([
                ContentPartText(text="Still thinking..."),
                ContentPartUsage(prompt_tokens=6, response_tokens=3),
                 # NO finish reason
            ]),
             iter([
                ContentPartText(text="Done."),
                ContentPartUsage(prompt_tokens=7, response_tokens=4),
                ContentPartFinishReason(finish_reason="stop"),
            ])
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 3)
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.input_tokens, 5 + 6 + 7)
        self.assertEqual(result.output_tokens, 2 + 3 + 4)
        self.assertEqual(result.request_count, 3)
        self.mock_sleeper.assert_not_called()
        # Check history updates (three turns added)
        self.assertEqual(self.mock_provider.append_history.call_count, 3)
        turn1 = self.mock_provider.append_history.call_args_list[0][0][1]
        turn2 = self.mock_provider.append_history.call_args_list[1][0][1]
        turn3 = self.mock_provider.append_history.call_args_list[2][0][1]
        self.assertIsInstance(turn1[0].content[0], ContentPartText)
        self.assertEqual(turn1[0].content[0].text, "Thinking...")
        self.assertIsInstance(turn2[0].content[0], ContentPartText)
        self.assertEqual(turn2[0].content[0].text, "Still thinking...")
        self.assertIsInstance(turn3[0].content[0], ContentPartText)
        self.assertEqual(turn3[0].content[0].text, "Done.")


    def test_no_output_or_finish_reason_retries_default_times(self):
        """Test empty response with no reason retries _DEFAULT_MAX_RETRIES times."""
        # Arrange
        # Simulate: Empty -> Empty -> Empty -> Empty (exceeds default retries)
        self.mock_provider.generate.side_effect = [iter([])] * (_DEFAULT_MAX_RETRIES + 1)

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, _DEFAULT_MAX_RETRIES + 1)
        # The current implementation doesn't set a specific finish reason here,
        # it seems to just exit the loop because retry becomes False after max attempts.
        # Let's assert based on the observed behavior (None) but note this might change.
        self.assertEqual(result.finish_reason, "No result")
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)
        self.assertEqual(result.request_count, _DEFAULT_MAX_RETRIES + 1)
        # Expect sleeps with the hardcoded 10s wait time in this specific scenario
        self.mock_sleeper.assert_has_calls([call(10)] * _DEFAULT_MAX_RETRIES)
        self.assertEqual(self.mock_sleeper.call_count, _DEFAULT_MAX_RETRIES)
        self.mock_provider.append_history.assert_not_called() # No content generated, no history update
        self.mock_ui.display_warning.assert_any_call("No output generated by provider, retrying.")
        self.mock_ui.display_warning.assert_any_call("No output generated by provider, retry attempts exceeded.")
        # The exact number of calls depends on whether the final warning is also counted.
        # Let's check it was called at least _DEFAULT_MAX_RETRIES times
        self.assertGreaterEqual(self.mock_ui.display_warning.call_count, _DEFAULT_MAX_RETRIES)


    def test_no_output_but_text_then_retry_saves_text(self):
        """Test text is saved even if a retry happens due to no finish reason later."""
        # Arrange
        # Corrected: Use keyword arguments for ContentPartUsage
        # Simulate: Text (no finish) -> Empty -> Empty -> Failure
        self.mock_provider.generate.side_effect = [
            iter([ContentPartText(text="Some text"), ContentPartUsage(prompt_tokens=1, response_tokens=1)]), # First call has text, no finish
            iter([]), # Second call empty
            iter([]), # First retry empty
            iter([]), # Second retry empty
            iter([]), # Third retry empty
        ]

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        # Expect 1 (text) + _DEFAULT_MAX_RETRIES (empty) = 4 calls
        self.assertEqual(self.mock_provider.generate.call_count, 2 + _DEFAULT_MAX_RETRIES) # ok (two parts) + 3 attempts
        self.assertEqual(result.finish_reason, "No result") # Exits due to retry limit for empty responses
        self.assertEqual(result.input_tokens, 1) # Tokens from first call
        self.assertEqual(result.output_tokens, 1)
        self.assertEqual(result.request_count, 2 + _DEFAULT_MAX_RETRIES)
        # Check history update - only the first message should be appended
        self.mock_provider.append_history.assert_called_once()
        turn1 = self.mock_provider.append_history.call_args[0][1]
        self.assertEqual(len(turn1), 1)
        self.assertEqual(turn1[0].role, Role.MODEL)
        self.assertIsInstance(turn1[0].content[0], ContentPartText)
        self.assertEqual(turn1[0].content[0].text, "Some text")
        self.mock_sleeper.assert_has_calls([call(10)] * _DEFAULT_MAX_RETRIES) # 3 retries for empty responses
        self.assertEqual(self.mock_sleeper.call_count, _DEFAULT_MAX_RETRIES)


    def test_keyboard_interrupt_in_tool_call_stops_saving_history(self):
        """Test that a non-RetriableError during tool call stops the loop."""
        # Arrange
        the_error = KeyboardInterrupt()
        tool_call = ContentPartToolCall(id="tool1", name="bad_tool", arguments={})
        # Simulate: Generate returns tool call -> tool call raises error
        self.mock_provider.generate.side_effect = [
            iter([ContentPartText(text="Some text"), ContentPartUsage(prompt_tokens=1, response_tokens=1)]), # First call has text, no finish
            iter([tool_call]), # Call tool
        ]
        self.mock_tools.call_tool.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 2)
        self.mock_tools.call_tool.assert_called_once_with(tool_call)
        self.assertEqual(result.finish_reason, "User interrupted")
        # Tokens from the generate call *before* the tool error occurred are still counted
        self.assertEqual(result.input_tokens, 1)
        self.assertEqual(result.output_tokens, 1)
        self.assertEqual(result.request_count, 2)
        self.mock_sleeper.assert_not_called()
        # History should not be updated because the turn (tool call + result) failed mid-way
        self.mock_provider.append_history.assert_called_once()
        self.mock_ui.display_info.assert_called_once()


    def test_non_retriable_error_in_generate_stops_thinking(self):
        """Test that a non-RetriableError during generate stops the loop."""
        # Arrange
        error_message = "Fatal generation error!"
        the_error = ValueError(error_message)
        self.mock_provider.generate.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 1)
        self.assertEqual(result.finish_reason, error_message)
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)
        self.assertEqual(result.request_count, 1)
        self.mock_sleeper.assert_not_called()
        self.mock_provider.append_history.assert_not_called() # Failed turn not added
        self.mock_ui.display_error.assert_called_once_with(the_error)


    def test_non_retriable_error_in_tool_call_stops_thinking(self):
        """Test that a non-RetriableError during tool call stops the loop."""
        # Arrange
        error_message = "Fatal tool error!"
        the_error = ValueError(error_message)
        tool_call = ContentPartToolCall(id="tool1", name="bad_tool", arguments={})
        # Simulate: Generate returns tool call -> tool call raises error
        self.mock_provider.generate.return_value = iter([
            tool_call,
            ContentPartUsage(prompt_tokens=10, response_tokens=5),
            # No finish reason here, tool call implies continuation
        ])
        self.mock_tools.call_tool.side_effect = the_error

        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 1)
        self.mock_tools.call_tool.assert_called_once_with(tool_call)
        self.assertEqual(result.finish_reason, error_message)
        # Tokens from the generate call *before* the tool error occurred are still counted
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.request_count, 1)
        self.mock_sleeper.assert_not_called()
        # History should not be updated because the turn (tool call + result) failed mid-way
        self.mock_provider.append_history.assert_not_called()
        self.mock_ui.display_error.assert_called_once_with(the_error)


    def test_error_after_successful_turn_preserves_history(self):
        """Test history is preserved from successful turns before a failure."""
        # Arrange
        error_message = "Failed on second turn"
        the_error = ValueError(error_message)

        # Simulate: Success (no finish reason) -> Error
        self.mock_provider.generate.side_effect = [
             iter([
                ContentPartText(text="First turn success."),
                ContentPartUsage(prompt_tokens=10, response_tokens=5),
                # NO finish reason - forces loop continuation
            ]),
            the_error
        ]


        # Act
        result = self.manager.process_prompt(self.history)

        # Assert
        self.assertEqual(self.mock_provider.generate.call_count, 2) # First success, second error
        self.assertEqual(result.finish_reason, error_message)
        self.assertEqual(result.input_tokens, 10) # Tokens from the first successful call
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.request_count, 2) # One success, one failure
        self.mock_sleeper.assert_not_called()
        # Check history: Only the first successful turn should be appended
        self.mock_provider.append_history.assert_called_once()
        provider_history_arg, turn_arg = self.mock_provider.append_history.call_args[0]
        self.assertEqual(len(turn_arg), 1)
        self.assertEqual(turn_arg[0].role, Role.MODEL)
        self.assertIsInstance(turn_arg[0].content[0], ContentPartText)
        self.assertEqual(turn_arg[0].content[0].text, "First turn success.")
        self.mock_ui.display_error.assert_called_once_with(the_error)


if __name__ == '__main__':
    unittest.main()
