"""Test fixtures for streetrace utility tests."""

import pytest


@pytest.fixture
def example_function():
    """Create a sample function with a known signature for testing hide_args."""

    def sample_fn(a: int, b: str, sensitive: str, api_key: str) -> str:
        """Sample function with multiple parameters.

        Args:
            a: First parameter
            b: Second parameter
            sensitive: A sensitive parameter that should be hidden
            api_key: An API key that should be hidden

        Returns:
            Combined string of all parameters

        """
        return f"{a}-{b}-{sensitive}-{api_key}"

    return sample_fn


@pytest.fixture
def sample_function_with_defaults():
    """Create a sample function with default parameters."""

    def sample_fn(a: int, b: str = "default", api_key: str = "default_key") -> str:
        """Sample function with default parameters.

        Args:
            a: First parameter
            b: Second parameter with default
            api_key: An API key with default value

        Returns:
            Combined string of all parameters

        """
        return f"{a}-{b}-{api_key}"

    return sample_fn


@pytest.fixture
def function_with_no_docstring():
    """Create a sample function without a docstring."""

    def sample_fn(a: int, b: str, api_key: str) -> str:
        return f"{a}-{b}-{api_key}"

    return sample_fn
