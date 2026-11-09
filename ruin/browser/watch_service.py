"""Manage the opt-in macOS user agent for ruin watch."""
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

from ruin.config import PROFILE

LABEL = "local.ruin-everything.academic-watch"


def configure(install):
    if sys.platform != "darwin":
        raise RuntimeError("Run ruin watch under your user service manager on this platform.")
    path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{LABEL}"

    def launchctl(*args, check=True):
        result = subprocess.run(["launchctl", *args], capture_output=True, text=True)
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip() or "launchctl could not update the watcher.")
        return result.returncode

    if not install:
        if launchctl("print", service, check=False) == 0:
            launchctl("bootout", service)
        path.unlink(missing_ok=True)
        print("Removed the institutional access watcher.")
        return

    PROFILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    log = PROFILE.parent / "academic-watch.log"
    log.touch(mode=0o600, exist_ok=True)
    settings = dict(Label=LABEL, ProgramArguments=[sys.executable, "-m", "ruin.cli", "watch"],
                    RunAtLoad=True, KeepAlive=True, ThrottleInterval=10,
                    StandardErrorPath=str(log), EnvironmentVariables={"RUIN_AUTO_UPDATE": "0"})
    path.parent.mkdir(parents=True, exist_ok=True)
    data = plistlib.dumps(settings)
    if not path.exists() or path.read_bytes() != data:
        with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
            temp.write(data)
        os.replace(temp.name, path)
        if launchctl("print", service, check=False) == 0:
            launchctl("bootout", service)
    if launchctl("print", service, check=False):
        launchctl("bootstrap", domain, str(path))
    print("Installed the institutional access watcher for this macOS login.")
