import base64
import os
import tempfile
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.browser.actions import exact_action
from ruin.browser.puzzles import detect
from test_yidun import puzzle_images

SITE = "https://unlisted.test/jobs/7#/review"


def popup(canvas=False):
    bg, tile = (base64.b64encode(x).decode() for x in puzzle_images())
    tag = "canvas" if canvas else "img"
    return f"""
        <section role="dialog" style="position:fixed;top:10px;left:20px;background:white">
          <div style="position:relative;width:300px;height:150px">
            <{tag} id="a" style="width:300px;height:150px"></{tag}>
            <{tag} id="b" style="position:absolute;top:0;left:12px;width:60px;height:150px"></{tag}>
          </div>
          <div style="width:245px;height:32px;background:#eee">
            <div draggable="true" style="width:35px;height:32px;background:violet"></div>
          </div>
        </section>
        <script>
        const a=document.querySelector('#a'), b=document.querySelector('#b');
        for (const [node, data] of [[a,'{bg}'],[b,'{tile}']]) {{
            const img=new Image();
            img.onload=()=>{{if (node.tagName==='CANVAS') {{
                node.width=img.naturalWidth; node.height=img.naturalHeight; node.getContext('2d').drawImage(img,0,0);
            }} else node.src=img.src;}};
            img.src='data:image/png;base64,'+data;
        }}
        const knob=document.querySelector('[draggable]');
        let x; window.moves=[];
        knob.ondragstart=e=>e.preventDefault();
        knob.onpointerdown=e=>{{x=e.clientX;knob.setPointerCapture(e.pointerId)}};
        knob.onpointermove=e=>{{if(x!==undefined) {{
            moves.push([e.clientX-x,e.clientY,performance.now()]); b.style.left=(12+(e.clientX-x)*228/210)+'px';
        }}}};
        knob.onpointerup=()=>{{
            if (Math.abs(parseFloat(b.style.left)-182*300/480)<2) {{
                document.querySelector('section').remove(); document.title='Received';
            }}
        }};
        </script>"""


class PostActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch("ruin.browser.actions.PROFILE", Path(temp) / "chrome"))
        driver = await self.enterAsyncContext(async_playwright())
        browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"))
        self.addAsyncCleanup(browser.close)
        self.context = await browser.new_context()
        self.page = await self.context.new_page()
        await self.page.route(
            "https://unlisted.test/**",
            lambda r: r.fulfill(body="<button>Apply</button>", content_type="text/html"),
        )
        await self.page.goto(SITE)

    async def test_delayed_post_submit_in_cross_origin_frame(self):
        await self.page.route(
            "https://another.test/**", lambda r: r.fulfill(body=popup(), content_type="text/html")
        )
        await self.page.evaluate("""() => {
            window.submits=0; document.querySelector('button').onclick=()=>{
                submits++;
                setTimeout(()=>{const f=document.createElement('iframe');f.width=430;f.height=260;
                    f.src='https://another.test/widget';document.body.append(f)},1100);
            };
        }""")
        result = await exact_action(self.context, SITE, "Apply")
        self.assertEqual((result.state, result.kind, result.attempts), ("challenge_cleared", "jigsaw", 1))
        self.assertEqual(await self.page.evaluate("submits"), 1)
        frame = self.page.frames[1]
        self.assertEqual(await frame.title(), "Received")
        moves = await frame.evaluate("moves")
        self.assertGreater(max(x for x, y, t in moves) - moves[-1][0], 2)
        self.assertGreater(len({y for x, y, t in moves}), 1)
        self.assertGreater(max(b[2] - a[2] for a, b in zip(moves, moves[1:])), 110)

    async def test_resume_canvas_without_replaying_form(self):
        await self.page.set_content('<button onclick="window.duplicated=true">Apply</button>' + popup(True))
        result = await exact_action(self.context, SITE, "Apply")
        self.assertEqual(result.state, "challenge_cleared")
        self.assertFalse(await self.page.evaluate("!!window.duplicated"))
        self.assertEqual(await self.page.title(), "Received")

    async def test_grid_routes_to_vision_and_scopes_verify(self):
        cells = "".join(
            f'<button role="gridcell" onclick="window.hits.push({n})">{n}</button>' for n in range(1, 10)
        )
        await self.page.set_content(f"""<div role="dialog" style="position:fixed">
            Select all images with bicycles
            <div role="grid" style="display:grid;grid-template-columns:repeat(3,60px)">{cells}</div>
            <button onclick="if (hits.join()==='2,5') this.parentNode.remove()">Verify</button>
            </div><style>[role=gridcell]{{width:60px;height:60px}}</style><script>window.hits=[]</script>""")
        with patch("ruin.browser.puzzles.visual_answer", return_value={"cells": [2, 5]}) as vision:
            result = await exact_action(self.context, SITE)
        self.assertEqual((result.kind, result.state), ("grid", "challenge_cleared"))
        self.assertEqual(vision.call_count, 1)

    async def test_retries_only_the_widget_after_ambiguous_image(self):
        await self.page.set_content(popup())
        encoded = base64.b64encode(puzzle_images(second_gap=True)[0]).decode()
        await self.page.evaluate(
            """async bad => {
            const board=document.getElementById('a'); await board.decode();
            const original=board.src;
            board.src='data:image/png;base64,'+bad; await board.decode();
            const refresh=document.createElement('button');refresh.title='Refresh';refresh.textContent='Refresh';
            window.refreshes=0;refresh.onclick=()=>{window.refreshes++;board.src=original};
            document.querySelector('section').append(refresh);
        }""",
            encoded,
        )
        result = await exact_action(self.context, SITE)
        self.assertEqual((result.state, result.attempts), ("challenge_cleared", 2))
        self.assertEqual(await self.page.evaluate("refreshes"), 1)

    async def test_decorative_banner_and_avatar_in_preview(self):
        await self.page.set_content("""
            <div role="dialog" style="position:fixed">
              <div style="width:310px;height:100px;background-image:linear-gradient(red,blue)">
                <img width="40" height="40" alt="Profile">
              </div>
              <button onclick="document.title='Clicked'">Confirm</button>
            </div>""")
        result = await exact_action(self.context, SITE, 'Confirm')
        self.assertEqual(result.state, 'no_challenge')
        self.assertEqual(await self.page.title(), 'Clicked')

    async def test_unsupported_visible_canvas_remains_pending(self):
        await self.page.set_content(
            '<dialog open>安全验证<canvas width="150" height="120"></canvas></dialog>'
        )
        result = await exact_action(self.context, SITE)
        self.assertEqual((result.state, result.kind, result.attempts), ("challenge_pending", "unresolved", 3))
        self.assertTrue(await self.page.locator("dialog").is_visible())

    async def test_nonchallenge_and_navigation(self):
        await self.page.set_content(
            '<canvas></canvas><input type="range"><button onclick="location.hash=123">Apply</button>'
        )
        async with AsyncExitStack() as stack:
            self.assertIsNone(await detect(self.page, stack))
        self.assertEqual((await exact_action(self.context, SITE, "Apply")).state, "navigated")
