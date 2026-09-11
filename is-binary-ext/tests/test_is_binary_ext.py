import unittest
from pathlib import Path

from is_binary_ext import is_binary_ext


class IsBinaryExtTests(unittest.TestCase):
    def test_recognizes_extensions_case_insensitively(self):
        self.assertTrue(is_binary_ext("photo.PNG"))
        self.assertTrue(is_binary_ext(Path("archive.tar.gz")))

    def test_rejects_unknown_or_missing_extensions(self):
        self.assertFalse(is_binary_ext("notes.txt"))
        self.assertFalse(is_binary_ext("Makefile"))
