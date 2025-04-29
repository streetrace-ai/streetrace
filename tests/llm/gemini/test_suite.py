"""Test suite for all Gemini implementation tests.

This module provides a test suite that runs all tests for the Gemini implementation.
"""

import unittest

from tests.llm.gemini.test_converter import TestGeminiHistoryConverter
from tests.llm.gemini.test_impl import TestGeminiImpl


def suite():
    """Create a test suite for all Gemini tests."""
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Add tests from TestGeminiHistoryConverter
    test_suite.addTest(loader.loadTestsFromTestCase(TestGeminiHistoryConverter))

    # Add tests from TestGeminiImpl
    test_suite.addTest(loader.loadTestsFromTestCase(TestGeminiImpl))

    return test_suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())