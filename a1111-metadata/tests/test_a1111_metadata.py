import binascii
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from a1111_metadata import Metadata, Outcome, copy_metadata, extract_metadata
from comfyui_metadata.container import build_exif, replace_webp_exif


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def png_image(parameters: str | None = None) -> bytes:
    output = bytearray(b"\x89PNG\r\n\x1a\n")
    output.extend(png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)))
    if parameters is not None:
        output.extend(
            png_chunk(b"tEXt", b"parameters\0" + parameters.encode("latin-1"))
        )
    output.extend(png_chunk(b"IDAT", zlib.compress(b"\0\x01\x02\x03\xff")))
    output.extend(png_chunk(b"IEND", b""))
    return bytes(output)


def webp_image() -> bytes:
    packed = ((2 - 1) << 14) | (2 - 1)
    pixels = b"\x2f" + packed.to_bytes(4, "little") + b"pixel-data"
    chunk = b"VP8L" + struct.pack("<I", len(pixels)) + pixels
    if len(pixels) & 1:
        chunk += b"\0"
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def webp_chunk(data: bytes, wanted: bytes) -> bytes:
    position = 12
    while position + 8 <= len(data):
        kind = data[position : position + 4]
        size = struct.unpack_from("<I", data, position + 4)[0]
        if kind == wanted:
            return data[position + 8 : position + 8 + size]
        position += 8 + size + (size & 1)
    raise AssertionError(f"Missing WebP chunk: {wanted!r}")


def png_chunk_payload(data: bytes, wanted: bytes) -> bytes:
    position = 8
    while position + 12 <= len(data):
        size = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        if kind == wanted:
            return data[position + 8 : position + 8 + size]
        position += 12 + size
    raise AssertionError(f"Missing PNG chunk: {wanted!r}")


class A1111MetadataTests(unittest.TestCase):
    def test_png_to_webp_preserves_encoded_pixels_and_unicode(self):
        parameters = "portrait, café\nSteps: 30, Seed: 42"
        source_bytes = png_image(parameters)
        destination_bytes = webp_image()
        pixels = webp_chunk(destination_bytes, b"VP8L")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            destination = Path(directory) / "destination.webp"
            source.write_bytes(source_bytes)
            destination.write_bytes(destination_bytes)
            self.assertEqual(copy_metadata(source, destination), Outcome.COPIED)
            updated = destination.read_bytes()
        self.assertEqual(webp_chunk(updated, b"VP8L"), pixels)
        self.assertEqual(extract_metadata(updated), Metadata(parameters))

    def test_webp_to_png_preserves_encoded_pixels(self):
        parameters = "landscape\nSteps: 20, Seed: 7"
        comment = b"UNICODE\0" + parameters.encode("utf-16-be")
        source_bytes = replace_webp_exif(webp_image(), build_exif(None, comment))
        destination_bytes = png_image()
        pixels = png_chunk_payload(destination_bytes, b"IDAT")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.webp"
            destination = Path(directory) / "destination.png"
            source.write_bytes(source_bytes)
            destination.write_bytes(destination_bytes)
            self.assertEqual(copy_metadata(source, destination), Outcome.COPIED)
            updated = destination.read_bytes()
        self.assertEqual(png_chunk_payload(updated, b"IDAT"), pixels)
        self.assertEqual(extract_metadata(updated), Metadata(parameters))

    def test_missing_metadata_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            destination = Path(directory) / "destination.webp"
            source.write_bytes(png_image())
            destination.write_bytes(webp_image())
            before = destination.read_bytes()
            self.assertEqual(copy_metadata(source, destination), Outcome.NO_METADATA)
            self.assertEqual(destination.read_bytes(), before)

    def test_non_a1111_webp_comment_is_ignored(self):
        data = replace_webp_exif(webp_image(), build_exif(None, b"ASCII\0\0\0other"))
        self.assertIsNone(extract_metadata(data))
