"""Lanceur stable : dernière version locale vérifiée, compilation si sources modifiées."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import threading
import os
import tkinter as tk
from tkinter import messagebox, ttk

from release_tools import load_release, source_digest

GITHUB_ORIGIN = "https://github.com/Timsback/Reliane.git"


def subprocess_environment():
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    if getattr(sys, "frozen", False):
        # Les outils du système ne doivent pas charger les DLL embarquées.
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        bundle = str(getattr(sys, "_MEIPASS", "")).rstrip("\\/").casefold()
        env["PATH"] = os.pathsep.join(part for part in env.get("PATH", "").split(os.pathsep)
                                      if part.casefold().rstrip("\\/") != bundle and not part.casefold().startswith(bundle+os.sep))
    return env


def question(root, title, message):
    result = {"yes": False}
    root.title(title)
    root.geometry("510x250")
    root.resizable(False, False)
    root.configure(bg="#25273D")
    tk.Label(root, text="Mise à jour de Reliane", font=("Trebuchet MS", 18, "bold"),
             bg="#25273D", fg="#F1EFE6").pack(anchor="w", padx=24, pady=(24, 12))
    tk.Label(root, text=message, font=("Segoe UI", 11), bg="#25273D", fg="#BABBCF",
             justify="left", wraplength=460).pack(anchor="w", padx=24)
    row = tk.Frame(root, bg="#25273D")
    row.pack(side="bottom", fill="x", padx=24, pady=22)
    def answer(value):
        result["yes"] = value
        root.quit()
    tk.Button(row, text="Plus tard", command=lambda: answer(False), relief="flat", bg="#383B56",
              fg="#F1EFE6", activebackground="#4C506E", padx=24, pady=7).pack(side="left")
    tk.Button(row, text="Mettre à jour", command=lambda: answer(True), relief="flat", bg="#E3C786",
              fg="#242536", activebackground="#EFDBAA", padx=30, pady=7).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", lambda: answer(False))
    root.deiconify()
    root.lift()
    root.after(100, root.focus_set)
    root.mainloop()
    root.withdraw()
    for child in root.winfo_children():
        child.destroy()
    return result["yes"]


def update_from_github(project, ask):
    """Ne fusionne que main, propre, en avance rapide, après accord explicite."""
    if not (Path(project) / ".git").is_dir():
        return False
    env = dict(subprocess_environment(), GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    def git(*args):
        return subprocess.run(["git", "-C", str(project), *args], text=True, capture_output=True,
                              timeout=12, env=env, creationflags=subprocess.CREATE_NO_WINDOW, check=True).stdout.strip()
    try:
        if git("remote", "get-url", "origin").rstrip("/") != GITHUB_ORIGIN:
            return False
        if git("branch", "--show-current") != "main":
            return False
        git("fetch", "--quiet", "origin", "main")
        ahead, behind = (int(value) for value in git("rev-list", "--left-right", "--count", "HEAD...origin/main").split())
        if not behind or ahead or git("status", "--porcelain", "--untracked-files=no"):
            return False
        if not ask():
            return False
        git("merge", "--ff-only", "origin/main")
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        # Hors ligne ou copie de travail modifiée : conserver la version locale.
        return False


def locate(base):
    base = Path(base)
    project = base.parent if base.name.lower() == "dist" else base
    distribution = project / "dist" if (project / "main.py").exists() or (project / "dist" / "release.json").exists() else base
    return project, distribution


def main():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    project, distribution = locate(base)
    root = tk.Tk()
    root.withdraw()
    root.title("Reliane · Mise à jour")
    try:
        remote_changed = update_from_github(project, lambda: question(root, "Reliane · Mise à jour disponible",
            "Une nouvelle version est disponible sur GitHub.\n\nLa télécharger et la construire maintenant ?\nVos réglages sont conservés."))
        current = None
        try:
            current, binary = load_release(distribution)
        except (OSError, ValueError, KeyError):
            binary = None
        can_build = (project / "build_release.py").is_file() and (project / ".venv/Scripts/python.exe").is_file()
        changed = can_build and (not current or source_digest(project) != current["build"])
        force = "--update" in sys.argv or remote_changed
        if changed and (not current or force or question(root, "Reliane · Nouvelle version", "Une nouvelle version du projet est disponible sur cet ordinateur.\n\nMettre à jour Reliane maintenant ?\nVos réglages sont conservés.")):
            root.deiconify()
            root.geometry("470x160")
            root.resizable(False, False)
            root.configure(bg="#25273D")
            tk.Label(root, text="Mise à jour de Reliane", font=("Segoe UI", 16, "bold"), bg="#25273D", fg="#F1EFE6").pack(pady=(23, 8))
            tk.Label(root, text="Construction de la nouvelle version…", font=("Segoe UI", 11), bg="#25273D", fg="#BABBCF").pack()
            bar = ttk.Progressbar(root, mode="indeterminate", length=410)
            bar.pack(pady=16)
            bar.start(15)
            root.protocol("WM_DELETE_WINDOW", lambda: None)
            outcome = {}
            def build():
                try:
                    log = project / "update-build.log"
                    with log.open("w", encoding="utf-8") as stream:
                        if remote_changed:
                            subprocess.run([str(project / ".venv/Scripts/python.exe"), "-m", "pip", "install", "-r", "requirements-lock.txt"],
                                           cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW, check=True, env=subprocess_environment())
                            subprocess.run([str(project / ".venv/Scripts/python.exe"), "fetch_assets.py"], cwd=project,
                                           stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, check=True, env=subprocess_environment())
                        result = subprocess.run([str(project / ".venv/Scripts/python.exe"), str(project / "build_release.py"), "--app-only"],
                                                cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                                                creationflags=subprocess.CREATE_NO_WINDOW, env=subprocess_environment())
                    if result.returncode:
                        raise RuntimeError("La construction a échoué. Consultez update-build.log. La version précédente est conservée.")
                    outcome["ok"] = True
                except Exception as exc:
                    outcome["error"] = str(exc)
            threading.Thread(target=build, daemon=True).start()
            def poll():
                if outcome:
                    root.quit()
                else:
                    root.after(100, poll)
            root.after(100, poll)
            root.mainloop()
            root.withdraw()
            if "error" in outcome:
                raise RuntimeError(outcome["error"])
            current, binary = load_release(distribution)
        if binary is None:
            raise RuntimeError("Aucune version installée. Exécutez build.bat depuis le dossier du projet.")
        args = [arg for arg in sys.argv[1:] if arg != "--update"]
        for option in ("--config", "--self-test"):
            if option in args:
                index = args.index(option)+1
                if index < len(args):
                    args[index] = str(Path(args[index]).expanduser().resolve())
        if "--config" not in args and "--demo" not in args:
            args = ["--config", str(distribution / "settings.json"), *args]
        if "--self-test" in args:
            return subprocess.run([str(binary), *args], cwd=distribution, env=subprocess_environment()).returncode
        subprocess.Popen([str(binary), *args], cwd=distribution, env=subprocess_environment())
    except Exception as exc:
        messagebox.showerror("Reliane · Lancement impossible", str(exc), parent=root)
        return 1
    finally:
        root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
