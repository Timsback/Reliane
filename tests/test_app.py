"""Parcours de bout en bout sur les vrais widgets Tk, avec une équipe isolée."""
import json
from pathlib import Path
import tempfile
import unittest
import customtkinter as ctk
from unittest.mock import patch

from config import ConfigError
from main import OrganizerApp


class AppTests(unittest.TestCase):
    def test_complete_demo_journey_and_responsive_layout(self):
        app = OrganizerApp(demo=True, no_tray=True)
        gui = app.gui
        failures = []
        gui.root.report_callback_exception = lambda *args: failures.append(str(args[1]))
        try:
            gui.root.update()
            with patch.object(gui.root, "focus_force", side_effect=AssertionError("Le focus Windows ne doit pas être forcé")):
                gui.show()
            restarted = []
            gui.offer_restart(lambda: restarted.append(True))
            gui.root.update()
            update_dialog = gui._update_dialog
            self.assertIn("Mise à jour prête", update_dialog.title())
            def controls(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from controls(child)
            restart_button = next(control for control in controls(update_dialog)
                                  if isinstance(control, ctk.CTkButton) and control.cget("text") == "Redémarrer")
            restart_button.invoke()
            self.assertEqual(restarted, [True])
            with patch("main.load_release", return_value=({}, Path(__file__))), patch("main.subprocess.Popen") as spawn, patch.object(app, "quit_app") as quit_mock:
                app.restart_latest()
                self.assertEqual(spawn.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
                quit_mock.assert_called_once()
            self.assertEqual(len(app.logic.all_accounts), 6)
            self.assertEqual(app.logic.foreground, 101)
            app.next_char()
            self.assertEqual(app.logic.foreground, 102)
            app.prev_char()
            self.assertEqual(app.logic.foreground, 101)
            app.prev_char()
            self.assertEqual(app.logic.foreground, 106)
            gui._do(app.logic.toggle_account, "Lichen")
            self.assertEqual(len(app.logic.get_cycle_list()), 5)
            gui.on_mode_change("Team 2")
            self.assertEqual([a["name"] for a in app.logic.get_cycle_list()], ["Nacre"])
            gui.on_mode_change("ALL")
            gui._do(app.logic.set_leader, "Mistral")
            app.focus_leader()
            self.assertEqual(app.logic.foreground, 102)
            app.toggle_pause()
            self.assertTrue(app.paused)
            app.toggle_pause()
            self.assertFalse(app.paused)
            app.open_radial()
            self.assertTrue(gui.radial.is_open)
            gui.radial.cancel()
            self.assertFalse(gui.radial.is_open)
            for geometry in ("1080x880", "620x660"):
                gui.root.geometry(geometry)
                gui.root.update()
                for page in ("Équipe", "Raccourcis", "Réglages"):
                    gui.show_page(page)
                    gui.root.update()
                    self.assertEqual(gui.page, page)
                    self.assertLessEqual(gui.body.winfo_x()+gui.body.winfo_width(), gui.root.winfo_width())
                    if page == "Équipe":
                        for row in gui.list_frame.winfo_children():
                            for control in row.winfo_children():
                                if control.winfo_manager() == "grid":
                                    self.assertLessEqual(control.winfo_x()+control.winfo_width(), row.winfo_width())
                    if page == "Réglages":
                        def descendants(widget):
                            for child in widget.winfo_children():
                                yield child
                                yield from descendants(child)
                        switch = next(control for control in descendants(gui.body) if isinstance(control, ctk.CTkSwitch))
                        before = switch._canvas._reliane_layers["slider_parts"]["params"][3]
                        self.assertLess(before[2]-before[0], switch._canvas.winfo_width()*.65)
                        switch.toggle()
                        gui.root.update()
                        after = switch._canvas._reliane_layers["slider_parts"]["params"][3]
                        self.assertNotEqual(before[0], after[0])
            self.assertTrue(gui._compact)
            gui.show_page("Raccourcis")
            previous = app.config.get("next_key")
            with self.assertRaises(ConfigError):
                gui.set_hotkey("next_key", "tab")
            self.assertEqual(app.config.get("next_key"), previous)
            gui.set_hotkey("next_key", "ctrl+shift+f8")
            self.assertEqual(app.config.get("next_key"), "ctrl+shift+f8")
            gui.set_direct(0, "alt+f6")
            self.assertEqual(app.config.get("cycle_row_binds")[0], "alt+f6")
            app.config.save_profile("Test parcours")
            app.logic.set_leader("Braise")
            gui.show_page("Équipe")
            with patch("gui.messagebox.askyesno", return_value=True):
                gui.load_profile("Test parcours")
            self.assertEqual(app.config.get("leader_name"), "Mistral")
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent / ".tmp") as folder:
                exported = Path(folder) / "export.json"
                with patch("gui.filedialog.asksaveasfilename", return_value=str(exported)):
                    gui.export_config()
                self.assertEqual(json.loads(exported.read_text(encoding="utf-8"))["leader_name"], "Mistral")
                with patch("gui.filedialog.askopenfilename", return_value=str(exported)), patch("gui.messagebox.askyesno", return_value=True):
                    gui.import_config()
            gui.show_page("Équipe")
            gui.edit_character("Mistral")
            gui.root.update()
            window = gui._dialogs[-1]
            self.assertTrue(window.winfo_exists())
            window.destroy()
            gui.logic._closed.update(name for name, _classe in gui.logic.characters)
            app.refresh()
            gui.root.update()
            self.assertFalse(app.logic.all_accounts)
            self.assertFalse(failures, failures)
        finally:
            app.quit_app()


if __name__ == "__main__":
    unittest.main()
