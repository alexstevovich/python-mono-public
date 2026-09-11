from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from .archive import create_tar
from .decode import decode_in_place, decode_tar, is_encrypted


def _yes_no(question: str) -> bool:
    while True:
        answer = input(f"{question} [y/n]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _new_password() -> str:
    password = getpass.getpass("Encryption password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not password:
        raise ValueError("password must not be empty")
    if password != confirmation:
        raise ValueError("passwords do not match")
    return password


def encode_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tar-encode",
        description="Create a streaming TAR with optional Zstandard compression and AES-256-GCM encryption.",
    )
    parser.add_argument("source", type=Path, help="directory to archive")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="exact output path; otherwise derive one beside SOURCE",
    )
    parser.add_argument("--compress", action="store_true", help="use Zstandard level 3")
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="use AES-256-GCM and prompt for a confirmed password",
    )
    parser.add_argument(
        "--password",
        help="encryption password for non-interactive automation (visible to process inspection)",
    )
    parser.add_argument(
        "--interactive", action="store_true", help="ask whether to compress and encrypt"
    )
    return parser


def _archive_output(source: Path, *, compression: bool, encryption: bool) -> Path:
    suffix = ".tar" + (".zst" if compression else "") + (".enc" if encryption else "")
    return source.with_name(source.name + suffix)


def encode_main(argv: list[str] | None = None) -> int:
    parser = encode_parser()
    arguments = parser.parse_args(argv)
    if arguments.interactive and (
        arguments.compress or arguments.encrypt or arguments.password is not None
    ):
        parser.error(
            "--interactive cannot be combined with --compress, --encrypt, or --password"
        )
    try:
        compression = (
            _yes_no("Use Zstandard compression?")
            if arguments.interactive
            else arguments.compress
        )
        encryption = (
            _yes_no("Encrypt the archive?")
            if arguments.interactive
            else (arguments.encrypt or arguments.password is not None)
        )
        password = None
        if encryption:
            password = arguments.password or _new_password()
        output = arguments.output or _archive_output(
            arguments.source,
            compression=compression,
            encryption=encryption,
        )
        create_tar(
            arguments.source, output, compression=compression, encryption=password
        )
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"tar-encode: {error}", file=sys.stderr)
        return 1


def decode_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tar-decode",
        description="Automatically decrypt and/or decompress an archive into a plain TAR.",
    )
    parser.add_argument("input", type=Path, help="encoded archive to decode")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="output TAR; omit to replace INPUT in place",
    )
    parser.add_argument(
        "--password", help="decryption password (visible to process inspection)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="prompt for a password only when INPUT is encrypted",
    )
    return parser


def decode_main(argv: list[str] | None = None) -> int:
    parser = decode_parser()
    arguments = parser.parse_args(argv)
    try:
        encrypted = is_encrypted(arguments.input)
        password = arguments.password
        if encrypted and password is None:
            if not arguments.interactive:
                parser.error("encrypted input requires --password or --interactive")
            password = getpass.getpass("Decryption password: ")
            if not password:
                raise ValueError("password must not be empty")
        if (
            arguments.output is None
            or arguments.output.absolute() == arguments.input.absolute()
        ):
            decode_in_place(arguments.input, compression=None, encryption=password)
        else:
            decode_tar(
                arguments.input, arguments.output, compression=None, encryption=password
            )
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"tar-decode: {error}", file=sys.stderr)
        return 1
