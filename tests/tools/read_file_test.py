import codecs
import os
import platform
import shutil
import tempfile
import unittest

from streetrace.tools.read_file import read_file


class TestReadFile(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()
        self.subdir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(self.subdir, exist_ok=True)

        # Create test files with different content
        self.root_file_path = os.path.join(self.temp_dir, "root_file.txt")
        self.subdir_file_path = os.path.join(self.subdir, "subdir_file.txt")
        self.empty_file_path = os.path.join(self.temp_dir, "empty_file.txt")
        self.binary_file_path = os.path.join(self.temp_dir, "binary_file.bin")
        self.utf8_file_path = os.path.join(self.temp_dir, "utf8_file.txt")
        self.special_chars_path = os.path.join(
            self.temp_dir, "file with spaces & special chars.txt"
        )

        # Content strings
        self.root_content = "This is content in the root file."
        self.subdir_content = "This is content in the subdirectory file."
        self.utf8_content = "Unicode text: こんにちは, 你好, Привет"
        self.special_chars_content = "File with special characters in the name."

        # Write content to files
        with open(self.root_file_path, "w") as f:
            f.write(self.root_content)

        with open(self.subdir_file_path, "w") as f:
            f.write(self.subdir_content)

        # Create an empty file
        open(self.empty_file_path, "w").close()

        # Create a binary file
        with open(self.binary_file_path, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04")

        # Create a UTF-8 file with non-ASCII characters
        with codecs.open(self.utf8_file_path, "w", encoding="utf-8") as f:
            f.write(self.utf8_content)

        # Create a file with special characters in the name
        with open(self.special_chars_path, "w") as f:
            f.write(self.special_chars_content)

        # Create a symlink if the platform supports it
        self.symlink_supported = True
        self.symlink_path = os.path.join(self.temp_dir, "symlink.txt")
        try:
            os.symlink(self.root_file_path, self.symlink_path)
        except (OSError, AttributeError):
            # Symlinks not supported on this platform or with these permissions
            self.symlink_supported = False

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_read_file_content(self):
        """Test reading file content correctly"""
        # Read from the root file
        content, msg = read_file(self.root_file_path, self.temp_dir)
        self.assertEqual(content, self.root_content)
        self.assertTrue("bytes read" in msg)

        # Read from subdirectory file
        content, msg = read_file(self.subdir_file_path, self.temp_dir)
        self.assertEqual(content, self.subdir_content)
        self.assertTrue("bytes read" in msg)

        # Read empty file
        content, msg = read_file(self.empty_file_path, self.temp_dir)
        self.assertEqual(content, "")
        self.assertEqual(msg, "0 bytes read")

    def test_nested_file_security(self):
        """Test reading a file in a subdirectory"""
        # Using the parent directory as root, we should be able to read the nested file
        content, _ = read_file(self.subdir_file_path, self.temp_dir)
        self.assertEqual(content, self.subdir_content)

        # Using the subdirectory as root, we should still be able to read that file
        content, _ = read_file(self.subdir_file_path, self.subdir)
        self.assertEqual(content, self.subdir_content)

    def test_directory_traversal_prevention(self):
        """Test that directory traversal attempts are blocked"""
        # Attempt to access a file outside work_dir using relative path (parent directory traversal)
        parent_dir = os.path.dirname(self.temp_dir)
        with self.assertRaises(ValueError) as context:
            # Create a path that attempts to go up and out of the allowed directory
            traversal_path = os.path.join(
                self.subdir, "..", "..", os.path.basename(parent_dir), "some_file.txt"
            )
            read_file(traversal_path, self.temp_dir)

        self.assertIn("Security error", str(context.exception))

        # Attempt to access a file outside work_dir using absolute path
        with self.assertRaises(ValueError) as context:
            # Directly try to access a path outside the temp directory
            outside_path = os.path.join(parent_dir, "some_file.txt")
            read_file(outside_path, self.temp_dir)

        self.assertIn("Security error", str(context.exception))

    def test_nonexistent_file(self):
        """Test reading a nonexistent file"""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent_file.txt")
        with self.assertRaises(ValueError) as context:
            read_file(nonexistent_path, self.temp_dir)

        self.assertIn("File not found", str(context.exception))

    def test_directory_as_file(self):
        """Test attempting to read a directory as a file"""
        with self.assertRaises(ValueError) as context:
            read_file(self.subdir, self.temp_dir)

        self.assertIn("Path is not a file", str(context.exception))

    def test_utf8_file(self):
        """Test reading a file with UTF-8 encoded text"""
        content, _ = read_file(self.utf8_file_path, self.temp_dir)
        self.assertEqual(content, self.utf8_content)

    def test_special_chars_in_filename(self):
        """Test reading a file with special characters in the filename"""
        content, _ = read_file(self.special_chars_path, self.temp_dir)
        self.assertEqual(content, self.special_chars_content)

    def test_symlink(self):
        """Test reading through a symbolic link if supported"""
        if not self.symlink_supported:
            self.skipTest("Symbolic links not supported on this platform")

        content, _ = read_file(self.symlink_path, self.temp_dir)
        self.assertEqual(content, self.root_content)

    def test_path_normalization(self):
        """Test path normalization with dot segments"""
        # Create paths with . and .. segments that resolve within the allowed area
        dot_path = os.path.join(self.temp_dir, ".", "root_file.txt")
        dotdot_path = os.path.join(self.temp_dir, "subdir", "..", "root_file.txt")

        # Both should read the same file
        content1, _ = read_file(dot_path, self.temp_dir)
        content2, _ = read_file(dotdot_path, self.temp_dir)

        self.assertEqual(content1, self.root_content)
        self.assertEqual(content2, self.root_content)

    def test_binary_file(self):
        """Test reading a binary file"""
        # Create a more complex binary file that will definitely fail in text mode
        binary_data = (
            bytes([0, 159, 146, 150]) + b"\x00\xff\xfe\x7f"
        )  # Include invalid UTF-8 sequences
        with open(self.binary_file_path, "wb") as f:
            f.write(binary_data)

        # Reading should return "<binary>"
        content = read_file(self.binary_file_path, self.temp_dir)
        self.assertEqual(content, "<binary>")

    def test_custom_encoding(self):
        """Test reading a file with a specific encoding"""
        # Write a file with Latin-1 encoding
        latin1_path = os.path.join(self.temp_dir, "latin1.txt")
        latin1_content = "Latin-1 text with special chars: é è ç"
        with codecs.open(latin1_path, "w", encoding="latin-1") as f:
            f.write(latin1_content)

        # Read with correct encoding
        content, _ = read_file(latin1_path, self.temp_dir, encoding="latin-1")
        self.assertEqual(content, latin1_content)

    def test_auto_detect_binary(self):
        """Test auto-detection of binary files"""
        # Create a binary file with null bytes and other binary data
        binary_data = bytes([0, 159, 146, 150]) + b"\x00\xff\xfe\x7f"
        with open(self.binary_file_path, "wb") as f:
            f.write(binary_data)

        # Auto-detect should identify this as binary and return "<binary>"
        # Note: read_file now returns tuple or <binary>, check the return type
        result = read_file(self.binary_file_path, self.temp_dir)
        self.assertEqual(result, "<binary>")

        # Create a text file that looks like a binary file (has many special chars)
        text_with_special_chars = "'.;○□♣♠☻☺ High proportion of special chars"
        special_chars_path = os.path.join(self.temp_dir, "special_chars.txt")
        with open(special_chars_path, "w", encoding="utf-8") as f:
            f.write(text_with_special_chars)

        # This file should not be detected as binary
        content, _ = read_file(special_chars_path, self.temp_dir)
        self.assertEqual(content, text_with_special_chars)

    def test_auto_detect_binary_with_text_file(self):
        """Test auto-detection doesn't falsely identify text files as binary"""
        # Regular text file should not be detected as binary
        content, _ = read_file(self.root_file_path, self.temp_dir)
        self.assertEqual(content, self.root_content)

        # Empty file should not be detected as binary
        content, _ = read_file(self.empty_file_path, self.temp_dir)
        self.assertEqual(content, "")


if __name__ == "__main__":
    unittest.main()
