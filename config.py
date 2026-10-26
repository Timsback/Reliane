"""Configuration portable, migrations non destructives et compositions d'équipe."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

DOSOFT_SETTINGS = r"C:\Program Files (x86)\Dosoft\settings.json"
DEFAULTS = {
    "prev_key": "tab", "next_key": "²", "leader_key": "f1",
    "toggle_app_key": "f10", "refresh_key": "f5", "quit_key": "",
    "pause_key": "ctrl+f10", "leader_name": "", "accounts_state": {},
    "accounts_team": {}, "current_mode": "ALL", "classes": {}, "custom_order": [],
    "radial_menu_active": False, "radial_menu_hotkey": "alt+left_click",
    "game_version": "Unity", "auto_focus_retro": False,
    "advanced_bind_mode": "cycle", "advanced_bind_modifier": "ctrl",
    "persistent_character_binds": {},
    "cycle_row_binds": [f"ctrl+f{i}" for i in range(1, 9)],
    "keyboard_layout": "azerty_fr", "language": "fr", "notif_api_mode": "v3",
    "theme": "reliane", "always_on_top": False, "game_only": True,
    "profiles": {}, "current_profile": "", "schema_version": 2,
}
PROFILE_KEYS = ("leader_name", "accounts_state", "accounts_team", "classes", "custom_order",
                "current_mode", "game_version", "advanced_bind_mode", "cycle_row_binds",
                "persistent_character_binds")
ENUMS = {"current_mode": ("ALL", "Team 1", "Team 2"), "game_version": ("Unity", "Rétro"),
         "advanced_bind_mode": ("cycle", "bind"), "keyboard_layout": ("azerty_fr", "qwerty_us"),
         "notif_api_mode": ("v2", "v3")}


def app_dir():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))


def resource_dir():
    return getattr(sys, "_MEIPASS", app_dir())


class ConfigError(Exception):
    pass


def validate(raw):
    if not isinstance(raw, dict):
        raise ConfigError("Le fichier doit contenir un objet JSON.")
    result = copy.deepcopy(DEFAULTS)
    result.update(copy.deepcopy(raw))
    for key, default in DEFAULTS.items():
        if type(result[key]) is not type(default):
            raise ConfigError(f"Format invalide pour « {key} ».")
    for key, values in ENUMS.items():
        if result[key] not in values:
            raise ConfigError(f"Valeur inconnue pour « {key} ».")
    for key in ("custom_order", "cycle_row_binds"):
        if not all(isinstance(v, str) for v in result[key]):
            raise ConfigError(f"« {key} » doit être une liste de textes.")
    result["custom_order"] = list(dict.fromkeys(result["custom_order"]))
    for key in ("classes", "accounts_team", "persistent_character_binds"):
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in result[key].items()):
            raise ConfigError(f"Format invalide pour « {key} ».")
    if any(v not in ("Team 1", "Team 2") for v in result["accounts_team"].values()):
        raise ConfigError("Une équipe doit être Team 1 ou Team 2.")
    if not all(isinstance(k, str) and type(v) is bool for k, v in result["accounts_state"].items()):
        raise ConfigError("Les états des personnages doivent être des booléens.")
    for name, profile in result["profiles"].items():
        if not isinstance(name, str) or not name.strip() or len(name) > 40 or not isinstance(profile, dict):
            raise ConfigError("Composition d'équipe invalide.")
        validate({k: v for k, v in profile.items() if k in PROFILE_KEYS})
    return result


class Config:
    def __init__(self, filename=None, memory=False):
        self.filename = str(filename or os.path.join(app_dir(), "settings.json"))
        self.memory = memory
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self.warnings = []
        self._blocked = False
        if not memory:
            if filename is None and not os.path.exists(self.filename):
                for old in (os.path.join(app_dir(), "dist", "settings.json"), DOSOFT_SETTINGS):
                    if os.path.isfile(old):
                        shutil.copy2(old, self.filename)
                        self.warnings.append("Vos réglages précédents ont été repris ; le fichier d'origine est conservé.")
                        break
            self.load()

    @staticmethod
    def read_file(path):
        try:
            if os.path.getsize(path) > 2_000_000:
                raise ConfigError("Le fichier de réglages dépasse 2 Mo.")
            with open(path, encoding="utf-8-sig") as stream:
                return validate(json.load(stream))
        except (OSError, ValueError, RecursionError) as exc:
            raise ConfigError(f"Lecture impossible : {exc}") from exc

    def load(self):
        if not os.path.isfile(self.filename):
            return
        try:
            self.data = self.read_file(self.filename)
        except ConfigError as exc:
            try:
                recovered = self.read_file(self.filename + ".bak")
                shutil.copy2(self.filename, self.filename + f".illisible-{time.time_ns()}")
                self.data = recovered
                self._blocked = True
                self.warnings.append("Réglages récupérés depuis la sauvegarde. Le fichier endommagé est conservé. Importez une sauvegarde pour rétablir l'enregistrement.")
            except (ConfigError, OSError):
                self._blocked = True
                self.warnings.append(f"{exc}\nLe fichier est préservé. Importez une sauvegarde pour rétablir l'enregistrement.")

    def save(self):
        with self._lock:
            if self.memory:
                return
            if self._blocked:
                raise ConfigError("Enregistrement suspendu pour préserver le fichier illisible. Importez une sauvegarde dans Réglages.")
            try:
                Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
                tmp = self.filename + ".tmp"
                with open(tmp, "w", encoding="utf-8") as stream:
                    json.dump(self.data, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                if os.path.isfile(self.filename):
                    shutil.copy2(self.filename, self.filename + ".bak")
                os.replace(tmp, self.filename)
            except OSError as exc:
                raise ConfigError(f"Enregistrement impossible : {exc}") from exc

    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self.update({key: value})

    def update(self, values):
        with self._lock:
            old = copy.deepcopy(self.data)
            self.data.update(copy.deepcopy(values))
            try:
                self.save()
            except ConfigError:
                self.data = old
                raise

    def replace(self, raw):
        new = validate(raw)
        if not self.memory and os.path.isfile(self.filename):
            shutil.copy2(self.filename, self.filename + f".avant-import-{time.time_ns()}.json")
        old, blocked = self.data, self._blocked
        self.data, self._blocked = new, False
        try:
            self.save()
        except ConfigError:
            self.data, self._blocked = old, blocked
            raise

    def reset(self):
        self.replace(DEFAULTS)

    def save_profile(self, name):
        name = name.strip()
        if not name or len(name) > 40:
            raise ConfigError("Choisissez un nom de 1 à 40 caractères.")
        profiles = copy.deepcopy(self.data["profiles"])
        profiles[name] = {k: copy.deepcopy(self.data[k]) for k in PROFILE_KEYS}
        self.update({"profiles": profiles, "current_profile": name})

    def load_profile(self, name):
        if name not in self.data["profiles"]:
            raise ConfigError("Cette composition n'existe plus.")
        self.update({**self.data["profiles"][name], "current_profile": name})

    def delete_profile(self, name):
        profiles = copy.deepcopy(self.data["profiles"])
        profiles.pop(name, None)
        self.update({"profiles": profiles, "current_profile": "" if self.data["current_profile"] == name else self.data["current_profile"]})
