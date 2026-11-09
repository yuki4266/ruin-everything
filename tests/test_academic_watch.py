import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from playwright.async_api import async_playwright

from ruin.browser.academic import AcademicFlow, academic_step
from ruin.browser.academic_watch import listen

IEEE = "https://ieeexplore.ieee.org"
ACM = "https://dl.acm.org"
SPRINGER = "https://link.springer.com"
WAYF = "https://wayf.springernature.com"
DUKE = "https://shib.oit.duke.edu"


class AcademicWatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.driver = await async_playwright().start()
        self.browser = await self.driver.chromium.launch()
        self.context = await self.browser.new_context()
        self.context.ruin_trusted_oauth_clients = []
        await self.context.route("**/*", lambda r: r.fulfill(content_type="text/html", body="<main></main>"))
        self.page = await self.context.new_page()
        self.flow = AcademicFlow()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.driver.stop()

    async def show(self, origin, html):
        await self.page.goto(origin)
        await self.page.set_content(html)

    async def test_discovery_uses_keyup_and_picks_exact_institution(self):
        for site in [IEEE, ACM, WAYF]:
            await self.show(site, """
                <input role=combobox aria-label="Find your institution"
                       onkeyup="if(this.value==='Duke University') choices.hidden=false">
                <div id=choices role=listbox hidden>
                  <button role=option>Duke Kunshan University</button>
                  <button role=option onclick="window.picked=true">Duke University Libraries</button>
                </div>""")
            self.assertEqual(await academic_step(self.page, self.flow), "search")
            self.assertEqual(await academic_step(self.page, self.flow), "select")
            self.assertTrue(await self.page.evaluate("window.picked"))
            self.assertIsNone(await academic_step(self.page, self.flow))

    async def test_springer_popup_and_new_tabs_join_running_listener(self):
        await self.context.route(WAYF + "/search", lambda r: r.fulfill(content_type="text/html", body="""
            <input placeholder="Search for an institution" onkeyup="document.title=this.value">"""))
        await self.show(SPRINGER, f'<a target="_blank" href="{WAYF}/search">Log in via an institution</a>')
        task = asyncio.create_task(listen(self.context, lambda message: None))
        try:
            async with self.context.expect_page() as popup:
                await asyncio.sleep(.7)
            new = await popup.value
            await new.wait_for_function("document.title === 'Duke University'")
            later = await self.context.new_page()
            await later.goto(ACM)
            await later.set_content('<input aria-label="Institution name" onkeyup="document.title=this.value">')
            await later.wait_for_function("document.title === 'Duke University'")
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

    async def test_off_origin_existing_session_and_other_school_untouched(self):
        content = '<input placeholder="Search for an institution"><button role=option>Duke University</button>'
        for url in ["https://dl.acm.org.evil.test", "http://dl.acm.org", "https://use.thiss.io"]:
            await self.show(url, content)
            self.assertIsNone(await academic_step(self.page, self.flow))
        await self.show(IEEE, "<header>Access provided by: Duke University</header>" + content)
        self.assertIsNone(await academic_step(self.page, self.flow))
        await self.show(ACM, content)
        await self.page.locator("input").fill("Other University")
        self.assertIsNone(await academic_step(self.page, self.flow))

    async def test_duke_bound_to_started_flow_and_same_origin_login(self):
        form = '<form><input name=j_username><input type=password><button>Log In</button></form>'
        await self.show(DUKE, form)
        with patch("ruin.browser.academic.offer_chrome_login", new_callable=AsyncMock) as native:
            self.assertIsNone(await academic_step(self.page, self.flow))
            self.flow.started()
            await self.page.locator("form").evaluate("f=>f.action='https://other.test/'")
            self.assertIsNone(await academic_step(self.page, self.flow))
            native.assert_not_awaited()
            await self.page.set_content(form)
            self.assertEqual(await academic_step(self.page, self.flow), "chrome")
            self.assertIsNone(await academic_step(self.page, self.flow))
            native.assert_awaited_once()
            await self.page.locator("input[type=password]").fill("fixture")
            self.assertIsNone(await academic_step(self.page, self.flow))
            await self.page.locator("[name=j_username]").fill("fixture")
            with patch("ruin.browser.academic.click", new_callable=AsyncMock) as submit:
                self.assertEqual(await academic_step(self.page, self.flow), "login")
                self.assertIsNone(await academic_step(self.page, self.flow))
                submit.assert_awaited_once()
        await self.page.set_content("<button>Approve Duo push</button>")
        self.assertIsNone(await academic_step(self.page, self.flow))


class ReconnectTest(unittest.IsolatedAsyncioTestCase):
    async def test_offline_browser_is_retried_without_launching_chrome(self):
        from contextlib import asynccontextmanager
        from pathlib import Path
        import tempfile

        from ruin.browser.academic_watch import watch

        attempts = []

        @asynccontextmanager
        async def attach(profile, cdp, *, launch_if_missing):
            attempts.append(launch_if_missing)
            if len(attempts) == 1:
                raise RuntimeError("offline")
            yield object()

        with tempfile.TemporaryDirectory() as directory, (
            patch("ruin.browser.academic_watch.PROFILE", Path(directory) / "profile")
        ), patch("ruin.browser.academic_watch.browser_context", attach), (
            patch("ruin.browser.academic_watch.listen", side_effect=asyncio.CancelledError)
        ):
            with self.assertRaises(asyncio.CancelledError):
                await watch()
        self.assertEqual(attempts, [False, False])
