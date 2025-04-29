"""Test suite for Claude provider.

This module runs all test cases for the Claude implementation.
"""

import unittest

from tests.llm.claude.test_converter import TestAnthropicHistoryConverter
from tests.llm.claude.test_impl import TestClaudeImpl


def create_suite():
    """Create a test suite that includes all Claude tests."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Add all test cases from TestAnthropicHistoryConverter
    suite.addTest(loader.loadTestsFromTestCase(TestAnthropicHistoryConverter))

    # Add all test cases from TestClaudeImpl
    suite.addTest(loader.loadTestsFromTestCase(TestClaudeImpl))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(create_suite())
