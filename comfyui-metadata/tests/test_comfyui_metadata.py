import binascii
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from comfyui_metadata import (
    Metadata,
    MissingWorkflowError,
    Outcome,
    copy_metadata,
    extract_metadata,
)
from comfyui_metadata.container import build_exif, exif_fields


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def png_image(*, workflow=None, prompt=None) -> bytes:
    output = bytearray(b"\x89PNG\r\n\x1a\n")
    output.extend(png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)))
    if workflow is not None:
        output.extend(png_chunk(b"tEXt", b"workflow\0" + json.dumps(workflow).encode()))
    if prompt is not None:
        output.extend(png_chunk(b"tEXt", b"prompt\0" + json.dumps(prompt).encode()))
    output.extend(png_chunk(b"IDAT", zlib.compress(b"\0\x01\x02\x03\xff")))
    output.extend(png_chunk(b"IEND", b""))
    return bytes(output)


def webp_image(pixel_payload: bytes | None = None) -> bytes:
    if pixel_payload is None:
        packed_dimensions = ((2 - 1) << 14) | (2 - 1)
        pixel_payload = (
            b"\x2f" + packed_dimensions.to_bytes(4, "little") + b"pixel-data"
        )
    chunk = b"VP8L" + struct.pack("<I", len(pixel_payload)) + pixel_payload
    if len(pixel_payload) & 1:
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


def little_endian_exif(description: bytes, comment: bytes) -> bytes:
    root_ifd = 8
    root_entries = 2
    exif_ifd = root_ifd + 2 + root_entries * 12 + 4
    data_start = exif_ifd + 2 + 12 + 4
    description = description + b"\0"
    comment_offset = data_start + len(description) + (len(description) & 1)
    data = bytearray(data_start)
    data[:2] = b"II"
    struct.pack_into("<H", data, 2, 42)
    struct.pack_into("<I", data, 4, root_ifd)
    struct.pack_into("<H", data, root_ifd, root_entries)
    struct.pack_into("<HHII", data, 10, 0x010E, 2, len(description), data_start)
    struct.pack_into("<HHII", data, 22, 0x8769, 4, 1, exif_ifd)
    struct.pack_into("<H", data, exif_ifd, 1)
    struct.pack_into(
        "<HHII", data, exif_ifd + 2, 0x9286, 7, len(comment), comment_offset
    )
    data.extend(description)
    if len(description) & 1:
        data.append(0)
    data.extend(comment)
    return bytes(data)


class ExifByteOrderTests(unittest.TestCase):
    def test_writer_uses_big_endian_tiff_and_round_trips(self):
        exif = build_exif(b"Workflow:{}", b"ASCII\0\0\0Prompt:{}")
        self.assertEqual(exif[:4], b"MM\0*")
        description, comment = exif_fields(exif)
        self.assertEqual(description, b"Workflow:{}\0")
        self.assertEqual(comment, b"ASCII\0\0\0Prompt:{}")

    def test_reader_accepts_little_endian_tiff(self):
        exif = little_endian_exif(b"Workflow:{}", b"ASCII\0\0\0Prompt:{}")
        description, comment = exif_fields(b"Exif\0\0" + exif)
        self.assertEqual(description, b"Workflow:{}\0")
        self.assertEqual(comment, b"ASCII\0\0\0Prompt:{}")


class MetadataCopyTests(unittest.TestCase):
    def test_png_to_webp_preserves_encoded_pixel_chunk(self):
        metadata = Metadata(
            workflow={"nodes": [{"type": "LoraInfo"}]},
            prompt={"1": {"class_type": "KSampler"}},
        )
        source_bytes = png_image(workflow=metadata.workflow, prompt=metadata.prompt)
        destination_bytes = webp_image()
        original_pixels = webp_chunk(destination_bytes, b"VP8L")

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            destination = Path(directory) / "destination.webp"
            source.write_bytes(source_bytes)
            destination.write_bytes(destination_bytes)
            self.assertEqual(copy_metadata(source, destination), Outcome.COPIED)
            updated = destination.read_bytes()

        self.assertEqual(webp_chunk(updated, b"VP8L"), original_pixels)
        self.assertEqual(extract_metadata(updated), metadata)
        self.assertEqual(struct.unpack_from("<I", updated, 4)[0], len(updated) - 8)

    def test_webp_to_png_preserves_idat_chunk(self):
        metadata = Metadata(workflow={"last_node_id": 5}, prompt=None)
        source = webp_image()
        exif = build_exif(b"Workflow:" + json.dumps(metadata.workflow).encode(), None)
        from comfyui_metadata.container import replace_webp_exif

        source = replace_webp_exif(source, exif)
        destination = png_image()
        original_idat = png_chunk_payload(destination, b"IDAT")

        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.webp"
            destination_path = Path(directory) / "destination.png"
            source_path.write_bytes(source)
            destination_path.write_bytes(destination)
            self.assertEqual(
                copy_metadata(source_path, destination_path), Outcome.COPIED
            )
            updated = destination_path.read_bytes()

        self.assertEqual(png_chunk_payload(updated, b"IDAT"), original_idat)
        self.assertEqual(extract_metadata(updated), metadata)
        workflow_position = updated.index(b"iTXt") - 4
        expected_length = len(b"workflow") + 5 + len(b'{"last_node_id":5}')
        self.assertEqual(
            struct.unpack_from(">I", updated, workflow_position)[0], expected_length
        )

    def test_missing_metadata_is_successful_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            missing_destination = Path(directory) / "missing.webp"
            source.write_bytes(png_image())
            self.assertEqual(
                copy_metadata(source, missing_destination), Outcome.NO_METADATA
            )
            self.assertFalse(missing_destination.exists())

    def test_png_prompt_without_workflow_is_invalid(self):
        with self.assertRaises(MissingWorkflowError):
            extract_metadata(png_image(prompt={"1": {}}))


if __name__ == "__main__":
    unittest.main()
