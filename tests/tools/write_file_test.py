import codecs
import os
import shutil
import tempfile
import unittest

import pytest

# Assuming read_file also returns a tuple (content, msg)
from streetrace.tools.read_file import read_file
from streetrace.tools.write_file import write_file


class TestWriteFile(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        # Store relative paths for assertions
        self.test_file_rel = "test_file.txt"
        self.test_binary_rel = "test_binary.bin"
        self.test_latin1_rel = "test_latin1.txt"
        self.nested_file_rel = os.path.join("nested", "dirs", "file.txt")
        self.test_type_rel = "test_type.txt"
        self.round_trip_rel = "round_trip.txt"

    def tearDown(self) -> None:
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_write_text_file(self) -> None:
        """Test writing a simple text file."""
        abs_path = os.path.join(self.temp_dir, self.test_file_rel)
        content = "This is a test file content."

        # Write the file
        rel_path, diff_msg = write_file(abs_path, content, self.temp_dir)
        assert rel_path == self.test_file_rel
        assert "File created" in diff_msg

        # Verify the file was written correctly
        with open(abs_path) as f:
            read_content = f.read()
        assert read_content == content

    def test_write_binary_file(self) -> None:
        """Test writing a binary file."""
        abs_path = os.path.join(self.temp_dir, self.test_binary_rel)
        content = b"\x00\x01\x02\x03\xff\xfe"

        # Write the binary file
        rel_path, diff_msg = write_file(
            abs_path,
            content,
            self.temp_dir,
            binary_mode=True,
        )
        assert rel_path == self.test_binary_rel
        assert "Binary file written" in diff_msg
        assert "6 bytes" in diff_msg

        # Verify the file was written correctly
        with open(abs_path, "rb") as f:
            read_content = f.read()
        assert read_content == content

    def test_write_with_encoding(self) -> None:
        """Test writing a file with a specific encoding."""
        abs_path = os.path.join(self.temp_dir, self.test_latin1_rel)
        content = "Latin-1 text with special chars: é è ç"

        # Write with Latin-1 encoding
        rel_path, diff_msg = write_file(
            abs_path,
            content,
            self.temp_dir,
            encoding="latin-1",
        )
        assert rel_path == self.test_latin1_rel
        assert "File created" in diff_msg

        # Verify the file was written with correct encoding
        with codecs.open(abs_path, "r", encoding="latin-1") as f:
            read_content = f.read()
        assert read_content == content

    def test_create_directory(self) -> None:
        """Test that directories are created if they don't exist."""
        abs_path = os.path.join(self.temp_dir, self.nested_file_rel)
        content = "File in nested directories"

        # This should create the necessary directories
        rel_path, diff_msg = write_file(abs_path, content, self.temp_dir)
        assert rel_path == self.nested_file_rel
        assert "File created" in diff_msg

        # Verify the file was written
        assert os.path.exists(abs_path)
        with open(abs_path) as f:
            read_content = f.read()
        assert read_content == content

    def test_security_restriction(self) -> None:
        """Test that writing outside work_dir is prevented."""
        # Try to write to a path outside the allowed root
        parent_dir = os.path.dirname(self.temp_dir)
        # Use an absolute path outside temp_dir to be sure
        outside_path = os.path.abspath(os.path.join(parent_dir, "outside_file.txt"))

        with pytest.raises(ValueError) as context:
            write_file(outside_path, "Should not write this", self.temp_dir)

        assert "Security error" in str(context.value)
        # Updated assertion message
        assert "outside the allowed working directory" in str(context.value)
        assert not os.path.exists(outside_path)

    def test_type_checking(self) -> None:
        """Test type checking for content based on mode."""
        abs_path = os.path.join(self.temp_dir, self.test_type_rel)

        # Try to write bytes in text mode
        with pytest.raises(TypeError, match="Content must be str when binary_mode is False"):
            write_file(abs_path, b"Bytes content", self.temp_dir, binary_mode=False)

        # Try to write text in binary mode
        with pytest.raises(TypeError, match="Content must be bytes when binary_mode is True"):
            write_file(abs_path, "Text content", self.temp_dir, binary_mode=True)

    def test_round_trip(self) -> None:
        """Test writing and then reading back a file with special encoding."""
        abs_path = os.path.join(self.temp_dir, self.round_trip_rel)
        content = "Unicode text: こんにちは, 你好, Привет"
        encoding = "utf-8"

        # Write the file with specific encoding
        write_file(abs_path, content, self.temp_dir, encoding=encoding)

        # Read it back with the same encoding using the read_file function
        # Assuming read_file returns (content, msg)
        read_content, read_msg = read_file(abs_path, self.temp_dir, encoding=encoding)

        # Verify content is preserved
        assert read_content == content
        assert "bytes read" in read_msg

    def test_overwrite_file_diff(self) -> None:
        """Test overwriting a file and checking the diff message."""
        abs_path = os.path.join(self.temp_dir, self.test_file_rel)
        initial_content = "Line 1\nLine 2\nLine 3"
        new_content = "Line 1\nLine Two\nLine 3"

        # Write initial content
        _, create_msg = write_file(abs_path, initial_content, self.temp_dir)
        assert "File created" in create_msg

        # Write new content
        rel_path, diff_msg = write_file(abs_path, new_content, self.temp_dir)
        assert rel_path == self.test_file_rel

        # Verify diff message indicates change
        assert "--- " in diff_msg
        assert "+++ " in diff_msg
        assert "-Line 2" in diff_msg
        assert "+Line Two" in diff_msg

        # Verify content was updated
        read_content, _ = read_file(abs_path, self.temp_dir)
        assert read_content == new_content

    def test_write_identical_content(self) -> None:
        """Test writing the same content results in an 'unchanged' message."""
        abs_path = os.path.join(self.temp_dir, self.test_file_rel)
        content = "Identical content."

        # Write initial content
        _, create_msg = write_file(abs_path, content, self.temp_dir)
        assert "File created" in create_msg

        # Write the same content again
        rel_path, diff_msg = write_file(abs_path, content, self.temp_dir)
        assert rel_path == self.test_file_rel
        assert "File content unchanged" in diff_msg


if __name__ == "__main__":
    unittest.main()
