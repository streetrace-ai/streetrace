"""Tests for the lite_llm_client module as a whole."""


def test_module_can_be_imported():
    """Test that the module can be imported without errors."""
    # Force a fresh import
    import sys

    if "streetrace.llm.lite_llm_client" in sys.modules:
        del sys.modules["streetrace.llm.lite_llm_client"]

    # Import the module
    import streetrace.llm.lite_llm_client

    # Verify the key components are exported
    assert hasattr(streetrace.llm.lite_llm_client, "LiteLLMClientWithUsage")
    assert hasattr(streetrace.llm.lite_llm_client, "RetryingLiteLlm")
    assert hasattr(streetrace.llm.lite_llm_client, "_try_extract_usage")
    assert hasattr(streetrace.llm.lite_llm_client, "_try_extract_cost")


def test_module_constants():
    """Test that the module has the expected constants with proper values."""
    from streetrace.llm.lite_llm_client import (
        _MAX_RETRIES,
        _RETRY_WAIT_INCREMENT,
        _RETRY_WAIT_MAX,
        _RETRY_WAIT_START,
    )

    # Verify constants have expected values
    assert _MAX_RETRIES == 7, "Max retries should be 7"
    assert _RETRY_WAIT_START == 30, "Initial retry wait should be 30 seconds"
    assert _RETRY_WAIT_INCREMENT == 30, "Retry wait increment should be 30 seconds"
    assert _RETRY_WAIT_MAX == 600, "Max retry wait should be 600 seconds (10 minutes)"
