import base64
import os
import tempfile
import unittest
from contextlib import AsyncExitStack
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

from ruin.browser.actions import exact_action
from ruin.browser.geetest import candidate_boxes, match_order
from ruin.browser.puzzles import detect

SITE = 'https://icons.test/job'
BOXES = [(20, 110, 60, 150), (90, 20, 130, 60), (150, 80, 190, 120)]


def bitmap():
    image = Image.new('RGB', (240, 180), 'white')
    draw = ImageDraw.Draw(image)
    for box, color in zip(BOXES, ['lime', 'blue', 'cyan']):
        draw.rectangle(box, fill=color, outline='black', width=3)
    data = BytesIO()
    image.save(data, 'PNG')
    return data.getvalue()


def detected_pixels(png):
    with Image.open(BytesIO(png)) as image:
        sx, sy = image.width/240, image.height/180
    return [(x1*sx, y1*sy, x2*sx, y2*sy) for x1, y1, x2, y2 in BOXES]


def popup():
    data = base64.b64encode(bitmap()).decode()
    return f'''<style>
      .geetest_panel {{position:fixed;left:20px;top:15px;background:white;z-index:20}}
      .geetest_item_wrap {{width:240px;height:180px;background-image:url(data:image/png;base64,{data})}}
      .geetest_tip_img {{width:120px;height:40px;background-image:linear-gradient(black,white)}}
      .geetest_item_img {{width:240px;height:202px;position:absolute;pointer-events:none}}
      a {{display:inline-block;padding:10px;cursor:pointer}}
      </style><div class="geetest_panel">Select in this order:
      <div class="geetest_tip_img"></div><div class="geetest_item_wrap"><img class="geetest_item_img"></div>
      <a class="geetest_refresh">Refresh</a><a class="geetest_commit">OK</a></div>
      <script>
      window.hits=[];window.rounds=[];window.refreshes=0;window.submits=0;
      document.querySelector('.geetest_item_wrap').onclick=e=>{{
        const r=e.currentTarget.getBoundingClientRect();
        hits.push([e.clientX-r.x,e.clientY-r.y,e.isTrusted,performance.now()]);
      }};
      document.querySelector('.geetest_commit').onclick=e=>{{
        rounds.push(hits.splice(0));window.commitTrusted=e.isTrusted;
        if(!window.fail) document.querySelector('.geetest_panel').remove();
      }};
      document.querySelector('.geetest_refresh').onclick=()=>{{refreshes++;hits=[]}};
      </script>'''


class IconImageTests(unittest.TestCase):
    def test_rotated_templates_preserve_prompt_order_and_exclude_distractor(self):
        from ruin.browser.geetest_shapes import template_order

        shapes = []
        for i in range(4):
            shape = Image.new('L', (90, 90))
            draw = ImageDraw.Draw(shape)
            if i == 0:
                draw.line([(15, 15), (15, 75), (75, 75)], fill=255, width=10)
            elif i == 1:
                draw.ellipse((12, 12, 78, 78), outline=255, width=10)
                draw.line((45, 15, 45, 60), fill=255, width=8)
            elif i == 2:
                draw.polygon([(45, 10), (80, 75), (10, 75)], outline=255, width=10)
            else:
                draw.line((10, 10, 80, 80), fill=255, width=10)
                draw.line((10, 80, 80, 10), fill=255, width=10)
            shapes.append(shape)
        board = Image.new('RGB', (400, 100), '#374142')
        boxes = []
        for i, shape in enumerate(shapes):
            board.paste('#12c9ed', (i*100+5, 5, i*100+95, 95), shape)
            boxes.append((i*100+5, 5, i*100+95, 95))
        tip = Image.new('RGB', (230, 80), 'white')
        for i, index in enumerate([2, 0, 1]):
            shape = shapes[index].rotate(30, expand=True)
            shape = shape.crop(shape.getbbox())
            shape.thumbnail((56, 56))
            tip.paste('#666666', (i*70+8, 12, i*70+8+shape.width, 12+shape.height), shape)
        def png(image):
            output = BytesIO()
            image.save(output, 'PNG')
            return output.getvalue()
        self.assertEqual(template_order(png(board), png(tip), boxes, 3), [3, 1, 2])
        self.assertEqual(template_order(png(board), png(tip), boxes, 4), [])

    def test_detector_filters_duplicate_invalid_and_footer_sized_boxes(self):
        with patch('ruin.browser.geetest.icon_detector') as detector:
            detector.return_value.detection.return_value = BOXES + [BOXES[0], [0, 0, 240, 180], [0, 0, float('nan'), 3]]
            self.assertEqual(candidate_boxes(bitmap()), BOXES)

    def test_order_is_not_sorted_and_rejects_extra_missing_or_duplicate_icons(self):
        for answer, expected in [({'target_count': 2, 'order': [3, 1]}, [3, 1]),
                                 ({'target_count': 2, 'order': [3, 1, 2]}, []),
                                 ({'target_count': 2, 'order': [1, 1]}, []),
                                 ({'target_count': 2, 'order': [True, 2]}, [])]:
            responses = [answer] + [{'candidate': n} for n in expected]
            with patch('ruin.browser.geetest.visual_answer', side_effect=responses), \
                    patch('ruin.browser.geetest_shapes.template_order', return_value=[]):
                self.assertEqual(match_order(bitmap(), bitmap(), BOXES), expected)


class GeeTestBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch('ruin.browser.actions.PROFILE', Path(tmp)/'chrome'))
        p = await self.enterAsyncContext(async_playwright())
        self.browser = await p.chromium.launch(channel=os.getenv('RUIN_TEST_CHANNEL', 'chromium'))
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context(device_scale_factor=2)
        self.page = await self.context.new_page()
        await self.page.route('https://icons.test/**', lambda r: r.fulfill(body=popup(), content_type='text/html'))
        await self.page.goto(SITE)

    async def test_visible_provider_uses_wrap_not_oversized_img(self):
        async with AsyncExitStack() as stack:
            widget = await detect(self.page, stack)
            self.assertEqual(widget.kind, 'geetest_icon')
            self.assertEqual(await widget.parts['board'].get_attribute('class'), 'geetest_item_wrap')
        await self.page.locator('.geetest_panel').evaluate("e=>e.style.display='none'")
        async with AsyncExitStack() as stack:
            self.assertIsNone(await detect(self.page, stack))

    async def test_order_dpr_css_scaling_trusted_clicks_and_commit_in_frame(self):
        await self.page.route('https://widget.test/**', lambda r: r.fulfill(body=popup(), content_type='text/html'))
        await self.page.set_content('<button onclick="window.replayed=true">Apply</button><iframe src="https://widget.test/a" style="margin:30px;border:6px solid red;width:400px;height:330px;transform:scale(.8);transform-origin:top left"></iframe>')
        frame = self.page.frames[1]
        await frame.wait_for_selector('.geetest_commit')
        # Detect in the actual screenshot dimensions; Chromium may normalize
        # transformed iframe screenshots independently of their viewport size.
        with patch('ruin.browser.geetest.candidate_boxes', side_effect=detected_pixels), \
                patch('ruin.browser.geetest.match_order', return_value=[3, 1, 2]):
            result = await exact_action(self.context, SITE, 'Apply')
        self.assertEqual((result.state, result.kind), ('challenge_cleared', 'geetest_icon'))
        hits = (await frame.evaluate('rounds'))[0]
        self.assertEqual(len(hits), 3, hits)
        # Mouse coordinates are transformed CSS offsets within the frame.
        for hit, box in zip(hits, [BOXES[2], BOXES[0], BOXES[1]]):
            self.assertAlmostEqual(hit[0], (box[0]+box[2])/2, delta=2, msg=hits)
            self.assertAlmostEqual(hit[1], (box[1]+box[3])/2, delta=2, msg=hits)
            self.assertTrue(hit[2])
        self.assertTrue(await frame.evaluate('commitTrusted'))
        self.assertGreater(hits[1][3]-hits[0][3], 240)
        self.assertFalse(await self.page.evaluate('!!window.replayed'))

    async def test_failed_confirmation_refreshes_twice_then_pending(self):
        await self.page.evaluate('window.fail=true')
        with patch('ruin.browser.geetest.candidate_boxes', side_effect=detected_pixels), \
                patch('ruin.browser.geetest.match_order', return_value=[1, 2, 3]):
            result = await exact_action(self.context, SITE)
        self.assertEqual((result.state, result.attempts), ('challenge_pending', 3))
        self.assertEqual(await self.page.evaluate('refreshes'), 2)
        self.assertEqual(len(await self.page.evaluate('rounds')), 3)

    async def test_changed_image_after_matching_does_not_click(self):
        from ruin.browser.geetest import solve_icons
        async with AsyncExitStack() as stack:
            widget = await detect(self.page, stack)
            original_screenshot = widget.parts['board'].screenshot
            calls = 0
            async def changing(**kwargs):
                nonlocal calls
                calls += 1
                data = await original_screenshot(**kwargs)
                return data if calls == 1 else b'changed'
            with patch.object(widget.parts['board'], 'screenshot', side_effect=changing), \
                    patch('ruin.browser.geetest.candidate_boxes', return_value=BOXES), \
                    patch('ruin.browser.geetest.match_order', return_value=[1, 2, 3]):
                self.assertFalse(await solve_icons(self.page, widget, SITE))
        self.assertEqual(await self.page.evaluate('hits'), [])

    async def test_incomplete_widget_is_pending_not_absent(self):
        await self.page.locator('.geetest_tip_img').evaluate('e=>e.remove()')
        async with AsyncExitStack() as stack:
            self.assertEqual((await detect(self.page, stack)).kind, 'geetest_pending')
