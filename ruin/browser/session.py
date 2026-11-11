"""Check a selected signed-in status page in a separate local Chrome tab."""
import asyncio
from time import monotonic

from playwright.async_api import TimeoutError as BrowserTimeout

from ruin.browser.background import new_agent_page
from ruin.auth.vault import origin_of


async def keep_alive(context, site, marker, interval, duration):
    origin_of(site)
    if not marker.strip() or min(interval, duration) <= 0:
        raise ValueError("Supply a signed-in text marker and positive timing values.")
    page = await new_agent_page(context, purpose="session-check")
    end = monotonic() + duration
    try:
        while True:
            response = await page.goto(site, wait_until="domcontentloaded")
            if page.url != site or not response or not response.ok:
                raise RuntimeError("The status page redirected or failed. Check the session in Chrome.")
            try:
                await page.get_by_text(marker, exact=True).first.wait_for(timeout=5000)
            except BrowserTimeout:
                raise RuntimeError("The signed-in text is missing. Check the session in Chrome.") from None
            remaining = end - monotonic()
            if remaining <= interval:
                await asyncio.sleep(max(0, remaining))
                return
            await asyncio.sleep(interval)
    finally:
        await page.close()
