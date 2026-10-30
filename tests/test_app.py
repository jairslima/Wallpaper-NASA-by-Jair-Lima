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

    def test_find_latest_image_uses_feed_when_api_returns_logo(self):
        logo = {
            "media_type": "image",
            "date": "2026-10-30",
            "title": "NASA Science",
            "hdurl": "https://science.nasa.gov/wp-content/themes/nasa-child/assets/images/nasa-logo@2x.png",
        }
        photo = {"media_type": "image", "date": "2026-10-30", "title": "Ghost", "hdurl": "https://x/apod/a.jpg?w=1"}
        with patch.object(app, "request_json", return_value=logo), patch.object(
            app, "fetch_feed_items", return_value=[{**photo, "media_type": "other", "hdurl": "https://youtu.be/x"}, photo]
        ):
            result = app.find_latest_image(date(2026, 10, 30))
        self.assertEqual(result["title"], "Ghost")

    def test_find_latest_image_uses_feed_when_api_is_down(self):
        photo = {"media_type": "image", "date": "2026-10-30", "title": "Ghost", "hdurl": "https://x/apod/a.png"}
        with patch.object(app, "request_json", side_effect=TimeoutError("x")), patch.object(
            app.time, "sleep"
        ), patch.object(app, "fetch_feed_items", return_value=[photo]):
            self.assertEqual(app.find_latest_image(date(2026, 10, 30))["title"], "Ghost")

    def test_fetch_feed_items_parses_rss(self):
        xml = (
            b'<rss xmlns:apod="https://science.nasa.gov/apod/"><channel><item><title>T</title>'
            b"<pubDate>Fri, 30 Oct 2026 04:05:00 +0000</pubDate>"
            b"<apod:hdurl>https://x/apod/a.jpg?w=10&#038;h=5</apod:hdurl></item></channel></rss>"
        )
        with patch.object(app.urllib.request, "urlopen", return_value=Response(xml, "text/xml")):
            items = app.fetch_feed_items()
        self.assertEqual(items[0]["date"], "2026-10-30")
        self.assertEqual(items[0]["hdurl"], "https://x/apod/a.jpg?w=10&h=5")
        self.assertTrue(app.is_real_photo(items[0]))

    def test_fetch_feed_items_rejects_entity_bomb(self):
        xml = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel/></rss>'
        with patch.object(app.urllib.request, "urlopen", return_value=Response(xml, "text/xml")):
            with self.assertRaises(RuntimeError):
                app.fetch_feed_items()

    def test_notify_once_a_day_sends_once_and_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "tg.py"
            script.write_text("def enviar(t):\n    return True, 'enviado'\n", encoding="utf-8")
            with patch.object(app, "APP_DIR", Path(tmp)), patch.object(app, "LOG_PATH", Path(tmp) / "l.log"), patch.object(
                app, "NOTIFY_SCRIPT", script
            ):
                app.notify_once_a_day("falha", "x")
                app.notify_once_a_day("falha", "x")
                log_text = (Path(tmp) / "l.log").read_text(encoding="utf-8")
                state = (Path(tmp) / "notify_state.json").read_text(encoding="utf-8")
            self.assertEqual(log_text.count("Aviso Telegram (falha)"), 1)
            self.assertIn(date.today().isoformat(), state)
            with patch.object(app, "NOTIFY_SCRIPT", Path(tmp) / "inexistente.py"):
                app.notify_once_a_day("outro", "x")  # não levanta

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
