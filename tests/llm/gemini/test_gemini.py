import unittest
from unittest import mock

from google import genai
from google.genai import types as google_types  # Alias to avoid conflict

# Import the Gemini class and other necessary items
from streetrace.llm.gemini.impl import MAX_MALFORMED_RETRIES, Gemini  # Import constant
from streetrace.llm.wrapper import History, Role  # Import History and Role


class TestGemini(unittest.TestCase):

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gemini_provider = Gemini()
        # Mock the client initialization to avoid actual API calls
        self.mock_client_instance = mock.MagicMock(
            spec=genai.GenerativeModel,
        )  # Spec should be GenerativeModel
        # Mock the client's model method to return our mock model instance
        self.patcher_client_model = mock.patch.object(
            genai.Client,
            "model",
            return_value=self.mock_client_instance,
        )
        self.mock_client_model = self.patcher_client_model.start()
        self.addCleanup(self.patcher_client_model.stop)

        # Mock the client factory itself if needed, though mocking model() might be enough
        self.patcher_init_client = mock.patch.object(
            self.gemini_provider,
            "initialize_client",
            return_value=mock.MagicMock(),  # Return a dummy client object
        )
        self.mock_init_client = self.patcher_init_client.start()
        self.addCleanup(self.patcher_init_client.stop)

        # Mock the conversation history management
        self.patcher_manage_history = mock.patch.object(
            self.gemini_provider,
            "manage_conversation_history",
            return_value=True,
        )
        self.mock_manage_history = self.patcher_manage_history.start()
        self.addCleanup(self.patcher_manage_history.stop)

    def test_generate_with_tool(self) -> None:
        """Test the generate method with a simple text response."""
        # Mock the stream response
        mock_response = mock.MagicMock(spec=google_types.GenerateContentResponse)
        mock_candidate = mock.MagicMock(spec=google_types.Candidate)
        mock_part = mock.MagicMock(spec=google_types.Part)
        mock_part.text = "Paris is the capital of France"
        # Configure parts access correctly
        mock_content = mock.MagicMock(spec=google_types.Content)
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        # Use string literals for finish reasons if enum path is problematic
        mock_candidate.finish_reason = "STOP"
        mock_candidate.finish_message = "Normal stop"
        mock_response.candidates = [mock_candidate]

        # Configure the mock client's generate_content method
        self.mock_client_instance.generate_content.return_value = mock_response

        # Define dummy input
        history = History()
        history.add_message(
            Role.USER,
            [mock.MagicMock(text="What is the capital of France?")],
        )
        provider_history = self.gemini_provider.transform_history(history)
        # Transform tools correctly expects a list of dicts, returns list of types.Tool
        # transformed_tools = self.gemini_provider.transform_tools(tools)
        transformed_tools = []  # Pass empty list if no tools needed for this test

        # Call the generate method
        response_stream = self.gemini_provider.generate(
            client=self.mock_client_instance,  # Pass the mocked model instance
            model_name="gemini-pro",  # Use a valid model name
            system_message="sys",
            messages=provider_history,
            tools=transformed_tools,
        )

        # Process the stream
        results = list(response_stream)
        assert len(results) > 0
        # Add more specific assertions based on expected wrapper types and content
        assert results[0].get_text() == "Paris is the capital of France"
        assert results[1].finish_reason == "STOP"

    def test_generate_with_empty_tool_response(self) -> None:
        """Test generation when a tool call is expected but doesn't return output (simulated)."""
        # Mock response indicating a function call
        mock_response = mock.MagicMock(spec=google_types.GenerateContentResponse)
        mock_candidate = mock.MagicMock(spec=google_types.Candidate)
        mock_function_call = mock.MagicMock(spec=google_types.FunctionCall)
        mock_function_call.name = "list_directory"
        mock_function_call.args = {"path": "/tmp"}
        mock_part = mock.MagicMock(spec=google_types.Part)
        mock_part.function_call = mock_function_call
        # Configure parts access correctly
        mock_content = mock.MagicMock(spec=google_types.Content)
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_candidate.finish_reason = "TOOL_CALL"  # Use string literal
        mock_candidate.finish_message = ""
        mock_response.candidates = [mock_candidate]

        self.mock_client_instance.generate_content.return_value = mock_response

        # Define dummy tools in the common format expected by transform_tools
        common_tools = [
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "Lists directory contents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to list"},
                        },
                        "required": ["path"],
                    },
                },
            },
        ]
        transformed_tools = self.gemini_provider.transform_tools(common_tools)

        history = History()
        history.add_message(Role.USER, [mock.MagicMock(text="List /tmp")])
        provider_history = self.gemini_provider.transform_history(history)

        # Call the generate method
        response_stream = self.gemini_provider.generate(
            client=self.mock_client_instance,
            model_name="gemini-pro",
            system_message="sys",
            messages=provider_history,
            tools=transformed_tools,
        )

        results = list(response_stream)
        assert len(results) > 0
        # Check that the first result is a tool call
        tool_calls = results[0].get_tool_calls()
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "list_directory"
        assert tool_calls[0].arguments == {"path": "/tmp"}
        assert results[1].finish_reason == "TOOL_CALL"

    def test_malformed_function_call_constant(self) -> None:
        """Test accessing the constant from the implementation module."""
        # Access the constant imported from the module
        assert MAX_MALFORMED_RETRIES == 3


if __name__ == "__main__":
    unittest.main()
