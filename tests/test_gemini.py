import unittest
import gemini
from unittest import mock
from google.genai import types

class TestGemini(unittest.TestCase):
    @mock.patch('gemini.initialize_client')
    @mock.patch('gemini.manage_token_count')
    def test_generate_with_tool(self, mock_manage_token_count, mock_initialize_client):
        # Mock the client and its methods
        mock_client = mock.MagicMock()
        mock_initialize_client.return_value = mock_client
        mock_manage_token_count.return_value = True
        
        mock_chunk = mock.MagicMock()
        mock_candidate = mock.MagicMock()
        mock_candidate.finish_reason = 'STOP'
        mock_candidate.finish_message = 'Normal stop'
        mock_chunk.candidates = [mock_candidate]
        mock_chunk.text = "Paris is the capital of France"
        mock_client.models.generate_content_stream.return_value = [mock_chunk]
        
        # Create mock tools and call_tool function
        tools = []
        def mock_call_tool(name, args, call):
            return "{}"
        
        prompt = "What is the capital of France?"
        conversation_history = gemini.generate_with_tool(prompt, tools, mock_call_tool)
        self.assertIsNotNone(conversation_history)
        self.assertTrue(len(conversation_history) > 0)

    @mock.patch('gemini.initialize_client')
    @mock.patch('gemini.manage_token_count')
    def test_generate_with_empty_tool_response(self, mock_manage_token_count, mock_initialize_client):
        # Mock the client and its methods
        mock_client = mock.MagicMock()
        mock_initialize_client.return_value = mock_client
        mock_manage_token_count.return_value = True
        
        # Set up function call chunk
        function_call = types.FunctionCall(
            name="list_directory",
            args={"path": "/tmp"},
            id="func123"
        )
        
        # Create mock chunk with function call
        mock_chunk = mock.MagicMock()
        mock_candidate = mock.MagicMock()
        mock_candidate.finish_reason = 'STOP'
        mock_candidate.finish_message = 'Normal stop'
        mock_chunk.candidates = [mock_candidate]
        mock_chunk.function_calls = [function_call]
        mock_chunk.text = ""
        mock_client.models.generate_content_stream.return_value = [mock_chunk]
        
        # Create mock tools
        tools = [{
            "function": {
                "name": "list_directory",
                "description": "Lists directory contents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to list"
                        }
                    },
                    "required": ["path"]
                }
            }
        }]
        
        # Create mock call_tool function
        def mock_call_tool(name, args, call):
            return "{}"
        
        prompt = "List the contents of the directory /tmp."
        conversation_history = gemini.generate_with_tool(prompt, tools, mock_call_tool)
        self.assertIsNotNone(conversation_history)
        # Check conversation history integrity
        self.assertTrue(len(conversation_history) > 0)
            
    def test_malformed_function_call_constant(self):
        # Simple test to verify the constant is defined
        self.assertEqual(gemini.MAX_MALFORMED_RETRIES, 3)

if __name__ == '__main__':
    unittest.main()