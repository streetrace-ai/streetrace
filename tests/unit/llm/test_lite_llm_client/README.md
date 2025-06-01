# Tests for `lite_llm_client.py`

This directory contains comprehensive tests for the `lite_llm_client.py` module, which implements enhanced LLM clients with retry, usage tracking, and cost calculation capabilities.

## Test Structure

1. **Helper Function Tests** (`test_helper_functions.py`)
   - Tests for `_try_extract_usage`: Verifies extraction of usage data from model responses
   - Tests for `_try_extract_cost`: Verifies cost calculation based on model, messages, and completion response

2. **LiteLLMClientWithUsage Tests** (`test_litellm_client_with_usage.py`)
   - Tests client initialization
   - Tests usage and cost processing for different response types
   - Tests error handling during cost calculation
   - Tests `acompletion` and `completion` methods with and without streaming

3. **RetryingLiteLlm Tests** (`test_retrying_lite_llm.py`)
   - Tests client initialization
   - Tests streaming behavior that bypasses retry logic
   - Tests error handling and retry behavior for rate limits and server errors

4. **Integration Tests** (`test_integration.py`)
   - End-to-end tests for usage reporting
   - Tests for error handling and UI feedback
   - Tests for successful extraction of usage and cost data

5. **Module Tests** (`test_module.py`)
   - Tests for module imports and exports
   - Tests for module constants

## Key Components Tested

- Usage data extraction from LLM responses
- Cost calculation based on token usage
- UI feedback for errors and warnings
- Retry logic for handling transient errors
- Proper streaming behavior without retries
- Error propagation for non-retryable errors

## Test Coverage

The test suite achieves ~68% code coverage for the module. The uncovered parts are primarily related to complex async generators and retry logic that is difficult to test directly.

## Running the Tests

To run these tests:

```bash
poetry run python -m pytest tests/unit/llm/test_lite_llm_client
```

To run with coverage:

```bash
poetry run python -m pytest tests/unit/llm/test_lite_llm_client --cov=streetrace.llm.lite_llm_client
```