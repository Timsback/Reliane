"""Manifeste local et vérification d'intégrité des versions de Reliane."""
import hashlib
import json
from pathlib import Path
import re
import os
import sys

SOURCE_NAMES = ("main.py", "gui.py", "config.py", "windows.py", "hotkeys.py", "radial.py", "notifications.py",
                "icons.py", "theme.py", "demo.py", "rendering.py", "smooth_widgets.py", "appmeta.py",
                "release_tools.py", "build_release.py", "Reliane.spec", "requirements-lock.txt")


def distribution_dir():
    if getattr(sys, "frozen", False):
        for parent in list(Path(sys.executable).resolve().parents)[:4]:
            if (parent / "release.json").is_file():
                return parent
    return Path(__file__).resolve().parent / "dist"


def source_digest(project):
    project = Path(project)
    digest = hashlib.sha256()
    paths = [project / name for name in SOURCE_NAMES]
    paths += sorted(path for path in (project / "assets").rglob("*") if path.is_file() and path.name != "release-build.json")
    for path in paths:
        digest.update(str(path.relative_to(project)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def file_digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_release(folder, verify=True):
    folder = Path(folder).resolve()
    data = json.loads((folder / "release.json").read_text(encoding="utf-8-sig"))
    if not re.fullmatch(r"\d+\.\d+\.\d+", data.get("version", "")) or not re.fullmatch(r"[0-9a-f]{16}", data.get("build", "")):
        raise ValueError("Manifeste de version invalide.")
    path = (folder / data["file"]).resolve()
    if not path.is_relative_to(folder / "releases") or path.suffix.lower() != ".exe":
        raise ValueError("Chemin de version interdit.")
    if not re.fullmatch(r"[0-9a-f]{64}", data.get("sha256", "")):
        raise ValueError("Empreinte de version invalide.")
    if verify and file_digest(path) != data["sha256"]:
        raise ValueError("La version installée est incomplète ou a été modifiée. Relancez la construction.")
    return data, path


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
