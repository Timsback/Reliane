"""Parcours de mise à jour Git sur un dépôt local isolé, sans compte externe."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from launcher import update_from_github


class GitUpdateTests(unittest.TestCase):
    def test_update_requires_consent_and_preserves_personal_data_and_local_edits(self):
        parent = Path(__file__).resolve().parent / ".tmp"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            base = Path(folder)
            remote, client, writer = (base/name for name in ("remote.git", "client", "writer"))
            def git(*args, cwd=None):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()
            def commit(path, text):
                git("add", ".", cwd=path)
                git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", "commit", "-m", text, cwd=path)
            git("init", "--bare", "--initial-branch=main", str(remote))
            git("clone", remote.as_posix(), str(client))
            (client/"app.py").write_text("version 1", encoding="utf-8")
            (client/".gitignore").write_text("settings.json\n", encoding="utf-8")
            commit(client, "Initial")
            git("push", "origin", "main", cwd=client)
            git("clone", "--branch", "main", remote.as_posix(), str(writer))
            (writer/"app.py").write_text("version 2", encoding="utf-8")
            commit(writer, "Update")
            git("push", "origin", "main", cwd=writer)
            (client/"settings.json").write_text("personal settings", encoding="utf-8")
            with patch("launcher.GITHUB_ORIGIN", remote.as_posix()):
                self.assertFalse(update_from_github(client, lambda: False))
                self.assertEqual((client/"app.py").read_text(), "version 1")
                self.assertTrue(update_from_github(client, lambda: True))
                self.assertEqual((client/"app.py").read_text(), "version 2")
                self.assertEqual((client/"settings.json").read_text(), "personal settings")
                (writer/"app.py").write_text("version 3", encoding="utf-8")
                commit(writer, "Another update")
                git("push", "origin", "main", cwd=writer)
                (client/"app.py").write_text("local edits", encoding="utf-8")
                self.assertFalse(update_from_github(client, lambda: True))
                self.assertEqual((client/"app.py").read_text(), "local edits")
