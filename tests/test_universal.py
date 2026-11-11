import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.browser.universal import browser_operation


class UniversalBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch("ruin.browser.actions.PROFILE", Path(temp) / "chrome"))
        driver = await self.enterAsyncContext(async_playwright())
        self.browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"))
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context()
        await self.context.route("**/*", lambda r: r.fulfill(content_type="text/html", body='''
            <title>Ordinary website</title><h1>Dashboard</h1>
            <label>Query<input id="query"></label>
            <input type="password" value="fixture-secret">
            <select id="choice"><option value="a">Alpha</option><option value="b">Beta</option></select>
            <button onclick="document.querySelector('h1').textContent='Saved'">Save</button>
            <a href="https://another.test/home">Other site</a>
        '''))
        self.page = await self.context.new_page()

    async def test_background_navigation_preserves_blank_tab_and_session(self):
        await self.context.add_cookies([{"name": "session", "value": "fixture", "url": "https://ordinary.test"}])
        result = await browser_operation(self.context, "navigate", url="https://ordinary.test/dashboard")
        self.assertEqual(self.page.url, "about:blank")
        self.assertEqual(len(self.context.pages), 2)
        self.page = self.context.pages[-1]
        self.assertEqual(result["url"], self.page.url)
        self.assertIn("Dashboard", result["text"])
        self.assertNotIn("fixture-secret", str(result))
        self.assertTrue(result["controls"])
        self.assertIn("session=fixture", await self.page.evaluate("document.cookie"))
        await browser_operation(self.context, "navigate", url=self.page.url)
        self.assertEqual(len(self.context.pages), 2)

    async def test_general_form_and_cross_domain_navigation(self):
        result = await browser_operation(self.context, "navigate", url="http://ordinary.test/form")
        self.page = self.context.pages[-1]
        site = result["url"]
        field = next(c for c in result["controls"] if c["tag"] == "input" and c["label"] == "Query")
        await browser_operation(self.context, "fill", site=site, selector=field["selector"], value="Example")
        await browser_operation(self.context, "select", site=site, selector="#choice", value="b")
        await browser_operation(self.context, "press", site=site, selector="#query", value="End")
        self.assertEqual(await self.page.locator("#query").input_value(), "Example")
        self.assertEqual(await self.page.locator("#choice").input_value(), "b")
        await browser_operation(self.context, "click", site=site, selector='role=button[name="Save"]')
        result = await browser_operation(self.context, "read", site=site, selector="h1")
        self.assertEqual(result["text"], "Saved")
        result = await browser_operation(self.context, "click", site=site, selector='role=link[name="Other site"]')
        self.assertEqual(result["url"], "https://another.test/home")
        result = await browser_operation(self.context, "inspect", site=result["url"])
        self.assertIn("Dashboard", result["text"])

    async def test_ambiguity_and_stale_urls_do_not_change_other_tabs(self):
        await browser_operation(self.context, "navigate", url="https://ordinary.test/")
        self.page = self.context.pages[-1]
        duplicate = await self.context.new_page()
        await duplicate.goto(self.page.url)
        for operation in ["inspect", "navigate"]:
            with self.assertRaises(RuntimeError):
                await browser_operation(self.context, operation, site=self.page.url, url="https://another.test/")
        self.assertEqual(duplicate.url, self.page.url)
        with self.assertRaises(RuntimeError):
            await browser_operation(self.context, "fill", site="https://missing.test/", selector="#query", value="x")
        await duplicate.goto("https://another.test/")
        with self.assertRaises(RuntimeError):
            await browser_operation(self.context, "fill", site=self.page.url, selector="input", value="x")
        self.assertEqual(await self.page.locator("#query").input_value(), "")

    async def test_navigation_preserves_unrelated_tabs_and_reports_redirect(self):
        await self.page.goto("https://ordinary.test/unfinished")
        await self.context.route("https://redirect.test/", lambda r: r.fulfill(content_type="text/html", body='<script>location.replace("https://destination.test/")</script>'))
        result = await browser_operation(self.context, "navigate", url="https://redirect.test/")
        redirected = self.context.pages[-1]
        await redirected.wait_for_url("https://destination.test/")
        result = await browser_operation(self.context, "inspect", site=redirected.url)
        self.assertEqual(result["url"], "https://destination.test/")
        self.assertEqual(self.page.url, "https://ordinary.test/unfinished")
        self.assertEqual(len((await browser_operation(self.context, "tabs"))["tabs"]), 2)

    async def test_invalid_navigation_keeps_blank_tab(self):
        for url in ["file:///tmp/example", "javascript:alert(1)", "https://user:secret@example.org", ""]:
            with self.assertRaises(ValueError):
                await browser_operation(self.context, "navigate", url=url)
        self.assertEqual(self.page.url, "about:blank")
