"""Test suite for all Ollama implementation tests.

This module provides a test suite that runs all tests for the Ollama implementation.
"""

import unittest

from tests.llm.ollama.test_converter import TestOllamaHistoryConverter
from tests.llm.ollama.test_impl import TestOllamaImpl


def suite():
    """Create a test suite for all Ollama tests."""
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Add tests from TestGeminiHistoryConverter
    test_suite.addTest(loader.loadTestsFromTestCase(TestOllamaHistoryConverter))

    # Add tests from TestGeminiImpl
    test_suite.addTest(loader.loadTestsFromTestCase(TestOllamaImpl))

    return test_suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())


# """Integration test suite for Ollama provider.

# This module contains a suite of standardized tests for the Ollama provider
# implementation. It includes both basic functionality tests and more comprehensive
# tests for specific features of the Ollama API.
# """

# import unittest
# from unittest.mock import MagicMock, patch

# from streetrace.llm.ollama.converter import OllamaHistoryConverter
# from streetrace.llm.ollama.impl import Ollama
# from streetrace.llm.wrapper import (
#     ContentPartText,
#     ContentPartToolCall,
#     ContentPartToolResult,
#     History,
#     Role,
# )


# class TestOllamaSuite(unittest.TestCase):
#     """Suite of tests for Ollama provider that focus on integration of components."""

#     def setUp(self):
#         """Set up test fixtures."""
#         # Patch the ollama module
#         self.ollama_patcher = patch("streetrace.llm.ollama.impl.ollama")
#         self.mock_ollama = self.ollama_patcher.start()

#         # Create a mock client
#         self.mock_client = MagicMock()
#         self.mock_ollama.Client.return_value = self.mock_client

#         # Create the Ollama instance
#         self.ollama = Ollama()

#         # Keep a reference to the real converter
#         self.real_converter = self.ollama._adapter

#         # Patch isinstance to avoid type errors
#         self.isinstance_patcher = patch("streetrace.llm.ollama.impl.isinstance")
#         self.mock_isinstance = self.isinstance_patcher.start()
#         # Make the first isinstance check return True to take the single response path
#         self.mock_isinstance.return_value = True

#     def tearDown(self):
#         """Tear down test fixtures."""
#         self.ollama_patcher.stop()
#         self.isinstance_patcher.stop()
#         # Restore the real converter
#         self.ollama._adapter = self.real_converter

#     def test_chat_streaming(self):
#         """Test streaming responses."""
#         # For streaming, we need isinstance to return False
#         self.mock_isinstance.return_value = False

#         # Create a history
#         history = History(system_message="You are a helpful assistant")
#         history.add_message(Role.USER, [ContentPartText(text="Hello")])

#         # Transform history
#         provider_history = self.ollama.transform_history(history)

#         # Create mock stream items
#         stream_item1 = MagicMock()
#         stream_item2 = MagicMock()
#         stream_item3 = MagicMock()

#         # Set up the chat method to return a stream
#         self.mock_client.chat.return_value = [stream_item1, stream_item2, stream_item3]

#         # Create a mock streaming converter that returns different content parts
#         # to simulate streaming behavior
#         mock_converter = MagicMock()
#         mock_converter.get_response_parts.side_effect = [
#             [ContentPartText(text="Hello")],
#             [ContentPartText(text="Hello there")],
#             [ContentPartText(text="Hello there! How can I help you today?"),
#              ContentPartToolCall(name="search_files", arguments={})],
#         ]

#         # Use the mock converter
#         self.ollama._adapter = mock_converter

#         # Generate the streaming response
#         all_parts = list(
#             self.ollama.generate(
#                 client=self.mock_client,
#                 model_name="llama3",
#                 system_message="You are a helpful assistant",
#                 messages=provider_history,
#                 tools=[],
#             )
#         )

#         # Verify the response parts
#         assert len(all_parts) == 4  # Three text parts, one tool call
#         assert all_parts[0].text == "Hello"
#         assert all_parts[1].text == "Hello there"
#         assert all_parts[2].text == "Hello there! How can I help you today?"
#         assert isinstance(all_parts[3], ContentPartToolCall)

#         # Verify chat was called once
#         self.mock_client.chat.assert_called_once()

#         # Verify the converter's get_response_parts was called for each stream item
#         assert mock_converter.get_response_parts.call_count == 3


# if __name__ == "__main__":
#     unittest.main()
