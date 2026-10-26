"""Raccourcis globaux clavier (par scan code) et souris (par polling)."""
import ctypes
import logging
import threading
import time

import keyboard

_user32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x0002

MODIFIER_VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10}
MODIFIER_NAMES = {"ctrl", "alt", "shift", "left ctrl", "right ctrl", "left alt", "right alt",
                  "alt gr", "left shift", "right shift", "left windows", "right windows"}
MOUSE_VK = {"left_click": 0x01, "right_click": 0x02, "middle_click": 0x04,
            "mouse4": 0x05, "mouse5": 0x06}

# Scan codes matériels (identiques en AZERTY/QWERTY : seul le libellé change).
_COMMON = {
    **{f"f{i}": 58 + i for i in range(1, 11)}, "f11": 87, "f12": 88,
    "tab": 15, "enter": 28, "space": 57, "esc": 1, "backspace": 14,
    "num 0": 82, "num 1": 79, "num 2": 80, "num 3": 81, "num 4": 75,
    "num 5": 76, "num 6": 77, "num 7": 71, "num 8": 72, "num 9": 73,
    **{str(d): (11 if d == 0 else d + 1) for d in range(10)},
}
_ROWS = {
    "azerty_fr": ("azertyuiop", "qsdfghjklm", "wxcvbn",
                  {"²": 41, "&": 2, "é": 3, '"': 4, "'": 5, "(": 6, "-": 7, "è": 8,
                   "_": 9, "ç": 10, "à": 11, ")": 12, "=": 13, "^": 26, "$": 27,
                   "ù": 40, "*": 43, "<": 86, ",": 50, ";": 51, ":": 52, "!": 53}),
    "qwerty_us": ("qwertyuiop", "asdfghjkl", "zxcvbnm",
                  {"`": 41, "-": 12, "=": 13, "[": 26, "]": 27, ";": 39, "'": 40,
                   "\\": 43, ",": 51, ".": 52, "/": 53}),
}
LAYOUTS = {"azerty_fr": "Français (AZERTY)", "qwerty_us": "English (QWERTY)"}
WINDOWS_LAYOUT_IDS = {"azerty_fr": "0000040C", "qwerty_us": "00000409"}


def build_layout(layout):
    top, mid, bot, extra = _ROWS.get(layout, _ROWS["azerty_fr"])
    keys = dict(_COMMON)
    for row, start in ((top, 16), (mid, 30), (bot, 44)):
        for i, ch in enumerate(row):
            keys[ch] = start + i
    keys.update(extra)
    return keys


def normalize_combo(combo):
    mods, keys = [], []
    for part in (p.strip().lower() for p in combo.split("+") if p.strip()):
        if part in MODIFIER_VK:
            if part not in mods:
                mods.append(part)
        else:
            keys.append(part)
    return "+".join([m for m in MODIFIER_VK if m in mods] + keys)


def split_combo(combo):
    """'ctrl+F1' -> ({'ctrl'}, 'f1')"""
    parts = normalize_combo(combo).split("+") if combo else []
    mods = {p for p in parts if p in MODIFIER_VK}
    rest = [p for p in parts if p not in MODIFIER_VK]
    return mods, (rest[-1] if rest else None)


def current_modifiers():
    return {m for m, vk in MODIFIER_VK.items() if _user32.GetAsyncKeyState(vk) & 0x8000}


def is_down(vk):
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def release_modifiers():
    held = current_modifiers()
    for m in held:
        _user32.keybd_event(MODIFIER_VK[m], 0, KEYEVENTF_KEYUP, 0)
    return held


def restore_modifiers(held):
    for m in held:
        if is_down(MODIFIER_VK[m]):
            _user32.keybd_event(MODIFIER_VK[m], 0, 0, 0)


class HotkeyManager:
    """Associe des combinaisons à des callbacks. Les callbacks tournent dans un thread dédié."""

    def __init__(self, layout="azerty_fr", enabled=True):
        self.set_layout(layout)
        self.key_actions = {}      # (frozenset(mods), scan_code) -> callback
        self.mouse_actions = {}    # (frozenset(mods), mouse_name) -> callback
        self.mouse_hold = {}       # combos souris "maintenues" : combo -> (on_press, on_release)
        self._mouse_state = {}
        self.paused = False
        self._hooked = False
        self._hook = None
        self._pressed = set()
        self._stop = threading.Event()
        if enabled:
            threading.Thread(target=self._mouse_loop, daemon=True).start()

    def set_layout(self, layout):
        self.keymap = build_layout(layout)

    def scan_code(self, key):
        if key in self.keymap:
            return self.keymap[key]
        try:
            codes = keyboard.key_to_scan_codes(key)
            return codes[0] if codes else None
        except (ValueError, KeyError):
            return None

    def clear(self):
        self.key_actions.clear()
        self.mouse_actions.clear()
        self.mouse_hold.clear()
        self._mouse_state.clear()

    def register(self, combo, callback):
        if not combo:
            return
        mods, key = split_combo(combo)
        if key is None:
            return
        if key in MOUSE_VK:
            self.mouse_actions[(frozenset(mods), key)] = callback
            return
        sc = self.scan_code(key)
        if sc is not None:
            self.key_actions[(frozenset(mods), sc)] = callback

    def register_hold(self, combo, on_press, on_release):
        """Combo souris maintenue (roue radiale) : press à l'appui, release au relâchement."""
        mods, key = split_combo(combo)
        if key in MOUSE_VK:
            self.mouse_hold[(frozenset(mods), key)] = (on_press, on_release)

    def start(self):
        if not self._hooked:
            self._hook = keyboard.hook(self._on_key)
            self._hooked = True

    def stop(self):
        if self._hooked:
            keyboard.unhook(self._hook)
            self._hooked = False
        self._stop.set()

    def _run(self, cb):
        # Les callbacks déposent des actions dans la file Tk : aucun état partagé
        # modifié depuis les hooks, aucune simulation de Ctrl/Alt/Shift.
        try:
            cb()
        except Exception:
            logging.exception("Erreur de raccourci")

    def _on_key(self, event):
        if event.event_type != keyboard.KEY_DOWN:
            self._pressed.discard(event.scan_code)
            return
        if self.paused or event.scan_code in self._pressed:
            return
        self._pressed.add(event.scan_code)
        cb = self.key_actions.get((frozenset(current_modifiers()), event.scan_code))
        if cb:
            self._run(cb)

    def _mouse_loop(self):
        while not self._stop.is_set():
            try:
                if not self.paused:
                    mods = frozenset(current_modifiers())
                    for (need, btn), cb in list(self.mouse_actions.items()):
                        self._edge((need, btn), mods == need and is_down(MOUSE_VK[btn]),
                                   lambda c=cb: self._run(c), None)
                    for (need, btn), (press, release) in list(self.mouse_hold.items()):
                        # Une fois ouverte, la roue reste tant que le bouton est tenu.
                        held = is_down(MOUSE_VK[btn])
                        active = held and (mods == need or self._mouse_state.get(("hold", btn)))
                        self._edge(("hold", btn), bool(active), press, release)
            except Exception:
                pass
            self._stop.wait(0.015)

    def _edge(self, key, pressed, on_press, on_release):
        was = self._mouse_state.get(key, False)
        if pressed and not was and on_press:
            on_press()
        elif not pressed and was and on_release:
            on_release()
        self._mouse_state[key] = pressed


def capture_combo(timeout=10.0, layout="azerty_fr", cancel=None):
    """Bloque jusqu'à la prochaine touche (ou bouton souris) et renvoie la combinaison. Esc = annuler."""
    result = {}
    done = threading.Event()
    keymap = build_layout(layout)
    physical_names = {scan: key for key, scan in keymap.items()}

    def on_key(e):
        if e.event_type != keyboard.KEY_DOWN or done.is_set():
            return
        name = (e.name or "").lower()
        if name in MODIFIER_NAMES:
            return
        if name == "esc":
            result["combo"] = None
        else:
            mods = [m for m in ("ctrl", "alt", "shift") if m in current_modifiers()]
            # La capture et l'exécution utilisent la même disposition physique.
            key = physical_names.get(e.scan_code, name)
            result["combo"] = "+".join(mods + [key])
        done.set()

    hook = keyboard.hook(on_key)
    # Les boutons souris : on attend qu'ils soient relâchés au départ (clic sur le bouton "capturer").
    end = time.monotonic() + timeout
    try:
        while any(is_down(vk) for vk in MOUSE_VK.values()) and time.monotonic() < end:
            if cancel and cancel.is_set():
                return None
            time.sleep(0.01)
        while not done.is_set() and time.monotonic() < end:
            if cancel and cancel.is_set():
                return None
            for name, vk in MOUSE_VK.items():
                if is_down(vk):
                    mods = [m for m in ("ctrl", "alt", "shift") if m in current_modifiers()]
                    result["combo"] = "+".join(mods + [name])
                    done.set()
                    break
            time.sleep(0.01)
    finally:
        keyboard.unhook(hook)
    return result.get("combo")


ACTION_LABELS = {"prev_key": "Précédent", "next_key": "Suivant", "leader_key": "Meneur",
                 "toggle_app_key": "Afficher Reliane", "refresh_key": "Actualiser",
                 "quit_key": "Quitter", "pause_key": "Pause des raccourcis"}


def binding_errors(cfg, manager):
    """Détecte les conflits réels, y compris deux libellés pour le même scan code."""
    entries = [(label, cfg.get(key, ""), False) for key, label in ACTION_LABELS.items()]
    if cfg.get("advanced_bind_mode") == "cycle":
        entries += [(f"Place {i + 1}", combo, False) for i, combo in enumerate(cfg.get("cycle_row_binds", []))]
    else:
        entries += [(name, combo, False) for name, combo in cfg.get("persistent_character_binds", {}).items()]
    if cfg.get("radial_menu_active"):
        entries.append(("Roue de sélection", cfg.get("radial_menu_hotkey", ""), True))
    errors, seen = [], {}
    for label, combo, radial in entries:
        if not combo:
            if radial:
                errors.append("La roue nécessite un raccourci souris.")
            continue
        mods, key = split_combo(combo)
        parts = normalize_combo(combo).split("+")
        if key is None or len([p for p in parts if p not in MODIFIER_VK]) != 1:
            errors.append(f"{label} : combinaison invalide.")
            continue
        if key in ("left_click", "right_click") and not mods:
            errors.append(f"{label} : ajoutez Ctrl, Alt ou Maj au clic.")
        if radial and key not in MOUSE_VK:
            errors.append("La roue nécessite un bouton souris.")
        code = key if key in MOUSE_VK else manager.scan_code(key)
        if code is None:
            errors.append(f"{label} : touche « {key} » inconnue.")
            continue
        identity = (frozenset(mods), code)
        if identity in seen:
            errors.append(f"{label} et {seen[identity]} utilisent {combo.upper()}.")
        else:
            seen[identity] = label
    return errors


def load_windows_layout(layout):
    try:
        _user32.LoadKeyboardLayoutW(WINDOWS_LAYOUT_IDS.get(layout, "0000040C"), 1)
    except Exception:
        pass
