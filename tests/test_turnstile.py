"""Exercise closed-shadow geometry, bounded actions and clearance boundaries."""
import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from playwright.async_api import async_playwright

from ruin.browser.actions import exact_action
from ruin.browser.background import prepare_page
from ruin.browser.clearance import matches, restore_clearance, save_clearance
from ruin.browser.compatibility import SCRIPT
from ruin.browser.turnstile import find_widget, gesture, rectangle, target, visual_state

SITE = 'https://application.test/job/1'
FRAME = 'https://challenges.cloudflare.com/turnstile-fixture'
BODY = '''<div id="host" style="position:absolute;left:120px;top:180px"></div>
<input type="hidden" name="cf-turnstile-response"><button id="submit">Submit</button>
<script>
window.submits=0;submit.onclick=()=>submits++;
let root=host.attachShadow({mode:'closed'}), nested=document.createElement('div');
root.append(nested);let shadow=nested.attachShadow({mode:'closed'});
let f=document.createElement('iframe');f.src='FRAME';f.style='width:300px;height:65px;border:0';shadow.append(f);
window.addEventListener('message',e=>{if(e.origin==='https://challenges.cloudflare.com' && e.data==='passed') {
 document.querySelector('input').value='fixture-single-use';host.style.display='none';}});
</script>'''.replace('FRAME', FRAME)
WIDGET = '''<body style="margin:0"><input type="checkbox" style="position:absolute;left:15px;top:20px;width:24px;height:24px">
<script>window.moves=[];window.clicks=[];document.addEventListener('mousemove',e=>moves.push([e.clientX,e.clientY]));
document.querySelector('input').onmousedown=e=>window.down=performance.now();
document.querySelector('input').onclick=e=>{clicks.push({trusted:e.isTrusted,duration:performance.now()-down});parent.postMessage('passed','*')};</script>'''


class GeometryTests(unittest.TestCase):
    def test_only_horizontal_geometry_and_skew_rejection(self):
        self.assertEqual(target({'x':10,'y':20,'width':300,'height':65}), (38,52.5))
        self.assertIsNone(target({'x':10,'y':20,'width':150,'height':140}))
        self.assertIsNone(rectangle([0,0,300,20,300,65,0,65]))
        self.assertIsNone(rectangle([0,0,float('nan'),0,1,1,0,1]))


class TurnstileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('ruin.browser.actions.PROFILE',self.temp/'profile'))
        driver=await self.enterAsyncContext(async_playwright())
        self.browser=await driver.chromium.launch(channel=os.getenv('RUIN_TEST_CHANNEL','chromium'))
        self.addAsyncCleanup(self.browser.close)
        self.context=await self.browser.new_context(device_scale_factor=2)
        self.context.ruin_profile=self.temp/'profile'
        self.enterContext(patch('ruin.browser.clearance.SNAPSHOT',self.temp/'cookies.json'))
        await self.context.route('https://application.test/**',lambda r:r.fulfill(body=BODY,content_type='text/html'))
        await self.context.route('https://challenges.cloudflare.com/**',lambda r:r.fulfill(body=WIDGET,content_type='text/html'))
        self.page=await self.context.new_page();await self.page.goto(SITE)
        await self.page.wait_for_function('document.querySelector("#host").offsetHeight>0')
        self.session=await self.context.new_cdp_session(self.page)
        self.addAsyncCleanup(self.session.detach)

    async def test_closed_roots_dpr2_native_input_and_no_form_replay(self):
        await prepare_page(self.page)
        widgets=await find_widget(self.page,self.session)
        self.assertEqual(len(widgets),1)
        self.assertEqual(widgets[0].box['width'],300)
        with patch('ruin.browser.turnstile.visual_state',AsyncMock(return_value='ready')):
            result=await exact_action(self.context,SITE,'Submit')
        self.assertEqual(result.state,'challenge_cleared')
        self.assertEqual(result.attempts,1)
        self.assertEqual(await self.page.evaluate('submits'),0)
        frame=next(f for f in self.page.frames if f.url==FRAME)
        clicks=await frame.evaluate('clicks')
        self.assertEqual(len(clicks),1)
        self.assertTrue(clicks[0]['trusted'])
        self.assertGreaterEqual(clicks[0]['duration'],70)
        # The approach starts outside the iframe; only its final moves enter it.
        self.assertGreaterEqual(len(await frame.evaluate('moves')),2)

    async def test_overlay_prevents_click_and_keeps_form(self):
        widgets=await find_widget(self.page,self.session)
        await self.page.evaluate('''()=>{let cover=document.createElement('div');cover.style='position:fixed;inset:0;z-index:999;background:white';document.body.append(cover)}''')
        self.assertFalse(await gesture(self.page,self.session,SITE,widgets[0]))
        self.assertEqual(await self.page.evaluate('submits'),0)

    async def test_stale_geometry_does_not_click(self):
        widgets=await find_widget(self.page,self.session)
        await self.page.locator('#host').evaluate("e=>e.style.left='400px'")
        self.assertFalse(await gesture(self.page,self.session,SITE,widgets[0]))

    async def test_failure_never_replays_submit(self):
        with patch('ruin.browser.turnstile.visual_state',AsyncMock(return_value='failed')):
            result=await exact_action(self.context,SITE,'Submit')
        self.assertEqual((result.state,result.kind,result.attempts),('challenge_pending','turnstile',0))
        self.assertEqual(await self.page.evaluate('submits'),0)

    async def test_invisible_preloaded_frame_does_not_block_submit(self):
        await self.page.locator('#host').evaluate("e=>e.style.display='none'")
        with patch('ruin.browser.turnstile.screenshot_widget',AsyncMock(return_value=None)):
            result=await exact_action(self.context,SITE,'Submit')
        self.assertEqual(result.state,'no_challenge')
        self.assertEqual(await self.page.evaluate('submits'),1)

    async def test_rendered_state_ignores_hidden_error_panels(self):
        frame=next(f for f in self.page.frames if f.url==FRAME)
        await frame.set_content('''<div id="host"></div><script>
            host.attachShadow({mode:'closed'}).innerHTML='<span>Verify you are human</span><span style="display:none">Verification failed</span>'
            </script>''')
        widgets=await find_widget(self.page,self.session)
        self.assertEqual(await visual_state(self.page,widgets[0]),'ready')

    async def test_future_documents_receive_compatibility_initialization(self):
        await prepare_page(self.page)
        await self.page.goto(SITE+'?next')
        self.assertFalse(await self.page.evaluate('navigator.webdriver'))
        self.assertTrue(await self.page.evaluate("!!globalThis[Symbol.for('ruin.inputCompatibility.v1')]"))

    async def test_script_idempotent_and_preserves_synthetic_coordinates(self):
        await self.page.evaluate(SCRIPT);await self.page.evaluate(SCRIPT)
        self.assertFalse(await self.page.evaluate('navigator.webdriver'))
        self.assertEqual(await self.page.evaluate("new MouseEvent('click',{screenX:12,screenY:34,clientX:5,clientY:6}).screenY"),34)

    async def test_private_cookie_snapshot_scope_expiry_and_profile(self):
        file=self.temp/'cookies.json';file.write_text(json.dumps({'legacy':{'untouched':True}}));file.chmod(0o600)
        cookie={'name':'cf_clearance','value':'fixture-not-real','domain':'application.test','path':'/',
                'expires':time.time()+600,'secure':True,'httpOnly':True,'sameSite':'None'}
        await self.context.add_cookies([cookie,dict(cookie,name='session',value='never-export')])
        self.assertEqual(await save_clearance(self.context,SITE,file),1)
        data=json.loads(file.read_text());self.assertEqual(data['legacy'],{'untouched':True})
        self.assertNotIn('never-export',file.read_text());self.assertEqual(file.stat().st_mode&0o777,0o600)
        await self.context.clear_cookies()
        self.assertEqual(await restore_clearance(self.context,file),1)
        self.assertEqual([c['name'] for c in await self.context.cookies()],['cf_clearance'])
        self.assertEqual(await restore_clearance(self.context,file),0)
        await self.context.clear_cookies();self.context.ruin_profile=self.temp/'other-profile'
        self.assertEqual(await restore_clearance(self.context,file),0)
        self.assertFalse(matches(cookie,'https://application.test.attacker.test'))
        self.assertFalse(matches(dict(cookie,expires=time.time()-1),SITE))
        self.assertFalse(matches(dict(cookie,expires=-1),SITE))
        file.chmod(0o644)
        with self.assertRaises(RuntimeError):await restore_clearance(self.context,file)

if __name__=='__main__':unittest.main()
