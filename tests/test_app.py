import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

import app


class Response:
    status = 200

    def __init__(self, data: bytes, content_type: str = "image/jpeg"):
        self.data = data
        self.headers = MagicMock()
        self.headers.get_content_type.return_value = content_type

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=-1):
        if not hasattr(self, "_stream"):
            self._stream = io.BytesIO(self.data)
        return self._stream.read(size)


class AppTests(unittest.TestCase):
    def test_find_latest_image_skips_video(self):
        responses = [
            {"media_type": "video", "date": "2026-07-29"},
            {"media_type": "image", "date": "2026-07-28", "hdurl": "https://example/image.jpg"},
        ]
        with patch.object(app, "request_json", side_effect=responses):
            result = app.find_latest_image(date(2026, 7, 29))
        self.assertEqual(result["date"], "2026-07-28")

    def test_download_rejects_non_image_and_preserves_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "wallpaper.jpg"
            destination.write_bytes(b"old")
            with patch("urllib.request.urlopen", return_value=Response(b"<html>", "text/html")):
                with self.assertRaises(RuntimeError):
                    app.download_and_validate("https://example.test", destination)
            self.assertEqual(destination.read_bytes(), b"old")

    def test_download_writes_valid_image(self):
        buffer = io.BytesIO()
        Image.new("RGB", (32, 24), "navy").save(buffer, "JPEG")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "wallpaper.jpg"
            with patch("urllib.request.urlopen", return_value=Response(buffer.getvalue())):
                app.download_and_validate("https://example.test", destination)
            with Image.open(destination) as result:
                self.assertEqual(result.size, (32, 24))


if __name__ == "__main__":
    unittest.main()
