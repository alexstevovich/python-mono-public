import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tar_archive import create_tar, decode_in_place, decode_tar, is_encrypted
from tar_archive.cli import decode_main, encode_main


class TarCommandTests(unittest.TestCase):
    def test_interactive_encode_collects_policy_and_confirmed_password(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            output = Path(directory) / "archive.bin"
            with (
                patch("tar_archive.cli._yes_no", side_effect=[True, True]),
                patch("tar_archive.cli._new_password", return_value="secret"),
                patch("tar_archive.cli.create_tar") as create,
            ):
                self.assertEqual(
                    encode_main([str(source), str(output), "--interactive"]), 0
                )
            create.assert_called_once_with(
                source, output, compression=True, encryption="secret"
            )

    def test_decode_auto_detects_compression_without_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "hello.txt").write_text("hello", encoding="utf-8")
            encoded = create_tar(source, root / "archive.tar.zst", compression=True)
            decoded = decode_tar(encoded, root / "decoded.tar", compression=None)
            with tarfile.open(decoded, "r:") as archive:
                self.assertEqual(
                    archive.extractfile("source/hello.txt").read(), b"hello"
                )

    def test_encrypted_decode_can_replace_input_in_place(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "hello.txt").write_text("hello", encoding="utf-8")
            encoded = create_tar(
                source,
                root / "archive.tar.zst.enc",
                compression=True,
                encryption="secret",
            )
            self.assertTrue(is_encrypted(encoded))
            result = decode_in_place(encoded, compression=None, encryption="secret")
            self.assertEqual(result, encoded)
            self.assertFalse(is_encrypted(encoded))
            with tarfile.open(encoded, "r:") as archive:
                self.assertEqual(
                    archive.extractfile("source/hello.txt").read(), b"hello"
                )

    def test_wrong_password_preserves_in_place_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "hello.txt").write_text("hello", encoding="utf-8")
            encoded = create_tar(source, root / "archive.enc", encryption="secret")
            original = encoded.read_bytes()

            with self.assertRaisesRegex(ValueError, "incorrect password"):
                decode_in_place(encoded, compression=None, encryption="wrong")

            self.assertEqual(encoded.read_bytes(), original)

    @patch("tar_archive.cli.getpass.getpass", return_value="secret")
    @patch("tar_archive.cli.decode_in_place")
    @patch("tar_archive.cli.is_encrypted", return_value=True)
    def test_interactive_decode_prompts_only_for_encrypted_input(
        self, _encrypted, decode, password
    ):
        self.assertEqual(decode_main(["archive.bin", "--interactive"]), 0)
        password.assert_called_once()
        decode.assert_called_once_with(
            Path("archive.bin"), compression=None, encryption="secret"
        )


if __name__ == "__main__":
    unittest.main()
