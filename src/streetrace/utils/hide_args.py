"""Utility function for modifying function signatures.

This module provides a decorator `hide_args` that allows hiding specific
keyword arguments from a function's signature and automatically injecting
them when the function is called. It's essential for StreetRace's tool
architecture, enabling clean interfaces for AI agents while maintaining
internal consistency.
"""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

TReturn = TypeVar("TReturn")


def hide_args[TReturn](
    fn: Callable[..., TReturn],
    **injected_kwargs: Any,
) -> Callable[..., TReturn]:
    """Get a wrapper that hides provided kwargs from the function signature.

    Attempts to remove Args from the docstring too, see impl for details.

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
        name: value for name, value in injected_kwargs.items() if name in sig.parameters
    }

    if not hidden_params:
        return fn  # No matching parameters to hide

    # Create a new signature and docstring that excludes the hidden ones
    new_params = [
        param for name, param in sig.parameters.items() if name not in hidden_params
    ]
    new_sig = sig.replace(parameters=new_params)
    new_doc = inspect.getdoc(fn) or ""
    if new_doc:
        doc_lines = new_doc.splitlines()
        filtered_lines = []
        skip_names = set(hidden_params.keys())

        for line in doc_lines:
            # Strip line for matching but preserve leading whitespace
            lstrip = line.lstrip()
            if any(
                lstrip.startswith((f"{param}:", f"{param} (", f":param {param}:"))
                for param in skip_names
            ):
                continue  # skip this line
            filtered_lines.append(line)

        new_doc = "\n".join(filtered_lines)

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> TReturn:
        bound_args = new_sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        all_args = dict(bound_args.arguments)
        all_args.update(hidden_params)
        return fn(**all_args)

    # Reflect modified signature
    wrapper.__signature__ = new_sig  # type: ignore[attr-defined]
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = new_doc

    return wrapper
