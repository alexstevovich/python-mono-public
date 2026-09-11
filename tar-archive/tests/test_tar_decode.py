import tempfile
import unittest
from pathlib import Path

from tar_archive.decode import decode_tar
from tar_archive.encryption import encrypted_writer


class DecodeArchiveTests(unittest.TestCase):
    def test_encrypted_archive_is_cloned_as_plain_tar(self):
        original = b"plain tar contents\0" * 10_000

        with tempfile.TemporaryDirectory() as temporary_directory:
            encrypted_path = Path(temporary_directory) / "example.tar.enc"
            with encrypted_path.open("wb") as output:
                with encrypted_writer(output, "secret") as encrypted:
                    encrypted.write(original)
            encrypted_before = encrypted_path.read_bytes()

            output_path = Path(temporary_directory) / "example.tar"
            decoded_path = decode_tar(
                encrypted_path,
                output_path,
                encryption="secret",
            )

            self.assertEqual(decoded_path.name, "example.tar")
            self.assertEqual(decoded_path.read_bytes(), original)
            self.assertEqual(encrypted_path.read_bytes(), encrypted_before)
            self.assertFalse(Path(f"{decoded_path}.part").exists())

    def test_output_directory_can_be_selected(self):
        original = b"plain tar contents"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            encrypted_path = root / "example.tar.enc"
            destination = root / "opened"
            destination.mkdir()
            with encrypted_path.open("wb") as output:
                with encrypted_writer(output, "secret") as encrypted:
                    encrypted.write(original)

            decoded_path = decode_tar(
                encrypted_path,
                destination / "chosen-name.tar",
                encryption="secret",
            )

            self.assertEqual(decoded_path, destination / "chosen-name.tar")
            self.assertEqual(decoded_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
