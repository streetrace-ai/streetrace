"""Unit tests for Gemini history converter.

This module contains tests for the GeminiHistoryConverter class that converts
between Streetrace history and Gemini-specific formats.
"""

import unittest
from unittest.mock import MagicMock, patch

from streetrace.llm.gemini.converter import GeminiHistoryConverter
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Role,
    ToolCallResult,
    ToolOutput,
)


class TestGeminiHistoryConverter(unittest.TestCase):
    """Tests for GeminiHistoryConverter class."""

    def setUp(self):
        """Set up test fixtures."""
        # We need to patch the create_provider_history to control the output
        self.converter = GeminiHistoryConverter()
        self.patcher = patch.object(self.converter, "create_history_messages")
        self.mock_create_history = self.patcher.start()

        # Default behavior - do nothing for system and context messages
        self.mock_create_history.side_effect = self.mock_create_history_messages

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()

    def mock_create_history_messages(self, role, items):
        """Mock implementation of create_history_messages."""
        # For system role, return empty iterator
        if role in [Role.SYSTEM, Role.CONTEXT]:
            return []

        # For user and model roles, return a mock message
        mock_msg = MagicMock(role=role.value)

        if isinstance(items[0], ContentPartText):
            mock_msg.parts = [MagicMock(text=items[0].text)]

        return [mock_msg]

    def test_basic_conversion_text_messages(self):
        """Test conversion of simple text messages for all role types."""
        # Create a history with messages from different roles
        history = History(
            system_message="You are a helpful assistant",
            context="This is contextual information",
        )

        # Add a user message
        history.add_user_message("Hello, how are you?")

        # Add a model response
        history.add_assistant_message_test(
            "I'm doing well, thank you for asking!",
        )

        # Set up the mock to return specific messages for each role
        self.mock_create_history.side_effect = lambda role, items: (
            []  # Return empty for system/context
            if role in [Role.SYSTEM, Role.CONTEXT]
            else [MagicMock(role=role.value, parts=[MagicMock(text=items[0].text)])]
        )

        # Convert to provider history
        provider_history = self.converter.create_provider_history(history)

        # Verify the conversion output - system and context messages are filtered out
        assert len(provider_history) == 2  # Only user and model messages

        # Check message roles and content
        assert provider_history[0].role == "user"
        assert provider_history[1].role == "model"

        # Verify the create_history_messages was called the right number of times
        assert self.mock_create_history.call_count == 4  # system, context, user, model

    def test_empty_history(self):
        """Test conversion of an empty History object."""
        history = History()
        provider_history = self.converter.create_provider_history(history)

        # Should return an empty list
        assert provider_history == []
        assert self.mock_create_history.call_count == 0

    def test_system_message_only(self):
        """Test conversion of a History with only a system message."""
        # Override the default mock to actually return a message for system role
        self.mock_create_history.side_effect = lambda role, items: (
            [MagicMock(role="user", parts=[MagicMock(text=items[0].text)])]
            if role == Role.SYSTEM
            else []
        )

        history = History(system_message="You are a helpful assistant")
        provider_history = self.converter.create_provider_history(history)

        # Should include the system message converted to user role
        assert len(provider_history) == 1
        assert provider_history[0].role == "user"
        assert self.mock_create_history.call_count == 1

    def test_complex_content_types(self):
        """Test conversion of messages with multiple content types."""

        # Setup the mock to handle different content types
        def mock_content_handler(role, items):
            if role in [Role.SYSTEM, Role.CONTEXT]:
                return []

            mock_parts = []
            for item in items:
                if isinstance(item, ContentPartText):
                    mock_parts.append(MagicMock(text=item.text))
                elif isinstance(item, ContentPartToolCall):
                    mock_parts.append(
                        MagicMock(
                            function_call=MagicMock(
                                name=item.name,
                                args=item.arguments,
                            ),
                        ),
                    )
                elif isinstance(item, ContentPartToolResult):
                    mock_parts.append(
                        MagicMock(function_response=MagicMock(name=item.name)),
                    )

            return [MagicMock(role=role.value, parts=mock_parts)]

        self.mock_create_history.side_effect = mock_content_handler

        history = History()

        # Add a message with a tool call
        history.add_assistant_message_test(
            "I need to search for something",
            {
                "tool_call_id": "search-1",
                "name": "search_files",
                "arguments": {"pattern": "*.py", "search_string": "def test"},
            },
        )

        # Add a message with a tool result
        history.add_tool_message(
            tool_call_id="search-1",
            name="search_files",
            content=ToolCallResult.ok(
                        output=ToolOutput(
                            type="text",
                            content="Found 5 files matching the pattern",
                        ),
                    ),
        )

        # Convert to provider history
        provider_history = self.converter.create_provider_history(history)

        # Verify the conversion output
        assert len(provider_history) == 2
        assert provider_history[0].role == "user"
        assert provider_history[1].role == "tool"

        # Verify the create_history_messages was called with the right arguments
        assert self.mock_create_history.call_count == 2

    def test_response_parsing_text(self):
        """Test parsing a simple text response from Gemini."""
        # Create a mock Gemini response with text content
        mock_response = MagicMock()
        mock_response.text = "This is a response from Gemini"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = []
        mock_response.candidates[0].finish_reason = "STOP"
        mock_response.candidates[0].finish_message = "Completed successfully"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.tool_use_prompt_token_count = 0

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content
        assert len(response_parts) == 3  # Text, Usage, FinishReason
        assert response_parts[0].text == "This is a response from Gemini"
        assert response_parts[1].prompt_tokens == 10
        assert response_parts[1].response_tokens == 5
        assert response_parts[2].finish_reason == "STOP"
        assert response_parts[2].finish_message == "Completed successfully"

    def test_empty_response(self):
        """Test handling of empty responses."""
        # Create a mock empty Gemini response
        mock_response = MagicMock()
        mock_response.candidates = []

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify empty result
        assert len(response_parts) == 0

    # Additional tests to improve coverage

    def test_create_history_messages_directly(self):
        """Test create_history_messages directly without mocking.

        This ensures the actual implementation is tested.
        """
        # Remove the patch for this test to test the real implementation
        self.patcher.stop()

        # Test with SYSTEM role - should produce no messages
        system_result = list(
            self.converter.create_history_messages(
                Role.SYSTEM,
                [ContentPartText(text="You are a helpful assistant")],
            ),
        )
        assert len(system_result) == 0

        # Test with CONTEXT role - should convert to USER role
        context_result = list(
            self.converter.create_history_messages(
                Role.CONTEXT,
                [ContentPartText(text="Some context information")],
            ),
        )
        assert len(context_result) == 1
        assert context_result[0].role == "user"
        assert context_result[0].parts[0].text == "Some context information"

        # Test with USER role and text
        user_result = list(
            self.converter.create_history_messages(
                Role.USER,
                [ContentPartText(text="Hello, how are you?")],
            ),
        )
        assert len(user_result) == 1
        assert user_result[0].role == "user"
        assert user_result[0].parts[0].text == "Hello, how are you?"

        # Restart the patch for other tests
        self.patcher.start()

    def test_create_history_messages_with_tool_calls(self):
        """Test create_history_messages with tool calls directly."""
        # Remove the patch for this test
        self.patcher.stop()

        # Test with a tool call content part
        tool_call_result = list(
            self.converter.create_history_messages(
                Role.USER,
                [
                    ContentPartToolCall(
                        tool_id="tool-123",
                        name="search_files",
                        arguments={"pattern": "*.py", "search_string": "test"},
                    ),
                ],
            ),
        )

        assert len(tool_call_result) == 1
        assert tool_call_result[0].role == "user"
        assert len(tool_call_result[0].parts) == 1
        assert tool_call_result[0].parts[0].function_call.name == "search_files"
        assert tool_call_result[0].parts[0].function_call.args == {
            "pattern": "*.py",
            "search_string": "test",
        }

        # Restart the patch for other tests
        self.patcher.start()

    def test_create_history_messages_with_tool_results(self):
        """Test create_history_messages with tool results directly."""
        # Remove the patch for this test
        self.patcher.stop()

        # Test with a tool result content part
        tool_result = list(
            self.converter.create_history_messages(
                Role.TOOL,
                [
                    ContentPartToolResult(
                        tool_id="result-123",
                        name="search_files",
                        content=ToolCallResult.ok(
                            output=ToolOutput(type="text", content="Found 10 matches"),
                        ),
                    ),
                ],
            ),
        )

        assert len(tool_result) == 1
        assert tool_result[0].role == "tool"
        assert len(tool_result[0].parts) == 1
        assert tool_result[0].parts[0].function_response.name == "search_files"
        assert "output" in tool_result[0].parts[0].function_response.response
        assert (
            tool_result[0].parts[0].function_response.response["output"]["type"]
            == "text"
        )
        assert (
            tool_result[0].parts[0].function_response.response["output"]["content"]
            == "Found 10 matches"
        )

        # Restart the patch for other tests
        self.patcher.start()

    def test_create_history_messages_multiple_parts(self):
        """Test create_history_messages with multiple content parts."""
        # Remove the patch for this test
        self.patcher.stop()

        # Test with multiple content parts
        result = list(
            self.converter.create_history_messages(
                Role.USER,
                [
                    ContentPartText(text="I need to search for something"),
                    ContentPartToolCall(
                        tool_id="tool-123",
                        name="search_files",
                        arguments={"pattern": "*.py", "search_string": "test"},
                    ),
                ],
            ),
        )

        assert len(result) == 1
        assert result[0].role == "user"
        assert len(result[0].parts) == 2
        assert result[0].parts[0].text == "I need to search for something"
        assert result[0].parts[1].function_call.name == "search_files"

        # Restart the patch for other tests
        self.patcher.start()

    def test_response_parsing_with_function_call(self):
        """Test parsing a response containing a function call."""
        # Create a mock Gemini response with a function call
        mock_response = MagicMock()
        mock_response.text = ""  # No text response
        mock_response.candidates = [MagicMock()]

        function_call = MagicMock()
        function_call.name = "search_files"
        function_call.args = {"pattern": "*.py", "search_string": "test"}
        function_call.id = "func-123"

        mock_part = MagicMock()
        mock_part.function_call = function_call
        mock_part.text = None

        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.candidates[0].finish_reason = "STOP"
        mock_response.candidates[0].finish_message = "Completed successfully"
        mock_response.usage_metadata = None  # No usage metadata

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify that the function call was parsed correctly
        assert len(response_parts) == 2  # Tool call and finish reason
        assert hasattr(response_parts[0], "name")
        assert response_parts[0].name == "search_files"
        assert response_parts[0].arguments == {
            "pattern": "*.py",
            "search_string": "test",
        }
        assert response_parts[0].tool_id == "func-123"

    def test_response_parsing_with_multiple_candidates(self):
        """Test parsing a response with multiple candidates."""
        # Create a mock Gemini response with multiple candidates
        mock_response = MagicMock()
        mock_response.text = "Main response text"

        # Create primary candidate
        primary_candidate = MagicMock()
        primary_candidate.content.parts = []
        primary_candidate.finish_reason = "STOP"
        primary_candidate.finish_message = "Primary candidate"

        # Create alternative candidates
        alt_candidate1 = MagicMock()
        alt_candidate1.finish_reason = "RECITATION"

        alt_candidate2 = MagicMock()
        alt_candidate2.finish_reason = "SAFETY"

        mock_response.candidates = [primary_candidate, alt_candidate1, alt_candidate2]
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_response.usage_metadata.tool_use_prompt_token_count = 2

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content
        assert len(response_parts) == 3  # Text, Usage, FinishReason
        assert response_parts[0].text == "Main response text"
        assert response_parts[1].prompt_tokens == 15
        assert response_parts[1].response_tokens == 12  # 10 + 2

        # Verify that multiple candidates are mentioned in the finish message
        assert response_parts[2].finish_reason == "STOP"
        assert "there were 3 candidates" in response_parts[2].finish_message
        assert "'RECITATION'" in response_parts[2].finish_message
        assert "'SAFETY'" in response_parts[2].finish_message

    def test_response_parsing_partial_usage_metadata(self):
        """Test parsing a response with partial usage metadata."""
        # Create a mock Gemini response with partial usage metadata
        mock_response = MagicMock()
        mock_response.text = "Response with partial usage data"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = []
        mock_response.candidates[0].finish_reason = "STOP"
        mock_response.candidates[0].finish_message = "Completed"

        # Only provide prompt_token_count, leave others as None
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = None
        mock_response.usage_metadata.tool_use_prompt_token_count = None

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content with default values for missing metrics
        assert len(response_parts) == 3  # Text, Usage, FinishReason
        assert response_parts[0].text == "Response with partial usage data"
        assert response_parts[1].prompt_tokens == 20
        assert response_parts[1].response_tokens == 0  # 0 + 0
        assert response_parts[2].finish_reason == "STOP"

    def test_response_no_finish_reason(self):
        """Test parsing a response with no finish reason."""
        # Create a mock Gemini response without a finish reason
        mock_response = MagicMock()
        mock_response.text = "Response without finish reason"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = []
        mock_response.candidates[0].finish_reason = None
        mock_response.candidates[0].finish_message = None
        mock_response.usage_metadata = None

        # Parse the response
        response_parts = list(self.converter.get_response_parts(mock_response))

        # Verify the parsed content (should not include finish reason part)
        assert len(response_parts) == 1  # Text only
        assert response_parts[0].text == "Response without finish reason"


if __name__ == "__main__":
    unittest.main()
