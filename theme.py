"""Reliane, grimoire sombre : forêt, bronze ancien et lumière de parchemin."""
import math
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw
from config import resource_dir

THEME = {
    "bg": "#191B2B", "panel": "#25273D", "row": "#2D3049", "row_hover": "#3A3E59",
    "row_active": "#3C405A", "row_active_border": "#D9BC79", "border": "#484B65",
    "accent": "#E3C786", "accent_hover": "#EFDBAA", "on_accent": "#242536",
    "seg_selected": "#50516D", "accent2": "#D3B46B", "text": "#F1EFE6",
    "muted": "#BABBCF", "control": "#383B56", "control_hover": "#4C506E",
    "danger": "#422C25", "danger_hover": "#593A2D", "danger_text": "#F2B59A",
    "star": "#E5C577", "ok": "#B5C978", "label": "Reliane", "title": "Reliane",
    "subtitle": "Le carnet de votre équipe.", "font_title": ("Palatino Linotype", 32, "bold"),
    "font_head": ("Palatino Linotype", 18, "bold"), "font_num": ("Consolas", 14),
    "font_body": ("Segoe UI", 13), "roman": False,
    "radial": {"slice": "#2D3049", "hover": "#4C506E", "active": "#3C405A",
               "border": "#D9BC79", "center": "#191B2B", "text": "#F1EFE6"},
}
THEMES = {"reliane": THEME}


def get_theme(_name=None):
    return THEME


def roman(n):
    return str(n)


@lru_cache(maxsize=24)
def logo(_theme_name=None, size=128):
    """Relique originale : œuf émeraude, sertissage bronze et rune de relais."""
    art = Path(resource_dir()) / "assets" / "dofus-emeraude.png"
    if art.is_file():
        with Image.open(art) as source:
            source = source.convert("RGBA")
            source.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size))
            canvas.alpha_composite(source, ((size-source.width)//2, (size-source.height)//2))
            return canvas
    factor = 6
    image = Image.new("RGBA", (size*factor, size*factor))
    draw = ImageDraw.Draw(image)
    k = size*factor / 64
    box = lambda values: tuple(v*k for v in values)
    points = []
    for index in range(240):
        angle = 2*math.pi*index/240
        width = 22*(1-0.23*math.cos(angle))
        points.append(((32+width*math.sin(angle))*k, (32-29*math.cos(angle))*k))
    draw.polygon(points, fill="#3D3526")
    inner = [(32*k+(x-32*k)*0.91, 32*k+(y-32*k)*0.91) for x, y in points]
    draw.polygon(inner, fill="#D4B36A")
    inner = [(32*k+(x-32*k)*0.78, 32*k+(y-32*k)*0.78) for x, y in points]
    draw.polygon(inner, fill="#386449")
    draw.ellipse(box((18, 15, 37, 47)), fill="#4D8057")
    draw.ellipse(box((21, 15, 29, 25)), fill="#7EA274")
    # Spirale interrompue par trois repères : les personnages se passent le relais.
    spiral = []
    for index in range(140):
        angle = math.radians(-75+index*2.8)
        radius = 15-index*0.075
        spiral.append(((33+radius*math.cos(angle))*k, (35+radius*math.sin(angle))*k))
    draw.line(spiral, fill="#EDCE81", width=max(1, int(3.8*k)), joint="curve")
    draw.polygon([(32*k, 4*k), (36*k, 10*k), (32*k, 14*k), (28*k, 10*k)], fill="#F8E5A9")
    return image.resize((size, size), Image.Resampling.LANCZOS)
