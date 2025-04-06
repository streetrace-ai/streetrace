"""
Unit tests for AI provider interface and factory.
"""

import unittest
import os
from unittest.mock import patch, MagicMock

from ai_interface import AIProvider
from claude_provider import ClaudeProvider
from gemini_provider import GeminiProvider
from openai_provider import OpenAIProvider
from ollama_provider import OllamaProvider
from ai_provider_factory import get_ai_provider, generate_with_tool


class TestAIProvider(unittest.TestCase):
    """Test cases for AI provider interface and factory."""

    def test_provider_implementations(self):
        """Verify that all provider implementations inherit from AIProvider."""
        self.assertTrue(issubclass(ClaudeProvider, AIProvider))
        self.assertTrue(issubclass(GeminiProvider, AIProvider))
        self.assertTrue(issubclass(OpenAIProvider, AIProvider))
        self.assertTrue(issubclass(OllamaProvider, AIProvider))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}, clear=True)
    def test_get_provider_claude(self):
        """Test getting Claude provider when ANTHROPIC_API_KEY is set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, ClaudeProvider)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True)
    def test_get_provider_gemini(self):
        """Test getting Gemini provider when GEMINI_API_KEY is set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, GeminiProvider)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True)
    def test_get_provider_openai(self):
        """Test getting OpenAI provider when OPENAI_API_KEY is set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, OpenAIProvider)

    @patch.dict(os.environ, {}, clear=True)
    def test_get_provider_ollama_default(self):
        """Test getting Ollama provider as default when no API keys are set."""
        provider = get_ai_provider()
        self.assertIsInstance(provider, OllamaProvider)

    def test_get_provider_explicit(self):
        """Test explicitly requesting a specific provider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("claude")
            self.assertIsInstance(provider, ClaudeProvider)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("gemini")
            self.assertIsInstance(provider, GeminiProvider)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True):
            provider = get_ai_provider("openai")
            self.assertIsInstance(provider, OpenAIProvider)

        provider = get_ai_provider("ollama")
        self.assertIsInstance(provider, OllamaProvider)

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