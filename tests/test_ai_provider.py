"""
Unit tests for AI provider interface and factory.
"""

import unittest
import os
from unittest.mock import patch

from llm.llmapi import LLMAPI
from llm.claude import Claude
from llm.gemini.impl import Gemini
from llm.openai.impl import OpenAI
from llm.ollama.impl import Ollama
from llm.llmapi_factory import get_ai_provider


class TestAIProvider(unittest.TestCase):
    """Test cases for AI provider interface and factory."""

    def test_provider_implementations(self):
        """Verify that all provider implementations inherit from LLMAPI."""
        self.assertTrue(issubclass(Claude, LLMAPI))
        self.assertTrue(issubclass(Gemini, LLMAPI))
        self.assertTrue(issubclass(OpenAI, LLMAPI))
        self.assertTrue(issubclass(Ollama, LLMAPI))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}, clear=True)
    def test_get_provider_claude(self):
        """Test getting Claude provider when ANTHROPIC_API_KEY is set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, Claude)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True)
    def test_get_provider_gemini(self):
        """Test getting Gemini provider when GEMINI_API_KEY is set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, Gemini)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True)
    def test_get_provider_openai(self):
        """Test getting OpenAI provider when OPENAI_API_KEY is set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, OpenAI)

    @patch.dict(os.environ, {}, clear=True)
    def test_get_provider_ollama_default(self):
        """Test getting Ollama provider as default when no API keys are set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, Ollama)

    def test_get_provider_explicit(self):
        """Test explicitly requesting a specific provider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("claude")
            self.assertIsInstance(provider, Claude)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("gemini")
            self.assertIsInstance(provider, Gemini)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("openai")
            self.assertIsInstance(provider, OpenAI)

        provider = get_ai_provider("ollama")
        self.assertIsInstance(provider, Ollama)

    def test_get_provider_invalid(self):
        """Test requesting an invalid provider."""
        with self.assertRaises(ValueError):
            get_ai_provider("invalid_provider")

    def test_get_provider_missing_key(self):
        """Test requesting a provider without required API key."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                get_ai_provider("claude")

            with self.assertRaises(ValueError):
                get_ai_provider("gemini")

            with self.assertRaises(ValueError):
                get_ai_provider("openai")


if __name__ == '__main__':
    unittest.main()