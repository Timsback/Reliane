"""Reliane — l'équipe au même tempo. Application Windows locale."""
import argparse
import ctypes
from ctypes import wintypes
import logging
import json
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import win32gui
import win32process

from config import Config, app_dir, resource_dir
from gui import OrganizerGUI, Tray
from hotkeys import HotkeyManager, binding_errors
from notifications import NotificationWatcher
from windows import DofusLogic
from appmeta import VERSION, BUILD_ID
from release_tools import atomic_json, load_release, distribution_dir

APP_NAME = "Reliane"
MUTEX_NAME = "Local\\RELIANE_SINGLE_INSTANCE_V1"


class OrganizerApp:
    def __init__(self, config_path=None, demo=False, no_tray=False):
        self.demo, self.paused, self.closing = demo, False, False
        self.capture_cancel = threading.Event()
        self._command_stop = threading.Event()
        self._command_seen = time.time_ns()
        self.config = Config(config_path, memory=demo)
        logging.info("Reliane %s build %s ; configuration %s ; demo=%s", VERSION, BUILD_ID, self.config.filename, demo)
        self.hotkeys = HotkeyManager(self.config.get("keyboard_layout"), enabled=not demo)
        self.logic = DofusLogic(self.config)
        if demo:
            from demo import DemoLogic
            self.logic = DemoLogic(self.config)
        self.notifier = NotificationWatcher(self.config, lambda texts: self.gui.ui(lambda: self.on_notification(texts)))
        self.tray = None
        self.gui = OrganizerGUI(self)
        self.logic.scan_slots()
        self.rebind_hotkeys()
        if not demo:
            try:
                self.hotkeys.start()
            except Exception:
                logging.exception("Installation des raccourcis")
                self.config.warnings.append("Les raccourcis n'ont pas pu démarrer. Essayez le lancement administrateur si le jeu est élevé.")
            self.notifier.start()
        if not no_tray:
            try:
                self.tray = Tray(self)
            except Exception:
                logging.exception("Zone de notification")
        self.gui.refresh_list()
        if self.config.warnings:
            self.gui.root.after(400, lambda: self.gui.show_notices(self.config.warnings))
        if not demo:
            threading.Thread(target=self._watch_commands, daemon=True).start()

    def _allowed(self, global_action=False):
        if self.closing or self.hotkeys.paused:
            return False
        if global_action:
            return True
        if self.paused:
            return False
        fg = win32gui.GetForegroundWindow()
        try:
            if win32process.GetWindowThreadProcessId(fg)[1] == os.getpid():
                return False
        except Exception:
            return False
        return not self.config.get("game_only") or any(a["hwnd"] == fg for a in self.logic.all_accounts)

    def rebind_hotkeys(self):
        cfg, hk = self.config.data, self.hotkeys
        self.gui.radial.cancel()
        hk.clear()
        hk.set_layout(cfg["keyboard_layout"])
        self.binding_issues = binding_errors(cfg, hk)
        def register(combo, callback, global_action=False):
            hk.register(combo, lambda: self.gui.ui(lambda: callback() if self._allowed(global_action) else None))
        for key, callback in (("prev_key", self.prev_char), ("next_key", self.next_char),
                              ("leader_key", self.focus_leader), ("refresh_key", self.refresh),
                              ("quit_key", self.quit_app)):
            register(cfg.get(key), callback)
        register(cfg.get("toggle_app_key"), self.gui.toggle_visibility, True)
        register(cfg.get("pause_key"), self.toggle_pause, True)
        if cfg["advanced_bind_mode"] == "cycle":
            for i, combo in enumerate(cfg["cycle_row_binds"]):
                register(combo, lambda i=i: self.focus_position(i))
        else:
            for name, combo in cfg["persistent_character_binds"].items():
                register(combo, lambda name=name: self.focus_name(name))
        if cfg.get("radial_menu_active"):
            hk.register_hold(cfg["radial_menu_hotkey"],
                             lambda: self.gui.ui(lambda: self.open_radial() if self._allowed() else None),
                             lambda: self.gui.ui(self.gui.radial.hide))

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.gui.radial.cancel()
        self.gui.update_status()
        self.gui.flash("Raccourcis en pause" if self.paused else "Raccourcis réactivés")

    def _current_index(self, cycle):
        fg = self.logic.foreground if self.demo else win32gui.GetForegroundWindow()
        return next((i for i, account in enumerate(cycle) if account["hwnd"] == fg), None)

    def _step(self, delta):
        cycle = self.logic.get_cycle_list()
        if not cycle:
            self.gui.flash("Aucun personnage dans le cycle. Activez une fenêtre détectée.")
            return
        index = self._current_index(cycle)
        index = (0 if delta > 0 else len(cycle)-1) if index is None else (index+delta) % len(cycle)
        self.focus_hwnd(cycle[index]["hwnd"])

    def next_char(self):
        self._step(1)

    def prev_char(self):
        self._step(-1)

    def focus_leader(self):
        if self.logic.leader_hwnd:
            self.focus_hwnd(self.logic.leader_hwnd)
        else:
            self.gui.flash("Choisissez un meneur avec l'étoile d'un personnage connecté.")

    def focus_position(self, index):
        cycle = self.logic.get_cycle_list()
        if 0 <= index < len(cycle):
            self.focus_hwnd(cycle[index]["hwnd"])

    def focus_name(self, name):
        account = self.logic.find(name)
        if account:
            self.focus_hwnd(account["hwnd"])

    def focus_hwnd(self, hwnd):
        if self.logic.focus_window(hwnd):
            self.gui.refresh_list()
        else:
            self.gui.flash("Windows a refusé le focus ou la fenêtre a été fermée. Actualisez la liste.", error=True)

    def open_radial(self):
        cycle = self.logic.get_cycle_list()
        index = self._current_index(cycle)
        self.gui.radial.show(cycle, cycle[index]["name"] if index is not None else None)

    def on_radial_select(self, account):
        self.focus_hwnd(account["hwnd"])

    def on_notification(self, texts):
        if self.paused or not self.config.get("auto_focus_retro") or self.config.get("game_version") == "Unity":
            return
        blob = " ".join(texts).casefold()
        for account in self.logic.get_cycle_list():
            if re.search(r"(?<![\w-])" + re.escape(account["name"].casefold()) + r"(?![\w-])", blob):
                self.focus_hwnd(account["hwnd"])
                return

    def refresh(self):
        self.logic.scan_slots()
        self.rebind_hotkeys()
        self.gui.refresh_list()

    def poll_update_request(self):
        if self.demo or self.gui._capturing:
            return
        path = Path(self.config.filename).parent / "reliane-command.json"
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            timestamp = request["timestamp"]
            if timestamp <= self._command_seen:
                return
            self._command_seen = timestamp
            logging.info("Demande de lancement reçue pour le build %s", request.get("build"))
            if request.get("build") != BUILD_ID:
                self.gui.offer_restart(self.restart_latest)
            else:
                self.gui.show()
                self.gui.flash(f"Reliane {VERSION} est à jour avec la dernière version installée.")
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError):
            logging.exception("Vérification d'une demande de lancement")

    def _watch_commands(self):
        # L'affichage / redémarrage reste indépendant de la détection des jeux.
        while not self._command_stop.wait(0.5):
            self.gui.ui(self.poll_update_request)

    def restart_latest(self):
        _release, binary = load_release(distribution_dir())
        subprocess.Popen([str(binary), "--config", self.config.filename, "--wait-pid", str(os.getpid())],
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
        self.quit_app()

    def check_updates(self):
        if self.demo:
            self.gui.flash("Les mises à jour s'effectuent depuis l'application normale, hors démonstration.")
            return
        distribution = distribution_dir()
        launcher = distribution / "Reliane.exe"
        if not launcher.is_file():
            self.gui.flash("Lanceur absent : exécutez build.bat.", error=True)
            return
        subprocess.Popen([str(launcher), "--update", "--config", self.config.filename],
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))

    def quit_app(self):
        # Peut être appelée depuis pystray ; toute destruction Tk reste sur son thread.
        if threading.current_thread() is not threading.main_thread():
            self.gui.ui(self.quit_app)
            return
        if self.closing:
            return
        self.closing = True
        self._command_stop.set()
        self.capture_cancel.set()
        self.notifier.stop()
        self.hotkeys.stop()
        if self.tray:
            self.tray.stop()
        self.gui.radial.cancel()
        self.gui.root.destroy()

    def run(self):
        self.gui.run()


def is_admin():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def run_as_admin():
    args = sys.argv[1:] if getattr(sys, "frozen", False) else [os.path.abspath(sys.argv[0])] + sys.argv[1:]
    args = [arg for arg in args if arg != "--admin"] + ["--no-admin"]
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                              subprocess.list2cmdline(args), app_dir(), 1) > 32


def single_instance(config_path=None):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        folder = Path(config_path).resolve().parent if config_path else Path(app_dir())
        atomic_json(folder / "reliane-command.json", {"timestamp": time.time_ns(), "build": BUILD_ID})
        sys.exit(0)
    return handle


def main():
    parser = argparse.ArgumentParser(description="Reliane — gestionnaire d'équipe Dofus")
    parser.add_argument("--demo", action="store_true", help="Démonstration isolée, sans hooks ni sauvegarde")
    parser.add_argument("--config", help="Chemin du fichier settings.json")
    parser.add_argument("--admin", action="store_true", help="Élévation facultative si Dofus est administrateur")
    parser.add_argument("--no-admin", action="store_true", help="Compatibilité : lancement normal")
    parser.add_argument("--no-tray", action="store_true", help="Fermer l'application avec la croix")
    parser.add_argument("--self-test", metavar="JSON", help="Écrire un diagnostic de packaging sans ouvrir l'interface")
    parser.add_argument("--wait-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.wait_pid:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        process = kernel.OpenProcess(0x00100000, False, args.wait_pid)
        if process:
            result = kernel.WaitForSingleObject(process, 30000)
            kernel.CloseHandle(process)
            if result != 0:
                return
    if args.self_test:
        from notifications import AVAILABLE
        from windows import UNITY_CLASSES, RETRO_CLASSES
        assets = Path(resource_dir()) / "assets"
        files = [assets / "dofus-emeraude.png", assets / "reliane.png", assets / "reliane.ico"]
        portraits = [assets / "classes" / f"{name.lower()}.png" for name in UNITY_CLASSES]
        portraits += [assets / "classes" / f"{name.lower()}_retro.png" for name in RETRO_CLASSES]
        missing = [str(path.relative_to(assets)) for path in files if not path.is_file()]
        checks = {"version": VERSION, "build": BUILD_ID, "frozen": bool(getattr(sys, "frozen", False)),
                  "missing_assets": missing, "portraits": sum(path.is_file() for path in portraits), "notifications_available": AVAILABLE}
        if AVAILABLE:
            from winrt.windows.ui.notifications import NotificationKinds
            from winrt.windows.ui.notifications.management import UserNotificationListenerAccessStatus
            checks["winrt_projection_loaded"] = bool(NotificationKinds.TOAST) and int(UserNotificationListenerAccessStatus.ALLOWED) >= 0
        output = Path(args.self_test).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(checks, indent=2), encoding="utf-8")
        sys.exit(0 if not missing and AVAILABLE else 1)
    if args.admin and not args.no_admin and not args.demo and not is_admin():
        if run_as_admin():
            return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    log_dir = Path(args.config).resolve().parent if args.config else Path(app_dir())
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "reliane.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    except OSError:
        logging.basicConfig(level=logging.INFO)
    mutex = single_instance(args.config) if not args.demo else None
    try:
        OrganizerApp(args.config, args.demo, args.no_tray).run()
    except Exception as exc:
        logging.exception("Démarrage de Reliane")
        ctypes.windll.user32.MessageBoxW(0, f"Reliane n'a pas pu démarrer.\n{exc}\n\nConsultez reliane.log à côté des réglages.", APP_NAME, 0x10)
    finally:
        if mutex:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    main()
