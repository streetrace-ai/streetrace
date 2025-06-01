"""Tests for the LiteLLMClientWithUsage class."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse

from streetrace.costs import UsageAndCost
from streetrace.llm.lite_llm_client import LiteLLMClientWithUsage
from streetrace.ui import ui_events


class TestLiteLLMClientWithUsage:
    """Tests for the LiteLLMClientWithUsage class."""

    def test_initialization(self, mock_ui_bus):
        """Test that the client initializes correctly."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        assert client.ui_bus == mock_ui_bus

    @pytest.mark.parametrize(
        ("response_type", "should_process"),
        [
            (ModelResponse, True),
            (CustomStreamWrapper, False),
            (str, False),
        ],
    )
    def test_process_usage_and_cost_response_type_handling(
        self,
        response_type,
        should_process,
        mock_ui_bus,
        model_response,
        custom_stream_wrapper,
    ):
        """Test that _process_usage_and_cost handles different response types."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]

        # Create the appropriate response object based on the test parameter
        if response_type == ModelResponse:
            response = model_response
        elif response_type == CustomStreamWrapper:
            response = custom_stream_wrapper
        else:
            response = "text response"

        # Mock the extract functions
        with (
            patch(
                "streetrace.llm.lite_llm_client._try_extract_usage",
            ) as mock_extract_usage,
            patch(
                "streetrace.llm.lite_llm_client._try_extract_cost",
            ) as mock_extract_cost,
        ):
            mock_extract_usage.return_value = (
                model_response["usage"] if should_process else None
            )
            mock_extract_cost.return_value = 0.0025 if should_process else None

            # Call the method
            client._process_usage_and_cost(model, messages, response)  # noqa: SLF001

            # Check if the extraction functions were called appropriately
            if should_process:
                mock_extract_usage.assert_called_once_with(response)
                mock_extract_cost.assert_called_once()
            elif response_type == CustomStreamWrapper:
                # For streaming, we expect a warning log but no further processing
                assert mock_extract_usage.call_count == 0
                assert mock_extract_cost.call_count == 0
            else:
                # For invalid types, we expect a warning log but no further processing
                assert mock_extract_usage.call_count == 0
                assert mock_extract_cost.call_count == 0

    def test_process_usage_and_cost_successful(self, mock_ui_bus, model_response):
        """Test successful processing of usage and cost data."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]

        # Mock successful extraction
        with (
            patch(
                "streetrace.llm.lite_llm_client._try_extract_usage",
            ) as mock_extract_usage,
            patch(
                "streetrace.llm.lite_llm_client._try_extract_cost",
            ) as mock_extract_cost,
        ):
            usage = model_response["usage"]
            mock_extract_usage.return_value = usage
            mock_extract_cost.return_value = 0.0025

            # Call the method
            client._process_usage_and_cost(model, messages, model_response)  # noqa: SLF001

            # Verify UI bus was called with correct usage data
            mock_ui_bus.dispatch_usage_data.assert_called_once()
            usage_and_cost = mock_ui_bus.dispatch_usage_data.call_args[0][0]
            assert isinstance(usage_and_cost, UsageAndCost)
            assert usage_and_cost.prompt_tokens == usage["prompt_tokens"]
            assert usage_and_cost.completion_tokens == usage["completion_tokens"]
            assert usage_and_cost.cost == 0.0025

    def test_process_usage_and_cost_cost_calculation_error(
        self,
        mock_ui_bus,
        model_response,
    ):
        """Test handling of cost calculation errors."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        model = "unknown-model"
        messages = [{"role": "user", "content": "Hello"}]

        # Mock usage extraction but make cost calculation fail
        with (
            patch(
                "streetrace.llm.lite_llm_client._try_extract_usage",
            ) as mock_extract_usage,
            patch(
                "streetrace.llm.lite_llm_client._try_extract_cost",
            ) as mock_extract_cost,
        ):
            mock_extract_usage.return_value = model_response["usage"]
            mock_extract_cost.side_effect = ValueError("Unknown model pricing")

            # Call the method
            client._process_usage_and_cost(model, messages, model_response)  # noqa: SLF001

            # Verify warning was sent to UI
            mock_ui_bus.dispatch_ui_update.assert_called_once()
            ui_event = mock_ui_bus.dispatch_ui_update.call_args[0][0]
            assert isinstance(ui_event, ui_events.Warn)
            assert "Cost could not be calculated" in str(ui_event)

    @pytest.mark.asyncio
    async def test_acompletion(self, mock_ui_bus):
        """Test that acompletion delegates to parent and processes usage."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]
        tools = []
        kwargs = {"max_tokens": 100}

        # Create a mock response
        mock_response = Mock(spec=ModelResponse)

        # Mock super().acompletion
        with (
            patch(
                "google.adk.models.lite_llm.LiteLLMClient.acompletion",
                AsyncMock(return_value=mock_response),
            ) as mock_super,
            patch.object(client, "_process_usage_and_cost") as mock_process,
        ):
            # Call the method
            result = await client.acompletion(model, messages, tools, **kwargs)

            # Verify parent method was called with correct arguments
            mock_super.assert_called_once_with(model, messages, tools, **kwargs)

            # Verify usage processing was called
            mock_process.assert_called_once_with(model, messages, mock_response)

            # Verify the result is what we expect
            assert result == mock_response

    def test_completion_non_streaming(self, mock_ui_bus):
        """Test that completion delegates to parent for non-streaming."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]
        tools = []
        kwargs = {"max_tokens": 100}

        # Create a mock response
        mock_response = Mock(spec=ModelResponse)

        # Mock super().completion
        with (
            patch(
                "google.adk.models.lite_llm.LiteLLMClient.completion",
                return_value=mock_response,
            ) as mock_super,
            patch.object(client, "_process_usage_and_cost") as mock_process,
        ):
            # Call the method (non-streaming)
            result = client.completion(
                model,
                messages,
                tools,
                stream=False,
                **kwargs,
            )

            # Verify parent method was called with correct arguments
            mock_super.assert_called_once_with(
                model,
                messages,
                tools,
                False,  # noqa: FBT003
                **kwargs,
            )

            # Verify usage processing was called
            mock_process.assert_called_once_with(model, messages, mock_response)

            # Verify the result is what we expect
            assert result == mock_response

    def test_completion_streaming(self, mock_ui_bus):
        """Test that completion delegates to parent but skips usage for streaming."""
        client = LiteLLMClientWithUsage(ui_bus=mock_ui_bus)
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "Hello"}]
        tools = []
        kwargs = {"max_tokens": 100}

        # Create a mock response
        mock_response = Mock(spec=CustomStreamWrapper)

        # Mock super().completion
        with (
            patch(
                "google.adk.models.lite_llm.LiteLLMClient.completion",
                return_value=mock_response,
            ) as mock_super,
            patch.object(client, "_process_usage_and_cost") as mock_process,
        ):
            # Call the method (streaming)
            result = client.completion(
                model,
                messages,
                tools,
                stream=True,
                **kwargs,
            )

            # Verify parent method was called with correct arguments
            mock_super.assert_called_once_with(
                model,
                messages,
                tools,
                True,  # noqa: FBT003
                **kwargs,
            )

            # Verify usage processing was NOT called for streaming
            mock_process.assert_not_called()

            # Verify the result is what we expect
            assert result == mock_response
