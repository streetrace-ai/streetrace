"""Tests for the utils package imports and basic functionality.

This test module verifies that the utils package correctly exposes its modules
and can be properly imported.
"""

from streetrace.utils import hide_args


class TestUtilsPackage:
    """Test suite for the utils package as a whole."""

    def test_hide_args_import(self):
        """Test that hide_args can be imported from the utils package."""
        # This test implicitly passes if the import statement works
        assert callable(hide_args)

    def test_package_public_api(self):
        """Test that expected functions are exposed in the utils package."""
        import streetrace.utils

        # Check that expected functions are available
        assert hasattr(streetrace.utils, "hide_args")
        # uid module functionality is intentionally not exposed directly
        # in the public API, but should be importable from its module

        from streetrace.utils import uid

        assert hasattr(uid, "get_user_identity")
