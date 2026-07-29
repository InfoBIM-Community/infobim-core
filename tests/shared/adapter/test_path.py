import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infobim.shared.adapter.path import CliPathAdapter


class CliPathAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = CliPathAdapter()

    def test_normalize_removes_boundary_quotes_and_whitespace(self) -> None:
        self.assertEqual(self.adapter.normalize("  './project'  "), "./project")

    def test_normalize_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.adapter.normalize("  ''  ")

    def test_normalize_rejects_null_character(self) -> None:
        with self.assertRaisesRegex(ValueError, "null character"):
            self.adapter.normalize("project\x00name")

    def test_normalize_rejects_invalid_windows_character(self) -> None:
        with patch("infobim.shared.adapter.path.os.name", "nt"):
            with self.assertRaisesRegex(ValueError, "invalid Windows character"):
                self.adapter.normalize(r"C:\projects\invalid?name")

    def test_resolve_uses_root_for_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as root_path:
            expected_path: Path = Path(root_path, "project").resolve()
            self.assertEqual(
                self.adapter.resolve("project", root_path=root_path),
                expected_path,
            )

    def test_resolve_preserves_absolute_path(self) -> None:
        absolute_path: Path = Path(os.path.abspath(os.sep))
        self.assertEqual(self.adapter.resolve(str(absolute_path)), absolute_path.resolve())


if __name__ == "__main__":
    unittest.main()
