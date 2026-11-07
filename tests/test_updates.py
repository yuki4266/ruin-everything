import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ruin import rules_loader, updater


class UpdateTests(unittest.TestCase):
    def test_hot_reload_snapshot_and_offline_fallback(self):
        raw = rules_loader.BUNDLED.read_bytes()
        revised = json.loads(raw)
        revised["ashby"]["heading"] = "h4"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, RUIN_RULE_UPDATES="1"):
            cache = Path(tmp) / "sites.json"
            with patch.object(rules_loader, "urlopen", return_value=io.BytesIO(raw)):
                first = rules_loader.snapshot(cache)
            with patch.object(rules_loader, "urlopen", return_value=io.BytesIO(json.dumps(revised).encode())):
                self.assertEqual(rules_loader.snapshot(cache), revised)
            self.assertNotEqual(first, revised)
            for content in [b'{}', b'x' * (rules_loader.LIMIT + 1)]:
                with patch.object(rules_loader, "urlopen", return_value=io.BytesIO(content)):
                    self.assertEqual(rules_loader.snapshot(cache), revised)
            with patch.object(rules_loader, "urlopen", side_effect=TimeoutError):
                self.assertEqual(rules_loader.snapshot(cache), revised)
                cache.write_bytes(b'broken')
                self.assertEqual(rules_loader.snapshot(cache), first)

    def test_overlapping_update_checks_and_throttle(self):
        entered, release = threading.Event(), threading.Event()
        def worker():
            entered.set()
            release.wait(5)
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater, "marker", return_value=Path(tmp)/"check"), \
                patch.object(updater, "update_installation", side_effect=worker) as update:
            thread = threading.Thread(target=updater.check)
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                updater.check()
            finally:
                release.set()
                thread.join()
            updater.check()
            update.assert_called_once()

    def test_git_update_preserves_user_edits(self):
        import subprocess
        def git(folder, *args):
            return subprocess.check_output(["git", "-C", str(folder), *args], text=True).strip()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "upstream"
            upstream.mkdir()
            git(upstream, "init", "-qb", "main")
            (upstream / "pyproject.toml").write_text("# original")
            git(upstream, "add", ".")
            def commit():
                git(upstream, "-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "fixture")
            commit()
            copy = root / "copy"
            git(root, "clone", "-q", str(upstream), str(copy))
            (upstream / "new.txt").write_text("new")
            git(upstream, "add", ".")
            commit()
            with patch.object(updater, "ROOT", copy), patch.object(updater, "marker", return_value=root / "stamp"):
                (copy / "pyproject.toml").write_text("# local edit")
                updater.update_installation()
                self.assertFalse((copy / "new.txt").exists())
                self.assertEqual((copy / "pyproject.toml").read_text(), "# local edit")
                git(copy, "restore", "pyproject.toml")
                updater.update_installation()
                self.assertEqual(git(copy, "rev-parse", "HEAD"), git(upstream, "rev-parse", "HEAD"))

    def test_pip_upgrades_only_to_a_newer_version(self):
        from unittest.mock import Mock
        dist = Mock(version="1.10")
        dist.read_text.side_effect = lambda key: "pip" if key == "INSTALLER" else None
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater, "ROOT", Path(tmp)), \
                patch.object(updater, "distribution", return_value=dist), \
                patch.object(updater, "pip_command", return_value=["pip", "install"]), \
                patch.object(updater.subprocess, "run") as install:
            for release in ["1.9", "1.11"]:
                data = json.dumps({"info": {"version": release}}).encode()
                with patch.object(updater, "urlopen", return_value=io.BytesIO(data)):
                    updater.update_installation()
            install.assert_called_once()
            self.assertTrue(install.call_args.args[0][-1].endswith("==1.11"))
