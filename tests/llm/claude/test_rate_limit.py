import logging
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

import anthropic
from anthropic._exceptions import APIStatusError, RateLimitError

# Import the class we want to test
from streetrace.llm.claude.impl import Claude


class TestClaudeRateLimitHandling(unittest.TestCase):

    def setUp(self):
        # Instantiate the Claude provider
        self.claude_provider = Claude()
        # Mock the API client initialization to control the client object
        self.mock_client_instance = MagicMock(spec=anthropic.Anthropic)

        # *** Configure the messages attribute on the mock client ***
        self.mock_messages = MagicMock()
        self.mock_client_instance.messages = self.mock_messages

        self.patcher_init_client = patch.object(
            self.claude_provider, "initialize_client", return_value=self.mock_client_instance
        )
        self.mock_init_client = self.patcher_init_client.start()
        self.addCleanup(self.patcher_init_client.stop)

    @patch("time.sleep")
    @patch("logging.warning")
    def test_rate_limit_retry(self, mock_log_warning, mock_sleep):
        # Configure the mock client's create method (now on mock_messages)
        response_mock = MagicMock(spec=anthropic.types.Message)
        # Set required attributes for the mock response
        response_mock.content = []
        response_mock.stop_reason = "end_turn"
        response_mock.role = "assistant"
        response_mock.model = "claude-model"
        response_mock.type = "message"
        response_mock.usage = anthropic.types.Usage(input_tokens=10, output_tokens=20)

        # Create a properly formed RateLimitError
        mock_api_response = MagicMock()
        mock_api_response.status_code = 429
        mock_api_response.headers = {}
        mock_api_response.text = "Rate limit exceeded"

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=mock_api_response,
            body={
                "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}
            },
        )

        # Setup mock to raise RateLimitError on first call, then return a successful response
        self.mock_messages.create.side_effect = [
            rate_limit_error,
            iter([anthropic.types.MessageStartEvent(message=response_mock, type="message_start"),
                  anthropic.types.MessageStopEvent(type="message_stop", anthropic_version="test-version")]) # Return iterable for stream
        ]

        # Call the generate method (use dummy data for history/tools)
        list(self.claude_provider.generate(
            client=self.mock_client_instance, # Pass the mock client
            model_name="test-model",
            system_message="sys",
            messages=[{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            tools=[]
        ))

        # Assert that sleep was called with the default retry time (e.g., 30 seconds)
        # Check the implementation for the exact sleep time
        mock_sleep.assert_called_once_with(30) # Assuming 30 seconds default

        # Assert that a warning was logged
        mock_log_warning.assert_called_once()
        self.assertIn("Rate limit error encountered", mock_log_warning.call_args[0][0])

        # Assert that client.messages.create was called twice
        self.assertEqual(self.mock_messages.create.call_count, 2)

    @patch("time.sleep")
    @patch("logging.warning")
    def test_multiple_rate_limit_retries(self, mock_log_warning, mock_sleep):
        # Configure the mock client's create method
        response_mock = MagicMock(spec=anthropic.types.Message)
        response_mock.content = []
        response_mock.stop_reason = "end_turn"
        response_mock.role = "assistant"
        response_mock.model = "claude-model"
        response_mock.type = "message"
        response_mock.usage = anthropic.types.Usage(input_tokens=10, output_tokens=20)

        mock_api_response = MagicMock()
        mock_api_response.status_code = 429
        mock_api_response.headers = {}
        mock_api_response.text = "Rate limit exceeded"

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=mock_api_response,
            body={
                "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}
            },
        )

        # Setup mock to raise RateLimitError twice, then return a successful response stream
        self.mock_messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            iter([anthropic.types.MessageStartEvent(message=response_mock, type="message_start"),
                  anthropic.types.MessageStopEvent(type="message_stop", anthropic_version="test-version")]) # Stream
        ]

        # Call the generate method
        list(self.claude_provider.generate(
            client=self.mock_client_instance,
            model_name="test-model",
            system_message="sys",
            messages=[{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            tools=[]
        ))

        # Assert that sleep was called twice, potentially with increasing backoff
        # Check implementation for backoff strategy
        self.assertEqual(mock_sleep.call_count, 2)
        # Example check if it sleeps 30s then 60s
        # mock_sleep.assert_has_calls([call(30), call(60)])
        mock_sleep.assert_called_with(60) # Check last call if exponential backoff

        # Assert that a warning was logged twice
        self.assertEqual(mock_log_warning.call_count, 2)
        for call in mock_log_warning.call_args_list:
            self.assertIn("Rate limit error encountered", call[0][0])

        # Assert that client.messages.create was called three times
        self.assertEqual(self.mock_messages.create.call_count, 3)

    def test_other_errors_not_retried(self):
        # Configure the mock to raise a different error
        self.mock_messages.create.side_effect = ValueError("Some other error")

        # Call the generate method and expect it to raise the error
        with self.assertRaisesRegex(ValueError, "Some other error"):
             list(self.claude_provider.generate(
                client=self.mock_client_instance,
                model_name="test-model",
                system_message="sys",
                messages=[{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
                tools=[]
            ))

        # Assert that client.messages.create was called only once
        self.assertEqual(self.mock_messages.create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
