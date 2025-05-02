import unittest
import uuid
from unittest.mock import MagicMock, call, patch

import litellm

# Assuming these imports work based on project structure
from streetrace.history import (
    History,
    Role,
)
from streetrace.interaction_manager import (
    _EMPTY_RESPONSE_MAX_RETRIES,
    InteractionManager,
    ThinkingResult,
)

# Removed ToolDescription from this import
from streetrace.tools.tool_call_result import ToolCallResult, ToolOutput
from streetrace.tools.tools import ToolCall
from streetrace.ui.console_ui import ConsoleUI

_FAKE_MODEL = "fake model"


class FakeMessageBuilder:
    """Fake message builder for testing."""

    message: dict[str, any]
    tool_calls: dict[str, dict[str, any]]

    def __init__(self, role: str, content: str) -> None:
        self.message = {
            "id": "test-" + str(uuid.uuid4()),
            "created": 1746140430,
            "model": _FAKE_MODEL,
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "content": content,
                        "role": role,
                    },
                    "finish_reason": "",
                },
            ],
        }
        self.tool_calls = {}

    def with_finish_reason(self, finish_reason: str) -> "FakeMessageBuilder":
        """Set the finish reason for the message."""
        self.message["choices"][0]["finish_reason"] = finish_reason
        return self

    def with_tool_call(self, name: str, args: dict[str, str]) -> "FakeMessageBuilder":
        """Set the tool call for the message."""
        tool_call_id = f"tool_call_{len(self.tool_calls)}"
        tool_call = {
            "type": "function",
            "id": tool_call_id,
            "function": {
                "name": name,
                "arguments": args,
            },
        }
        self.tool_calls[tool_call_id] = (
            litellm.ChatCompletionMessageToolCall.model_validate(
                tool_call,
            )
        )
        if self.message["choices"][0]["message"].get("tool_calls") is None:
            self.message["choices"][0]["message"]["tool_calls"] = []
        self.message["choices"][0]["message"]["tool_calls"].append(tool_call)
        return self

    def with_usage(
        self,
        prompt_tokens: int,
        response_tokens: int,
    ) -> "FakeMessageBuilder":
        """Set the usage for the message."""
        self.message["usage"] = {
            "completion_tokens": response_tokens,
            "prompt_tokens": prompt_tokens,
            "total_tokens": prompt_tokens + response_tokens,
            "completion_tokens_details": None,
            "prompt_tokens_details": {
                "audio_tokens": None,
                "cached_tokens": 0,
            },
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        return self

    def response_message(self) -> litellm.Message:
        """Convert the message to a litellm litellm.Message."""
        return litellm.ModelResponse.model_validate(self.message)


@patch("litellm.completion")
class TestInteractionManager(unittest.TestCase):

    def setUp(self) -> None:
        """Set up test fixtures, mock dependencies."""
        # ToolCall needs 'tools' and 'tools_impl' attributes in the spec
        # We can mock the spec_set to include these, or just mock the instance directly
        # Mocking the instance is simpler here as we don't need strict spec checking for the mock itself.
        self.mock_tools = MagicMock(spec=ToolCall)  # Removed spec=ToolCall
        self.mock_tools.tools = (
            []
        )  # Provide the 'tools' attribute expected by InteractionManager
        self.mock_ui = MagicMock(spec=ConsoleUI)
        self.mock_sleeper = MagicMock()
        self.mock_status = MagicMock()
        self.mock_ui.status.return_value.__enter__.return_value = (
            self.mock_status
        )  # Mock the context manager

        self.manager = InteractionManager(
            ui=self.mock_ui,
            sleeper=self.mock_sleeper,  # Inject the mock sleeper
        )

        self.history = History(system_message="System Prompt")
        # Add initial user message to the history's conversation list
        self.history.messages.append(
            litellm.Message(role=Role.USER.value, content="User Prompt"),
        )

    def test_system_message_is_processed(self, mock_completion) -> None:
        """Test that a successful run returns a ThinkingResult with correct stats."""
        # Arrange
        _system_message = "System Prompt"
        _user_message = "User Prompt"
        history = History(system_message=_system_message)
        # Add initial user message to the history's conversation list
        history.messages.append(
            litellm.Message(role=Role.USER, content=_user_message),
        )

        # Act
        _ = self.manager.process_prompt(_FAKE_MODEL, history, self.mock_tools)

        mock_completion.assert_called_once()

        args, kwargs = mock_completion.call_args

        assert len(kwargs["messages"]) == 2
        assert "messages" in kwargs
        assert kwargs["messages"][0]["role"] == Role.SYSTEM
        assert kwargs["messages"][0]["content"] == _system_message
        assert kwargs["messages"][1]["role"] == Role.USER
        assert kwargs["messages"][1]["content"] == _user_message

    def test_context_message_is_processed(self, mock_completion) -> None:
        """Test that a successful run returns a ThinkingResult with correct stats."""
        # Arrange
        _context_message = "Context Prompt"
        _user_message = "User Prompt"
        history = History(context=_context_message)
        # Add initial user message to the history's conversation list
        history.messages.append(
            litellm.Message(role=Role.USER, content=_user_message),
        )

        # Act
        _ = self.manager.process_prompt(_FAKE_MODEL, history, self.mock_tools)

        mock_completion.assert_called_once()

        args, kwargs = mock_completion.call_args

        assert len(kwargs["messages"]) == 2
        assert "messages" in kwargs
        assert kwargs["messages"][0]["role"] == Role.CONTEXT
        assert kwargs["messages"][0]["content"] == _context_message
        assert kwargs["messages"][1]["role"] == Role.USER
        assert kwargs["messages"][1]["content"] == _user_message

    def test_successful_completion_returns_thinking_result(
        self,
        mock_completion,
    ) -> None:
        """Test that a successful run returns a ThinkingResult with correct stats."""
        # Arrange
        mock_completion.return_value = (
            FakeMessageBuilder("assistant", "Hello!")
            .with_finish_reason("stop")
            .with_usage(13, 43)
            .response_message()
        )

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert isinstance(result, ThinkingResult)
        assert result.finish_reason == "stop"
        assert result.input_tokens == 13
        assert result.output_tokens == 43
        assert result.request_count == 1
        mock_completion.assert_called_once()
        self.mock_sleeper.assert_not_called()  # No retries, no sleep

        assert len(self.history.messages) == 2

    def test_tool_call_displays_success(self, mock_completion) -> None:
        """Test that a successful tool call displays the result correctly."""
        # Arrange
        tool_result_content = ToolCallResult(
            success=True,
            output=ToolOutput(type="text", content="Sunny"),
        )
        self.mock_tools.call_tool.return_value = (
            tool_result_content  # Mock the tool execution
        )

        tool_call_builder = (
            FakeMessageBuilder("assistant", "Hello!")
            .with_finish_reason("tool_call")
            .with_usage(13, 43)
            .with_tool_call("get_weather", {"location": "London"})
        )

        mock_completion.side_effect = [
            tool_call_builder.response_message(),
            FakeMessageBuilder("assistant", "Sunny")
            .with_finish_reason("stop")
            .with_usage(15, 10)
            .response_message(),
        ]

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        self.mock_ui.display_tool_call.assert_called_once_with(
            next(iter(tool_call_builder.tool_calls.values())),
        )
        self.mock_ui.display_tool_result.assert_called_once_with("get_weather", tool_result_content)
        self.mock_ui.display_tool_error.assert_not_called()
        assert result.input_tokens == 13 + 15
        assert result.output_tokens == 43 + 10

    def test_tool_call_with_finish_reason_continues_the_loop(
        self,
        mock_completion,
    ) -> None:
        """Test that a successful tool call displays the result correctly.

        This test is identical to test_tool_call_displays_success with the difference
        being the finish_reason of the first message: "stop" vs "tool_call".
        Just in case we decide to handle finish_reasons in the state machine (we shouldn't).
        """
        # Arrange
        tool_result_content = ToolCallResult(
            success=True,
            output=ToolOutput(type="text", content="Sunny"),
        )
        self.mock_tools.call_tool.return_value = (
            tool_result_content  # Mock the tool execution
        )

        tool_call_builder = (
            FakeMessageBuilder("assistant", "Hello!")
            .with_finish_reason(
                "stop",
            )  # Finish reason = "stop", while there are tool calls
            .with_usage(13, 43)
            .with_tool_call("get_weather", {"location": "London"})
        )

        mock_completion.side_effect = [
            tool_call_builder.response_message(),
            FakeMessageBuilder("assistant", "Sunny")
            .with_finish_reason("stop")
            .with_usage(15, 10)
            .response_message(),
        ]

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        self.mock_ui.display_tool_call.assert_called_once_with(
            next(iter(tool_call_builder.tool_calls.values())),
        )
        assert result.input_tokens == 13 + 15
        assert result.output_tokens == 43 + 10

    def test_tool_call_displays_failure(self, mock_completion) -> None:
        """Test that a failed tool call displays the error correctly."""
        # Arrange
        tool_error_output = ToolOutput(type="error", content="API Key Invalid")
        tool_result_content = ToolCallResult(
            success=False,  # Changed to failure=False, assuming success=False is the indicator
            output=tool_error_output,
        )
        self.mock_tools.call_tool.return_value = (
            tool_result_content  # Mock the tool execution
        )

        tool_call_builder = (
            FakeMessageBuilder("assistant", "Hello!")
            .with_usage(10, 15)
            .with_tool_call("get_weather", {"location": "InvalidCity"})
        )

        mock_completion.side_effect = [
            tool_call_builder.response_message(),
            FakeMessageBuilder("assistant", "Tool failed: API Key Invalid")
            .with_finish_reason("stop")
            .with_usage(12, 6)
            .response_message(),
        ]

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        self.mock_ui.display_tool_call.assert_called_once_with(
            next(iter(tool_call_builder.tool_calls.values())),
        )
        self.mock_ui.display_tool_error.assert_called_once_with("get_weather", tool_result_content)
        self.mock_ui.display_tool_result.assert_not_called()
        assert result.input_tokens == 10 + 12  # Sum of tokens from both calls
        assert result.output_tokens == 15 + 6  # Sum of tokens from both calls

    def test_no_finish_reason_continues_thinking(self, mock_completion) -> None:
        """Test that lack of finish reason triggers another generate cycle."""
        # Arrange
        # Simulate: Text -> Text (no finish reason) -> Text + Finish Reason

        mock_completion.side_effect = [
            FakeMessageBuilder("assistant", "Thinking...")
            .with_usage(5, 2)
            .response_message(),
            FakeMessageBuilder("assistant", "Still thinking...")
            .with_usage(6, 3)
            .response_message(),
            FakeMessageBuilder("assistant", "Done.")
            .with_finish_reason("stop")
            .with_usage(7, 4)
            .response_message(),
        ]

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == 3
        assert result.finish_reason == "stop"
        assert result.input_tokens == 5 + 6 + 7
        assert result.output_tokens == 2 + 3 + 4
        assert result.request_count == 3
        self.mock_sleeper.assert_not_called()
        # Ensure history is appended correctly across turns
        # Turn 1
        turn1_message = self.history.messages[1]
        assert turn1_message.content == "Thinking..."
        assert turn1_message.role == "assistant"
        # Turn 2
        turn2_message = self.history.messages[2]
        assert turn2_message.content == "Still thinking..."
        assert turn2_message.role == "assistant"
        # Turn 3
        turn3_message = self.history.messages[3]
        assert turn3_message.content == "Done."
        assert turn3_message.role == "assistant"

    def test_no_output_or_finish_reason_retries_default_times(
        self,
        mock_completion,
    ) -> None:
        """Test empty response with no reason retries _EMPTY_RESPONSE_MAX_RETRIES times."""
        # Arrange
        num_attempts = _EMPTY_RESPONSE_MAX_RETRIES + 1
        mock_completion.side_effect = [
            FakeMessageBuilder("assistant", "").response_message(),
        ] * num_attempts

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == num_attempts
        assert result.finish_reason == "No result"
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.request_count == num_attempts
        # Expect sleeps with the hardcoded wait time
        self.mock_sleeper.assert_has_calls([call(10)] * _EMPTY_RESPONSE_MAX_RETRIES)
        assert self.mock_sleeper.call_count == _EMPTY_RESPONSE_MAX_RETRIES
        # Check warnings: _EMPTY_RESPONSE_MAX_RETRIES for retrying, one for exceeding retries
        expected_warnings = [
            call("No output generated by provider, retrying."),
        ] * _EMPTY_RESPONSE_MAX_RETRIES
        self.mock_ui.display_warning.assert_has_calls(expected_warnings)
        assert self.mock_ui.display_warning.call_count == _EMPTY_RESPONSE_MAX_RETRIES
        expected_errors = [call("Failed: No result")]
        self.mock_ui.display_error.assert_has_calls(expected_errors)
        assert self.mock_ui.display_error.call_count == 1

    def test_no_output_but_text_then_retry_saves_text(self, mock_completion) -> None:
        """Test text is saved even if a retry happens due to no finish reason later."""
        # Arrange
        # Simulate: Text (no finish) -> Empty -> Empty -> Empty -> Empty (failure)
        num_attempts = _EMPTY_RESPONSE_MAX_RETRIES + 1
        # We need enough iterables for the initial text call + all empty attempts
        side_effects = [
            FakeMessageBuilder("assistant", "Some text")
            .with_usage(1, 1)
            .response_message(),
        ]
        side_effects.extend(
            [FakeMessageBuilder("assistant", "").response_message()] * num_attempts,
        )  # Add empty iterators for subsequent calls
        mock_completion.side_effect = side_effects

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        # Expected calls: 1 (text) + num_empty_attempts = 1 + 4 = 5
        total_calls = 1 + num_attempts
        assert mock_completion.call_count == total_calls

        assert (
            result.finish_reason == "No result"
        )  # Exits due to retry limit for empty responses
        assert result.input_tokens == 1  # Tokens from first call only
        assert result.output_tokens == 1
        assert result.request_count == total_calls  # 5 requests total
        # Check history update - only the first message should be appended
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

    def test_keyboard_interrupt_during_generation(self, mock_completion) -> None:
        """Test KeyboardInterrupt during LLM generation."""
        # Arrange
        the_error = KeyboardInterrupt()
        # Simulate interrupt after partial text
        mock_completion.side_effect = the_error

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == 1
        assert result.finish_reason == "User interrupted"
        assert result.input_tokens == 0  # No usage info received before interrupt
        assert result.output_tokens == 0
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        # History should NOT be updated as the generation turn didn't complete successfully
        self.mock_ui.display_info.assert_called_once_with(
            "Interrupted: User interrupted",
        )

    def test_keyboard_interrupt_during_tool_execution(self, mock_completion) -> None:
        """Test KeyboardInterrupt during the tool execution loop."""
        # Arrange
        the_error = KeyboardInterrupt()

        tool_call_builder = (
            FakeMessageBuilder("assistant", "Hello!")
            .with_finish_reason("tool_call")
            .with_usage(10, 5)
            .with_tool_call("get_weather", {"location": "London"})
        )

        mock_completion.side_effect = [
            tool_call_builder.response_message(),
            FakeMessageBuilder("assistant", "Sunny")
            .with_finish_reason("stop")
            .with_usage(15, 10)
            .response_message(),
        ]

        self.mock_tools.call_tool.side_effect = the_error

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == 1
        self.mock_tools.call_tool.assert_called_once_with(
            next(iter(tool_call_builder.tool_calls.values())),
        )
        assert result.finish_reason == "User interrupted"
        # Tokens from the generate call *before* the interrupt occurred are counted
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        # History should NOT be updated as the tool execution turn didn't complete
        self.mock_ui.display_info.assert_called_once_with(
            "Interrupted: User interrupted",
        )

    def test_non_retriable_error_in_generate_stops_thinking(
        self,
        mock_completion,
    ) -> None:
        """Test that a non-RetriableError during generate stops the loop."""
        # Arrange
        error_message = "Fatal generation error!"
        the_error = ValueError(error_message)
        mock_completion.side_effect = the_error

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == 1
        assert result.finish_reason == error_message
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        self.mock_ui.display_error.assert_called_once_with(f"Failed: {error_message}")

    def test_non_retriable_error_in_tool_call_stops_thinking(
        self,
        mock_completion,
    ) -> None:
        """Test that a non-RetriableError during tool call stops the loop."""
        # Arrange
        error_message = "Fatal tool error!"
        the_error = ValueError(error_message)
        # Simulate: Generate returns tool call -> tool call raises error
        tool_call_builder = (
            FakeMessageBuilder("assistant", "Hello!")
            .with_finish_reason("tool_call")
            .with_usage(10, 5)
            .with_tool_call("bad_tool", {})
        )

        mock_completion.side_effect = [
            tool_call_builder.response_message(),
        ]
        self.mock_tools.call_tool.side_effect = the_error

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == 1
        self.mock_tools.call_tool.assert_called_once_with(
            next(iter(tool_call_builder.tool_calls.values())),
        )
        assert result.finish_reason == error_message
        # Tokens from the generate call *before* the tool error occurred are still counted
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.request_count == 1
        self.mock_sleeper.assert_not_called()
        # History should not be updated because the turn (tool call + result) failed mid-way
        self.mock_ui.display_error.assert_called_once_with(f"Failed: {error_message}")

    def test_error_after_successful_turn_preserves_history(
        self,
        mock_completion,
    ) -> None:
        """Test history is preserved from successful turns before a failure."""
        # Arrange
        error_message = "Failed on second turn"
        the_error = ValueError(error_message)

        # Simulate: Success (no finish reason) -> Error
        mock_completion.side_effect = [
            FakeMessageBuilder("assistant", "First turn success.").with_usage(10, 5)
            # NO finish reason - forces loop continuation
            .response_message(),
            the_error,
        ]

        # Act
        result = self.manager.process_prompt(_FAKE_MODEL, self.history, self.mock_tools)

        # Assert
        assert mock_completion.call_count == 2  # First success, second error
        assert result.finish_reason == error_message
        assert result.input_tokens == 10  # Tokens from the first successful call
        assert result.output_tokens == 5
        assert result.request_count == 2  # One success, one failure
        self.mock_sleeper.assert_not_called()
        # Check history: Only the first successful turn should be appended
        last_message = self.history.messages[-1]
        assert last_message.content == "First turn success."
        assert last_message.role == "assistant"
        self.mock_ui.display_error.assert_called_once_with(f"Failed: {the_error}")


if __name__ == "__main__":
    unittest.main()
