import unittest
import os
import tools.search as search


class TestSearchFiles(unittest.TestCase):

    def setUp(self):
        # Create dummy files for testing
        self.test_dir = 'test_files'
        os.makedirs(self.test_dir, exist_ok=True)
        self.file1_path = os.path.join(self.test_dir, 'file1.txt')
        self.file2_path = os.path.join(self.test_dir, 'file2.txt')
        with open(self.file1_path, 'w', encoding='utf-8') as f:
            f.write("This is the first file.\nIt contains some text.\nThis is a test.\n")
        with open(self.file2_path, 'w', encoding='utf-8') as f:
            f.write("This is the second file.\nIt has different content.\nAnother test here.\n")

    def tearDown(self):
        # Remove dummy files and directory
        os.remove(self.file1_path)
        os.remove(self.file2_path)
        os.rmdir(self.test_dir)

    def test_search_files_found(self):
        # Test when the search string is found in the files
        pattern = '*.txt'
        search_string = 'test'
        matches = search.search_files(pattern, search_string, root_dir=self.test_dir)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]['filepath'], self.file1_path)
        self.assertEqual(matches[1]['filepath'], self.file2_path)

    def test_search_files_not_found(self):
        # Test when the search string is not found in the files
        pattern = '*.txt'
        search_string = 'nonexistent'
        matches = search.search_files(pattern, search_string, root_dir=self.test_dir)
        self.assertEqual(len(matches), 0)

    def test_search_files_glob_pattern(self):
        # Test with a specific glob pattern
        pattern = 'file1.txt'
        search_string = 'first'
        matches = search.search_files(pattern, search_string, root_dir=self.test_dir)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['filepath'], self.file1_path)

    def test_search_files_empty_string(self):
        # Test with an empty search string
        pattern = '*.txt'
        search_string = ''
        matches = search.search_files(pattern, search_string, root_dir=self.test_dir)
        self.assertGreater(len(matches), 0)  # Assuming every line will match


if __name__ == '__main__':
    unittest.main()
