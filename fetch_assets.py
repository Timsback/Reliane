"""Récupère les ressources de jeu séparément du dépôt public, sans génération IA."""
import argparse
from pathlib import Path
import shutil
from urllib.request import Request, urlopen
from io import BytesIO
from PIL import Image

ICON_URLS = ("https://static.ankama.com/dofus/www/game/items/200/23002.png",
             "https://api.dofusdb.fr/img/items/23002.png")


def download_icon(destination):
    errors = []
    for url in ICON_URLS:
        try:
            headers = {"User-Agent": "Reliane-personal/1.1", "Accept": "image/png,image/webp,image/*;q=0.8"}
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("Image trop volumineuse")
            with Image.open(BytesIO(data)) as source:
                if not 1 <= min(source.size) <= max(source.size) <= 2048:
                    raise ValueError("Dimensions inattendues")
                source.convert("RGBA").save(destination, format="PNG")
            return
        except (OSError, ValueError) as exc:
            errors.append(f"{url} : {type(exc).__name__}")
    raise RuntimeError("Impossible de récupérer l'icône Dofus. Réessayez avec une connexion Internet.\n"+"\n".join(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skin", type=Path, default=Path(r"C:\Program Files (x86)\Dosoft\skin"))
    args = parser.parse_args()
    assets = Path(__file__).resolve().parent / "assets"
    assets.mkdir(exist_ok=True)
    egg = assets / "dofus-emeraude.png"
    if not egg.exists():
        download_icon(egg)
    classes = ("cra", "ecaflip", "eliotrope", "eniripsa", "enutrof", "feca", "forgelance", "huppermage",
               "iop", "osamodas", "ouginak", "pandawa", "roublard", "sacrieur", "sadida", "sram", "steamer", "xelor", "zobal")
    target = assets / "classes"
    target.mkdir(exist_ok=True)
    for name in classes:
        for suffix in ("", "_retro"):
            source = args.skin / f"{name}{suffix}.png"
            if source.exists():
                shutil.copy2(source, target / source.name)
    game_icons = assets / "game-icons"
    game_icons.mkdir(exist_ok=True)
    for name in ("character", "carac", "sort"):
        source = args.skin / f"{name}.png"
        if source.exists():
            shutil.copy2(source, game_icons / source.name)
    from theme import logo
    logo(size=512).save(assets / "reliane.png")
    logo(size=256).save(assets / "reliane.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    logo(size=64).save(assets / "favicon.ico", sizes=[(16,16),(32,32),(48,48),(64,64)])
    print(f"Icône Dofus récupérée ; {len(list(target.glob('*.png')))} portraits locaux disponibles.")
    if not any(target.glob("*.png")):
        print("Portraits absents : les symboles de secours seront utilisés. Passez --skin CHEMIN pour fournir vos PNG de classe.")


if __name__ == "__main__":
    main()
