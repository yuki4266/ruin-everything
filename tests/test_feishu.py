import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.auth.feishu import VERIFY_URL, alignment, feishu_slider

SITE = "https://example.jobs.feishu.cn/123/login?redirect_path=%2Fresume%2F456%2Fapply"
FRAME_URL = VERIFY_URL + "?fixture=1"
LOGIN = f"""
<button>获取验证码</button><iframe width="400" height="300" src="{FRAME_URL}"></iframe>
<script>
onmessage = e => {{
    if (e.origin !== 'https://rmc.bytedance.com') return;
    document.querySelector('iframe').remove();
    if (e.data === 'accepted') document.querySelector('button').textContent = '重新获取(30s)';
}};
</script>"""
# The inner drawing needs 90 degrees of clockwise rotation to match the outer ring.
PUZZLE = """
<div class="vc-captcha-verify whirl" style="position:relative">
  <img class="whirl-img-outer-base" width="120" height="120">
  <img class="whirl-img-inner-base" width="80" height="80" style="position:absolute;left:20px;top:20px">
  <div class="captcha-slider-box" style="width:220px;height:30px;background:#ddd">
    <div class="captcha-slider-btn" style="width:40px;height:30px;background:#aaa"></div>
  </div>
</div>
<script>
const [outer, inner] = document.images;
for (const img of [outer, inner]) {
    const c = document.createElement('canvas');
    c.width = c.height = img.width;
    const ctx = c.getContext('2d');
    const g = ctx.createConicGradient(img === inner ? -Math.PI / 2 : 0, c.width/2, c.height/2);
    for (const [stop,color] of [[0,'red'],[0.3,'green'],[0.7,'blue'],[1,'red']]) {
        g.addColorStop(stop, color);
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, c.width, c.height);
    img.src = c.toDataURL();
}
let start, angle;
const knob = document.querySelector('.captcha-slider-btn');
knob.onpointerdown = e => { start = e.clientX; knob.setPointerCapture(e.pointerId); };
knob.onpointermove = e => {
    if (start === undefined) return;
    angle = 2 * (e.clientX - start);
    inner.style.transform = 'rotate(' + angle + 'deg)';
};
knob.onpointerup = () => parent.postMessage(
    Math.abs(angle - 90) < 3 ? 'accepted' : 'rejected', 'https://example.jobs.feishu.cn');
</script>"""


class FeishuSliderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch("ruin.auth.feishu.PROFILE", Path(temp) / "chrome"))
        pw = await self.enterAsyncContext(async_playwright())
        browser = await pw.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"))
        self.addAsyncCleanup(browser.close)
        self.page = await browser.new_page()
        await self.page.route(SITE, lambda route: route.fulfill(body=LOGIN, content_type="text/html; charset=utf-8"))
        await self.page.route(FRAME_URL, lambda route: route.fulfill(body=PUZZLE, content_type="text/html; charset=utf-8"))
        await self.page.goto(SITE)

    async def run_slider(self, enabled=True):
        return await feishu_slider(self.page, SITE, {"auto_signup": enabled})

    async def test_rotate_and_repeat_during_countdown(self):
        self.assertEqual(await self.run_slider(enabled=False), "slider_pending")
        self.assertEqual(await self.run_slider(), "sms_requested")
        self.assertEqual(await self.run_slider(), "sms_requested")
        self.assertEqual(await self.page.locator("iframe").count(), 0)

    async def test_unconfirmed_when_widget_disappears(self):
        await self.page.evaluate("""() => { onmessage = () => document.querySelector('iframe').remove(); }""")
        self.assertEqual(await self.run_slider(), "slider_pending")
        self.assertEqual(await self.page.locator("iframe").count(), 0)
        self.assertEqual(await self.page.get_by_role("button").inner_text(), "获取验证码")

    async def test_changed_url_and_ambiguous_images(self):
        self.assertIsNone(await feishu_slider(self.page, SITE + "&other=1", {"auto_signup": True}))
        self.assertIsNone(alignment([(80, 80, 80)] * 360, [(80, 80, 80)] * 360))
        await self.page.frame_locator("iframe").locator(".vc-captcha-verify").evaluate(
            "el => el.classList.remove('whirl')")
        self.assertEqual(await self.run_slider(), "slider_pending")
