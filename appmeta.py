"""Identité de la version exécutée, indépendante du lanceur stable."""
import json
from pathlib import Path
import sys

VERSION = "1.1.0"
try:
    BUILD_ID = json.loads((Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets" / "release-build.json").read_text(encoding="utf-8"))["build"]
except (OSError, ValueError, KeyError):
    BUILD_ID = "sources"
