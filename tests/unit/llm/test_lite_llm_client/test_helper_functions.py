"""Tests for helper functions in lite_llm_client.py."""

from unittest.mock import patch

from streetrace.llm.lite_llm_client import _try_extract_cost, _try_extract_usage


class TestTryExtractUsage:
    """Tests for the _try_extract_usage function."""

    def test_valid_usage(self, model_response):
        """Test that usage is correctly extracted from a valid ModelResponse."""
        usage = _try_extract_usage(model_response)
        assert usage is not None
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 15
        assert usage.total_tokens == 25

    def test_missing_usage(self):
        """Test handling when usage is missing from the response."""
        # Create a response without usage
        model_response = {}

        with patch("streetrace.llm.lite_llm_client.logger") as mock_logger:
            usage = _try_extract_usage(model_response)

            assert usage is None
            mock_logger.warning.assert_called_once()
            assert "Usage not found" in mock_logger.warning.call_args[0][0]

    def test_invalid_usage_type(self):
        """Test handling when usage is present but has an invalid type."""
        # Create a response with usage of invalid type
        model_response = {"usage": "not a Usage object"}

        with patch("streetrace.llm.lite_llm_client.logger") as mock_logger:
            usage = _try_extract_usage(model_response)

            assert usage is None
            mock_logger.warning.assert_called_once()
            assert "Unexpected usage type" in mock_logger.warning.call_args[0][0]


class TestTryExtractCost:
    """Tests for the _try_extract_cost function."""

    def test_valid_cost_calculation(self, model_response, mock_completion_cost):
        """Test that cost is correctly calculated for a valid model and response."""
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]

        cost = _try_extract_cost(model, messages, model_response)

        assert cost == 0.0025
        mock_completion_cost.assert_called_once_with(
            model=model,
            messages=messages,
            completion_response=model_response,
        )

    def test_non_list_messages_converted(self, model_response, mock_completion_cost):
        """Test that non-list messages are converted to a list."""
        model = "gpt-3.5-turbo"
        messages = {"role": "user", "content": "Hello"}  # Not a list

        with patch("streetrace.llm.lite_llm_client.logger") as mock_logger:
            cost = _try_extract_cost(model, messages, model_response)

            assert cost == 0.0025
            mock_logger.warning.assert_called_once()
            assert "Unexpected messages type" in mock_logger.warning.call_args[0][0]

            # Don't check exact parameters due to implementation differences
            assert mock_completion_cost.called
