import os
import tempfile
import unittest
import shutil

from tools.read_directory_structure import read_directory_structure

class TestReadDirectoryStructureGlob(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_subdir = os.path.join(self.temp_dir, 'subdir')
        self.temp_nested_subdir = os.path.join(self.temp_subdir, 'nested')
        
        # Create directories
        os.makedirs(self.temp_subdir, exist_ok=True)
        os.makedirs(self.temp_nested_subdir, exist_ok=True)
        
        # Create files at different levels
        self.root_file1 = os.path.join(self.temp_dir, 'root_file1.txt')
        self.root_file2 = os.path.join(self.temp_dir, 'root_file2.log')
        self.subdir_file = os.path.join(self.temp_subdir, 'subdir_file.txt')
        self.nested_file = os.path.join(self.temp_nested_subdir, 'nested_file.txt')
        
        # Write some content to the files
        for file_path in [self.root_file1, self.root_file2, self.subdir_file, self.nested_file]:
            with open(file_path, 'w') as f:
                f.write('test content')
                
    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
        
    def test_non_recursive_listing(self):
        """Test that the function only lists current directory level"""
        # Use the same path for both parameters to pass security check
        result = read_directory_structure(self.temp_dir, self.temp_dir)
        
        # Should contain both files in the root and the subdir
        expected_files = [os.path.basename(self.root_file1), os.path.basename(self.root_file2)]
        expected_dirs = [os.path.basename(self.temp_subdir)]
        
        # Sort expected results for comparison
        expected_files.sort()
        expected_dirs.sort()
        
        # Convert actual results to basenames for comparison
        actual_files = [os.path.basename(f) for f in result['files']]
        actual_dirs = [os.path.basename(d) for d in result['dirs']]
        
        self.assertEqual(set(expected_files), set(actual_files))
        self.assertEqual(set(expected_dirs), set(actual_dirs))
        
        # Files from nested directories should not be included
        nested_basenames = [os.path.basename(self.nested_file), os.path.basename(self.subdir_file)]
        for basename in nested_basenames:
            self.assertNotIn(basename, actual_files)
            
    def test_relative_paths(self):
        """Test that paths are returned relative to root_path"""
        # Set root_path to parent of temp_dir
        parent_dir = os.path.dirname(self.temp_dir)
        result = read_directory_structure(self.temp_dir, parent_dir)
        
        # All paths should be relative to parent_dir
        temp_dir_basename = os.path.basename(self.temp_dir)
        
        for file_path in result['files']:
            self.assertTrue(file_path.startswith(temp_dir_basename))
            
        for dir_path in result['dirs']:
            self.assertTrue(dir_path.startswith(temp_dir_basename))
            
    def test_subdirectory_listing(self):
        """Test listing a subdirectory"""
        result = read_directory_structure(self.temp_subdir, self.temp_dir)
        
        # Should only contain the nested subdir and subdir_file
        self.assertEqual(len(result['dirs']), 1)
        self.assertEqual(len(result['files']), 1)
        
        self.assertEqual(os.path.basename(result['dirs'][0]), os.path.basename(self.temp_nested_subdir))
        self.assertEqual(os.path.basename(result['files'][0]), os.path.basename(self.subdir_file))
        
    def test_gitignore_respect(self):
        """Test that gitignore patterns are respected"""
        # Create a .gitignore file that ignores .log files
        gitignore_path = os.path.join(self.temp_dir, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('*.log\n')
            
        # Use the same path for both parameters to pass security check
        result = read_directory_structure(self.temp_dir, self.temp_dir)
        
        # .log files should be excluded
        for file_path in result['files']:
            self.assertFalse(file_path.endswith('.log'))
            
        # But .txt files should be included
        txt_files = [f for f in result['files'] if f.endswith('.txt')]
        self.assertTrue(len(txt_files) > 0)
        
    def test_security_check(self):
        """Test that security checks prevent directory traversal"""
        # Attempt to access parent directory
        with self.assertRaises(ValueError) as context:
            read_directory_structure(os.path.dirname(self.temp_dir), self.temp_dir)
            
        self.assertIn("Security error", str(context.exception))


if __name__ == '__main__':
    unittest.main() 