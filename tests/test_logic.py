import unittest
from unittest.mock import patch

from config import Config
from windows import DofusLogic, _is_dofus_unity_title


class LogicTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(memory=True)
        self.logic = DofusLogic(self.config)
        self.windows = [(11, "Éclat - Crâ - 3.0 - Release"), (12, "B - Pandawa - 3.0"), (13, "C - Iop - 3.0")]

    def scan(self):
        with patch("windows._list_windows", return_value=self.windows):
            self.logic.scan_slots()

    def test_title_detection_and_reject_other_unity_apps(self):
        self.assertTrue(_is_dofus_unity_title("Éclat - Crâ - 3.0"))
        self.assertFalse(_is_dofus_unity_title("Another Unity game"))

    def test_scan_class_and_state_persist_on_reconnect(self):
        self.scan()
        self.assertEqual(self.logic.find("Éclat")["classe"], "Cra")
        self.logic.toggle_account("B")
        self.logic.set_leader("B")
        self.windows = [(19, "B - Pandawa - 3.0")]
        self.scan()
        self.assertEqual(self.logic.leader_hwnd, 19)
        self.assertFalse(self.logic.find("B")["active"])
        self.assertIn("Éclat", self.config.get("custom_order"))

    def test_filtered_move_preserves_other_team_and_inactive_slots(self):
        self.scan()
        self.logic.change_team("B")
        self.logic.set_mode("Team 1")
        self.logic.move_account("C", -1)
        self.assertEqual(self.config.get("custom_order"), ["C", "B", "Éclat"])
        self.assertEqual([a["name"] for a in self.logic.get_cycle_list()], ["C", "Éclat"])
        self.logic.set_account_position("C", 1)
        self.assertEqual(self.config.get("custom_order"), ["Éclat", "B", "C"])

    def test_retro_and_menu_detection(self):
        self.config.set("game_version", "Rétro")
        self.windows = [(1, "A - Dofus Retro"), (2, "Dofus Retro")]
        self.scan()
        self.assertEqual(self.logic.all_accounts[0]["name"], "A")
        self.assertEqual(self.logic.all_accounts[1]["name"], "Menu Rétro 1")

    def test_close_sends_normal_window_close(self):
        self.scan()
        with patch("windows.win32gui.PostMessage") as post:
            self.logic.close_account_window("B")
        self.assertEqual(post.call_args.args[0], 12)
        self.assertEqual(post.call_args.args[1], 0x10)

    def test_taskbar_restores_hidden_windows_after_failure(self):
        self.scan()
        calls = []
        def show(hwnd, mode):
            calls.append((hwnd, mode))
            if hwnd == 12 and mode == 0:
                raise RuntimeError("window gone")
        with patch("windows.win32gui.ShowWindow", side_effect=show):
            with self.assertRaises(RuntimeError):
                self.logic.sort_taskbar()
        self.assertIn((11, 8), calls)


if __name__ == "__main__":
    unittest.main()
