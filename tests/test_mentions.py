import unittest
import os
import sys
import tempfile
import shutil

# Add the root directory to sys.path to allow importing main
# Assuming tests are run from the project root or the tests directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the function to be tested
parse_and_load_mentions_func = None # Rename variable to avoid confusion
parse_arguments_func = None
import_error = None
try:
    # Try importing both functions needed
    from src.streetrace.main import parse_and_load_mentions, parse_arguments
    parse_and_load_mentions_func = parse_and_load_mentions
    parse_arguments_func = parse_arguments # Store it too
except ImportError as e:
    import_error = e # Store the error
    print(f"Failed to import from main: {e}")
    # Keep functions as None

class TestMentions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up temporary directories once for the class."""
        # Create a base directory for all test artifacts
        cls.base_temp_dir = tempfile.mkdtemp(prefix="streetrace_test_mentions_")
        cls.test_dir = os.path.join(cls.base_temp_dir, "workdir")
        cls.subdir = os.path.join(cls.test_dir, "subdir")
        cls.outside_dir = os.path.join(cls.base_temp_dir, "outside")

        os.makedirs(cls.subdir)
        os.makedirs(cls.outside_dir)

        # Create test files
        with open(os.path.join(cls.test_dir, "file1.txt"), "w") as f:
            f.write("Content of file1")
        with open(os.path.join(cls.subdir, "file2.py"), "w") as f:
            f.write("Content of file2")
        with open(os.path.join(cls.test_dir, "other.md"), "w") as f:
            f.write("Markdown content")
        with open(os.path.join(cls.outside_dir, "secret.txt"), "w") as f:
            f.write("Secret content")
        # File with special chars
        cls.special_filename = "file_with-hyphen.log"
        with open(os.path.join(cls.test_dir, cls.special_filename), "w") as f:
             f.write("Special chars file")

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary directories once after all tests."""
        # Add safety check in case base_temp_dir wasn't created
        if hasattr(cls, 'base_temp_dir') and os.path.exists(cls.base_temp_dir):
             shutil.rmtree(cls.base_temp_dir)

    def setUp(self):
        """Check if imports worked before running tests."""
        if parse_and_load_mentions_func is None:
             self.fail(f"Import of parse_and_load_mentions failed: {import_error}. Cannot run tests.")
        if parse_arguments_func is None:
             self.fail(f"Import of parse_arguments failed: {import_error}. Cannot run tests.")
        # Suppress print statements from the function under test during unit tests
        # This requires careful patching
        # For now, we'll allow the prints but they might clutter test output
        pass

    # --- Test methods using parse_and_load_mentions_func ---

    def test_no_mentions(self):
        prompt = "This is a regular prompt."
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(result, [])

    def test_one_valid_mention_root(self):
        prompt = "Please check @file1.txt for details."
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("file1.txt", "Content of file1"))

    def test_one_valid_mention_subdir(self):
        mention_path = os.path.join("subdir", "file2.py")
        prompt = f"Look at @{mention_path} implementation."
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (mention_path, "Content of file2"))

    def test_multiple_valid_mentions(self):
        mention_path_subdir = os.path.join("subdir", "file2.py")
        prompt = f"Compare @file1.txt and @{mention_path_subdir}."
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        print(f"Result: {result}")
        self.assertEqual(len(result), 2)
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2")
        ]
        self.assertCountEqual(result, expected)

    def test_duplicate_mentions(self):
        prompt = "Check @file1.txt and also @file1.txt again."
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("file1.txt", "Content of file1"))

    def test_mention_non_existent_file(self):
        prompt = "What about @nonexistent.txt?"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(result, [])

    def test_mention_directory(self):
        prompt = "Look in @subdir"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(result, [])

    def test_mixed_validity_mentions(self):
        mention_path_subdir = os.path.join("subdir", "file2.py")
        prompt = f"See @file1.txt and @nonexistent.md and @{mention_path_subdir}"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 2)
        expected = [
            ("file1.txt", "Content of file1"),
            (mention_path_subdir, "Content of file2")
        ]
        self.assertCountEqual(result, expected)

    def test_mention_outside_working_dir_relative(self):
        outside_file_path = os.path.join(self.outside_dir, "secret.txt")
        rel_path_to_outside = os.path.relpath(outside_file_path, self.test_dir)
        prompt = f"Trying to access @{rel_path_to_outside}"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(result, [], f"Security check failed for relative path: {rel_path_to_outside}")

    def test_mention_outside_working_dir_absolute(self):
        abs_path_to_secret = os.path.join(self.outside_dir, "secret.txt")
        prompt = f"Trying to access @{abs_path_to_secret}"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(result, [], f"Security check failed for absolute path: {abs_path_to_secret}")

    def test_mention_with_dot_slash(self):
        prompt = "Check @./file1.txt"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("./file1.txt", "Content of file1"))

    def test_mention_with_spaces_around(self):
        prompt = "Check  @file1.txt  now."
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("file1.txt", "Content of file1"))

    def test_mention_at_end_of_prompt(self):
        prompt = "The file is @other.md"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("other.md", "Markdown content"))

    def test_mention_special_chars_in_path(self):
        prompt = f"Look at @{self.special_filename}"
        result = parse_and_load_mentions_func(prompt, self.test_dir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (self.special_filename, "Special chars file"))


if __name__ == '__main__':
    # Ensure the script can find 'main.py' when run directly
    # Adjust path if necessary based on how tests are executed
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Re-check imports in case running the file directly works differently
    try:
        from src.streetrace.main import parse_and_load_mentions, parse_arguments
        parse_and_load_mentions_func = parse_and_load_mentions
        parse_arguments_func = parse_arguments
    except ImportError as e:
        print(f"Failed to import from main.py when running directly: {e}")
        sys.exit(1)

    # Assign the functions back for the tests to run if executed directly
    # Note: This is redundant if the top-level import worked, but safe.
    TestMentions.parse_and_load_mentions_func = parse_and_load_mentions_func
    TestMentions.parse_arguments_func = parse_arguments_func

    # Check again before running unittest.main()
    if TestMentions.parse_and_load_mentions_func is None or TestMentions.parse_arguments_func is None:
         print("Imports failed, cannot run tests.")
         sys.exit(1)

    unittest.main()
