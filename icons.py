"""Icônes de classe : PNG d'un dossier skin/ si présent, sinon pastille générée."""
import os
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from config import app_dir, resource_dir

SKIN_DIRS = [
    os.path.join(app_dir(), "skin"),
    os.path.join(resource_dir(), "assets", "classes"),
    os.path.join(resource_dir(), "skin"),
]

PALETTE = {
    "Cra": "#7a9a3a", "Ecaflip": "#c2913a", "Eliotrope": "#3aa6a6", "Eniripsa": "#c25a8a",
    "Enutrof": "#a8843a", "Feca": "#3a7ac2", "Forgelance": "#5a6ac2", "Huppermage": "#8a5ac2",
    "Iop": "#c2463a", "Osamodas": "#6a9a5a", "Ouginak": "#8a6a4a", "Pandawa": "#4a9a7a",
    "Roublard": "#5a5a5a", "Sacrieur": "#a83a3a", "Sadida": "#4a8a3a", "Sram": "#6a4a8a",
    "Steamer": "#3a8aa8", "Xelor": "#4a5a9a", "Zobal": "#9a6a9a",
}


def _find_png(classe, retro):
    base = classe.lower()
    names = [f"{base}_retro.png", f"{base}.png"] if retro else [f"{base}.png"]
    for d in SKIN_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None


@lru_cache(maxsize=128)
def class_image(classe, retro=False, size=32):
    """Renvoie une image PIL RGBA carrée."""
    path = _find_png(classe, retro) if classe and classe != "Inconnu" else None
    if path:
        try:
            with Image.open(path) as source:
                source = source.convert("RGBA")
                source.thumbnail((size, size), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (size, size))
                canvas.alpha_composite(source, ((size-source.width)//2, (size-source.height)//2))
                return canvas
        except OSError:
            pass
    img = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = PALETTE.get(classe, "#827458")
    k = size * 4 / 64
    box = lambda values: tuple(v*k for v in values)
    pts = lambda values: [(x*k, y*k) for x, y in values]
    stroke = max(1, int(3*k))
    d.ellipse(box((2, 2, 62, 62)), fill="#FAF3DC", outline="#B8A37B", width=max(1, int(1.5*k)))
    line = lambda values, width=3: d.line(pts(values), fill=color, width=max(1, int(width*k)), joint="curve")
    polygon = lambda values: d.polygon(pts(values), fill=color)
    if classe == "Cra":
        d.arc(box((12, 12, 45, 52)), -85, 85, fill=color, width=stroke)
        line([(30, 13), (30, 51)], 2)
        line([(17, 32), (50, 32)])
        polygon([(51, 32), (43, 26), (43, 38)])
    elif classe in ("Iop", "Sram", "Forgelance"):
        polygon([(32, 10), (38, 20), (34, 40), (29, 40), (26, 20)])
        line([(21, 40), (43, 40)], 4)
        line([(32, 40), (32, 53)], 5)
    elif classe == "Feca":
        polygon([(16, 19), (32, 12), (48, 19), (45, 38), (32, 52), (19, 38)])
        d.line(pts([(32, 20), (32, 43)]), fill="#FAF3DC", width=stroke)
    elif classe == "Eniripsa":
        polygon([(12, 24), (26, 29), (26, 43), (17, 37)])
        polygon([(52, 24), (38, 29), (38, 43), (47, 37)])
        d.rounded_rectangle(box((28, 17, 36, 47)), radius=2*k, fill=color)
        d.rounded_rectangle(box((19, 27, 45, 35)), radius=2*k, fill=color)
    elif classe == "Sadida":
        polygon([(48, 13), (44, 36), (30, 46), (18, 41), (17, 30), (27, 19)])
        d.line(pts([(15, 51), (40, 25)]), fill="#59652F", width=stroke)
    elif classe == "Pandawa":
        d.rounded_rectangle(box((19, 16, 43, 49)), radius=7*k, fill=color)
        d.arc(box((32, 21, 51, 41)), -90, 90, fill=color, width=4*int(k))
        for y in (23, 42):
            d.line(pts([(21, y), (41, y)]), fill="#FAF3DC", width=2*int(k))
    elif classe == "Ecaflip":
        polygon([(32, 11), (47, 32), (32, 53), (17, 32)])
        d.ellipse(box((28, 28, 36, 36)), fill="#FAF3DC")
    elif classe == "Xelor":
        line([(18, 15), (46, 15)], 4)
        line([(18, 49), (46, 49)], 4)
        polygon([(21, 19), (43, 19), (33, 32), (43, 45), (21, 45), (31, 32)])
    elif classe == "Enutrof":
        line([(37, 13), (25, 47)], 5)
        polygon([(20, 34), (37, 40), (29, 54), (17, 49)])
        d.arc(box((31, 8, 45, 22)), 0, 360, fill=color, width=stroke)
    elif classe == "Eliotrope":
        d.ellipse(box((15, 13, 49, 51)), outline=color, width=5*int(k))
        d.ellipse(box((25, 23, 39, 41)), outline=color, width=2*int(k))
    elif classe == "Sacrieur":
        d.ellipse(box((17, 18, 34, 36)), fill=color)
        d.ellipse(box((30, 18, 47, 36)), fill=color)
        polygon([(17, 29), (47, 29), (32, 51)])
    elif classe == "Roublard":
        d.ellipse(box((17, 24, 46, 51)), fill=color)
        line([(34, 24), (38, 16), (45, 16)])
        line([(45, 10), (45, 20)], 2)
        line([(40, 15), (50, 15)], 2)
    elif classe == "Zobal":
        polygon([(14, 18), (32, 23), (50, 18), (45, 43), (32, 52), (19, 43)])
        d.ellipse(box((20, 29, 28, 35)), fill="#FAF3DC")
        d.ellipse(box((36, 29, 44, 35)), fill="#FAF3DC")
    else:
        # Rune élémentaire commune aux autres classes, à huit branches.
        points = []
        for index in range(16):
            angle = index*math.pi/8
            radius = 20 if index%2 == 0 else 10
            points.append((32+radius*math.cos(angle), 32+radius*math.sin(angle)))
        polygon(points)
        d.ellipse(box((27, 27, 37, 37)), fill="#FAF3DC")
    return img.resize((size, size), Image.Resampling.LANCZOS)


def app_icon(size=64):
    from theme import logo
    return logo(size=size)
