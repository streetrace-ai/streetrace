"""Test suite for all Ollama implementation tests.

This module provides a test suite that runs all tests for the Ollama implementation.
"""

import unittest

from tests.llm.ollama.test_converter import TestOllamaHistoryConverter
from tests.llm.ollama.test_impl import TestOllamaImpl


def suite():
    """Create a test suite for all Ollama tests."""
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Add tests from TestGeminiHistoryConverter
    test_suite.addTest(loader.loadTestsFromTestCase(TestOllamaHistoryConverter))

    # Add tests from TestGeminiImpl
    test_suite.addTest(loader.loadTestsFromTestCase(TestOllamaImpl))

    return test_suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
