"""Tests for the hide_args decorator utility.

This test module verifies that the hide_args decorator correctly modifies function
signatures to hide specified parameters and automatically injects them when the
function is called.
"""

import inspect

from streetrace.utils.hide_args import hide_args


class TestHideArgs:
    """Test suite for the hide_args decorator."""

    def test_hide_args_signature_modification(self, example_function):
        """Test that hide_args removes specified parameters from the signature."""
        # Original function has 4 parameters
        orig_sig = inspect.signature(example_function)
        assert len(orig_sig.parameters) == 4
        assert "sensitive" in orig_sig.parameters
        assert "api_key" in orig_sig.parameters

        # Create wrapped function with hidden parameters
        wrapped = hide_args(example_function, sensitive="hidden", api_key="secret-key")

        # Verify signature is modified
        new_sig = inspect.signature(wrapped)
        assert len(new_sig.parameters) == 2
        assert "a" in new_sig.parameters
        assert "b" in new_sig.parameters
        assert "sensitive" not in new_sig.parameters
        assert "api_key" not in new_sig.parameters

    def test_hide_args_docstring_modification(self, example_function):
        """Test that hide_args removes parameter documentation for hidden parameters."""
        # Original function has documentation for all parameters
        orig_doc = inspect.getdoc(example_function)
        assert orig_doc
        assert "sensitive: A sensitive parameter" in orig_doc
        assert "api_key: An API key" in orig_doc

        # Create wrapped function
        wrapped = hide_args(example_function, sensitive="hidden", api_key="secret-key")

        # Verify docstring is modified
        new_doc = inspect.getdoc(wrapped)
        assert new_doc
        assert "a: First parameter" in new_doc
        assert "b: Second parameter" in new_doc
        assert "sensitive: A sensitive parameter" not in new_doc
        assert "api_key: An API key" not in new_doc

    def test_hide_args_behavior(self, example_function):
        """Test that the wrapped function correctly injects hidden parameters."""
        # Create wrapped function
        wrapped = hide_args(example_function, sensitive="hidden", api_key="secret-key")

        # Call wrapped function without hidden parameters
        result = wrapped(1, "test")

        # Verify hidden parameters were injected
        assert result == "1-test-hidden-secret-key"

        # NOTE: The implementation doesn't allow overriding hidden parameters
        # from the outside since they're not part of the public signature anymore.
        # This is the expected behavior.

    def test_hide_args_with_no_matching_params(self, example_function):
        """Test that hide_args returns original function when no parameters match."""
        # Create wrapped function with non-matching parameters
        wrapped = hide_args(example_function, non_existent="value")

        # Verify wrapped function is identical to original
        assert wrapped is example_function

    def test_hide_args_with_defaults(self, sample_function_with_defaults):
        """Test that hide_args works with functions having default parameters."""
        # Create wrapped function
        wrapped = hide_args(sample_function_with_defaults, api_key="new-key")

        # Call with only required parameters
        result = wrapped(1)

        # Verify default for 'b' and injected value for 'api_key'
        assert result == "1-default-new-key"

        # Call with explicit value for 'b'
        result = wrapped(1, "explicit")
        assert result == "1-explicit-new-key"

    def test_hide_args_with_no_docstring(self, function_with_no_docstring):
        """Test that hide_args works correctly with functions having no docstring."""
        # Create wrapped function
        wrapped = hide_args(function_with_no_docstring, api_key="secret-key")

        # Verify function still works
        result = wrapped(1, "test")
        assert result == "1-test-secret-key"

        # Verify signature is modified
        new_sig = inspect.signature(wrapped)
        assert "api_key" not in new_sig.parameters

    def test_hide_args_preserves_function_name(self, example_function):
        """Test that hide_args preserves the original function name."""
        original_name = example_function.__name__
        wrapped = hide_args(example_function, sensitive="hidden")
        assert wrapped.__name__ == original_name

    def test_hide_args_with_partial_params(self, example_function):
        """Test that hide_args works when hiding only some of the parameters."""
        # Hide only one parameter
        wrapped = hide_args(example_function, sensitive="hidden")

        # Verify only one parameter is hidden
        new_sig = inspect.signature(wrapped)
        assert len(new_sig.parameters) == 3
        assert "sensitive" not in new_sig.parameters
        assert "api_key" in new_sig.parameters

        # Call function with visible parameters
        result = wrapped(1, "test", api_key="visible-key")
        assert result == "1-test-hidden-visible-key"

    def test_original_function_still_works(self, example_function):
        """Test that the original function still works normally after wrapping."""
        # Create wrapped function
        _ = hide_args(example_function, sensitive="hidden", api_key="secret-key")

        # Call original function with all parameters
        result = example_function(1, "test", "original-sensitive", "original-key")

        # Verify original function works normally
        assert result == "1-test-original-sensitive-original-key"
