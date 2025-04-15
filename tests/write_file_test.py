import codecs
import os
import shutil
import tempfile
import unittest

from tools.read_file import read_file
from tools.write_file import write_file


class TestWriteFile(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.subdir = os.path.join(self.temp_dir, "subdir")

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def test_write_text_file(self):
        """Test writing a simple text file"""
        file_path = os.path.join(self.temp_dir, "test_file.txt")
        content = "This is a test file content."

        # Write the file
        result = write_file(file_path, content, self.temp_dir)
        self.assertEqual(result, file_path)

        # Verify the file was written correctly
        with open(file_path, "r") as f:
            read_content = f.read()
        self.assertEqual(read_content, content)

    def test_write_binary_file(self):
        """Test writing a binary file"""
        file_path = os.path.join(self.temp_dir, "test_binary.bin")
        content = b"\x00\x01\x02\x03\xff\xfe"

        # Write the binary file
        result = write_file(file_path, content, self.temp_dir, binary_mode=True)
        self.assertEqual(result, file_path)

        # Verify the file was written correctly
        with open(file_path, "rb") as f:
            read_content = f.read()
        self.assertEqual(read_content, content)

    def test_write_with_encoding(self):
        """Test writing a file with a specific encoding"""
        file_path = os.path.join(self.temp_dir, "test_latin1.txt")
        content = "Latin-1 text with special chars: é è ç"

        # Write with Latin-1 encoding
        result = write_file(file_path, content, self.temp_dir, encoding="latin-1")
        self.assertEqual(result, file_path)

        # Verify the file was written with correct encoding
        with codecs.open(file_path, "r", encoding="latin-1") as f:
            read_content = f.read()
        self.assertEqual(read_content, content)

    def test_create_directory(self):
        """Test that directories are created if they don't exist"""
        nested_path = os.path.join(self.temp_dir, "nested", "dirs", "file.txt")
        content = "File in nested directories"

        # This should create the necessary directories
        result = write_file(nested_path, content, self.temp_dir)
        self.assertEqual(result, nested_path)

        # Verify the file was written
        self.assertTrue(os.path.exists(nested_path))
        with open(nested_path, "r") as f:
            read_content = f.read()
        self.assertEqual(read_content, content)

    def test_security_restriction(self):
        """Test that writing outside work_dir is prevented"""
        # Try to write to a path outside the allowed root
        parent_dir = os.path.dirname(self.temp_dir)
        outside_path = os.path.join(parent_dir, "test_file.txt")

        with self.assertRaises(ValueError) as context:
            write_file(outside_path, "Should not write this", self.temp_dir)

        self.assertIn("Security error", str(context.exception))
        self.assertFalse(os.path.exists(outside_path))

    def test_type_checking(self):
        """Test type checking for content based on mode"""
        file_path = os.path.join(self.temp_dir, "test_type.txt")

        # Try to write bytes in text mode
        with self.assertRaises(TypeError):
            write_file(file_path, b"Bytes content", self.temp_dir, binary_mode=False)

        # Try to write text in binary mode
        with self.assertRaises(TypeError):
            write_file(file_path, "Text content", self.temp_dir, binary_mode=True)

    def test_round_trip(self):
        """Test writing and then reading back a file with special encoding"""
        file_path = os.path.join(self.temp_dir, "round_trip.txt")
        content = "Unicode text: こんにちは, 你好, Привет"
        encoding = "utf-8"

        # Write the file with specific encoding
        write_file(file_path, content, self.temp_dir, encoding=encoding)

        # Read it back with the same encoding
        read_content = read_file(file_path, self.temp_dir, encoding=encoding)

        # Verify content is preserved
        self.assertEqual(read_content, content)


if __name__ == "__main__":
    unittest.main()
