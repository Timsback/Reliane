"""Construit une version immuable et actualise atomiquement le manifeste du lanceur."""
import argparse
from pathlib import Path
import shutil
import json
import subprocess
import sys

from appmeta import VERSION
from release_tools import atomic_json, file_digest, source_digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-only", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    distribution = project / "dist"
    build = source_digest(project)
    atomic_json(project / "assets/release-build.json", {"version": VERSION, "build": build})
    release = distribution / "releases" / f"{VERSION}-{build}"
    release.mkdir(parents=True, exist_ok=True)
    binary = release / "Reliane-app.exe"
    marker = release / ".complete.json"
    complete = False
    try:
        status = json.loads(marker.read_text(encoding="utf-8"))
        complete = status["build"] == build and status["sha256"] == file_digest(binary)
    except (OSError, ValueError, KeyError):
        pass
    if not complete:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(release), "Reliane.spec"], cwd=project, check=True)
        atomic_json(marker, {"build": build, "sha256": file_digest(binary)})
    previous = distribution / "release.json"
    if previous.exists():
        shutil.copy2(previous, distribution / "release.previous.json")
    atomic_json(previous, {"version": VERSION, "build": build,
                          "file": str(binary.relative_to(distribution)).replace("\\", "/"), "sha256": file_digest(binary)})
    if not args.app_only:
        bootstrap = project / "build/launcher-output"
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(bootstrap), "RelianeLauncher.spec"], cwd=project, check=True)
        shutil.copy2(bootstrap / "Reliane.exe", project / "Reliane.exe")
        shutil.copy2(bootstrap / "Reliane.exe", distribution / "Reliane.exe")
    print(f"Reliane {VERSION} / {build} : prête")


if __name__ == "__main__":
    main()
