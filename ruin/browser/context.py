from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


@asynccontextmanager
async def browser_context(profile: Path, cdp: str | None = None, channel=None):
    async with async_playwright() as playwright:
        if cdp:
            endpoint = urlsplit(cdp)
            if endpoint.scheme != "http" or endpoint.hostname not in {
                "localhost", "127.0.0.1", "::1"
            }:
                raise ValueError("CDP 需要本机 Chrome 的 HTTP 调试地址。")
            browser = await playwright.chromium.connect_over_cdp(cdp)
            if not browser.contexts:
                raise RuntimeError("Chrome 没有可用的浏览器会话。")
            yield browser.contexts[0]
        else:
            profile.mkdir(mode=0o700, parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                profile, channel=channel, headless=False
            )
            try:
                yield context
            finally:
                await context.close()
