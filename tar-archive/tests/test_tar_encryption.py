import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from tar_archive import create_tar
from tar_archive.encryption import MAGIC, NONCE_SIZE, SALT_SIZE, TAG_SIZE


class EncryptionTests(unittest.TestCase):
    def test_encrypted_archive_can_be_authenticated_and_decrypted(self):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        except ImportError:
            self.skipTest("optional cryptography package is not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "source"
            source.mkdir()
            (source / "hello.txt").write_text("hello", encoding="utf-8")
            target = base / "target"
            target.mkdir()

            encrypted_path = create_tar(
                source,
                target / "arbitrary-name.bin",
                encryption="test password",
            )
            encrypted = encrypted_path.read_bytes()

        header_size = len(MAGIC) + SALT_SIZE + NONCE_SIZE
        header = encrypted[:header_size]
        salt = header[len(MAGIC) : len(MAGIC) + SALT_SIZE]
        nonce = header[-NONCE_SIZE:]
        ciphertext = encrypted[header_size:-TAG_SIZE]
        tag = encrypted[-TAG_SIZE:]
        key = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(b"test password")
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(header)
        plain_tar = decryptor.update(ciphertext) + decryptor.finalize()

        with tarfile.open(fileobj=io.BytesIO(plain_tar), mode="r:") as archive:
            file = archive.extractfile("source/hello.txt")
            self.assertEqual(file.read(), b"hello")


if __name__ == "__main__":
    unittest.main()
