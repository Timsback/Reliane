from pathlib import Path
import unittest

from PIL import Image

from icons import _find_png
from smooth_widgets import raster
from theme import THEME, logo
from windows import UNITY_CLASSES, RETRO_CLASSES


class VisualTests(unittest.TestCase):
    def test_all_classes_have_bundled_portraits(self):
        if not _find_png("Cra", False):
            self.skipTest("Portraits de jeu optionnels non fournis dans le dépôt public.")
        for retro, classes in ((False, UNITY_CLASSES), (True, RETRO_CLASSES)):
            for name in classes:
                with self.subTest(name=name, retro=retro):
                    path = _find_png(name, retro)
                    self.assertIsNotNone(path)
                    with Image.open(path) as source:
                        self.assertGreaterEqual(min(source.size), 64)

    def test_small_logo_has_transparency_and_legible_silhouette(self):
        for size in (16, 32, 64, 256):
            mark = logo(size=size)
            self.assertEqual(mark.size, (size, size))
            self.assertEqual(mark.mode, "RGBA")
            alpha = mark.getchannel("A")
            self.assertEqual(alpha.getpixel((0, 0)), 0)
            self.assertGreater(alpha.getpixel((size//2, size//2)), 240)

    def test_rounded_edges_are_antialiased(self):
        image = raster(100, 36, "round", (0, 0, 99.75, 35.75), 8, "#B5C978")
        alpha = image.getchannel("A")
        values = set(alpha.crop((0, 0, 10, 10)).get_flattened_data())
        self.assertGreater(len(values - {0, 255}), 8)

    def test_text_contrast(self):
        def luminance(color):
            channels = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
            channels = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
            return sum(v*w for v, w in zip(channels, (.2126, .7152, .0722)))
        for foreground, background in (("text", "panel"), ("muted", "panel"), ("on_accent", "accent"), ("text", "row_active")):
            a, b = sorted((luminance(THEME[foreground]), luminance(THEME[background])))
            self.assertGreaterEqual((b+.05)/(a+.05), 4.5)
