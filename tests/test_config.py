import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from config import Config, ConfigError, DEFAULTS, validate


class ConfigTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parent / ".tmp"
        test_root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=test_root)
        self.path = Path(self.folder.name) / "settings.json"

    def tearDown(self):
        self.folder.cleanup()

    def test_legacy_migration_preserves_unknown_data_and_unicode(self):
        raw = {"leader_name": "Éclat", "classes": {"Éclat": "Cra"}, "unknown_legacy": {"a": 1}}
        self.path.write_text(json.dumps(raw), encoding="utf-8")
        cfg = Config(self.path)
        self.assertEqual(cfg.get("leader_name"), "Éclat")
        self.assertTrue(cfg.get("game_only"))
        cfg.set("next_key", "alt+²")
        self.assertEqual(Config(self.path).get("unknown_legacy"), {"a": 1})
        self.assertEqual(json.loads(Path(str(self.path)+".bak").read_text())["leader_name"], "Éclat")

    def test_invalid_structures_and_profiles_rejected(self):
        for raw in ([], {"classes": []}, {"accounts_state": {"A": "false"}},
                    {"profiles": {"bad": {"custom_order": 1}}}, {"accounts_team": {"A": "wrong"}}):
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                validate(raw)

    def test_corrupt_file_is_never_overwritten(self):
        self.path.write_text("{ broken", encoding="utf-8")
        cfg = Config(self.path)
        self.assertTrue(cfg.warnings)
        with self.assertRaises(ConfigError):
            cfg.set("leader_name", "A")
        self.assertEqual(self.path.read_text(), "{ broken")
        self.assertEqual(cfg.get("leader_name"), "")

    def test_corruption_recovers_backup_and_retains_original(self):
        cfg = Config(self.path)
        cfg.set("leader_name", "A")
        cfg.set("leader_name", "B")
        self.path.write_text("{ damaged", encoding="utf-8")
        cfg = Config(self.path)
        self.assertEqual(cfg.get("leader_name"), "A")
        self.assertTrue(list(self.path.parent.glob("*.illisible-*")))
        cfg.replace(cfg.data)
        self.assertEqual(Config(self.path).get("leader_name"), "A")
        self.assertTrue(list(self.path.parent.glob("*.avant-import-*")))

    def test_failed_write_rolls_back_in_memory(self):
        cfg = Config(self.path)
        cfg.set("leader_name", "A")
        with patch("config.os.replace", side_effect=PermissionError("read only")):
            with self.assertRaises(ConfigError):
                cfg.set("leader_name", "B")
        self.assertEqual(cfg.get("leader_name"), "A")
        self.assertEqual(Config(self.path).get("leader_name"), "A")

    def test_profiles_are_independent_and_persistent(self):
        cfg = Config(self.path)
        cfg.update({"custom_order": ["A", "B"], "leader_name": "A"})
        cfg.save_profile("Donjon")
        cfg.data["custom_order"].reverse()
        cfg.set("leader_name", "B")
        cfg.load_profile("Donjon")
        self.assertEqual(cfg.get("custom_order"), ["A", "B"])
        self.assertEqual(cfg.get("leader_name"), "A")
        self.assertEqual(Config(self.path).get("profiles"), cfg.get("profiles"))
        cfg.delete_profile("Donjon")
        self.assertEqual(cfg.get("leader_name"), "A")
        self.assertEqual(cfg.get("profiles"), {})

    def test_demo_does_not_touch_disk(self):
        cfg = Config(self.path, memory=True)
        cfg.save_profile("Test")
        cfg.set("leader_name", "Demo")
        self.assertFalse(self.path.exists())

    def test_invalid_import_does_not_replace_config(self):
        cfg = Config(self.path)
        cfg.set("leader_name", "A")
        with self.assertRaises(ConfigError):
            cfg.replace({"classes": []})
        self.assertEqual(Config(self.path).get("leader_name"), "A")


if __name__ == "__main__":
    unittest.main()
