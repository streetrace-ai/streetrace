"""Test suite for Anthropic provider.

This module runs all test cases for the Anthropic implementation.
"""

import unittest

from tests.llm.anthropic.test_converter import TestAnthropicHistoryConverter
from tests.llm.anthropic.test_impl import TestAnthropicImpl


def create_suite():
    """Create a test suite that includes all Anthropic tests."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Add all test cases from TestAnthropicHistoryConverter
    suite.addTest(loader.loadTestsFromTestCase(TestAnthropicHistoryConverter))

    # Add all test cases from TestAnthropicImpl
    suite.addTest(loader.loadTestsFromTestCase(TestAnthropicImpl))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(create_suite())
