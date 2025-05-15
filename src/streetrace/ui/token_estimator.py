"""A prompt_toolkit Validator that estimates the number of tokens in given Document.

Can be injected into PromptSession.prompt to provide real time esitmates in rprompt.
"""

from collections.abc import Callable
from typing import override

from prompt_toolkit.document import Document
from prompt_toolkit.validation import Validator

from streetrace.llm_interface import LlmInterface


class TokenEstimatingValidator(Validator):
    """Estimate the number of tokens in the current prompt."""

    _llm: LlmInterface
    _set_count: Callable[[str], None] = None

    def __init__(self, llm: LlmInterface) -> None:
        """Provide the LlmInterface to use for token count estimation."""
        self._llm = llm

    def set_count(self, set_count: Callable[[int], None]) -> Validator:
        """Assign a callable that accepts the token count."""
        if not set_count or not callable(set_count):
            msg = "set_count must be a Callable[[str], None]"
            raise TypeError(msg)
        self._set_count = set_count
        return self

    @override
    def validate(self, doc: Document) -> None:
        """Estimate the number of tokens in the current prompt.

        Gets the token count from the provided LlmInterface and updates the
        rprompt of the provided PromptSession.

        Args:
            doc (Document): The typed prompt

        """
        if not self._llm or not self._set_count or not callable(self._set_count):
            return

        prompt = doc.text or ""
        estimated_tokens = self._llm.estimate_token_count(prompt)
        self._set_count(estimated_tokens)
