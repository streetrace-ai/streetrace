import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import time
import logging
import anthropic
from anthropic._exceptions import APIStatusError

# Add parent directory to path to import claude module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import claude

class TestClaudeRateLimitHandling(unittest.TestCase):
    
    @patch('claude.client')
    @patch('time.sleep')
    @patch('logging.warning')
    def test_rate_limit_retry(self, mock_log_warning, mock_sleep, mock_client):
        # Configure the mock to raise RateLimitError once, then succeed
        response_mock = MagicMock()
        response_mock.content = []
        response_mock.stop_reason = 'end_turn'
        response_mock.role = 'assistant'
        response_mock.usage.input_tokens = 100
        response_mock.usage.output_tokens = 200
        
        # Create a properly formed RateLimitError
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.text = "Rate limit exceeded"
        
        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=mock_response, 
            body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}
        )
        
        # Setup mock to raise RateLimitError on first call, then return a successful response
        mock_client.messages.create.side_effect = [
            rate_limit_error,
            response_mock
        ]
        
        # Call the function
        conversation_history = claude.generate_with_tool("Test prompt")
        
        # Assert that sleep was called with 30 seconds
        mock_sleep.assert_called_once_with(30)
        
        # Assert that a warning was logged
        mock_log_warning.assert_called_once()
        self.assertIn("Rate limit error", mock_log_warning.call_args[0][0])
        
        # Assert that client.messages.create was called twice
        self.assertEqual(mock_client.messages.create.call_count, 2)
        
    @patch('claude.client')
    @patch('time.sleep')
    @patch('logging.warning')
    def test_multiple_rate_limit_retries(self, mock_log_warning, mock_sleep, mock_client):
        # Configure the mock to raise RateLimitError twice, then succeed
        response_mock = MagicMock()
        response_mock.content = []
        response_mock.stop_reason = 'end_turn'
        response_mock.role = 'assistant'
        response_mock.usage.input_tokens = 100
        response_mock.usage.output_tokens = 200
        
        # Create a properly formed RateLimitError
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.text = "Rate limit exceeded"
        
        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=mock_response, 
            body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}
        )
        
        # Setup mock to raise RateLimitError twice, then return a successful response
        mock_client.messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            response_mock
        ]
        
        # Call the function
        conversation_history = claude.generate_with_tool("Test prompt")
        
        # Assert that sleep was called twice, each time with 30 seconds
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(30)
        
        # Assert that a warning was logged twice
        self.assertEqual(mock_log_warning.call_count, 2)
        for call in mock_log_warning.call_args_list:
            self.assertIn("Rate limit error", call[0][0])
        
        # Assert that client.messages.create was called three times
        self.assertEqual(mock_client.messages.create.call_count, 3)
        
    @patch('claude.client')
    def test_other_errors_not_retried(self, mock_client):
        # Configure the mock to raise a different error
        mock_client.messages.create.side_effect = ValueError("Some other error")
        
        # Call the function and expect it to raise the error
        with self.assertRaises(ValueError):
            claude.generate_with_tool("Test prompt")
        
        # Assert that client.messages.create was called only once
        self.assertEqual(mock_client.messages.create.call_count, 1)

if __name__ == '__main__':
    unittest.main()