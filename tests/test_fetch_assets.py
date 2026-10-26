from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from fetch_assets import download_icon


class AssetDownloadTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parent/".tmp"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.target = Path(self.temp.name)/"icon.png"

    def tearDown(self):
        self.temp.cleanup()

    def test_html_response_uses_mirror_and_normalizes_image_format(self):
        stream = BytesIO()
        Image.new("RGBA", (16,16), (40,160,70,128)).save(stream, format="WEBP", lossless=True)
        with patch("fetch_assets.urlopen", side_effect=[BytesIO(b"<html>Unavailable</html>"), BytesIO(stream.getvalue())]) as request:
            download_icon(self.target)
        self.assertEqual(request.call_count, 2)
        with Image.open(self.target) as result:
            self.assertEqual(result.format, "PNG")
            self.assertEqual(result.getpixel((8,8)), (40,160,70,128))

    def test_invalid_responses_fail_without_creating_an_asset(self):
        with patch("fetch_assets.urlopen", side_effect=lambda *args,**kwargs: BytesIO(b"not an image")):
            with self.assertRaises(RuntimeError):
                download_icon(self.target)
        self.assertFalse(self.target.exists())
