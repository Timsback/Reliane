"""Interface Reliane : équipe, raccourcis et réglages dans une fenêtre adaptative."""
import copy
import ctypes
import json
import logging
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from rendering import prepare_fonts, enable_antialiasing
prepare_fonts()
import customtkinter as ctk
enable_antialiasing()
from smooth_widgets import install as install_smooth_widgets
install_smooth_widgets()
import pystray
import win32gui
from PIL import Image, ImageTk, ImageOps

from config import Config, ConfigError, DEFAULTS, PROFILE_KEYS, resource_dir
from hotkeys import ACTION_LABELS, LAYOUTS, MOUSE_VK, binding_errors, capture_combo, normalize_combo, split_combo
from icons import class_image
from notifications import AVAILABLE
from radial import RadialMenu
from theme import THEME, logo
from windows import RETRO_CLASSES, UNITY_CLASSES, UNKNOWN
from appmeta import VERSION

APP_TITLE = "Reliane"
MODE_LABELS = {"Tous": "ALL", "Équipe 1": "Team 1", "Équipe 2": "Team 2"}


def pretty(combo):
    names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Maj", "tab": "Tab", "space": "Espace",
             "left_click": "Clic G", "right_click": "Clic D", "middle_click": "Clic milieu",
             "mouse4": "Souris 4", "mouse5": "Souris 5"}
    return " + ".join(names.get(part, part.upper()) for part in normalize_combo(combo).split("+")) if combo else "Non défini"


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self.timer = widget, text, None, None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<Button-1>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def schedule(self, _event=None):
        self.timer = self.widget.after(650, self.show)

    def show(self):
        self.timer = None
        if not self.widget.winfo_exists():
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        x, y = self.widget.winfo_rootx(), self.widget.winfo_rooty()+self.widget.winfo_height()+6
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background=THEME["control"], foreground=THEME["text"],
                 font=("Segoe UI", 10), padx=10, pady=6, wraplength=280, justify="left").pack()

    def hide(self, _event=None):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class Styler:
    def __init__(self):
        self.T = THEME

    def font(self, size=13, weight="normal", family="Segoe UI"):
        if size >= 17:
            family = "Trebuchet MS"
        return ctk.CTkFont(family=family, size=size, weight=weight)

    def frame(self, parent, color="panel", border=True):
        return ctk.CTkFrame(parent, fg_color=self.T.get(color, color), corner_radius=3,
                            border_width=1 if border else 0, border_color=self.T["border"])

    def label(self, parent, text, muted=False, size=13, weight="normal", **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=self.T["muted" if muted else "text"],
                           font=self.font(size, weight), **kwargs)

    def button(self, parent, text, command, kind="ghost", width=120, height=36, tip=None):
        colors = {"accent": ("accent", "accent_hover", "on_accent"),
                  "danger": ("danger", "danger_hover", "danger_text"),
                  "ghost": ("control", "control_hover", "text"),
                  "subtle": ("panel", "control", "muted")}[kind]
        button = ctk.CTkButton(parent, text=text, command=command, width=width, height=height,
                               corner_radius=3, fg_color=self.T[colors[0]], hover_color=self.T[colors[1]],
                               border_width=0 if kind == "subtle" else 1, border_color=self.T["border"],
                               text_color=self.T[colors[2]], text_color_disabled="#728278",
                               font=self.font(13, "bold" if kind == "accent" else "normal"))
        button._canvas.configure(takefocus=1)
        button._reliane_base_border = 0 if kind == "subtle" else 1
        button._canvas.bind("<Return>", lambda _event: button.invoke())
        button._canvas.bind("<space>", lambda _event: button.invoke())
        button._canvas.bind("<FocusIn>", lambda _event: button.configure(border_width=2, border_color=self.T["accent"]))
        button._canvas.bind("<FocusOut>", lambda _event: button.configure(border_width=button._reliane_base_border, border_color=self.T["border"]))
        if tip:
            Tooltip(button, tip)
        return button

    def option(self, parent, values, command=None, width=170):
        option = ctk.CTkOptionMenu(parent, values=values, command=command, width=width, height=34,
                                  fg_color=self.T["control"], button_color=self.T["control"],
                                  button_hover_color=self.T["control_hover"], text_color=self.T["text"],
                                  dropdown_fg_color=self.T["panel"], dropdown_text_color=self.T["text"],
                                  dropdown_hover_color=self.T["control_hover"], font=self.font(),
                                  dropdown_font=self.font(), corner_radius=3)
        option._canvas.configure(takefocus=1)
        option._canvas.bind("<Return>", lambda _event: option._open_dropdown_menu())
        option._canvas.bind("<space>", lambda _event: option._open_dropdown_menu())
        return option

    def entry(self, parent, placeholder="", width=240):
        return ctk.CTkEntry(parent, placeholder_text=placeholder, width=width, height=36,
                             fg_color=self.T["bg"], border_color=self.T["border"],
                             text_color=self.T["text"], placeholder_text_color=self.T["muted"],
                             font=self.font(), corner_radius=9)

    def switch(self, parent, text, variable, command):
        switch = ctk.CTkSwitch(parent, text=text, variable=variable, command=command,
                               progress_color=self.T["seg_selected"], button_color=self.T["accent"],
                               button_hover_color=self.T["accent_hover"], fg_color=self.T["control"],
                               text_color=self.T["text"], font=self.font())
        switch._canvas.configure(takefocus=1)
        switch._canvas.bind("<space>", lambda _event: switch.toggle())
        return switch

    def titlebar(self, window):
        try:
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            color = THEME["bg"].lstrip("#")
            value = ctypes.c_int(int(color[4:6]+color[2:4]+color[0:2], 16))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(value), 4)
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), 4)
        except Exception:
            pass


class IllustratedHeader(tk.Canvas):
    """Bandeau d'interface de jeu : ardoise facettée, icône Dofus et texte natif."""
    def __init__(self, parent, demo=False):
        super().__init__(parent, height=82, bg="#35374F", highlightthickness=0, borderwidth=0)
        self.demo = demo
        self._last_width = 0
        self.bind("<Configure>", self.redraw)

    def redraw(self, event):
        if event.width == self._last_width:
            return
        self._last_width = event.width
        self.delete("all")
        self.create_polygon(0, 0, 170, 0, 120, 82, 0, 82, fill="#3D3F59", outline="")
        self.create_polygon(event.width-240, 0, event.width-80, 0, event.width-130, 82, event.width-300, 82, fill="#3B3D55", outline="")
        self._mark_photo = ImageTk.PhotoImage(logo(size=68))
        self.create_image(48, 40, image=self._mark_photo)
        self.create_text(94, 29, text="Reliane", anchor="w", fill="#F3F0E7", font=("Trebuchet MS", 25, "bold"))
        self.create_text(96, 57, text="GESTIONNAIRE D'ÉQUIPE  ·  DOFUS UNITY & RÉTRO", anchor="w", fill="#CACBDD", font=("Segoe UI", 9))
        if self.demo:
            self.create_text(event.width-18, 26, text="DÉMONSTRATION", anchor="e", fill="#E3C786", font=("Segoe UI", 9, "bold"))
        self.create_line(0, 81, event.width, 81, fill="#66677E", width=1)


class OrganizerGUI:
    def __init__(self, app):
        self.app, self.config, self.logic = app, app.config, app.logic
        self.T, self.S, self.theme_name = THEME, Styler(), "reliane"
        self._queue = queue.Queue()
        self.page = "Équipe"
        self._last_snapshot = None
        self._compact = False
        self._capturing = False
        self._flash_timer = None
        self._dialogs = []
        ctk.set_appearance_mode("dark")
        ctk.set_widget_scaling(1)
        self.root = ctk.CTk(fg_color=THEME["bg"])
        self.root.title("Reliane · Démonstration" if app.demo else APP_TITLE)
        self.root.geometry("1060x820")
        self.root.minsize(620, 620)
        self.root.attributes("-topmost", self.config.get("always_on_top"))
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.report_callback_exception = self._report_error
        self._set_icon()
        self.radial = RadialMenu(self.root, app.on_radial_select, THEME["radial"])
        self._build()
        self.root.bind("<Configure>", self._resize, add="+")
        for index, page in enumerate(("Équipe", "Raccourcis", "Réglages"), 1):
            self.root.bind(f"<Control-Key-{index}>", lambda _event, page=page: self.show_page(page))
        self.root.after(100, lambda: self.S.titlebar(self.root))
        self.root.after(30, self._drain)
        self.root.after(1000, self._auto_scan)

    def _set_icon(self):
        from PIL import ImageTk
        self._icon = ImageTk.PhotoImage(logo(size=64))
        self.root.iconphoto(True, self._icon)
        path = Path(resource_dir()) / "assets" / "reliane.ico"
        if path.exists():
            self.root.iconbitmap(str(path))
            self.root.after(500, lambda: self.root.iconbitmap(str(path)))

    def _build(self):
        S, T = self.S, self.T
        self.header = IllustratedHeader(self.root, self.app.demo)
        self.header.pack(fill="x", padx=24, pady=(18, 14))
        nav = ctk.CTkFrame(self.root, fg_color="transparent")
        nav.pack(fill="x", padx=24, pady=(0, 14))
        self.nav_buttons = {}
        for page in ("Équipe", "Raccourcis", "Réglages"):
            button = S.button(nav, page, lambda page=page: self.show_page(page), width=126, height=36)
            icon_name = {"Équipe": "character", "Raccourcis": "sort", "Réglages": "carac"}[page]
            icon_path = Path(resource_dir()) / "assets" / "game-icons" / f"{icon_name}.png"
            if icon_path.is_file():
                with Image.open(icon_path) as source:
                    icon_image = ctk.CTkImage(source.convert("RGBA"), size=(21, 21))
                button.configure(image=icon_image, compound="left")
            button.pack(side="left", padx=(0, 6))
            self.nav_buttons[page] = button
        self.pause_button = S.button(nav, "Ⅱ  Pause", self.app.toggle_pause, width=108,
                                      tip="Suspend la navigation, la roue et l'auto-focus. Le raccourci d'affichage reste disponible.")
        self.pause_button.pack(side="right")
        footer = ctk.CTkFrame(self.root, fg_color=T["panel"], corner_radius=0)
        footer.pack(side="bottom", fill="x")
        self.status = S.label(footer, "Prêt · Tout reste sur cet ordinateur.", muted=True, size=12, anchor="w")
        self.status.pack(side="left", fill="x", expand=True, padx=24, pady=10)
        S.label(footer, f"RELIANE  /  {VERSION}", muted=True, size=10).pack(side="right", padx=24)
        self.body = ctk.CTkFrame(self.root, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=28, pady=(0, 20))
        self.show_page("Équipe")

    def show_page(self, page):
        if self._capturing:
            return
        self.page = page
        for child in self.body.winfo_children():
            child.destroy()
        for name, button in self.nav_buttons.items():
            button.configure(fg_color=self.T["accent"] if name == page else self.T["panel"],
                             text_color=self.T["on_accent"] if name == page else self.T["muted"])
        {"Équipe": self._build_team, "Raccourcis": self._build_shortcuts, "Réglages": self._build_settings}[page]()

    def _heading(self, parent, title, subtitle):
        self.S.label(parent, title, size=28, weight="bold", anchor="w").pack(fill="x", pady=(0, 4))
        self.S.label(parent, subtitle, muted=True, anchor="w", wraplength=530, justify="left").pack(fill="x", pady=(0, 18))

    def _build_team(self):
        S, T = self.S, self.T
        profile = S.frame(self.body)
        profile.pack(fill="x", pady=(0, 14))
        S.label(profile, "COMPOSITION", muted=True, size=10, weight="bold").pack(side="left", padx=14, pady=12)
        names = list(self.config.get("profiles"))
        self.profile_menu = S.option(profile, names or ["Aucune sauvegarde"], self.load_profile, width=180)
        self.profile_menu.set(self.config.get("current_profile") or "Choisir…")
        self.profile_menu.pack(side="left", padx=(0, 8))
        self.profile_save = S.button(profile, "Enregistrer", self.save_profile, width=100,
                                     tip="Enregistrer l'ordre, les équipes, le meneur et les accès directs.")
        self.profile_save.pack(side="right", padx=(6, 12))
        S.button(profile, "+ Nouvelle", self.new_profile, "subtle", width=100).pack(side="right")
        area = ctk.CTkFrame(self.body, fg_color="transparent")
        area.pack(fill="both", expand=True)
        area.grid_rowconfigure(0, weight=1)
        area.grid_columnconfigure(0, weight=1)
        left = S.frame(area)
        left.grid(row=0, column=0, sticky="nsew")
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        S.label(top, "Ordre d'initiative", size=17, weight="bold").pack(side="left")
        self.version_menu = S.option(top, ["Unity", "Rétro"], self.on_version_change, width=100)
        self.version_menu.set(self.config.get("game_version"))
        self.version_menu.pack(side="right")
        filters = ctk.CTkFrame(left, fg_color="transparent")
        filters.pack(fill="x", padx=16, pady=(0, 10))
        self.mode_buttons = {}
        for label, mode in MODE_LABELS.items():
            button = S.button(filters, label, lambda mode=mode: self.on_mode_change(mode), width=90, height=30)
            button.pack(side="left", padx=(0, 4))
            self.mode_buttons[mode] = button
        self.count_label = S.label(left, "", muted=True, size=12, anchor="w")
        self.count_label.pack(fill="x", padx=18, pady=(0, 6))
        self.connection = self.count_label
        self.list_frame = ctk.CTkScrollableFrame(left, fg_color=T["panel"], corner_radius=0,
                                                 scrollbar_button_color=T["control"], scrollbar_button_hover_color=T["muted"])
        self.list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        tools = ctk.CTkFrame(left, fg_color="transparent")
        tools.pack(fill="x", padx=16, pady=(8, 14))
        S.button(tools, "↻  Actualiser", self.manual_refresh, "subtle", width=115).pack(side="left")
        S.button(tools, "Ranger la barre Windows", self.trigger_sort_taskbar, "subtle", width=184,
                 tip="Réaffiche les fenêtres dans l'ordre. Le résultat dépend du regroupement de votre barre Windows.").pack(side="right")
        self.side = ctk.CTkFrame(area, fg_color="transparent", width=240)
        self.side.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        self.side.grid_propagate(False)
        self.side.pack_propagate(False)
        pilot = S.frame(self.side)
        pilot.pack(fill="x")
        S.label(pilot, "NAVIGATION", muted=True, size=11, weight="bold").pack(anchor="w", padx=18, pady=(18, 4))
        S.label(pilot, "Changer de personnage", size=17, weight="bold").pack(anchor="w", padx=18, pady=(0, 12))
        S.button(pilot, "Personnage suivant  →", self.app.next_char, "accent", width=204, height=42).pack(padx=18, pady=(0, 8))
        S.button(pilot, "←  Personnage précédent", self.app.prev_char, width=204, height=38).pack(padx=18, pady=(0, 8))
        S.button(pilot, "☆  Revenir au meneur", self.app.focus_leader, "subtle", width=204).pack(padx=18, pady=(0, 16))
        keys = S.frame(self.side)
        keys.pack(fill="x", pady=(14, 0))
        S.label(keys, "SOUS LA MAIN", muted=True, size=10, weight="bold").pack(anchor="w", padx=18, pady=(16, 8))
        for key, title in (("next_key", "Suivant"), ("prev_key", "Précédent"), ("toggle_app_key", "Afficher / masquer")):
            row = ctk.CTkFrame(keys, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=4)
            S.label(row, title, muted=True, size=12).pack(side="left")
            S.label(row, pretty(self.config.get(key)), size=12, weight="bold").pack(side="right")
        S.button(keys, "Personnaliser les touches →", lambda: self.show_page("Raccourcis"), "subtle", width=204).pack(padx=18, pady=(8, 12))
        S.label(self.side, "LE PETIT MÉMO DU MENEUR", muted=True, size=10, weight="bold").pack(anchor="w", padx=5, pady=(22, 6))
        S.label(self.side, "La case inclut le personnage dans le cycle. L'étoile désigne le meneur. Les flèches règlent l'initiative.",
                muted=True, size=12, wraplength=228, justify="left").pack(anchor="w", padx=5)
        if self._compact:
            self.side.grid_remove()
        self.refresh_list()

    def refresh_list(self):
        if self.page != "Équipe" or not hasattr(self, "list_frame"):
            self.update_status()
            return
        S, T = self.S, self.T
        for child in self.list_frame.winfo_children():
            child.destroy()
        cycle = self.logic.get_cycle_list()
        positions = {a["name"]: i for i, a in enumerate(cycle)}
        mode = self.config.get("current_mode")
        accounts = [a for a in self.logic.all_accounts if mode == "ALL" or a["team"] == mode]
        self.count_label.configure(text=f"{len(cycle):02d} dans le cycle  ·  {len(accounts):02d} fenêtre(s) dans cette vue")
        for value, button in self.mode_buttons.items():
            button.configure(fg_color=T["seg_selected"] if value == mode else T["control"],
                             text_color=T["text"] if value == mode else T["muted"])
        if not accounts:
            self._empty_state(bool(self.logic.all_accounts))
        fg = self._foreground_hwnd()
        leader = self.config.get("leader_name")
        for account in accounts:
            name, position = account["name"], positions.get(account["name"])
            active = account["hwnd"] == fg
            row = ctk.CTkFrame(self.list_frame, fg_color=T["row_active"] if active else T["row"],
                               corner_radius=3, border_width=1, border_color=T["row_active_border"] if active else T["border"])
            row.pack(fill="x", padx=6, pady=4)
            row.grid_columnconfigure(3, weight=1)
            variable = ctk.BooleanVar(value=account["active"])
            check = ctk.CTkCheckBox(row, text="", width=24, variable=variable,
                                   command=lambda name=name: self._do(self.logic.toggle_account, name),
                                   checkbox_width=19, checkbox_height=19, corner_radius=5,
                                   fg_color=T["accent"], hover_color=T["accent_hover"], border_color=T["muted"],
                                   checkmark_color=T["on_accent"])
            check.grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=12)
            check._canvas.configure(takefocus=1)
            check._canvas.bind("<space>", lambda _event, check=check: check.toggle())
            Tooltip(check, "Inclure ou exclure ce personnage du cycle")
            pos = S.button(row, f"{position + 1:02d}" if position is not None else "—",
                           lambda name=name: self.change_position(name), "subtle", width=32, height=36,
                           tip="Choisir la position dans l'initiative")
            pos.grid(row=0, column=1, rowspan=2, padx=(0, 6))
            image = ctk.CTkImage(class_image(account["classe"], account["is_retro"], 96), size=(40, 40))
            badge = ctk.CTkLabel(row, image=image, text="", width=44)
            badge.grid(row=0, column=2, rowspan=2, padx=(0, 8))
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.grid(row=0, column=3, rowspan=2, sticky="ew", pady=7)
            name_limit = 13 if self._compact else 26
            title = S.button(text, name if len(name) < name_limit else name[:name_limit-3]+"…",
                             lambda hwnd=account["hwnd"]: self.app.focus_hwnd(hwnd), "subtle", width=80, height=28,
                             tip=f"Afficher {name}")
            title.configure(anchor="w", fg_color="transparent", text_color=T["text"], font=S.font(14, "bold"), border_width=0)
            title.pack(fill="x")
            suffix = " · à l'écran" if active else (" · hors cycle" if not account["active"] else "")
            description = account["classe"] if self._compact else f"{account['classe']}  ·  Éq. {account['team'][-1]}{suffix}"
            S.label(text, description, muted=True, size=11,
                    anchor="w", height=18).pack(fill="x", padx=6)
            team = S.button(row, account["team"][-1], lambda name=name: self._do(self.logic.change_team, name),
                            "subtle", width=28, height=34, tip="Changer d'équipe : 1 / 2")
            team.grid(row=0, column=4, rowspan=2, padx=1)
            star = S.button(row, "★" if name == leader else "☆", lambda name=name: self._do(self.logic.set_leader, name),
                            "subtle", width=30, height=34, tip="Définir comme meneur")
            star.configure(text_color=T["star"] if name == leader else T["muted"])
            star.grid(row=0, column=5, rowspan=2, padx=2)
            for column, (symbol, delta) in enumerate((("↑", -1), ("↓", 1)), 6):
                button = S.button(row, symbol, lambda name=name, delta=delta: self._do(self.logic.move_account, name, delta),
                                  "subtle", width=30, height=34, tip="Monter" if delta == -1 else "Descendre")
                button.grid(row=0, column=column, rowspan=2, padx=1)
                if position is None or not 0 <= position + delta < len(cycle):
                    button.configure(state="disabled")
            S.button(row, "···", lambda name=name: self.edit_character(name), "subtle", width=34, height=34,
                     tip="Classe, équipe, accès direct et fermeture").grid(row=0, column=8, rowspan=2, padx=(2, 10))
        self._last_snapshot = self._snapshot()
        self.update_status()

    def _empty_state(self, filtered=False):
        S = self.S
        S.label(self.list_frame, "◎", muted=True, size=58).pack(pady=(34, 10))
        S.label(self.list_frame, "Cette équipe est encore vide" if filtered else "Votre prochaine aventure commence ici.",
                size=19, weight="bold", wraplength=420).pack(padx=20, pady=(0, 8))
        text = ("Les personnages sont dans une autre équipe. Revenez à Tous pour modifier leur affectation." if filtered else
                f"Ouvrez Dofus {self.config.get('game_version')} et connectez vos personnages. Leurs fenêtres apparaîtront automatiquement ici.")
        S.label(self.list_frame, text, muted=True, wraplength=370, justify="center").pack(padx=20, pady=(0, 16))
        S.button(self.list_frame, "Voir tous les personnages" if filtered else "Rechercher les fenêtres",
                 lambda: self.on_mode_change("ALL") if filtered else self.manual_refresh(), "accent", width=220).pack(pady=(0, 16))
        if not filtered:
            S.label(self.list_frame, "Unity ou Rétro ? Vérifiez la version sélectionnée ci-dessus.", muted=True,
                    size=11, wraplength=340).pack(padx=16, pady=(0, 25))

    def _scroll_page(self, title, subtitle):
        scroll = ctk.CTkScrollableFrame(self.body, fg_color=self.T["bg"],
                                         scrollbar_button_color=self.T["control"], scrollbar_button_hover_color=self.T["muted"])
        scroll.pack(fill="both", expand=True)
        self._heading(scroll, title, subtitle)
        return scroll

    def _section(self, parent, title, description=None):
        frame = self.S.frame(parent)
        frame.pack(fill="x", pady=(0, 14))
        self.S.label(frame, title, size=17, weight="bold", anchor="w").pack(fill="x", padx=20, pady=(16, 4))
        if description:
            self.S.label(frame, description, muted=True, wraplength=510, justify="left", anchor="w").pack(fill="x", padx=20, pady=(0, 10))
        return frame

    def _key_row(self, parent, label, combo, setter, description=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=6)
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="x", expand=True)
        self.S.label(col, label, anchor="w").pack(fill="x")
        if description:
            self.S.label(col, description, muted=True, size=11, anchor="w").pack(fill="x")
        self.S.button(row, "×", lambda: setter(""), "subtle", width=34, tip="Effacer le raccourci").pack(side="right", padx=(6, 0))
        button = self.S.button(row, pretty(combo), lambda: None, width=190,
                               tip="Cliquez puis appuyez sur une combinaison. Échap annule ; délai de 10 secondes.")
        button.configure(command=lambda: self.catch_key(button, setter))
        button.pack(side="right")
        return button

    def _build_shortcuts(self):
        S = self.S
        page = self._scroll_page("Chaque geste compte.", "Cliquez sur une touche pour la changer. Échap annule la capture ; × retire un raccourci.")
        issues = getattr(self.app, "binding_issues", [])
        if issues:
            warning = self._section(page, "Raccourcis à vérifier", "\n".join(issues))
            S.label(warning, "Corrigez les conflits ci-dessous.", muted=True).pack(anchor="w", padx=20, pady=(0, 12))
        global_keys = self._section(page, "Navigation & application", "L'affichage et la pause restent accessibles partout. La navigation suit la portée définie dans Réglages.")
        for key, label in ACTION_LABELS.items():
            self._key_row(global_keys, label, self.config.get(key), lambda combo, key=key: self.set_hotkey(key, combo))
        S.label(global_keys, "Une pression = une action. Les touches restent transmises au jeu.", muted=True, size=11).pack(anchor="w", padx=20, pady=(4, 16))
        direct = self._section(page, "Accès directs", "Par place : suit l'initiative. Par personnage : reste attaché au pseudo, même si l'ordre change.")
        mode = S.option(direct, ["Par place", "Par personnage"], self.set_bind_mode, width=200)
        mode.set("Par place" if self.config.get("advanced_bind_mode") == "cycle" else "Par personnage")
        mode.pack(anchor="w", padx=20, pady=(0, 10))
        if self.config.get("advanced_bind_mode") == "cycle":
            binds = self.config.get("cycle_row_binds")
            for index in range(max(8, min(16, len(binds)))):
                self._key_row(direct, f"Place {index+1:02d}", binds[index] if index < len(binds) else "",
                              lambda combo, index=index: self.set_direct(index, combo))
        else:
            names = list(dict.fromkeys([a["name"] for a in self.logic.all_accounts] +
                                       list(self.config.get("persistent_character_binds"))))
            if not names:
                S.label(direct, "Connectez un personnage pour lui attribuer un raccourci.", muted=True).pack(padx=20, pady=12)
            for name in names:
                self._key_row(direct, name, self.config.get("persistent_character_binds").get(name, ""),
                              lambda combo, name=name: self.set_direct(name, combo))
        S.label(direct, "Les modifications sont enregistrées immédiatement.", muted=True, size=11).pack(anchor="w", padx=20, pady=(8, 16))

    def _setting_switch(self, parent, key, label, callback=None):
        variable = ctk.BooleanVar(value=self.config.get(key))
        def save():
            self.config.set(key, variable.get())
            if callback:
                callback()
            self.flash("Réglage enregistré")
        switch = self.S.switch(parent, label, variable, save)
        switch.pack(anchor="w", padx=20, pady=9)
        return switch

    def _build_settings(self):
        S = self.S
        page = self._scroll_page("À votre rythme.", "Des réglages utiles, des données locales et une équipe qui vous ressemble.")
        usage = self._section(page, "Confort de jeu", "Les raccourcis de navigation sont limités aux fenêtres Dofus par défaut. Ils sont suspendus pendant la saisie dans Reliane.")
        self._setting_switch(usage, "game_only", "Navigation uniquement quand Dofus est au premier plan")
        self._setting_switch(usage, "always_on_top", "Garder Reliane au-dessus des autres fenêtres",
                             lambda: self.root.attributes("-topmost", self.config.get("always_on_top")))
        row = ctk.CTkFrame(usage, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(8, 18))
        S.label(row, "Disposition des raccourcis", muted=True).pack(side="left")
        layout = S.option(row, list(LAYOUTS.values()), self.set_layout, width=200)
        layout.set(LAYOUTS[self.config.get("keyboard_layout")])
        layout.pack(side="right")
        radial = self._section(page, "La roue de relais", "Maintenez un bouton souris, survolez un personnage et relâchez. Le centre annule la sélection.")
        self._setting_switch(radial, "radial_menu_active", "Activer la roue de sélection", self._rebind_checked)
        self._key_row(radial, "Maintenir pour ouvrir", self.config.get("radial_menu_hotkey"),
                      lambda combo: self.set_hotkey("radial_menu_hotkey", combo))
        S.label(radial, "Conseil : Alt + clic gauche, ou un bouton latéral de souris.", muted=True, size=11).pack(anchor="w", padx=20, pady=(4, 16))
        notify = self._section(page, "Notifications Dofus Rétro", "Met au premier plan un personnage actif cité dans une nouvelle notification Dofus ou Ankama. Les notifications restent conservées.")
        switch = self._setting_switch(notify, "auto_focus_retro", "Revenir au personnage à son tour", self.app.notifier.start)
        if not AVAILABLE or self.app.demo:
            switch.configure(state="disabled")
        S.label(notify, "Désactivé dans la démonstration" if self.app.demo else self.app.notifier.status,
                muted=True, size=12).pack(anchor="w", padx=20, pady=(0, 16))
        data = self._section(page, "Vos réglages vous suivent", "Les sauvegardes contiennent vos pseudos, équipes et touches. Aucun mot de passe n'est demandé ni enregistré.")
        row = ctk.CTkFrame(data, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 12))
        S.button(row, "Exporter…", self.export_config, "accent", width=130).pack(side="left", padx=(0, 8))
        S.button(row, "Importer…", self.import_config, width=130).pack(side="left")
        if self.app.demo:
            S.label(data, "Mode démo : aucune donnée réelle n'est modifiée.", muted=True, size=11).pack(anchor="w", padx=20, pady=(0, 12))
        else:
            S.label(data, self.config.filename, muted=True, size=11, wraplength=510, justify="left").pack(anchor="w", padx=20, pady=(0, 12))
        profiles = self.config.get("profiles")
        if profiles:
            row = ctk.CTkFrame(data, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=(0, 16))
            menu = S.option(row, list(profiles), width=180)
            menu.pack(side="left")
            S.button(row, "Supprimer la composition", lambda: self.delete_profile(menu.get()), "subtle", width=190).pack(side="left", padx=8)
        about = self._section(page, f"Reliane {VERSION}", "Un compagnon local pour vos fenêtres Dofus Unity et Rétro. Application indépendante, sans affiliation à Ankama.")
        S.button(about, "Vérifier les mises à jour", self.app.check_updates, width=270).pack(anchor="w", padx=20, pady=(0, 10))
        S.label(about, "Données de jeu locales · Mises à jour via le dépôt GitHub", muted=True, size=12).pack(anchor="w", padx=20, pady=(0, 10))
        row = ctk.CTkFrame(about, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        S.button(row, "Guide de prise en main", self.show_help, width=180).pack(side="left")
        S.button(row, "Quitter Reliane", self.app.quit_app, "subtle", width=140).pack(side="right")

    def _rebind_checked(self):
        issues = binding_errors(self.config.data, self.app.hotkeys)
        if issues:
            self.config.set("radial_menu_active", False)
            self.show_page("Réglages")
            raise ConfigError("\n".join(issues))
        self.app.rebind_hotkeys()

    def set_layout(self, label):
        layout = next(key for key, value in LAYOUTS.items() if value == label)
        self.config.set("keyboard_layout", layout)
        self.app.rebind_hotkeys()
        self.flash("Disposition enregistrée ; le clavier Windows reste inchangé.")

    def set_bind_mode(self, label):
        mode = "cycle" if label == "Par place" else "bind"
        self._save_bindings({"advanced_bind_mode": mode})

    def _save_bindings(self, changes):
        candidate = copy.deepcopy(self.config.data)
        candidate.update(changes)
        issues = binding_errors(candidate, self.app.hotkeys)
        if issues:
            # Autoriser la correction progressive d'une configuration ancienne conflictuelle.
            previous = binding_errors(self.config.data, self.app.hotkeys)
            if any(issue not in previous for issue in issues):
                raise ConfigError("\n".join(issues))
        self.config.update(changes)
        self.app.rebind_hotkeys()
        page = self.page
        self.show_page(page)
        self.flash("Raccourci enregistré")

    def set_hotkey(self, key, combo):
        if key == "radial_menu_hotkey":
            if combo and split_combo(combo)[1] not in MOUSE_VK:
                raise ConfigError("La roue nécessite un bouton souris.")
            if combo and split_combo(combo)[1] in ("left_click", "right_click") and not split_combo(combo)[0]:
                raise ConfigError("Ajoutez Ctrl, Alt ou Maj au clic.")
            if not combo:
                self._save_bindings({key: "", "radial_menu_active": False})
                return
        self._save_bindings({key: normalize_combo(combo)})

    def set_direct(self, target, combo):
        if isinstance(target, int):
            binds = list(self.config.get("cycle_row_binds"))
            binds += [""] * max(0, target+1-len(binds))
            binds[target] = normalize_combo(combo)
            self._save_bindings({"cycle_row_binds": binds})
        else:
            binds = dict(self.config.get("persistent_character_binds"))
            if combo:
                binds[target] = normalize_combo(combo)
            else:
                binds.pop(target, None)
            self._save_bindings({"persistent_character_binds": binds})

    def catch_key(self, button, setter):
        if self._capturing:
            return
        self._capturing = True
        self.app.hotkeys.paused = True
        button.configure(text="Appuyez…  (Échap annule)")
        self.flash("Capture en cours · 10 secondes · Échap pour annuler", ms=11000)
        def job():
            combo, error = None, None
            try:
                combo = capture_combo(layout=self.config.get("keyboard_layout"), cancel=self.app.capture_cancel)
            except Exception as exc:
                error = str(exc)
            self.ui(lambda: done(combo, error))
        def done(combo, error):
            self._capturing = False
            self.app.hotkeys.paused = False
            if error:
                raise ConfigError(f"Capture impossible : {error}")
            if combo is not None:
                try:
                    setter(combo)
                except Exception:
                    self.show_page(self.page)
                    raise
            else:
                self.show_page(self.page)
                self.flash("Capture annulée")
        threading.Thread(target=job, daemon=True).start()

    def _dialog(self, title, size="450x440"):
        window = ctk.CTkToplevel(self.root)
        window.title(f"{title} · Reliane")
        window.geometry(size)
        window.configure(fg_color=self.T["bg"])
        window.transient(self.root)
        window.resizable(False, False)
        icon_path = Path(resource_dir()) / "assets" / "reliane.ico"
        if icon_path.is_file():
            window.after(300, lambda: window.iconbitmap(str(icon_path)) if window.winfo_exists() else None)
        window.grab_set()
        window.after(100, lambda: (self.S.titlebar(window), window.lift()))
        self._dialogs.append(window)
        return window

    def offer_restart(self, restart):
        existing = getattr(self, "_update_dialog", None)
        if existing and existing.winfo_exists():
            existing.lift()
            return
        window = self._dialog("Mise à jour prête", "470x265")
        window.transient("")
        window.attributes("-topmost", True)
        self._update_dialog = window
        self.S.label(window, "Une nouvelle version est prête.", size=22, weight="bold").pack(anchor="w", padx=24, pady=(24, 12))
        self.S.label(window, "Redémarrez Reliane pour utiliser la dernière version installée.\n\nVos équipes et vos raccourcis sont conservés.",
                     muted=True, wraplength=420, justify="left").pack(anchor="w", padx=24)
        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=24, pady=24)
        self.S.button(buttons, "Plus tard", window.destroy, width=150).pack(side="left")
        self.S.button(buttons, "Redémarrer", lambda: (window.destroy(), restart()), "accent", width=200).pack(side="right")

    def edit_character(self, name):
        account = self.logic.find(name)
        if not account:
            return
        S = self.S
        window = self._dialog(name, "440x440")
        S.label(window, name, size=24, weight="bold").pack(anchor="w", padx=24, pady=(24, 4))
        S.label(window, "Les changements sont appliqués à l'enregistrement.", muted=True, size=12).pack(anchor="w", padx=24, pady=(0, 20))
        S.label(window, "Classe", muted=True).pack(anchor="w", padx=24)
        classes = [UNKNOWN] + (RETRO_CLASSES if account["is_retro"] else UNITY_CLASSES)
        class_menu = S.option(window, classes, width=390)
        class_menu.set(account["classe"] if account["classe"] in classes else UNKNOWN)
        class_menu.pack(padx=24, pady=(4, 12))
        if not account["is_retro"] and account["classe"] != UNKNOWN:
            class_menu.configure(state="disabled")
        S.label(window, "Équipe", muted=True).pack(anchor="w", padx=24)
        team_menu = S.option(window, ["Équipe 1", "Équipe 2"], width=390)
        team_menu.set("Équipe 1" if account["team"] == "Team 1" else "Équipe 2")
        team_menu.pack(padx=24, pady=(4, 20))
        def save():
            classes_map = dict(self.config.get("classes"))
            teams = dict(self.config.get("accounts_team"))
            classes_map[name] = class_menu.get()
            teams[name] = "Team 1" if team_menu.get() == "Équipe 1" else "Team 2"
            self.config.update({"classes": classes_map, "accounts_team": teams})
            window.destroy()
            self.app.refresh()
            self.flash("Personnage mis à jour")
        S.button(window, "Enregistrer", save, "accent", width=390).pack(padx=24)
        S.button(window, "Configurer un accès direct →", lambda: (window.destroy(), self.show_page("Raccourcis")),
                 "subtle", width=390).pack(padx=24, pady=(8, 0))
        S.button(window, "Fermer cette fenêtre de jeu…", lambda: self.close_one(name, window),
                 "danger", width=390).pack(padx=24, pady=(8, 18))

    def change_position(self, name):
        cycle = self.logic.get_cycle_list()
        if not any(account["name"] == name for account in cycle):
            self.flash("Activez ce personnage pour le placer dans l'initiative.")
            return
        window = self._dialog("Position dans l'initiative", "360x220")
        self.S.label(window, name, size=19, weight="bold").pack(pady=(24, 12))
        menu = self.S.option(window, [str(i+1) for i in range(len(cycle))], width=300)
        menu.set(str(next(i+1 for i, account in enumerate(cycle) if account["name"] == name)))
        menu.pack(pady=(0, 18))
        self.S.button(window, "Déplacer", lambda: (self._do(self.logic.set_account_position, name, int(menu.get())-1), window.destroy()),
                      "accent", width=300).pack()

    def new_profile(self):
        window = self._dialog("Nouvelle composition", "400x260")
        self.S.label(window, "Gardez cette composition.", size=21, weight="bold").pack(padx=24, pady=(24, 8))
        self.S.label(window, "Ordre, équipes, meneur et accès directs seront mémorisés.", muted=True,
                     wraplength=340).pack(padx=24, pady=(0, 14))
        entry = self.S.entry(window, "Ex. Donjons du soir", width=340)
        entry.pack(padx=24, pady=(0, 16))
        def save():
            name = entry.get().strip()
            if name in self.config.get("profiles"):
                raise ConfigError("Ce nom existe déjà. Choisissez un autre nom.")
            self.config.save_profile(name)
            window.destroy()
            self.show_page("Équipe")
            self.flash("Composition enregistrée")
        self.S.button(window, "Créer la composition", save, "accent", width=340).pack()
        window.after(200, entry.focus_set)

    def save_profile(self):
        name = self.config.get("current_profile")
        if not name:
            self.new_profile()
            return
        self.config.save_profile(name)
        self.flash(f"Composition « {name} » enregistrée")

    def load_profile(self, name):
        if name not in self.config.get("profiles"):
            return
        current = self.config.get("current_profile")
        snapshot = self.config.get("profiles").get(current)
        dirty = snapshot is None or any(self.config.get(key) != snapshot.get(key, DEFAULTS[key]) for key in PROFILE_KEYS)
        if dirty and not messagebox.askyesno("Charger la composition", "Les ajustements actuels n'ont pas été enregistrés dans une composition.\n\nCharger cette composition et remplacer les réglages d'équipe actuels ?", parent=self.root):
            self.profile_menu.set(current or "Choisir…")
            return
        self.config.load_profile(name)
        self.app.refresh()
        self.show_page("Équipe")
        self.flash(f"Composition « {name} » chargée")

    def delete_profile(self, name):
        if messagebox.askyesno("Supprimer la composition", f"Supprimer « {name} » ?\nLes réglages actuels de votre équipe sont conservés.", parent=self.root):
            self.config.delete_profile(name)
            self.show_page("Réglages")
            self.flash("Composition supprimée")

    def export_config(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Exporter les réglages Reliane", defaultextension=".json",
                                           initialfile="reliane-sauvegarde.json", filetypes=[("Fichier JSON", "*.json")])
        if path:
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(self.config.filename)):
                raise ConfigError("Choisissez un autre fichier que les réglages actifs.")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(self.config.data, stream, ensure_ascii=False, indent=2)
            self.flash("Sauvegarde exportée")

    def import_config(self):
        path = filedialog.askopenfilename(parent=self.root, title="Importer des réglages Reliane ou MyDosoft",
                                         filetypes=[("Fichier JSON", "*.json"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        data = Config.read_file(path)
        issues = binding_errors(data, self.app.hotkeys)
        if issues:
            raise ConfigError("Raccourcis incompatibles dans ce fichier :\n"+"\n".join(issues))
        if messagebox.askyesno("Importer les réglages", "Remplacer les réglages actuels par cette sauvegarde ?\nUne copie du fichier actuel sera conservée avant l'import.", parent=self.root):
            self.config.replace(data)
            self.root.attributes("-topmost", self.config.get("always_on_top"))
            self.app.refresh()
            self.app.notifier.start()
            self.show_page("Réglages")
            self.flash("Réglages importés")

    def close_one(self, name, parent):
        if messagebox.askyesno("Fermer la fenêtre de jeu", f"Demander la fermeture de la fenêtre de {name} ?\nLe jeu pourra afficher une confirmation.", parent=parent):
            self.logic.close_account_window(name)
            parent.destroy()
            self.flash("Demande de fermeture envoyée au jeu")
            self.root.after(700, self.app.refresh)

    def trigger_sort_taskbar(self):
        if not self.logic.get_cycle_list():
            self.flash("Aucune fenêtre active à ranger.")
            return
        if getattr(self, "_sorting", False):
            return
        self._sorting = True
        self.flash("Rangement des fenêtres…")
        def job():
            error = None
            try:
                self.logic.sort_taskbar()
            except Exception as exc:
                error = str(exc)
            self.ui(lambda: done(error))
        def done(error):
            self._sorting = False
            self.flash("Rangement impossible : "+error if error else "Fenêtres réaffichées dans l'ordre · Le regroupement dépend de Windows.", error=bool(error), ms=7000)
        threading.Thread(target=job, daemon=True).start()

    def _do(self, function, *args):
        function(*args)
        self.refresh_list()

    def on_mode_change(self, mode):
        self.logic.set_mode(mode)
        self.refresh_list()

    def on_version_change(self, version):
        self.config.set("game_version", version)
        self.app.refresh()
        if not self.app.demo:
            self.app.notifier.start()

    def manual_refresh(self):
        self.app.refresh()
        self.flash(f"Recherche terminée · {len(self.logic.all_accounts)} fenêtre(s) détectée(s)")

    def _foreground_hwnd(self):
        return self.logic.foreground if self.app.demo else win32gui.GetForegroundWindow()

    def _snapshot(self):
        return (self._foreground_hwnd(), tuple((a["hwnd"], a["name"], a["classe"], a["active"], a["team"]) for a in self.logic.all_accounts))

    def _auto_scan(self):
        if self.app.closing:
            return
        try:
            self.app.poll_update_request()
            if self.app.closing:
                return
            self.logic.scan_slots()
            if self._snapshot() != self._last_snapshot:
                self.refresh_list()
                self._last_snapshot = self._snapshot()
            self.update_status()
        except Exception as exc:
            logging.exception("Détection des fenêtres")
            self.flash(str(exc), error=True)
        self.root.after(1500, self._auto_scan)

    def update_status(self):
        self.pause_button.configure(text="▶  Reprendre" if self.app.paused else "Ⅱ  Pause",
                                    fg_color=self.T["accent"] if self.app.paused else self.T["control"],
                                    text_color=self.T["on_accent"] if self.app.paused else self.T["text"])

    def _resize(self, event):
        if event.widget is not self.root:
            return
        compact = event.width / ctk.get_widget_scaling() < 920 if hasattr(ctk, "get_widget_scaling") else event.width < 920
        if compact != self._compact:
            self._compact = compact
            if self.page == "Équipe" and hasattr(self, "side"):
                if compact:
                    self.side.grid_remove()
                else:
                    self.side.grid()

    def flash(self, text, ms=5000, error=False):
        if self._flash_timer:
            self.root.after_cancel(self._flash_timer)
        self.status.configure(text=text, text_color=self.T["danger_text"] if error else self.T["accent"])
        self._flash_timer = self.root.after(ms, self._clear_flash)

    def _clear_flash(self):
        self._flash_timer = None
        self.status.configure(text="Raccourcis en pause" if self.app.paused else "Prêt · Tout reste sur cet ordinateur.", text_color=self.T["muted"])

    def ui(self, function):
        if not self.app.closing:
            self._queue.put(function)

    def _drain(self):
        if self.app.closing:
            return
        for _index in range(100):
            try:
                function = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                function()
            except Exception as exc:
                self._report_error(type(exc), exc, exc.__traceback__)
            if self.app.closing:
                return
        self.root.after(30, self._drain)

    def _report_error(self, exc_type, exc, traceback):
        logging.error("Erreur interface", exc_info=(exc_type, exc, traceback))
        messagebox.showerror("Reliane · Action impossible", str(exc), parent=self.root)

    def show_notices(self, notices):
        messagebox.showinfo("Reliane · Vos réglages", "\n\n".join(notices), parent=self.root)

    def show_help(self):
        window = self._dialog("Prise en main", "510x460")
        self.S.label(window, "Prêt pour le prochain tour ?", size=23, weight="bold").pack(anchor="w", padx=26, pady=(24, 16))
        for title, text in (("01  Connectez", "Ouvrez vos clients Dofus et choisissez Unity ou Rétro. La liste se met à jour automatiquement."),
                            ("02  Composez", "Activez les personnages avec la case, choisissez un meneur avec l'étoile et réglez l'initiative avec les flèches."),
                            ("03  Jouez", "Les raccourcis passent de fenêtre en fenêtre. F10 affiche Reliane ; Ctrl + F10 met la navigation en pause (touches par défaut)."),
                            ("04  Retrouvez", "Enregistrez une composition pour retrouver votre organisation. La croix masque Reliane dans la zone de notification.")):
            self.S.label(window, title, size=15, weight="bold").pack(anchor="w", padx=26, pady=(8, 2))
            self.S.label(window, text, muted=True, wraplength=450, justify="left").pack(anchor="w", padx=26)
        self.S.button(window, "C'est parti", window.destroy, "accent", width=450).pack(padx=26, pady=20)

    def hide(self):
        if not self.app.tray:
            self.app.quit_app()
        elif not self._capturing:
            self.root.withdraw()

    def show(self):
        self.root.deiconify()

    def toggle_visibility(self):
        self.show() if self.root.state() == "withdrawn" else self.hide()

    def run(self):
        self.root.mainloop()


class Tray:
    def __init__(self, app):
        gui = app.gui
        menu = pystray.Menu(
            pystray.MenuItem("Afficher Reliane", lambda: gui.ui(gui.show), default=True),
            pystray.MenuItem("Pause / Reprendre", lambda: gui.ui(app.toggle_pause)),
            pystray.MenuItem("Actualiser les fenêtres", lambda: gui.ui(app.refresh)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter Reliane", lambda: gui.ui(app.quit_app)),
        )
        self.icon = pystray.Icon("reliane", logo(size=64), APP_TITLE, menu)
        self.icon.run_detached()

    def stop(self):
        self.icon.stop()
