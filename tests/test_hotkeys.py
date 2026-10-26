import unittest
from unittest.mock import patch
from types import SimpleNamespace

import keyboard

from config import Config
from hotkeys import HotkeyManager, binding_errors, build_layout, normalize_combo


class HotkeyTests(unittest.TestCase):
    def setUp(self):
        self.manager = HotkeyManager(enabled=False)
        self.cfg = Config(memory=True).data

    def tearDown(self):
        self.manager.stop()

    def test_defaults_have_no_conflict(self):
        self.assertEqual(binding_errors(self.cfg, self.manager), [])

    def test_physical_key_aliases_conflict(self):
        self.cfg.update({"next_key": "ctrl+&", "prev_key": "CTRL+1"})
        self.assertTrue(any("Précédent" in error and "Suivant" in error for error in binding_errors(self.cfg, self.manager)))

    def test_unsafe_click_and_radial_keyboard_rejected(self):
        self.cfg.update({"next_key": "left_click", "radial_menu_active": True, "radial_menu_hotkey": "alt+a"})
        issues = binding_errors(self.cfg, self.manager)
        self.assertEqual(len(issues), 2)

    def test_modifier_order_normalized(self):
        self.assertEqual(normalize_combo(" Shift + CTRL + F1 "), "ctrl+shift+f1")

    def test_one_action_per_press_and_pause(self):
        calls = []
        self.manager.register("tab", lambda: calls.append(1))
        down = SimpleNamespace(event_type=keyboard.KEY_DOWN, scan_code=15)
        up = SimpleNamespace(event_type=keyboard.KEY_UP, scan_code=15)
        with patch("hotkeys.current_modifiers", return_value=set()):
            self.manager._on_key(down)
            self.manager._on_key(down)
            self.assertEqual(calls, [1])
            self.manager._on_key(up)
            self.manager._on_key(down)
            self.assertEqual(calls, [1, 1])
            self.manager._on_key(up)
            self.manager.paused = True
            self.manager._on_key(down)
            self.assertEqual(calls, [1, 1])

    def test_layout_maps_physical_keys(self):
        self.assertEqual(build_layout("azerty_fr")["a"], build_layout("qwerty_us")["q"])


if __name__ == "__main__":
    unittest.main()
