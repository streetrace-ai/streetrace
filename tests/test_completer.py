import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText, to_plain_text

from streetrace.completer import PathCompleter, CommandCompleter, PromptCompleter

# Store original os functions
original_os_path_abspath = os.path.abspath
original_os_path_join = os.path.join
original_os_path_normpath = os.path.normpath
original_os_path_relpath = os.path.relpath
original_os_path_isdir = os.path.isdir
original_os_listdir = os.listdir

# Helper function to simplify getting completion texts
def get_completion_texts(completer, text, cursor_offset=0):
    # CommandCompleter now uses document.text, not just text_before_cursor
    doc = Document(text, len(text) + cursor_offset) 
    completions = list(completer.get_completions(doc, MagicMock()))
    return sorted([c.text for c in completions])

# Helper function to simplify getting completion displays
def get_completion_displays(completer, text, cursor_offset=0):
    doc = Document(text, len(text) + cursor_offset)
    completions = list(completer.get_completions(doc, MagicMock()))
    displays = []
    for c in completions:
        display_val = getattr(c, 'display', '')
        displays.append(to_plain_text(display_val))
    return sorted(displays)

class TestPathCompleter(unittest.TestCase):
    # These tests remain the same as PathCompleter logic is stable
    @patch('os.path.isdir')
    @patch('os.listdir')
    @patch('os.path.abspath')
    @patch('os.path.join')
    @patch('os.path.relpath')
    def test_complete_root_files_and_dirs(self, mock_relpath, mock_join, mock_abspath, mock_listdir, mock_isdir):
        working_dir = "/fake/work"
        src_dir_path = original_os_path_join(working_dir, "src")
        readme_path = original_os_path_join(working_dir, "README.md")
        hidden_path = original_os_path_join(working_dir, ".hiddenfile")
        mock_isdir.side_effect = lambda p: original_os_path_normpath(p) in [working_dir, src_dir_path]
        mock_listdir.side_effect = lambda p: ["README.md", "src", ".hiddenfile"] if original_os_path_normpath(p) == working_dir else []
        mock_abspath.return_value = working_dir
        mock_join.side_effect = original_os_path_join
        def relpath_side_effect(p, start):
             if start != working_dir: raise ValueError(f"Unexpected start path: {start}")
             norm_p = original_os_path_normpath(p)
             if norm_p == readme_path: return "README.md"
             if norm_p == src_dir_path: return "src"
             if norm_p == hidden_path: return ".hiddenfile"
             raise ValueError(f"Unexpected path: {p}")
        mock_relpath.side_effect = relpath_side_effect
        completer = PathCompleter(working_dir)
        self.assertEqual(completer.working_dir, working_dir)
        self.assertEqual(get_completion_texts(completer, '@'), ['README.md', 'src/'])
        self.assertEqual(get_completion_texts(completer, '@R'), ['README.md'])
        self.assertEqual(get_completion_texts(completer, '@s'), ['src/'])
        self.assertEqual(get_completion_texts(completer, '@.'), ['.hiddenfile'])
        self.assertEqual(get_completion_displays(completer, '@'), ['README.md', 'src/'])

    @patch('os.path.isdir')
    @patch('os.listdir')
    @patch('os.path.abspath')
    @patch('os.path.join')
    @patch('os.path.relpath')
    def test_complete_subdirectory(self, mock_relpath, mock_join, mock_abspath, mock_listdir, mock_isdir):
        working_dir = "/fake/work"
        src_dir = original_os_path_join(working_dir, "src")
        main_py_path = original_os_path_join(src_dir, "main.py")
        mock_isdir.side_effect = lambda p: original_os_path_normpath(p) in [working_dir, src_dir]
        def abspath_side_effect(path):
            if path == working_dir: return working_dir
            if path == src_dir: return src_dir
            if path == original_os_path_join(working_dir, 'src'): return src_dir
            if path == '.': return working_dir
            return original_os_path_abspath(path)
        mock_abspath.side_effect = abspath_side_effect
        def listdir_side_effect_subdir(path):
            norm_path = original_os_path_normpath(path)
            if norm_path == src_dir: return ["main.py"]
            if norm_path == working_dir: return ["src"]
            return []
        mock_listdir.side_effect = listdir_side_effect_subdir
        mock_join.side_effect = original_os_path_join
        mock_relpath.side_effect = lambda p, start: "src/main.py" if p == main_py_path and start == working_dir else original_os_path_relpath(p, start).replace('\\', '/')
        completer = PathCompleter(working_dir)
        self.assertEqual(completer.working_dir, working_dir)
        self.assertEqual(get_completion_texts(completer, '@src/'), ['src/main.py'])
        self.assertEqual(get_completion_displays(completer, '@src/'), ['main.py'])
        self.assertEqual(get_completion_texts(completer, '@src/m'), ['src/main.py'])
        self.assertEqual(get_completion_displays(completer, '@src/m'), ['main.py'])

    @patch('os.path.isdir')
    def test_invalid_working_dir(self, mock_isdir):
        mock_isdir.return_value = False
        with patch('builtins.print') as mock_print:
            with patch('os.path.abspath', lambda p: "/current/dir" if p == "." else original_os_path_abspath(p)) as mock_abspath_fallback:
                completer = PathCompleter("/invalid/dir")
                mock_isdir.assert_called_with("/invalid/dir")
                self.assertEqual(mock_abspath_fallback('.'), "/current/dir")
                mock_print.assert_called_once()
                self.assertEqual(completer.working_dir, "/current/dir")


class TestCommandCompleter(unittest.TestCase):
    # Updated tests for new CommandCompleter logic
    def test_complete_commands_strict(self):
        """Test completion only when command is the only input (trimmed)."""
        commands = ["/exit", "/help", "/history"]
        completer = CommandCompleter(commands)
        # Valid cases
        self.assertEqual(get_completion_texts(completer, '/'), ['/exit', '/help', '/history'])
        self.assertEqual(get_completion_texts(completer, '  /h  '), ['/help', '/history']) # Whitespace OK
        self.assertEqual(get_completion_texts(completer, '/hist'), ['/history'])
        self.assertEqual(get_completion_texts(completer, '/exit'), ['/exit'])
        self.assertEqual(get_completion_texts(completer, ''), []) # Empty is not / command
        
        # Invalid cases (command not the only thing)
        self.assertEqual(get_completion_texts(completer, 'exit'), []) # Not command format
        self.assertEqual(get_completion_texts(completer, 'word /h'), []) # Command not alone
        self.assertEqual(get_completion_texts(completer, '/help me'), []) # Command not alone
        self.assertEqual(get_completion_texts(completer, ' /help abc '), []) # Command not alone (even with whitespace)


class TestPromptCompleterComposition(unittest.TestCase):
    # Tests remain the same as PromptCompleter delegates based on internal logic of children
    def setUp(self):
        self.mock_path_completer = MagicMock(spec=PathCompleter)
        self.mock_command_completer = MagicMock(spec=CommandCompleter)
        self.prompt_completer = PromptCompleter([self.mock_path_completer, self.mock_command_completer])

    def test_calls_both_delegates(self):
        doc = Document('some text', len('some text'))
        event = MagicMock()
        self.mock_path_completer.get_completions.return_value = iter([Completion('path_comp')])
        self.mock_command_completer.get_completions.return_value = iter([Completion('cmd_comp')])
        completions = list(self.prompt_completer.get_completions(doc, event))
        self.mock_path_completer.get_completions.assert_called_once_with(doc, event)
        self.mock_command_completer.get_completions.assert_called_once_with(doc, event)
        completion_texts = sorted([c.text for c in completions])
        self.assertEqual(completion_texts, ['cmd_comp', 'path_comp'])

    def test_works_if_one_delegate_returns_nothing(self):
        doc = Document('@path', len('@path'))
        event = MagicMock()
        self.mock_path_completer.get_completions.return_value = iter([Completion('path/comp1'), Completion('path/comp2')])
        self.mock_command_completer.get_completions.return_value = iter([])
        completions = list(self.prompt_completer.get_completions(doc, event))
        self.mock_path_completer.get_completions.assert_called_once_with(doc, event)
        self.mock_command_completer.get_completions.assert_called_once_with(doc, event)
        completion_texts = sorted([c.text for c in completions])
        self.assertEqual(completion_texts, ['path/comp1', 'path/comp2'])

    def test_works_if_command_delegate_returns_nothing(self):
        doc = Document('/xyz', len('/xyz'))
        event = MagicMock()
        self.mock_path_completer.get_completions.return_value = iter([])
        self.mock_command_completer.get_completions.return_value = iter([])
        completions = list(self.prompt_completer.get_completions(doc, event))
        self.mock_path_completer.get_completions.assert_called_once_with(doc, event)
        self.mock_command_completer.get_completions.assert_called_once_with(doc, event)
        self.assertEqual(completions, [])

if __name__ == '__main__':
    unittest.main()
