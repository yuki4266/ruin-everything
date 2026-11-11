import asyncio
import json
import os
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
from .background import AgentTabs, BACKGROUND_FLAGS

LOCAL_CDP = "http://127.0.0.1:9222"


def prepare_profile(profile: Path):
    """Enable session restoration before launching an offline persistent profile."""
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    preferences = set(profile.glob("*/Preferences")) | {profile / "Default" / "Preferences"}
    for path in preferences:
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault("session", {})["restore_on_startup"] = 1
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temp:
            json.dump(data, temp)
        os.replace(temp.name, path)


def chrome_executable():
    candidates = ["google-chrome", "google-chrome-stable", "chrome", "chromium"]
    if sys.platform == "darwin":
        candidates.insert(0, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    elif sys.platform == "win32":
        import os
        candidates[:0] = [str(Path(os.environ[key]) / "Google/Chrome/Application/chrome.exe")
                          for key in ("PROGRAMFILES", "LOCALAPPDATA") if key in os.environ]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    raise RuntimeError("Install Chrome or use --cdp with an existing local Chrome endpoint.")


async def listening():
    try:
        _, writer = await asyncio.open_connection("127.0.0.1", 9222)
    except ConnectionRefusedError:
        return False
    writer.close()
    await writer.wait_closed()
    return True


def launch_command(profile):
    executable = chrome_executable()
    arguments = [f"--user-data-dir={profile.resolve()}",
                 "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=9222",
                 "--no-first-run", "--no-default-browser-check", "--restore-last-session",
                 *BACKGROUND_FLAGS]
    if sys.platform == "darwin":
        app = next((p for p in Path(executable).parents if p.suffix == ".app"), None)
        if app is None:
            raise RuntimeError("A macOS Chrome app bundle is required for background launch.")
        return ["/usr/bin/open", "-g", "-n", "-a", str(app), "--args", *arguments]
    return [executable, *arguments]


@asynccontextmanager
async def browser_context(profile: Path, cdp: str | None = None, channel=None, *, launch_if_missing=True):
    from ruin.auth.trusted import load_trusted_oauth_clients

    clients = load_trusted_oauth_clients(profile.parent / "trusted-auth.json")
    url = cdp or LOCAL_CDP
    endpoint = urlsplit(url)
    if endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("CDP requires a local Chrome HTTP debugging endpoint.")
    if url.rstrip("/") in {LOCAL_CDP, "http://localhost:9222"} and not await listening():
        if not launch_if_missing:
            raise RuntimeError("Shared Chrome is offline. Start the project browser and open the original job.")
        prepare_profile(profile)
        subprocess.Popen(launch_command(profile), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        for _ in range(100):
            if await listening():
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("Chrome did not open port 9222. Check whether the dedicated profile is in use.")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(url, no_defaults=True)
        if not browser.contexts:
            raise RuntimeError("Chrome has no accessible browser context.")
        context = browser.contexts[0]
        context.ruin_trusted_oauth_clients = clients
        context.ruin_agent_tabs = AgentTabs(profile.parent / "agent-tabs.json")
        if url.rstrip('/') in {LOCAL_CDP, 'http://localhost:9222'} and os.getenv('RUIN_LOCAL_AUTH_VAULT', '1') != '0':
            from ruin.auth.vault_runtime import ensure_service
            await ensure_service(url)
        yield context
