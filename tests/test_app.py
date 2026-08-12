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

    def test_request_json_with_retries_recovers_after_transient_failure(self):
        responses = [TimeoutError("timed out"), {"media_type": "image", "date": "2026-08-12"}]
        with patch.object(app, "request_json", side_effect=responses):
            with patch.object(app.time, "sleep") as mock_sleep:
                result = app.request_json_with_retries(date(2026, 8, 12))
        self.assertEqual(result["date"], "2026-08-12")
        mock_sleep.assert_called_once()

    def test_request_json_with_retries_raises_after_exhausting_attempts(self):
        with patch.object(app, "request_json", side_effect=TimeoutError("timed out")):
            with patch.object(app.time, "sleep") as mock_sleep:
                with self.assertRaises(TimeoutError):
                    app.request_json_with_retries(date(2026, 8, 12), attempts=3)
        self.assertEqual(mock_sleep.call_count, 2)

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

    def test_prepare_panorama_preserves_ratio_and_uses_center_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jpg"
            destination = Path(directory) / "panorama.jpg"
            image = Image.new("RGB", (400, 400), "red")
            for y in range(100, 300):
                for x in range(400):
                    image.putpixel((x, y), (0, 128, 255))
            image.save(source, "JPEG", quality=100)

            app.prepare_panorama(source, destination, (400, 100))

            with Image.open(destination) as result:
                self.assertEqual(result.size, (400, 100))
                red, green, blue = result.getpixel((200, 50))
                self.assertLess(red, 20)
                self.assertGreater(green, 100)
                self.assertGreater(blue, 220)

    def test_prepare_panorama_replaces_destination_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jpg"
            destination = Path(directory) / "panorama.jpg"
            Image.new("RGB", (100, 50), "purple").save(source, "JPEG")
            destination.write_bytes(b"old")

            app.prepare_panorama(source, destination, (200, 100))

            with Image.open(destination) as result:
                self.assertEqual(result.size, (200, 100))


if __name__ == "__main__":
    unittest.main()
