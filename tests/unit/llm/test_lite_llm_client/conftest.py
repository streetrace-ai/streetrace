"""Test fixtures for lite_llm_client.py tests."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse

from streetrace.llm.lite_llm_client import (
    LiteLLMClientWithUsage,
)
from streetrace.ui.ui_bus import UiBus


@pytest.fixture
def mock_ui_bus() -> UiBus:
    """Return a mocked UiBus instance."""
    return Mock(spec=UiBus)


@pytest.fixture
def model_name() -> str:
    """Return a test model name."""
    return "test-model"


@pytest.fixture
def model_response_dict() -> dict[str, Any]:
    """Return a dictionary representing a typical ModelResponse."""
    return {
        "id": "test-response-id",
        "created": 1748634945,
        "object": "chat.completion",
        "model": "test-model",
        "choices": [
            {
                "message": {"content": "Test response content", "role": "assistant"},
                "index": 0,
                "finish_reason": "stop",
            },
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25,
        },
    }


@pytest.fixture
def model_response(model_response_dict) -> ModelResponse:
    """Return a ModelResponse instance."""
    return ModelResponse(**model_response_dict)


@pytest.fixture
def messages() -> list[dict[str, str]]:
    """Return sample messages for testing."""
    return [{"role": "user", "content": "Hello, world!"}]


@pytest.fixture
def custom_stream_wrapper() -> CustomStreamWrapper:
    """Return a mocked CustomStreamWrapper."""
    return Mock(spec=CustomStreamWrapper)


@pytest.fixture
def mock_completion_cost():
    """Return a mocked completion_cost function."""
    with patch("streetrace.llm.lite_llm_client.completion_cost") as mock_cost:
        mock_cost.return_value = 0.0025
        yield mock_cost


@pytest.fixture
def litellm_client_with_usage(mock_ui_bus) -> LiteLLMClientWithUsage:
    """Return a real LiteLLMClientWithUsage instance with mocked dependencies."""
    return LiteLLMClientWithUsage(ui_bus=mock_ui_bus)


@pytest.fixture
def llm_request() -> LlmRequest:
    """Return a LlmRequest instance for testing."""
    request = Mock(spec=LlmRequest)
    request.messages = [{"role": "user", "content": "Hello, world!"}]
    return request


@pytest.fixture
def llm_response() -> LlmResponse:
    """Return a LlmResponse instance for testing."""
    response = Mock(spec=LlmResponse)
    response.text = "Test response"
    return response
