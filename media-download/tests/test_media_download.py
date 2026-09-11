import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_download import (
    download_audio,
    download_video,
    format_upload_date,
    has_video_stream,
    make_chapter_metadata,
)
from media_download.cli import audio_main, chapters_main, video_main


class MediaDownloadTests(unittest.TestCase):
    @patch("media_download.audio.yt_dlp.YoutubeDL")
    def test_audio_passes_explicit_output_and_playlist_policy(self, youtube_dl):
        downloader = youtube_dl.return_value.__enter__.return_value
        downloader.download.return_value = 0
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            download_audio("https://example.test/audio", output, download_playlist=True)
        options = youtube_dl.call_args.args[0]
        self.assertFalse(options["noplaylist"])
        self.assertTrue(options["ignoreerrors"])
        self.assertIn("%(title)s [%(id)s].%(ext)s", options["outtmpl"])
        downloader.download.assert_called_once_with(["https://example.test/audio"])

    def test_chapter_metadata_is_normalized(self):
        metadata = make_chapter_metadata(
            {"chapters": [{"title": "Opening", "start_time": 2, "end_time": 7}]},
            "webm",
        )
        self.assertEqual(metadata[0]["duration_seconds"], 5)
        self.assertEqual(metadata[0]["filename"], "Opening.webm")
        self.assertEqual(format_upload_date("20260907"), "2026-09-07")

    def test_video_stream_detection_handles_merged_formats(self):
        self.assertTrue(
            has_video_stream(
                {"requested_formats": [{"vcodec": "av1"}, {"vcodec": "none"}]}
            )
        )
        self.assertFalse(has_video_stream({"requested_formats": [{"vcodec": "none"}]}))

    @patch("media_download.video.yt_dlp.YoutubeDL")
    def test_video_requires_and_returns_a_video_download(self, youtube_dl):
        downloader = youtube_dl.return_value.__enter__.return_value
        downloader.extract_info.return_value = {"vcodec": "av1"}
        downloader.prepare_filename.return_value = "downloaded.webm"
        with tempfile.TemporaryDirectory() as directory:
            result = download_video("https://example.test/video", Path(directory))
        self.assertEqual(result, Path("downloaded.webm"))
        self.assertIn("bestvideo", youtube_dl.call_args.args[0]["format"])


class MediaDownloadCliTests(unittest.TestCase):
    @patch("media_download.cli.download_audio")
    def test_audio_cli_delegates_all_options(self, download):
        self.assertEqual(audio_main(["url", "-o", "chosen", "--playlist"]), 0)
        download.assert_called_once_with("url", Path("chosen"), download_playlist=True)

    @patch("media_download.cli._require_ffmpeg", return_value=True)
    @patch("media_download.cli.download_audio_chapters")
    def test_chapters_cli_checks_ffmpeg_and_delegates(self, download, require):
        download.return_value = Path("chosen/item"), Path("chosen/item/metadata.json")
        self.assertEqual(chapters_main(["url", "-o", "chosen"]), 0)
        require.assert_called_once()
        download.assert_called_once_with("url", Path("chosen"))

    @patch("media_download.cli._require_ffmpeg", return_value=True)
    @patch("media_download.cli.download_video")
    def test_video_cli_checks_ffmpeg_and_delegates(self, download, require):
        download.return_value = Path("chosen/video.webm")
        self.assertEqual(video_main(["url", "-o", "chosen"]), 0)
        require.assert_called_once()
        download.assert_called_once_with("url", Path("chosen"))


if __name__ == "__main__":
    unittest.main()
