import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from launcher import locate
from release_tools import SOURCE_NAMES, atomic_json, file_digest, load_release, source_digest, distribution_dir


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parent / ".tmp"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_verified_release_and_tamper_detection(self):
        binary = self.root / "releases" / "1.1.0-aaaaaaaaaaaaaaaa" / "Reliane-app.exe"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"MZ-test-fixture")
        atomic_json(self.root / "release.json", {"version": "1.1.0", "build": "a"*16,
                    "file": str(binary.relative_to(self.root)), "sha256": file_digest(binary)})
        release, path = load_release(self.root)
        self.assertEqual(path, binary)
        binary.write_bytes(b"damaged")
        with self.assertRaises(ValueError):
            load_release(self.root)

    def test_manifest_cannot_launch_outside_releases(self):
        atomic_json(self.root / "release.json", {"version": "1.1.0", "build": "a"*16,
                    "file": "../other.exe", "sha256": "b"*64})
        with self.assertRaises(ValueError):
            load_release(self.root, verify=False)

    def test_source_change_is_detected_and_metadata_does_not_loop(self):
        for name in SOURCE_NAMES:
            (self.root / name).write_text(name, encoding="utf-8")
        assets = self.root / "assets"
        assets.mkdir()
        (assets / "icon.png").write_bytes(b"image")
        before = source_digest(self.root)
        atomic_json(assets / "release-build.json", {"build": before})
        self.assertEqual(source_digest(self.root), before)
        (self.root / "gui.py").write_text("new UI", encoding="utf-8")
        self.assertNotEqual(source_digest(self.root), before)

    def test_root_and_dist_launcher_resolve_same_distribution(self):
        (self.root / "main.py").write_text("# source", encoding="utf-8")
        (self.root / "dist").mkdir()
        self.assertEqual(locate(self.root), locate(self.root / "dist"))

    def test_release_location_does_not_depend_on_settings_directory(self):
        (self.root/"release.json").write_text("{}", encoding="utf-8")
        executable = self.root/"releases"/"version"/"Reliane-app.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"MZ")
        with patch("release_tools.sys.executable", str(executable)), patch("release_tools.sys.frozen", True, create=True):
            self.assertEqual(distribution_dir(), self.root)
