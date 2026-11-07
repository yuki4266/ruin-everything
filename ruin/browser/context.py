import asyncio
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

LOCAL_CDP = "http://127.0.0.1:9222"


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


@asynccontextmanager
async def browser_context(profile: Path, cdp: str | None = None, channel=None):
    url = cdp or LOCAL_CDP
    endpoint = urlsplit(url)
    if endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("CDP requires a local Chrome HTTP debugging endpoint.")
    if url.rstrip("/") in {LOCAL_CDP, "http://localhost:9222"} and not await listening():
        profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        subprocess.Popen([
            chrome_executable(), f"--user-data-dir={profile.resolve()}",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=9222",
            "--no-first-run", "--no-default-browser-check", "about:blank",
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        for _ in range(100):
            if await listening():
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("Chrome did not open port 9222. Check whether the dedicated profile is in use.")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(url)
        if not browser.contexts:
            raise RuntimeError("Chrome has no accessible browser context.")
        yield browser.contexts[0]
