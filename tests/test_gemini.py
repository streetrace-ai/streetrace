import unittest
import gemini
from unittest import mock
from google.genai import types

class TestGemini(unittest.TestCase):
    def test_generate_with_tool(self):
        prompt = "What is the capital of France?"
        conversation_history = gemini.generate_with_tool(prompt)
        self.assertIsNotNone(conversation_history)

    @mock.patch('tools.fs_tool.list_directory')
    def test_generate_with_empty_tool_response(self, mock_list_directory):
        mock_list_directory.return_value = {"fs_tool.list_directory_response": "{}"}
        prompt = "List the contents of the directory /tmp."
        conversation_history = gemini.generate_with_tool(prompt)
        self.assertIsNotNone(conversation_history)
        filtered_conversation_history = [content for content in conversation_history if content is not None]
        for content in filtered_conversation_history:
            self.assertTrue(content.parts)

if __name__ == '__main__':
    unittest.main()