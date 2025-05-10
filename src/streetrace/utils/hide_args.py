"""Utility function for modifying function signatures.

This module provides a decorator `hide_args` that allows hiding specific
keyword arguments from a function's signature and automatically injecting
them when the function is called.
"""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any


def hide_args(fn: Callable, **injected_kwargs: Any) -> Callable:
    """Get a wrapper that hides provided kwargs from the function signature.

    The hidden args will be substituted with the provided values when calling
    the wrapper.

    Args:
        fn: The original function to wrap.
        injected_kwargs: Parameter names and values to hide and auto-inject.

    Returns:
        A callable with a modified signature and injected arguments.

    """
    sig = inspect.signature(fn)

    # Identify which injected parameters actually exist in the function signature
    hidden_params = {
        name: value for name, value in injected_kwargs.items()
        if name in sig.parameters
    }

    if not hidden_params:
        return fn  # No matching parameters to hide

    # Create a new signature that excludes the hidden ones
    new_params = [
        param for name, param in sig.parameters.items()
        if name not in hidden_params
    ]
    new_sig = sig.replace(parameters=new_params)

    @wraps(fn)
    def wrapper(*args, **kwargs) -> Callable:
        bound_args = new_sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        all_args = dict(bound_args.arguments)
        all_args.update(hidden_params)
        return fn(**all_args)

    # Reflect modified signature
    wrapper.__signature__ = new_sig

    # Optional: enforce the name just in case
    wrapper.__name__ = fn.__name__
    return wrapper
