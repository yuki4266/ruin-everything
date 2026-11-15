"""Complete a visible rotation puzzle on the selected Feishu Jobs login tab."""

import asyncio
import math
import random
import re
from urllib.parse import urlsplit

import numpy as np
from filelock import FileLock, Timeout as LockBusy
from ruin.browser.driver import Error, TimeoutError as BrowserTimeout

from ruin.browser.background import prepare_page
from ruin.config import PROFILE

VERIFY_URL = "https://rmc.bytedance.com/verifycenter/captcha/v2"
FRAME = f'iframe[src^="{VERIFY_URL}?"]:visible, iframe[src="{VERIFY_URL}"]:visible'
WIDGET = ".vc-captcha-verify.whirl:visible"
SMS_COUNTDOWN = re.compile(r"^重新获取\s*[(（]\s*\d{1,3}\s*[s秒]\s*[)）]$", re.I)

# Sample the two sides of the circular seam in rendered CSS coordinates.
RINGS = """images => {
    if (images.length !== 2) return null;
    const inner = images.find(i => i.matches('.whirl-img-inner-base'));
    const outer = images.find(i => i.matches('.whirl-img-outer-base'));
    if (!inner || !outer || images.some(i => !i.complete || !i.naturalWidth || !i.clientWidth)) {
        return null;
    }
    return [inner, outer].map(img => {
        const canvas = document.createElement('canvas');
        const size = canvas.width = canvas.height = img.clientWidth;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, size, size);
        let pixels;
        try {
            pixels = ctx.getImageData(0, 0, size, size).data;
        } catch (error) {
            if (error.name === 'SecurityError') return null;
            throw error;
        }
        const radius = inner.clientWidth / 2 * (img === inner ? 0.92 : 1.03);
        return Array.from({length: 360}, (_, degree) => {
            const a = degree * Math.PI / 180;
            const x = Math.floor(size / 2 + radius * Math.cos(a));
            const y = Math.floor(size / 2 + radius * Math.sin(a));
            const i = 4 * (y * size + x);
            return [pixels[i], pixels[i + 1], pixels[i + 2]];
        });
    });
}"""

ANGLES = """images => images.map(img => {
    const transform = getComputedStyle(img).transform;
    if (transform === 'none') return 0;
    const m = new DOMMatrixReadOnly(transform);
    const angle = Math.atan2(m.b, m.a) * 180 / Math.PI;
    return img.matches('.whirl-img-inner-base') ? angle : -angle;
}).reduce((a, b) => a + b, 0)"""


def alignment(inner, outer):
    """Clockwise degrees to bring the inner edge into register with the outer."""
    inside, outside = (np.asarray(ring, dtype=np.float64) for ring in (inner, outer))
    if (inside.shape != (360, 3) or outside.shape != inside.shape
            or not np.isfinite(inside).all() or not np.isfinite(outside).all()):
        return None
    if min(inside.std(axis=0).max(), outside.std(axis=0).max()) < 2:
        return None
    inside, outside = [(a - a.mean(axis=0)) / np.maximum(8, a.std(axis=0))
                       for a in (inside, outside)]
    # Polar RGB continuity plus angular gradients; no image model is involved.
    gradients = [np.roll(a, -2, axis=0) - np.roll(a, 2, axis=0) for a in (inside, outside)]
    scores = np.array([
        np.abs(np.roll(inside, angle, axis=0) - outside).mean()
        + 0.25 * np.abs(np.roll(gradients[0], angle, axis=0) - gradients[1]).mean()
        for angle in range(360)
    ])
    best = int(scores.argmin())
    alternative = min(scores[(best + delta) % 360] for delta in range(12, 349))
    if alternative <= scores[best] * 1.08:
        return None
    # Refine the circular minimum to sub-degree precision.
    left, center, right = scores[(best - 1) % 360], scores[best], scores[(best + 1) % 360]
    curvature = left - 2 * center + right
    offset = np.clip(0.5 * (left - right) / curvature, -0.5, 0.5) if curvature > 0 else 0
    return float((best + offset) % 360)


async def rotate(page, widget, site):
    from ruin.browser.puzzles import move_drag

    images = widget.locator("img.whirl-img-inner-base, img.whirl-img-outer-base")
    rings = await images.evaluate_all(RINGS)
    if not rings or not all(rings):
        return False
    target = alignment(*rings)
    if target is None:
        return False
    button = widget.locator(".captcha-slider-btn")
    await prepare_page(page)
    await button.hover(timeout=2000)
    knob = await button.bounding_box(timeout=2000)
    track = await widget.locator(".captcha-slider-box").bounding_box(timeout=2000)
    if not knob or not track or page.url != site:
        return False
    x, y = knob["x"] + knob["width"] / 2, knob["y"] + knob["height"] / 2
    travel = track["x"] + track["width"] - knob["x"] - knob["width"]
    if travel < 40:
        return False
    before = await images.evaluate_all(ANGLES)
    # Measure the widget's relative rotation per pixel while holding the knob.
    probe = round(travel / 10)
    await page.mouse.move(x, y)
    await page.mouse.down()
    try:
        if not await move_drag(page, site, x, y, 0, probe, steps=5):
            return False
        await widget.evaluate("() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        after = await images.evaluate_all(ANGLES)
        rate = ((after - before + 180) % 360 - 180) / probe
        if abs(rate) < 0.1 or page.url != site:
            return False
        distance = ((target - before) * math.copysign(1, rate)) % 360 / abs(rate)
        if distance > travel + 1:
            return False
        ratio = min(1.0, max(0.0, distance / travel))
        if not await move_drag(page, site, x, y, probe, ratio * travel, steps=18):
            return False
        await asyncio.sleep(random.uniform(0.15, 0.25))
        return page.url == site
    finally:
        await page.mouse.up()


async def feishu_slider(page, site, profile):
    url = urlsplit(site)
    if (url.scheme != "https" or not re.fullmatch(r"[a-z0-9-]+\.jobs\.feishu\.cn", url.netloc)
            or not re.fullmatch(r"/(?:\d+|campus|social)/login/?", url.path) or page.url != site):
        return None
    countdown = page.get_by_role("button", name=SMS_COUNTDOWN)
    if await countdown.is_visible():
        return "sms_requested" if page.url == site else "slider_pending"
    frames = page.locator(FRAME)
    count = await frames.count()
    if not count:
        return None
    if count != 1 or profile.get("auto_signup") is not True:
        return "slider_pending"
    # Separate MCP clients can share the same physical mouse in the CDP tab.
    PROFILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with FileLock(PROFILE.parent / "feishu-slider.lock", timeout=0):
            handle = await frames.element_handle(timeout=2000)
            frame = await handle.content_frame()
            if not frame or frame.url.partition("?")[0] != VERIFY_URL:
                return "slider_pending"
            widget = frame.locator(WIDGET)
            if await widget.count() != 1 or not await rotate(page, widget, site):
                return "slider_pending"
            await countdown.wait_for(state="visible", timeout=6000)
            return "sms_requested" if page.url == site else "slider_pending"
    except (BrowserTimeout, LockBusy):
        return "slider_pending"
    except Error:
        if page.is_closed() or page.url != site or not await frames.count():
            return "slider_pending"
        raise
