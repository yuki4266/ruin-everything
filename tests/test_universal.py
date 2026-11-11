import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import Error, Locator, async_playwright

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
        self.pdf = Path(temp) / "sample résumé.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nfixture")

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

    async def test_upload_hidden_nested_frame_and_events(self):
        await self.page.goto("https://ordinary.test/upload")
        await self.page.set_content('<iframe src="https://another.test/form"></iframe>')
        child = self.page.frames[1]
        await child.set_content('<iframe srcdoc="<input type=file hidden>"></iframe>')
        nested = child.child_frames[0]
        field = nested.locator("input")
        await field.evaluate("""e => {
            window.events = []
            for (const type of ['input','change']) e.addEventListener(type, () => events.push(type))
        }""")
        result = await browser_operation(self.context, "upload", site=self.page.url, file_path=str(self.pdf))
        self.assertEqual(result, {"state": "file_selected", "url": self.page.url, "filename": self.pdf.name})
        self.assertEqual(await nested.evaluate("events"), ["input", "change"])
        self.assertEqual(await field.evaluate("e => e.files[0].text()"), self.pdf.read_text())

    async def test_upload_target_validation_and_explicit_drop(self):
        await self.page.set_content("""
            <input type=file><iframe srcdoc='<input type=file>'></iframe>
            <div id="zone" ondragover="event.preventDefault()"
                 ondrop="event.preventDefault();window.dropped = event.dataTransfer.files[0]">Drop here</div>
        """)
        opts = dict(site=self.page.url, file_path=str(self.pdf))
        with self.assertRaisesRegex(ValueError, "Multiple upload targets"):
            await browser_operation(self.context, "upload", **opts)
        for selector in ("#missing", "input:disabled"):
            with self.assertRaisesRegex(ValueError, "No upload target"):
                await browser_operation(self.context, "upload", selector=selector, **opts)
        result = await browser_operation(self.context, "set_files", selector="#zone", **opts)
        self.assertEqual(result["state"], "drop_dispatched")
        self.assertEqual(await self.page.evaluate("dropped.name"), self.pdf.name)
        self.assertEqual(await self.page.evaluate("dropped.text()"), self.pdf.read_text())
        self.assertEqual(await self.page.locator("input").evaluate("e => e.files.length"), 0)

    async def test_file_input_compatibility_and_permissions(self):
        await self.page.set_content('<input type=file>')
        opts = dict(site=self.page.url, file_path=str(self.pdf))
        native = Locator.set_input_files
        async def unsupported(locator, files, **kwargs):
            if isinstance(files, Path):
                raise Error("Protocol error: 'DOM.setFileInputFiles' wasn't found")
            return await native(locator, files, **kwargs)
        with patch.object(Locator, "set_input_files", unsupported):
            await browser_operation(self.context, "upload", **opts)
        field = self.page.locator("input")
        self.assertEqual(await field.evaluate("e => e.files[0].type"), "application/pdf")
        self.assertEqual(await field.evaluate("e => e.files[0].text()"), self.pdf.read_text())
        with patch.object(Locator, "set_input_files", side_effect=Error("Permission denied")) as denied:
            with self.assertRaisesRegex(Error, "Permission denied"):
                await browser_operation(self.context, "upload", **opts)
            self.assertEqual(denied.await_count, 1)
        for path in ("sample.pdf", str(self.pdf.parent), str(self.pdf.with_suffix(".missing")), None):
            with self.assertRaises(ValueError):
                await browser_operation(self.context, "upload", site=self.page.url, file_path=path)
