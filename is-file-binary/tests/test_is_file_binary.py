import tempfile
import unittest
from pathlib import Path

from is_file_binary import is_file_binary


class IsFileBinaryTests(unittest.TestCase):
    def test_detects_text_and_binary_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_file = root / "text"
            binary_file = root / "binary"
            empty_file = root / "empty"
            text_file.write_text("Hello, π!\n", encoding="utf-8")
            binary_file.write_bytes(b"image\x00payload")
            empty_file.write_bytes(b"")
            self.assertFalse(is_file_binary(text_file))
            self.assertTrue(is_file_binary(binary_file))
            self.assertFalse(is_file_binary(empty_file))

    def test_propagates_file_errors(self):
        with self.assertRaises(FileNotFoundError):
            is_file_binary("missing-file")
