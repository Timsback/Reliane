"""Équipe de démonstration explicitement fictive, isolée des fenêtres et fichiers réels."""
from windows import DofusLogic


class DemoLogic(DofusLogic):
    def __init__(self, config):
        super().__init__(config)
        self.foreground = 101
        self._closed = set()
        self.characters = [("Aster", "Cra"), ("Mistral", "Pandawa"), ("Sélène", "Eniripsa"),
                           ("Braise", "Iop"), ("Nacre", "Feca"), ("Lichen", "Sadida")]
        config.data.update({"custom_order": [name for name, _classe in self.characters],
                            "classes": dict(self.characters), "leader_name": "Aster",
                            "accounts_team": {"Nacre": "Team 2", "Lichen": "Team 2"}})
        config.save_profile("L'escouade du soir")

    def scan_slots(self):
        cfg = self.config.data
        order = cfg["custom_order"]
        self.all_accounts = [{"name": name, "classe": cfg["classes"].get(name, classe),
                              "hwnd": index+101, "active": cfg["accounts_state"].get(name, True),
                              "team": cfg["accounts_team"].get(name, "Team 1"),
                              "is_retro": cfg["game_version"] != "Unity"}
                             for index, (name, classe) in enumerate(self.characters) if name not in self._closed]
        self.all_accounts.sort(key=lambda account: order.index(account["name"]) if account["name"] in order else 999)
        self.leader_hwnd = next((a["hwnd"] for a in self.all_accounts if a["name"] == cfg["leader_name"]), None)
        return self.all_accounts

    def focus_window(self, hwnd):
        self.foreground = hwnd
        return True

    def close_account_window(self, name):
        self._closed.add(name)
        return True

    def sort_taskbar(self):
        return len(self.get_cycle_list())
