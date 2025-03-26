import pathspec
import unittest

from tools.read_directory_structure import is_ignored

# Unit tests for is_ignored
class TestIsIgnored(unittest.TestCase):
    def setUp(self):
        gitignore_content = 'ignored_file.txt\nignored_dir/'
        self.spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_content.splitlines())
        self.base_path = 'test_directory'

    def test_ignored_file(self):
        self.assertTrue(is_ignored('test_directory/ignored_file.txt', self.base_path, self.spec))

    def test_included_file(self):
        self.assertFalse(is_ignored('test_directory/included_file.txt', self.base_path, self.spec))

    def test_ignored_dir(self):
        self.assertTrue(is_ignored('test_directory/ignored_dir/', self.base_path, self.spec))

    def test_included_dir(self):
        self.assertFalse(is_ignored('test_directory/included_dir/', self.base_path, self.spec))


if __name__ == '__main__':
    unittest.main()
