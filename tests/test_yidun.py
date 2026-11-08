import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from playwright.async_api import async_playwright

from ruin.auth.yidun import ASSET_HOST, gap_fraction, moka_slider


SITE = "https://app.mokahr.com/campus_apply/zhongan/123?ref=fixture#/job/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
POPUP = f"""
<div class="sd-Modal-content-fixture">
    <input placeholder="请输入手机号"><input placeholder="请输入验证码"><button>获取验证码</button>
</div>
<div class="yidun_popup"><div class="yidun--jigsaw" style="position: relative">
    <img class="yidun_bg-img" width="240" height="120" src="https://{ASSET_HOST}/bg.png">
    <img class="yidun_jigsaw" width="48" height="120" style="position:absolute;left:0"
        src="https://{ASSET_HOST}/piece.png">
    <div class="yidun_control" style="width:240px;height:30px;background:#eee">
        <div class="yidun_slider" style="width:40px;height:30px;background:#888"></div>
    </div>
</div></div>
<script>
const knob = document.querySelector('.yidun_slider'), piece = document.querySelector('.yidun_jigsaw');
let start;
knob.onpointerdown = e => {{ start = e.clientX; knob.setPointerCapture(e.pointerId); }};
knob.onpointermove = e => {{
    if (start !== undefined) piece.style.left = ((e.clientX - start) * 192 / 200) + 'px';
}};
knob.onpointerup = () => {{
    if (Math.abs(parseFloat(piece.style.left) - 91) < 2) {{
        document.querySelector('.yidun_popup').remove();
        if (!document.body.dataset.reject) document.querySelector('button').textContent = '重新获取（59）';
    }}
}};
</script>"""


def puzzle_images(second_gap=False):
    tile = np.zeros((240, 96, 4), np.uint8)
    cv2.rectangle(tile, (7, 65), (63, 128), (160, 180, 50, 255), -1)
    cv2.circle(tile, (63, 97), 14, (160, 180, 50, 255), -1)
    bg = np.full((240, 480), 210, np.uint8)
    for offset in ([182, 310] if second_gap else [182]):
        bg[:, offset:offset + 96][tile[:, :, 3] > 0] = 70
    return tuple(cv2.imencode(".png", img)[1].tobytes() for img in (bg, tile))


class YidunTests(unittest.IsolatedAsyncioTestCase):
    def test_ambiguous_edges(self):
        self.assertIsNone(gap_fraction(*puzzle_images(second_gap=True)))

    async def test_scaled_drag_and_sms_evidence(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch("ruin.auth.yidun.PROFILE", Path(temp) / "chrome"))
        pw = await self.enterAsyncContext(async_playwright())
        browser = await pw.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"))
        self.addAsyncCleanup(browser.close)
        page = await browser.new_page()
        bg, tile = puzzle_images()

        def serve_image(route):
            return route.fulfill(body=bg if route.request.url.endswith("bg.png") else tile,
                                 content_type="image/png", headers={"Access-Control-Allow-Origin": "*"})

        await page.route("https://app.mokahr.com/**", lambda r: r.fulfill(
            body=POPUP, content_type="text/html; charset=utf-8"))
        await page.route(f"https://{ASSET_HOST}/*", serve_image)
        await page.goto(SITE)
        enabled = {"auto_signup": True}
        self.assertIsNone(await moka_slider(page, SITE.replace("aaaa", "bbbb"), enabled))
        self.assertEqual(await moka_slider(page, SITE, {}), "slider_pending")
        self.assertEqual(await moka_slider(page, SITE, enabled), "sms_requested")
        self.assertEqual(await moka_slider(page, SITE, enabled), "sms_requested")
        await page.reload()
        await page.evaluate("document.body.dataset.reject = 'true'")
        self.assertEqual(await moka_slider(page, SITE, enabled), "slider_pending")
        self.assertEqual(await page.locator(".yidun_popup").count(), 0)
        self.assertEqual(await page.get_by_role("button").inner_text(), "获取验证码")
