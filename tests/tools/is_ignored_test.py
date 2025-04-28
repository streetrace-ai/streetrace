import unittest
from pathlib import Path

import pathspec

from streetrace.tools.read_directory_structure import is_ignored


# Unit tests for is_ignored
class TestIsIgnored(unittest.TestCase):
    def setUp(self) -> None:
        self.base_path = Path("tests").resolve()
        self.ignored_dir: Path = None
        self.included_dir: Path = None
        self.ignored_file: Path = None
        self.included_file: Path = None
        for p in self.base_path.iterdir():
            if p.is_dir():
                if not self.ignored_dir:
                    self.ignored_dir = p
                elif not self.included_dir:
                    self.included_dir = p
            elif p.is_file():
                if not self.ignored_file:
                    self.ignored_file = p
                elif not self.included_file:
                    self.included_file = p
        self.spec = pathspec.PathSpec.from_lines(
            "gitwildmatch",
            [self.ignored_file.name, self.ignored_dir.name + "/"],
        )

    def test_ignored_file(self) -> None:
        assert is_ignored(self.ignored_file, self.base_path, self.spec)

    def test_included_file(self) -> None:
        assert not is_ignored(
            self.included_file,
            self.base_path,
            self.spec,
        )

    def test_ignored_dir(self) -> None:
        assert is_ignored(self.ignored_dir, self.base_path, self.spec)

    def test_included_dir(self) -> None:
        assert not is_ignored(self.included_dir, self.base_path, self.spec)


if __name__ == "__main__":
    unittest.main()
