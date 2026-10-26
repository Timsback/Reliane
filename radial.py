"""Roue de focus radiale : s'ouvre sous la souris, sélection au survol, validation au relâchement."""
import math
import tkinter as tk

import win32api
from PIL import ImageTk

from icons import class_image

SIZE = 400
R_OUT = 175
R_IN = 35
TRANSPARENT = "magenta"
DEFAULT_COLORS = {"slice": "#2b2b2b", "hover": "#3d3d3d", "active": "#1c456d",
                  "border": "#1a1a1a", "center": "#1a1a1a", "text": "#ecf0f1"}


class RadialMenu:
    def __init__(self, root, on_select, colors=None):
        self.on_select = on_select
        self.c = {**DEFAULT_COLORS, **(colors or {})}
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", TRANSPARENT)
        self.canvas = tk.Canvas(self.win, width=SIZE, height=SIZE, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.win.withdraw()
        self.items, self.arcs, self._photos = [], [], []
        self.hovered = -1
        self.current_name = None
        self.is_open = False
        self.win.bind("<Escape>", lambda _event: self.cancel())

    def show(self, items, current_name):
        if self.is_open or not items:
            return
        self.items, self.current_name = list(items), current_name
        self.hovered = -1
        self._build()
        x, y = win32api.GetCursorPos()
        monitor = win32api.GetMonitorInfo(win32api.MonitorFromPoint((x, y)))["Work"]
        left = max(monitor[0], min(x - SIZE // 2, monitor[2] - SIZE))
        top = max(monitor[1], min(y - SIZE // 2, monitor[3] - SIZE))
        self.win.geometry(f"{SIZE}x{SIZE}{left:+d}{top:+d}")
        self.win.deiconify()
        self.win.lift()
        self.is_open, self.hovered = True, -1
        self._poll()

    def hide(self):
        if not self.is_open:
            return
        self.is_open = False
        self.win.withdraw()
        if 0 <= self.hovered < len(self.items):
            self.on_select(self.items[self.hovered])

    def cancel(self):
        self.hovered = -1
        self.hide()

    def _slice_color(self, i):
        if i == self.hovered:
            return self.c["hover"]
        return self.c["active"] if self.items[i]["name"] == self.current_name else self.c["slice"]

    def _build(self):
        c, cx, col = self.canvas, SIZE // 2, self.c
        c.delete("all")
        self.arcs, self._photos = [], []
        n = len(self.items)
        ext = 360 / n
        # Anneau extérieur coloré, puis les parts par-dessus.
        c.create_oval(cx - R_OUT - 3, cx - R_OUT - 3, cx + R_OUT + 3, cx + R_OUT + 3, fill=col["border"], outline="")
        for i, acc in enumerate(self.items):
            # Part 0 centrée en haut, puis sens horaire.
            start = 90 - ext / 2 - i * ext
            arc = c.create_arc(cx - R_OUT, cx - R_OUT, cx + R_OUT, cx + R_OUT, start=start,
                               extent=min(ext, 359.9), fill=self._slice_color(i),
                               outline=col["center"], width=2, style=tk.PIESLICE)
            self.arcs.append(arc)
            mid = math.radians(start + ext / 2)
            r = R_IN + (R_OUT - R_IN) * 0.65
            px, py = cx + r * math.cos(mid), cx - r * math.sin(mid)
            photo = ImageTk.PhotoImage(class_image(acc["classe"], acc.get("is_retro", False), 36))
            self._photos.append(photo)
            c.create_image(px, py - 10, image=photo)
            c.create_text(px, py + 18, text=acc["name"][:12], fill=col["text"], font=("Segoe UI", 9, "bold"))
        c.create_oval(cx - R_IN, cx - R_IN, cx + R_IN, cx + R_IN, fill=col["center"], outline=col["border"], width=3)

    def _poll(self):
        if not self.is_open:
            return
        mx, my = win32api.GetCursorPos()
        dx = mx - (self.win.winfo_rootx() + SIZE // 2)
        dy = (self.win.winfo_rooty() + SIZE // 2) - my
        dist = math.hypot(dx, dy)
        idx = -1
        if R_IN < dist <= R_OUT + 60 and self.items:
            n = len(self.items)
            ext = 360 / n
            # Angle mesuré depuis le haut, sens horaire.
            ang = (90 - math.degrees(math.atan2(dy, dx)) + ext / 2) % 360
            idx = int(ang // ext) % n
        if idx != self.hovered:
            self.hovered = idx
            for i, arc in enumerate(self.arcs):
                self.canvas.itemconfig(arc, fill=self._slice_color(i))
        self.win.after(15, self._poll)
