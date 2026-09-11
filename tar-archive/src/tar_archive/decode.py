import io
import os
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path

from .console import print_message
from .encryption import MAGIC, NONCE_SIZE, SALT_SIZE, TAG_SIZE

COPY_BUFFER_SIZE = 8 * 1024 * 1024
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def is_encrypted(path: str | Path) -> bool:
    with Path(path).open("rb") as source:
        return source.read(len(MAGIC)) == MAGIC


class _EncryptedReader(io.RawIOBase):
    """Read this project's AES-GCM format without buffering the whole archive."""

    def __init__(self, source, password: str):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        except ImportError as exc:
            raise RuntimeError(
                "Decryption requires the 'cryptography' package; run setup.cmd"
            ) from exc

        header_size = len(MAGIC) + SALT_SIZE + NONCE_SIZE
        source.seek(0, os.SEEK_END)
        total_size = source.tell()
        if total_size < header_size + TAG_SIZE:
            raise ValueError("Encrypted archive is too short or damaged")

        source.seek(0)
        header = source.read(header_size)
        if header[: len(MAGIC)] != MAGIC:
            raise ValueError("This is not an archive encrypted by tar_archive")

        salt_start = len(MAGIC)
        salt = header[salt_start : salt_start + SALT_SIZE]
        nonce = header[salt_start + SALT_SIZE :]
        source.seek(-TAG_SIZE, os.SEEK_END)
        tag = source.read(TAG_SIZE)
        source.seek(header_size)

        key = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(
            password.encode("utf-8")
        )
        self._source = source
        self._remaining = total_size - header_size - TAG_SIZE
        self._decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        self._decryptor.authenticate_additional_data(header)
        self._finished = False

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        if self._finished:
            return 0
        if self._remaining == 0:
            try:
                self._decryptor.finalize()  # Verifies the password and authentication tag.
            except Exception as error:
                raise ValueError(
                    "incorrect password or encrypted archive authentication failed"
                ) from error
            self._finished = True
            return 0

        amount = min(len(buffer), self._remaining)
        encrypted = self._source.read(amount)
        if len(encrypted) != amount:
            raise ValueError("Encrypted archive ended unexpectedly")
        plain = self._decryptor.update(encrypted)
        buffer[: len(plain)] = plain
        self._remaining -= amount
        return len(plain)


def decode_tar(
    archive_path: str | Path,
    output_path: str | Path,
    *,
    compression: bool | None = None,
    encryption: str | None = None,
) -> Path:
    """Stream an encrypted/compressed archive into an exact plain-TAR path."""
    archive_path = Path(archive_path).absolute()
    output_path = Path(output_path).absolute()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive does not exist: {archive_path}")
    if not output_path.parent.is_dir():
        raise NotADirectoryError(
            f"Decoded output directory does not exist: {output_path.parent}"
        )
    partial_path = Path(f"{output_path}.part")
    if output_path.exists():
        raise FileExistsError(f"Decoded archive already exists: {output_path}")

    print()
    print_message("OPEN", str(archive_path), "cyan")
    print_message("OUTPUT", str(output_path), "cyan")
    print_message("DECRYPT", "AES-256-GCM" if encryption else "Not needed", "yellow")
    compression_label = (
        "Automatic"
        if compression is None
        else ("Zstandard" if compression else "Not needed")
    )
    print_message("DECOMPRESS", compression_label, "yellow")

    partial_created = False
    try:
        with ExitStack() as stack:
            source_file = stack.enter_context(archive_path.open("rb"))
            source = source_file
            if encryption:
                source = stack.enter_context(
                    io.BufferedReader(
                        _EncryptedReader(source_file, encryption), COPY_BUFFER_SIZE
                    )
                )
            if compression is None:
                compression = (
                    source.peek(len(ZSTD_MAGIC))[: len(ZSTD_MAGIC)] == ZSTD_MAGIC
                )
            if compression:
                try:
                    from compression import zstd
                except ImportError as exc:
                    raise RuntimeError(
                        "Zstandard archives require Python 3.14 with compression.zstd"
                    ) from exc
                source = stack.enter_context(zstd.ZstdFile(source, mode="rb"))

            output = stack.enter_context(
                partial_path.open("xb", buffering=COPY_BUFFER_SIZE)
            )
            partial_created = True
            shutil.copyfileobj(source, output, length=COPY_BUFFER_SIZE)
            output.flush()
            os.fsync(output.fileno())

        partial_path.rename(output_path)
    except BaseException:
        if partial_created:
            partial_path.unlink(missing_ok=True)
        raise

    print_message(
        "VERIFIED", "Encryption/compression layers decoded successfully", "green"
    )
    print_message(
        "COMPLETE", f"{output_path} ({output_path.stat().st_size:,} bytes)", "green"
    )
    return output_path


def decode_in_place(
    archive_path: str | Path,
    *,
    compression: bool | None = None,
    encryption: str | None = None,
) -> Path:
    """Decode through a sibling temporary file, then replace the input safely."""
    archive_path = Path(archive_path).absolute()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_path.name}.",
        suffix=".decoded",
        dir=archive_path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        decode_tar(
            archive_path,
            temporary,
            compression=compression,
            encryption=encryption,
        )
        os.replace(temporary, archive_path)
        return archive_path
    finally:
        temporary.unlink(missing_ok=True)
