"""Détection, focus, ordre et fermeture des fenêtres Dofus."""
import ctypes
import logging
import time
import unicodedata

import win32con
import win32gui
import win32process

UNITY_CLASSES = [
    "Cra", "Ecaflip", "Eliotrope", "Eniripsa", "Enutrof", "Feca", "Forgelance",
    "Huppermage", "Iop", "Osamodas", "Ouginak", "Pandawa", "Roublard", "Sacrieur",
    "Sadida", "Sram", "Steamer", "Xelor", "Zobal",
]
RETRO_CLASSES = [
    "Cra", "Ecaflip", "Eniripsa", "Enutrof", "Feca", "Iop", "Osamodas",
    "Pandawa", "Sacrieur", "Sadida", "Sram", "Xelor",
]
UNKNOWN = "Inconnu"
RETRO_SUFFIX = " - Dofus Retro"
TEAMS = ("Team 1", "Team 2")
VERSIONS = ("Unity", "Rétro")
UNKNOWN_ORDER = 50

_user32 = ctypes.windll.user32
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002


def _plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _match_class(text):
    p = _plain(text)
    for c in UNITY_CLASSES:
        if _plain(c) == p:
            return c
    return None


def _is_dofus_unity_title(title):
    if title.lower().startswith("dofus"):
        return True
    parts = [p.strip() for p in title.split(" - ")]
    return len(parts) >= 2 and _match_class(parts[1]) is not None


def _list_windows(game_version):
    found = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return True
        if game_version == "Unity":
            # Dofus 3 : "Dofus" sur l'écran de connexion, puis "Pseudo - Classe - 3.x - Release".
            if win32gui.GetClassName(hwnd) == "UnityWndClass" and _is_dofus_unity_title(title):
                found.append((hwnd, title))
        elif title == "Dofus Retro" or title.endswith(RETRO_SUFFIX):
            found.append((hwnd, title))
        return True

    win32gui.EnumWindows(cb, None)
    return found


class DofusLogic:
    def __init__(self, config):
        self.config = config
        self.all_accounts = []
        self.leader_hwnd = None

    # ---------- détection ----------
    def scan_slots(self):
        cfg = self.config.data
        version = cfg.get("game_version", "Unity")
        is_retro = version != "Unity"
        classes = cfg.setdefault("classes", {})
        states = cfg.setdefault("accounts_state", {})
        teams = cfg.setdefault("accounts_team", {})
        order = cfg.setdefault("custom_order", [])

        accounts, menu_n, changed = [], 0, False
        for hwnd, title in _list_windows(version):
            if is_retro:
                name = title[: -len(RETRO_SUFFIX)].strip() if title.endswith(RETRO_SUFFIX) else ""
                guessed = None
            else:
                parts = [p.strip() for p in title.split(" - ")]
                name = "" if title.lower().startswith("dofus") else parts[0]
                guessed = _match_class(parts[1]) if len(parts) > 1 else None
            if not name:
                menu_n += 1
                name = f"Menu {'Rétro' if is_retro else 'Unity'} {menu_n}"
            if guessed and classes.get(name) != guessed:
                classes[name] = guessed
                changed = True
            elif name not in classes:
                classes[name] = UNKNOWN
                changed = True
            if name not in order:
                order.append(name)
                changed = True
            accounts.append({
                "name": name,
                "hwnd": hwnd,
                "classe": classes.get(name, UNKNOWN),
                "active": states.get(name, True),
                "team": teams.get(name, "Team 1"),
                "is_retro": is_retro,
            })

        def rank(a):
            return order.index(a["name"]) if a["name"] in order else UNKNOWN_ORDER

        self.all_accounts = sorted(accounts, key=rank)
        leader = cfg.get("leader_name", "")
        self.leader_hwnd = next((a["hwnd"] for a in self.all_accounts if a["name"] == leader), None)
        if changed and not self.config._blocked:
            self.config.save()
        return self.all_accounts

    def get_cycle_list(self):
        mode = self.config.data.get("current_mode", "ALL")
        return [a for a in self.all_accounts
                if a["active"] and (mode == "ALL" or a["team"] == mode)]

    def find(self, name):
        return next((a for a in self.all_accounts if a["name"] == name), None)

    # ---------- ordre d'initiative ----------
    def _update_global_order(self, cycle):
        """Réinjecte l'ordre de la liste visible dans custom_order sans toucher aux autres."""
        order = self.config.data.setdefault("custom_order", [])
        names = [a["name"] for a in cycle]
        for n in names:
            if n not in order:
                order.append(n)
        slots = sorted(order.index(n) for n in names)
        for slot, n in zip(slots, names):
            order[slot] = n
        self.config.save()
        self.all_accounts.sort(key=lambda a: order.index(a["name"]) if a["name"] in order else UNKNOWN_ORDER)

    def move_account(self, name, delta):
        cycle = self.get_cycle_list()
        idx = next((i for i, a in enumerate(cycle) if a["name"] == name), None)
        if idx is None:
            return
        new = idx + delta
        if 0 <= new < len(cycle):
            cycle[idx], cycle[new] = cycle[new], cycle[idx]
            self._update_global_order(cycle)

    def set_account_position(self, name, position):
        cycle = self.get_cycle_list()
        idx = next((i for i, a in enumerate(cycle) if a["name"] == name), None)
        if idx is None:
            return
        acc = cycle.pop(idx)
        cycle.insert(max(0, min(position, len(cycle))), acc)
        self._update_global_order(cycle)

    # ---------- états ----------
    def toggle_account(self, name):
        acc = self.find(name)
        if acc:
            acc["active"] = not acc["active"]
            self.config.data.setdefault("accounts_state", {})[name] = acc["active"]
            self.config.save()

    def change_team(self, name):
        acc = self.find(name)
        if acc:
            acc["team"] = "Team 2" if acc["team"] == "Team 1" else "Team 1"
            self.config.data.setdefault("accounts_team", {})[name] = acc["team"]
            self.config.save()

    def set_class(self, name, classe):
        self.config.data.setdefault("classes", {})[name] = classe
        acc = self.find(name)
        if acc:
            acc["classe"] = classe
        self.config.save()

    def set_mode(self, mode):
        self.config.set("current_mode", mode)

    def set_leader(self, name):
        acc = self.find(name)
        self.leader_hwnd = acc["hwnd"] if acc else None
        self.config.set("leader_name", name)

    # ---------- actions fenêtres ----------
    def close_account_window(self, name):
        acc = self.find(name)
        if acc:
            # WM_CLOSE laisse le client afficher sa confirmation et libérer ses données.
            win32gui.PostMessage(acc["hwnd"], win32con.WM_CLOSE, 0, 0)
            return True
        return False

    def close_all_active_accounts(self):
        for acc in self.get_cycle_list():
            self.close_account_window(acc["name"])

    @staticmethod
    def focus_window(hwnd):
        """Met une fenêtre au premier plan malgré le verrou de focus de Windows."""
        try:
            if not win32gui.IsWindow(hwnd):
                return False
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            _user32.AllowSetForegroundWindow(pid)
            # Un appui Alt simulé débloque SetForegroundWindow depuis un process en arrière-plan.
            if not _user32.GetAsyncKeyState(VK_MENU) & 0x8000:
                _user32.keybd_event(VK_MENU, 0, 0, 0)
                _user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            win32gui.SetForegroundWindow(hwnd)
            return win32gui.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def sort_taskbar(self):
        """Masque puis réaffiche les fenêtres dans l'ordre pour réordonner la barre des tâches."""
        cycle = list(self.get_cycle_list())
        hidden = []
        try:
            for acc in cycle:
                win32gui.ShowWindow(acc["hwnd"], win32con.SW_HIDE)
                hidden.append(acc["hwnd"])
            time.sleep(0.3)
        finally:
            # Chaque fenêtre masquée doit être restaurée, même si une autre a disparu.
            for hwnd in hidden:
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNA)
                    time.sleep(0.05)
                except Exception:
                    logging.exception("Restauration d'une fenêtre")
        return len(hidden)
