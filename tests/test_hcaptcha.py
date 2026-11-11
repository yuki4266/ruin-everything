"""Exercise real Chromium input across two nested, cross-origin frames."""

import os
import tempfile
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.browser.actions import exact_action
from ruin.browser.background import new_agent_page
from ruin.browser.puzzles import detect

SITE = 'https://portal.test/jobs/5149'


class HCaptchaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch('ruin.browser.actions.PROFILE', Path(temp) / 'chrome'))
        driver = await self.enterAsyncContext(async_playwright())
        browser = await driver.chromium.launch(channel=os.getenv('RUIN_TEST_CHANNEL', 'chromium'))
        self.addAsyncCleanup(browser.close)
        self.context = await browser.new_context(viewport={'width': 1100, 'height': 950})
        self.user_page = await self.context.new_page()
        self.page = await new_agent_page(self.context, purpose="challenge-test")

    async def mount(self, content, mode='challenge'):
        await self.context.route('https://portal.test/**', lambda r: r.fulfill(content_type='text/html', body='''
            <body style="margin:0;height:1800px"><button onclick="window.replayed=true">Apply</button>
            <iframe id="icims_content_iframe" src="https://form.test/login"
            style="position:absolute;left:141px;top:310px;width:800px;height:650px;border:7px solid black"></iframe>'''))
        await self.context.route('https://form.test/**', lambda r: r.fulfill(content_type='text/html', body=f'''
            <iframe src="https://newassets.hcaptcha.com/widget#frame={mode}"
            style="position:absolute;left:53px;top:61px;width:440px;height:480px;border:5px solid black"></iframe>
            <iframe style="display:none" src="https://newassets.hcaptcha.com/hidden#frame=challenge"></iframe>'''))
        await self.context.route('https://newassets.hcaptcha.com/**', lambda r: r.fulfill(content_type='text/html', body=content))
        await self.page.goto(SITE)
        await self.page.evaluate('scrollTo(0, 170)')
        self.frame = next(f for f in self.page.frames if '/widget#' in f.url)
        await self.frame.wait_for_selector('body')

    async def test_indexed_grid_with_hidden_duplicates_and_nested_offsets(self):
        cells = ''.join(f'<div class="task-image" onclick="hits.push({i});focusStates.push(document.hasFocus())">{i}</div>' for i in range(9))
        await self.mount(f'''<style>.task-image{{width:90px;height:90px;background:#acd}}</style>
            <h2>Select all images with bicycles</h2><div style="display:grid;grid-template-columns:repeat(3,90px)">{cells}</div>
            <div hidden>{cells}</div><div class="button-submit" role="button"
            onclick="if(hits.join()==='0,4,8')document.body.replaceChildren()">Verify</div>
            <script>window.hits=[];window.focusStates=[]</script>''')
        with patch('ruin.browser.puzzles.visual_answer', return_value={'cells': [1, 5, 9]}):
            result = await exact_action(self.context, SITE, 'Apply')
        self.assertEqual((result.kind, result.state), ('hcaptcha_grid', 'challenge_cleared'))
        self.assertEqual(await self.frame.evaluate('hits'), [0, 4, 8])
        self.assertEqual(await self.frame.evaluate('focusStates'), [True, True, True])
        self.assertEqual(self.user_page.url, 'about:blank')
        self.assertFalse(await self.page.evaluate('!!window.replayed'))

    async def test_checkbox_click_reaches_nested_control_once(self):
        await self.mount('''<div id="checkbox" role="checkbox" aria-checked="false"
            style="margin:40px;width:32px;height:32px;background:gray"
            onclick="this.setAttribute('aria-checked','true');window.hits++"></div><script>window.hits=0</script>''', 'checkbox')
        result = await exact_action(self.context, SITE)
        self.assertEqual(result.state, 'challenge_cleared')
        self.assertEqual(await self.frame.evaluate('hits'), 1)

    async def test_points_with_scaled_outer_frame(self):
        await self.mount('''<h2>Click the TWO matching shapes</h2>
            <div class="challenge-container"><canvas width="360" height="240"></canvas></div>
            <div class="button-submit" role="button" onclick="if(hits.length===2 &&
            Math.abs(hits[0][0]-90)<2 && Math.abs(hits[0][1]-60)<2 &&
            Math.abs(hits[1][0]-270)<2 && Math.abs(hits[1][1]-180)<2)document.body.replaceChildren()">Verify</div>
            <script>window.hits=[];document.querySelector('canvas').onclick=e=>hits.push([e.offsetX,e.offsetY])</script>''')
        await self.page.locator('#icims_content_iframe').evaluate("e=>{e.style.transform='scale(.8)';e.style.transformOrigin='0 0'}")
        with patch('ruin.browser.puzzles.visual_answer', return_value={'points': [{'x': .25, 'y': .25}, {'x': .75, 'y': .75}]}):
            result = await exact_action(self.context, SITE)
        self.assertEqual((result.kind, result.state), ('hcaptcha_points', 'challenge_cleared'))

    async def test_uncertain_points_do_not_click_or_verify(self):
        await self.mount('''<h2>Click the TWO matching shapes</h2>
            <div class="challenge-container"><canvas width="360" height="240"></canvas></div>
            <div class="button-submit" onclick="window.verified=true">Verify</div>
            <script>window.hits=0;document.querySelector('canvas').onclick=()=>hits++</script>''')
        with patch('ruin.browser.puzzles.visual_answer', return_value={'points': [{'x': float('nan'), 'y': .5}]}):
            result = await exact_action(self.context, SITE)
        self.assertEqual(result.state, 'challenge_pending')
        self.assertEqual(await self.frame.evaluate('hits'), 0)
        self.assertFalse(await self.frame.evaluate('!!window.verified'))

    async def test_canvas_drag_moves_left_and_down_then_verifies(self):
        await self.mount('''<h2>Drag the correct item into the empty space</h2>
            <div class="challenge-container"><canvas width="360" height="240"></canvas></div>
            <div class="button-submit" role="button" onclick="if(ok)document.body.replaceChildren()">Verify</div>
            <script>window.ok=false;window.points=[];const c=document.querySelector('canvas');
            c.onpointerdown=e=>{points.push([e.offsetX,e.offsetY]);c.setPointerCapture(e.pointerId)};
            c.onpointerup=e=>{points.push([e.offsetX,e.offsetY]);ok=Math.abs(points[0][0]-288)<2&&
            Math.abs(points[0][1]-48)<2&&Math.abs(e.offsetX-90)<2&&Math.abs(e.offsetY-192)<2};</script>''')
        with patch('ruin.browser.puzzles.visual_answer', return_value={'from_x': .8, 'from_y': .2, 'to_x': .25, 'to_y': .8}):
            result = await exact_action(self.context, SITE)
        self.assertEqual((result.kind, result.state), ('hcaptcha_drag', 'challenge_cleared'))
        self.assertTrue(await self.frame.evaluate('ok'))

    async def test_hidden_outer_frame_is_not_a_visible_challenge(self):
        await self.mount('<div class="button-submit">Verify</div>')
        await self.page.locator('#icims_content_iframe').evaluate("e=>e.style.visibility='hidden'")
        async with AsyncExitStack() as stack:
            self.assertIsNone(await detect(self.page, stack))

    async def test_unsupported_challenge_is_pending_with_specific_reason(self):
        await self.mount('<div class="button-submit">Verify</div>')
        result = await exact_action(self.context, SITE)
        self.assertEqual(result.state, 'challenge_pending')
        self.assertIn('hcaptcha_pending', result.reason)
        self.assertNotIn('unique', result.reason)
