"""Exercise background rendering, target isolation and persistent ownership."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.browser.background import AgentTabs, new_agent_page, prepare_page, target_info
from ruin.browser.context import launch_command
from ruin.browser.universal import browser_operation


class BackgroundLaunchTests(unittest.TestCase):
    def test_macos_launch_preserves_profile_and_stays_in_background(self):
        with patch('ruin.browser.context.sys.platform', 'darwin'), patch(
            'ruin.browser.context.chrome_executable',
            return_value='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        ):
            command = launch_command(Path('/tmp/fixture-profile'))
        self.assertEqual(command[:6], ['/usr/bin/open', '-g', '-n', '-a',
                                     '/Applications/Google Chrome.app', '--args'])
        for flag in ['--disable-background-timer-throttling', '--disable-backgrounding-occluded-windows',
                     '--disable-renderer-backgrounding', '--disable-ipc-flooding-protection',
                     '--restore-last-session', f'--user-data-dir={Path("/tmp/fixture-profile").resolve()}']:
            self.assertIn(flag, command)

    def test_registry_is_private_and_does_not_store_auth_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'agent-tabs.json'
            registry = AgentTabs(path)
            registry.put('fixture-target', 'browser', 'https://example.test/?token=fixture-secret')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('fixture-secret', path.read_text())
            self.assertEqual(AgentTabs(path).read(), registry.read())
            path.chmod(0o644)
            with self.assertRaises(RuntimeError):
                registry.read()


class BackgroundBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        driver = await self.enterAsyncContext(async_playwright())
        self.browser = await driver.chromium.launch(channel=os.getenv('RUIN_TEST_CHANNEL', 'chromium'))
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context()
        self.context.ruin_agent_tabs = AgentTabs(self.temp / 'tabs.json')
        await self.context.route('https://fixture.test/**', lambda r: r.fulfill(
            content_type='text/html', body='<title>Fixture</title><input id="draft"><p>Task</p>'))
        self.user = await self.context.new_page()
        await self.user.goto('https://fixture.test/user')
        await self.user.locator('#draft').fill('Unfinished draft')

    async def test_reuse_survives_registry_reload_and_preserves_manual_navigation(self):
        first = await browser_operation(self.context, 'navigate', url='https://fixture.test/task-one')
        agent = next(p for p in self.context.pages if p.url == first['url'])
        self.context.ruin_agent_tabs = AgentTabs(self.temp / 'tabs.json')
        await browser_operation(self.context, 'navigate', url='https://fixture.test/task-two')
        self.assertEqual(len(self.context.pages), 2)
        self.assertEqual(agent.url, 'https://fixture.test/task-two')
        tabs = (await browser_operation(self.context, 'tabs'))['tabs']
        self.assertEqual([t['agent_owned'] for t in tabs], [False, True])
        await agent.goto('https://fixture.test/manual')
        await browser_operation(self.context, 'inspect', site=agent.url)
        await browser_operation(self.context, 'navigate', url='https://fixture.test/task-three')
        self.assertEqual(agent.url, 'https://fixture.test/manual')
        self.assertEqual(len(self.context.pages), 3)
        self.assertEqual(await self.user.locator('#draft').input_value(), 'Unfinished draft')
        # Explicit targeting remains available for authorized existing pages.
        await browser_operation(self.context, 'navigate', site=agent.url, url='https://fixture.test/explicit')
        self.assertEqual(agent.url, 'https://fixture.test/explicit')

    async def test_background_target_renders_and_receives_trusted_input(self):
        agent = await new_agent_page(self.context)
        self.assertEqual((await target_info(agent))['browserContextId'],
                         (await target_info(self.user))['browserContextId'])
        await agent.set_content('''<button onclick="window.result={trusted:event.isTrusted,
            focused:document.hasFocus(),visible:document.visibilityState}">Run</button>
            <script>window.framesRun=0;function tick(){framesRun++;requestAnimationFrame(tick)}tick()</script>''')
        # A different selected tab must not prevent input/rendering on the agent target.
        other = await self.context.new_page()
        await other.set_content('<input value="User page">')
        await prepare_page(agent)
        await agent.get_by_role('button', name='Run').click()
        async with asyncio.timeout(5):
            await agent.wait_for_function('framesRun > 2')
        self.assertEqual(await agent.evaluate('result'),
                         {'trusted': True, 'focused': True, 'visible': 'visible'})
        self.assertGreater(len(await agent.screenshot()), 100)
        self.assertEqual(await self.user.locator('#draft').input_value(), 'Unfinished draft')

    async def test_new_target_in_empty_context_does_not_land_in_user_context(self):
        # Empty ambiguous contexts must fail instead of creating in the wrong window.
        empty = await self.browser.new_context()
        with self.assertRaisesRegex(RuntimeError, 'existing tab'):
            await new_agent_page(empty)
        self.assertEqual(len(self.context.pages), 1)
        await empty.close()


if __name__ == '__main__':
    unittest.main()
