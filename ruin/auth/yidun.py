"""Preserve the ZhongAn login countdown result for existing registration clients."""

import re
from contextlib import AsyncExitStack
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout

from ruin.browser.actions import execute
from ruin.browser.puzzles import detect, drag
from ruin.config import PROFILE  # Kept for existing adapter configurations.


WIDGET = ".yidun_popup:visible .yidun--jigsaw:visible"
COUNTDOWN = re.compile(r"^重新获取\s*[（(]\s*\d{1,3}\s*(?:秒|s)?\s*[）)]$", re.I)
ASSET_HOST = "necaptcha.nosdn.127.net"


def gap_fraction(background, piece):
    import cv2
    import numpy as np
    from ruin.browser.puzzle_images import gap_x
    x = gap_x(background, piece)
    if x is not None:
        width = cv2.imdecode(np.frombuffer(background, np.uint8), cv2.IMREAD_GRAYSCALE).shape[1]
        return x / width


async def drag_to_gap(page, widget, site):
    """Legacy one-gesture API, scoped to the caller's visible widget."""
    if page.url != site or await widget.count() != 1:
        return False
    async with AsyncExitStack() as handles:
        puzzle = await detect(page, handles)
        if puzzle and puzzle.kind == "jigsaw" and await widget.evaluate(
            "(root, knob) => root.contains(knob)", puzzle.parts["knob"]
        ):
            return await drag(page, puzzle, site)
    return False


async def moka_slider(page, site, profile):
    url = urlsplit(site)
    if url.scheme != "https" or url.netloc != "app.mokahr.com" or page.url != site:
        return None
    dialog = page.locator('div[class*="sd-Modal-content-"]:visible').filter(
        has=page.get_by_placeholder("请输入手机号", exact=True)).filter(
        has=page.get_by_placeholder("请输入验证码", exact=True))
    if await dialog.count() != 1:
        return None
    countdown = dialog.get_by_role("button", name=COUNTDOWN)
    if await countdown.count() == 1 and await countdown.is_visible():
        return "sms_requested"
    if not await page.locator(WIDGET).count():
        return None
    if profile.get("auto_signup") is not True:
        return "slider_pending"
    result = await execute(page, site)
    if result.state == "challenge_cleared":
        try:
            await countdown.wait_for(state="visible", timeout=7000)
            return "sms_requested" if page.url == site else "slider_pending"
        except BrowserTimeout:
            pass
    return "slider_pending"
