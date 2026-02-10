"""Utility functions for DSL runtime operations.

Provide helper functions for common operations in DSL workflows,
including text normalization for comparison.
"""

import re

# Punctuation characters to remove during normalization
COMPARISON_PUNCTUATION = ".!?,;:"

# Pattern to match markdown modifiers (bold, italic, code, headers)
MARKDOWN_PATTERN = re.compile(r"[*_`#]+")

# Pattern to collapse multiple whitespace characters
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_for_comparison(text: str) -> str:
    """Normalize text for comparison by removing formatting noise.

    Apply the following transformations in order:
    1. Remove markdown modifiers (**, *, _, `, #)
    2. Remove punctuation (., !, ?, ,, ;, :)
    3. Convert to lowercase
    4. Strip leading/trailing whitespace
    5. Collapse multiple whitespace to single space

    Args:
        text: The text to normalize.

    Returns:
        Normalized text suitable for comparison.

    """
    # Remove markdown modifiers
    result = MARKDOWN_PATTERN.sub("", text)

    # Remove punctuation
    for char in COMPARISON_PUNCTUATION:
        result = result.replace(char, "")

    # Convert to lowercase
    result = result.lower()

    # Collapse whitespace and strip
    return WHITESPACE_PATTERN.sub(" ", result).strip()


def list_concat(left: object, right: object) -> object:
    """Concatenate two values, coercing to lists when needed.

    If both operands are lists, concatenate them directly.
    If one operand is a list and the other is not, wrap the non-list
    as a single-element list (unless it's None, which is skipped).
    If neither operand is a list, fall back to regular ``+``.

    Args:
        left: Left operand (often a list of findings).
        right: Right operand (agent result, may be list or scalar).

    Returns:
        Concatenated result.

    """
    if isinstance(left, list):
        if isinstance(right, list):
            return left + right
        if right is None:
            return left
        return [*left, right]
    if isinstance(right, list):
        if left is None:
            return right
        return [left, *right]
    return left + right  # type: ignore[operator]


def normalized_equals(left: object, right: object) -> bool:
    """Perform normalized equality comparison.

    Compare two values after normalizing them using normalize_for_comparison().
    Non-string values are converted to strings before normalization.

    Args:
        left: The left operand to compare.
        right: The right operand to compare.

    Returns:
        True if the normalized values are equal, False otherwise.

    """
    left_normalized = normalize_for_comparison(str(left))
    right_normalized = normalize_for_comparison(str(right))
    return left_normalized == right_normalized
