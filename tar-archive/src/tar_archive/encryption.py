import os
from contextlib import contextmanager

MAGIC = b"BTAR-AESGCM-1\x00"
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16


class EncryptedWriter:
    """Small streaming AES-GCM writer; it does not close its output."""

    def __init__(self, output, password: str):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        except ImportError as exc:
            raise RuntimeError(
                "Encryption requires the optional 'cryptography' package"
            ) from exc

        salt = os.urandom(SALT_SIZE)
        nonce = os.urandom(NONCE_SIZE)
        header = MAGIC + salt + nonce
        key = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(
            password.encode("utf-8")
        )

        self._output = output
        self._encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        self._encryptor.authenticate_additional_data(header)
        self._output.write(header)
        self._finished = False

    def write(self, data: bytes) -> int:
        if self._finished:
            raise ValueError("EncryptedWriter is already finished")
        encrypted = self._encryptor.update(data)
        if encrypted:
            self._output.write(encrypted)
        return len(data)

    def flush(self) -> None:
        self._output.flush()

    def finish(self) -> None:
        if self._finished:
            return
        final_bytes = self._encryptor.finalize()
        if final_bytes:
            self._output.write(final_bytes)
        self._output.write(self._encryptor.tag)
        self._finished = True


@contextmanager
def encrypted_writer(output, password: str):
    writer = EncryptedWriter(output, password)
    try:
        yield writer
        writer.finish()
    finally:
        # The containing archive operation owns and closes the output file.
        pass
