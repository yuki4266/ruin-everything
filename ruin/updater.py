"""Check an installation for updates in a separate, quiet process."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from http.client import HTTPException
from importlib.metadata import distribution
from pathlib import Path
from urllib.request import urlopen

from filelock import FileLock, Timeout
from packaging.version import Version

NAME = "ruin-everything"
INTERVAL = 6 * 3600
ROOT = Path(__file__).resolve().parents[1]
QUIET = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def marker():
    key = hashlib.sha256(f"{sys.prefix}:{ROOT}".encode()).hexdigest()[:16]
    return Path.home() / ".ruin" / "updates" / key / "last_update_check"


def due(stamp):
    try:
        age = time.time() - stamp.stat().st_mtime
        return age < 0 or age >= INTERVAL
    except FileNotFoundError:
        return True


def start_update_check():
    if os.environ.get("RUIN_AUTO_UPDATE", "1") == "0":
        return
    try:
        if due(marker()):
            subprocess.Popen([sys.executable, "-P", "-m", "ruin.updater"], start_new_session=True, **QUIET)
    except OSError:
        pass


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, timeout=60).strip()


def pip_command():
    if importlib.util.find_spec("pip"):
        return [sys.executable, "-m", "pip", "install"]
    if shutil.which("uv") and sys.prefix != sys.base_prefix:
        return ["uv", "pip", "install", "--python", sys.executable]
    return None


def update_installation():
    dist = distribution(NAME)
    extras = [name for name, module in (("mcp", "mcp"), ("agent", "openai"))
              if importlib.util.find_spec(module)]
    suffix = "[" + ",".join(extras) + "]" if extras else ""
    install = pip_command()
    if (ROOT / ".git").exists():
        if (git("branch", "--show-current") != "main" or git("status", "--porcelain") or
                git("rev-parse", "--abbrev-ref", "@{upstream}") != "origin/main"):
            return
        pending = marker().with_name("refresh_editable")
        before = (ROOT / "pyproject.toml").read_bytes()
        git("pull", "--ff-only", "origin", "main")
        if (ROOT / "pyproject.toml").read_bytes() != before:
            pending.touch()
        if install and pending.exists():
            subprocess.run([*install, "-e", str(ROOT) + suffix], timeout=180, check=True)
            pending.unlink()
        return

    prefix = Path(sys.prefix)
    managed_tool = (prefix / "uv-receipt.toml").is_file()
    # uvx owns its disposable environment. Direct URL and local wheel installs may be pinned.
    if dist.read_text("direct_url.json") or ((dist.read_text("INSTALLER") or "").strip() == "uv" and not managed_tool):
        return
    with urlopen(f"https://pypi.org/pypi/{NAME}/json", timeout=2) as response:
        info = json.load(response)["info"]
    if Version(info["version"]) <= Version(dist.version):
        return
    if managed_tool:
        subprocess.run(["uv", "tool", "upgrade", NAME], env={**os.environ, "UV_TOOL_DIR": str(prefix.parent)},
                       timeout=180, check=True)
    elif install:
        subprocess.run([*install, "--upgrade", NAME + suffix + "==" + str(Version(info["version"]))],
                       timeout=180, check=True)


def check():
    stamp = marker()
    try:
        stamp.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with FileLock(str(stamp) + ".lock", timeout=0):
            if due(stamp):
                stamp.touch()
                update_installation()
    except (OSError, ValueError, KeyError, HTTPException, Timeout, subprocess.SubprocessError):
        # An unreachable registry, busy installer or offline checkout can retry next interval.
        return


if __name__ == "__main__":
    check()
