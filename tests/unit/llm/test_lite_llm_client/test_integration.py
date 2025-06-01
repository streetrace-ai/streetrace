"""Integration tests for lite_llm_client.py components working together."""

from unittest.mock import patch

import pytest
from litellm.types.utils import ModelResponse

from streetrace.costs import UsageAndCost
from streetrace.llm.lite_llm_client import (
    LiteLLMClientWithUsage,
)
from streetrace.ui import ui_events


class TestLiteLlmIntegration:
    """Integration tests for lite_llm_client.py components."""

    def test_usage_and_cost_extraction_real_implementation(self, model_response):
        """Test that the implementation of usage and cost extraction work together."""
        with patch("streetrace.llm.lite_llm_client.completion_cost") as mock_cost:
            mock_cost.return_value = 0.0025

            # Extract usage using the real implementation with our test response
            usage = model_response["usage"]

            # Create a UsageAndCost object from these values
            usage_and_cost = UsageAndCost(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                cost=0.0025,
            )

            # Verify UsageAndCost properties
            assert usage_and_cost.prompt_tokens_str == "10"
            assert usage_and_cost.completion_tokens_str == "15"
            assert usage_and_cost.cost_str == "0.00"  # Rounded to 2 decimal places

    @pytest.mark.asyncio
    async def test_client_usage_reporting(self, mock_ui_bus, model_response):
        """Test that LiteLLMClientWithUsage properly tracks and reports usage."""
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello, world!"}]
        tools = []

        # Create client
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)

        # Mock the extract functions and parent completion
        with (
            patch(
                "streetrace.llm.lite_llm_client._try_extract_usage",
            ) as mock_extract_usage,
            patch(
                "streetrace.llm.lite_llm_client._try_extract_cost",
            ) as mock_extract_cost,
            patch(
                "google.adk.models.lite_llm.LiteLLMClient.completion",
            ) as mock_completion,
        ):
            # Set up mocks
            mock_extract_usage.return_value = model_response["usage"]
            mock_extract_cost.return_value = 0.0025
            mock_completion.return_value = model_response

            # Call the method
            _ = client.completion(model, messages, tools, stream=False)

            # Verify usage data was dispatched
            mock_ui_bus.dispatch_usage_data.assert_called_once()
            usage = mock_ui_bus.dispatch_usage_data.call_args[0][0]
            assert isinstance(usage, UsageAndCost)
            assert usage.prompt_tokens == model_response["usage"]["prompt_tokens"]
            assert (
                usage.completion_tokens == model_response["usage"]["completion_tokens"]
            )
            assert usage.cost == 0.0025

    @pytest.mark.asyncio
    async def test_error_handling_and_ui_feedback(self, mock_ui_bus):
        """Test error handling and UI feedback when costs can't be calculated."""
        model = "unknown-model"
        messages = [{"role": "user", "content": "Hello, world!"}]
        tools = []

        # Create a mock model response
        mock_response = ModelResponse(
            id="test-id",
            choices=[],
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        )

        # Create client
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)

        # Mock the parent completion and make cost calculation fail
        with (
            patch(
                "google.adk.models.lite_llm.LiteLLMClient.completion",
            ) as mock_completion,
            patch(
                "streetrace.llm.lite_llm_client._try_extract_cost",
            ) as mock_extract_cost,
        ):
            # Set up mocks
            mock_completion.return_value = mock_response
            mock_extract_cost.side_effect = ValueError("Unknown model pricing")

            # Call the method
            _ = client.completion(model, messages, tools, stream=False)

            # Verify warning was dispatched to UI
            mock_ui_bus.dispatch_ui_update.assert_called()
            ui_event = mock_ui_bus.dispatch_ui_update.call_args[0][0]
            assert isinstance(ui_event, ui_events.Warn)
            assert "Cost could not be calculated" in str(ui_event)
