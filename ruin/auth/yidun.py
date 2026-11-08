"""Handle ZhongAn's visible NetEase Yidun puzzle on an exact Moka job tab."""

import re
from base64 import b64decode
from urllib.parse import urlsplit

from filelock import FileLock, Timeout as LockBusy
from playwright.async_api import Error, TimeoutError as BrowserTimeout

from ruin.config import PROFILE


WIDGET = ".yidun_popup:visible .yidun--jigsaw:visible"
COUNTDOWN = re.compile(r"^重新获取\s*[（(]\s*\d{1,3}\s*(?:秒|s)?\s*[）)]$", re.I)
ASSET_HOST = "necaptcha.nosdn.127.net"


def gap_fraction(background, piece):
    """Match the alpha outline along its original row, retaining transparent padding."""
    import cv2
    import numpy as np

    bg = cv2.imdecode(np.frombuffer(background, np.uint8), cv2.IMREAD_GRAYSCALE)
    tile = cv2.imdecode(np.frombuffer(piece, np.uint8), cv2.IMREAD_UNCHANGED)
    if (bg is None or tile is None or tile.ndim != 3 or tile.shape[2] != 4
            or bg.shape[0] != tile.shape[0] or bg.shape[1] <= tile.shape[1]):
        return None
    kernel = np.ones((3, 3), np.uint8)
    mask = (tile[:, :, 3] > 128).astype(np.uint8)
    outline = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, kernel)
    perimeter = cv2.countNonZero(outline)
    if perimeter < 32:
        return None
    edges = cv2.Canny(cv2.GaussianBlur(bg, (3, 3), 0), 50, 120)
    # One pixel of tolerance accommodates antialiasing on the outline.
    edges = cv2.dilate(edges, kernel)
    scores = cv2.matchTemplate(edges, outline, cv2.TM_CCORR)[0] / (255 * perimeter)
    best = int(scores.argmax())
    rivals = scores[np.abs(np.arange(len(scores)) - best) > 6]
    if not rivals.size or scores[best] < 0.65 or scores[best] - rivals.max() < 0.08:
        return None
    return best / bg.shape[1]


async def drag_to_gap(page, widget, site):
    background = widget.locator("img.yidun_bg-img")
    piece = widget.locator("img.yidun_jigsaw")
    images = widget.locator("img.yidun_bg-img, img.yidun_jigsaw")
    sources = await images.evaluate_all("""els => els.map(e => e.currentSrc)""")
    if len(sources) != 2 or any(urlsplit(src)[:2] != ("https", ASSET_HOST) for src in sources):
        return False
    # Read the two public assets with Chrome's cache and the site's CORS rules.
    data = await widget.evaluate("""async (widget, expected) => {
        const images = [...widget.querySelectorAll('img.yidun_bg-img, img.yidun_jigsaw')];
        if (images.some((e, i) => !e.complete || !e.naturalWidth || e.currentSrc !== expected[i])) return null;
        const bytes = await Promise.all(expected.map(async src => {
            const res = await fetch(src, {credentials:'omit', redirect:'error', signal:AbortSignal.timeout(4000)});
            if (!res.ok) throw new Error('Image unavailable');
            const blob = await res.blob();
            if (blob.size > 2000000 || !blob.type.startsWith('image/')) return null;
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        })).catch(() => null);
        if (!bytes || bytes.some(b => !b)) return null;
        return images[0].matches('.yidun_bg-img') ? bytes : bytes.reverse();
    }""", sources)
    if not data:
        return False
    fraction = gap_fraction(b64decode(data[0]), b64decode(data[1]))
    if fraction is None:
        return False

    await page.bring_to_front()
    knob = widget.locator(".yidun_slider")
    await knob.hover(timeout=2000)
    track = await widget.locator(".yidun_control").bounding_box(timeout=2000)
    button = await knob.bounding_box(timeout=2000)
    board = await background.bounding_box(timeout=2000)
    tile = await piece.bounding_box(timeout=2000)
    if not all((track, button, board, tile)) or page.url != site:
        return False
    if sources != await images.evaluate_all("els => els.map(e => e.currentSrc)"):
        return False
    tile_travel = board["width"] - tile["width"]
    knob_travel = track["width"] - button["width"]
    if min(tile_travel, knob_travel) <= 0:
        return False
    target = board["x"] + board["width"] * fraction
    x = button["x"] + button["width"] / 2
    y = button["y"] + button["height"] / 2
    start = x
    limit = track["x"] + track["width"] - button["width"] / 2
    await page.mouse.move(x, y)
    await page.mouse.down()
    try:
        # Yidun scales knob travel to the piece's available travel. Use its actual
        # displayed position to correct for CSS scaling and slider end padding.
        ratio = knob_travel / tile_travel
        for _ in range(3):
            error = target - tile["x"]
            if abs(error) <= 1.5:
                return True
            x = min(limit, max(start, x + error * ratio))
            await page.mouse.move(x, y, steps=18)
            tile = await piece.bounding_box(timeout=1500)
            if not tile or page.url != site:
                return False
        return abs(target - tile["x"]) <= 1.5
    finally:
        await page.mouse.up()


async def moka_slider(page, site, profile):
    url = urlsplit(site)
    if (url.scheme != "https" or url.netloc != "app.mokahr.com" or page.url != site
            or not re.fullmatch(r"/campus_apply/zhongan/\d+/?", url.path)
            or not re.fullmatch(r"/job/[\da-fA-F]{8}(?:-[\da-fA-F]{4}){3}-[\da-fA-F]{12}", url.fragment)):
        return None
    dialog = page.locator('div[class*="sd-Modal-content-"]:visible').filter(
        has=page.get_by_placeholder("请输入手机号", exact=True)).filter(
        has=page.get_by_placeholder("请输入验证码", exact=True))
    if await dialog.count() != 1:
        return None
    countdown = dialog.get_by_role("button", name=COUNTDOWN)
    if await countdown.count() == 1 and await countdown.is_visible():
        return "sms_requested" if page.url == site else "slider_pending"
    widget = page.locator(WIDGET)
    count = await widget.count()
    if not count:
        return None
    if count != 1 or profile.get("auto_signup") is not True:
        return "slider_pending"
    PROFILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with FileLock(PROFILE.parent / "moka-slider.lock", timeout=0):
            if not await drag_to_gap(page, widget, site):
                return "slider_pending"
            await countdown.wait_for(state="visible", timeout=7000)
            return "sms_requested" if page.url == site else "slider_pending"
    except (BrowserTimeout, LockBusy):
        return "slider_pending"
    except Error:
        if page.is_closed() or page.url != site or not await widget.count():
            return "slider_pending"
        raise
