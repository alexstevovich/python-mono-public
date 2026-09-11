import os
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tar_archive.archive import (
    TAR_BUFFER_SIZE,
    ZSTD_LEVEL,
    _add_directory_tree,
    _open_archive,
    create_tar,
)


class FakeArchive:
    def __init__(self):
        self.added = []
        self.links = []

    def add(self, path, arcname, recursive):
        self.added.append((Path(path), arcname, recursive))

    def addfile(self, info):
        self.links.append(info)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tree_addition_includes_files_and_empty_directories(self):
        source = self.base / "source"
        source.mkdir()
        (source / "empty").mkdir()
        (source / "file.txt").write_text("hello", encoding="utf-8")
        archive = FakeArchive()

        _add_directory_tree(archive, source)

        names = {item[1] for item in archive.added}
        self.assertEqual(names, {"source", "source/empty", "source/file.txt"})
        self.assertTrue(all(not item[2] for item in archive.added))

    def test_default_archive_is_real_streaming_tar_with_file_contents(self):
        source = self.base / "source"
        target = self.base / "target"
        source.mkdir()
        target.mkdir()
        (source / "hello.txt").write_text("hello", encoding="utf-8")
        archive_path = target / "chosen-output.data"

        result = create_tar(source, archive_path)

        self.assertEqual(result, archive_path)
        self.assertTrue(result.exists())
        self.assertFalse(Path(f"{result}.part").exists())
        with tarfile.open(result, "r:") as archive:
            extracted = archive.extractfile("source/hello.txt")
            self.assertEqual(extracted.read(), b"hello")

    @patch("tar_archive.archive.tarfile.open")
    def test_compression_wraps_stream_in_zstd_level_three(self, open_tar):
        zstd_file = unittest.mock.MagicMock()
        zstd = types.SimpleNamespace(ZstdFile=zstd_file)
        compression = types.ModuleType("compression")
        compression.zstd = zstd
        open_tar.return_value.__enter__.return_value = FakeArchive()
        output = unittest.mock.MagicMock()

        with patch.dict(sys.modules, {"compression": compression}):
            with _open_archive(output, compression=True, encryption=None):
                pass

        zstd_file.assert_called_once_with(output, mode="wb", level=ZSTD_LEVEL)
        options = open_tar.call_args.kwargs
        self.assertEqual(options["mode"], "w|")
        self.assertEqual(options["bufsize"], TAR_BUFFER_SIZE)
        self.assertFalse(options["dereference"])

    @patch("tar_archive.archive._open_archive")
    def test_failure_removes_new_partial_archive(self, open_archive):
        source = self.base / "source"
        target = self.base / "target"
        source.mkdir()
        target.mkdir()
        archive_path = target / "failed.tar.zst"
        open_archive.side_effect = RuntimeError("archive failed")

        with self.assertRaisesRegex(RuntimeError, "archive failed"):
            create_tar(source, archive_path)

        self.assertFalse((target / "failed.tar.zst").exists())
        self.assertFalse((target / "failed.tar.zst.part").exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows junction test")
    def test_junction_is_archived_as_link_without_traversal(self):
        source = self.base / "source"
        outside = self.base / "outside"
        source.mkdir()
        outside.mkdir()
        (outside / "not-added.txt").write_text("outside", encoding="utf-8")
        junction = source / "junction"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.skipTest(f"Creating a junction failed: {result.stderr}")

        archive = FakeArchive()
        try:
            _add_directory_tree(archive, source)
        finally:
            if os.path.lexists(junction):
                os.rmdir(junction)

        self.assertEqual(len(archive.links), 1)
        self.assertEqual(
            archive.links[0].pax_headers["backup.windows_link_type"],
            "junction",
        )
        self.assertNotIn("source/junction/not-added.txt", {x[1] for x in archive.added})


if __name__ == "__main__":
    unittest.main()
