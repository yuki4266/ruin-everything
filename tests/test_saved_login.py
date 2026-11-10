import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.auth.saved_login import resume_saved_login
from ruin.browser.universal import browser_operation
from ruin.browser.actions import exact_action

DUKE = "https://shib.oit.duke.edu/idp/authn"
DUO = "https://api-example.duosecurity.com/frame/prompt"
FORM = '<form><input name=j_username value=fixture><input type=password value=fixture-secret><input type=submit id=Submit value="Continue"></form>'


class SavedLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch("ruin.browser.actions.PROFILE", Path(temp) / "chrome"))
        self.enterContext(patch("ruin.auth.saved_login.WAIT_SECONDS", .1))
        pw = await self.enterAsyncContext(async_playwright())
        self.browser = await pw.chromium.launch()
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context()
        await self.context.route("**/*", lambda r: r.fulfill(body="<main>Destination</main>", content_type="text/html"))
        self.page = await self.context.new_page()

    async def show(self, url, html):
        await self.page.goto(url)
        await self.page.set_content(html)

    async def test_universal_follows_filled_duke_form_through_executor(self):
        await self.show(DUKE, FORM.replace('<form>', '<form action="/accepted">'))
        await self.context.route("https://shib.oit.duke.edu/accepted?*", lambda r: r.fulfill(
            body='<script>location.replace("https://canvas.example.test/courses")</script>', content_type="text/html"))
        result = await browser_operation(self.context, "inspect", site=DUKE)
        self.assertEqual(result["url"], "https://canvas.example.test/courses")
        self.assertEqual(result["authentication"], {"state": "redirected", "actions": ["login"]})
        self.assertNotIn("fixture-secret", str(result))

    async def test_waits_for_late_autofill_and_does_not_reclick_same_document(self):
        await self.show(DUKE, FORM.replace('value=fixture-secret', '').replace('<form>', '<form onsubmit="event.preventDefault();window.submissions=(window.submissions||0)+1">'))
        await self.page.evaluate("setTimeout(()=>document.querySelector('[type=password]').value='fixture-secret',50)")
        async def quick_click(page, node, **kwargs):
            await node.click()
        with patch("ruin.auth.saved_login.WAIT_SECONDS", .3), patch("ruin.auth.saved_login.click", side_effect=quick_click):
            result = await resume_saved_login(self.page)
            self.assertEqual(result["actions"], ["login"])
            await self.page.locator('form').evaluate('e=>e.outerHTML=e.outerHTML')
            self.assertEqual((await resume_saved_login(self.page))["actions"], [])
        self.assertEqual(await self.page.evaluate("window.submissions"), 1)

    async def test_empty_fields_cross_origin_and_impostor_do_not_submit(self):
        for url, form in [(DUKE, FORM.replace('value=fixture>', '>')),
                          (DUKE, FORM.replace('<form>', '<form action="https://other.test">')),
                          ("https://shib.oit.duke.edu.evil.test/", FORM)]:
            await self.show(url, form)
            with patch("ruin.auth.saved_login.click") as clicked:
                await resume_saved_login(self.page)
                clicked.assert_not_called()

    async def test_duo_trust_question_and_iframe(self):
        async def quick_click(page, node, **kwargs):
            await node.click()
        for label in ["Yes, trust browser", "Yes, this is my device", "Is this your device?", "Yes"]:
            html = f'<h1>Is this your device?</h1><button onclick="this.remove()">{label}</button>'
            await self.show(DUO, html)
            with patch("ruin.auth.saved_login.click", side_effect=quick_click):
                result = await resume_saved_login(self.page)
            self.assertEqual(result["actions"], ["trust_browser"])
        await self.context.route(DUO, lambda r: r.fulfill(body='<button onclick="this.remove()">Yes, trust browser</button>', content_type="text/html"))
        await self.show(DUKE, f'<iframe src="{DUO}"></iframe>')
        await self.page.frame_locator('iframe').get_by_role('button').wait_for()
        with patch("ruin.auth.saved_login.click", side_effect=quick_click):
            self.assertEqual((await resume_saved_login(self.page))["actions"], ["trust_browser"])
        await self.show("https://other.test/", f'<iframe src="{DUO}"></iframe>')
        self.assertIsNone(await resume_saved_login(self.page))

    async def test_push_waits_full_fifteen_seconds_without_approving(self):
        await self.show(DUO, '<h1>Check your phone</h1><button>Approve Duo push</button><input autocomplete=one-time-code>')
        with patch("ruin.auth.saved_login.WAIT_SECONDS", 15), patch("ruin.auth.saved_login.click") as clicked:
            started = time.monotonic()
            result = await resume_saved_login(self.page)
            self.assertGreaterEqual(time.monotonic() - started, 15)
            clicked.assert_not_called()
        self.assertEqual(result["state"], "verification_required")
        self.assertEqual(await self.page.locator('input').input_value(), '')

    async def test_duo_redirect_during_wait_returns_without_handoff(self):
        await self.show(DUO, '<h1>Check your phone</h1>')
        await self.page.evaluate("setTimeout(()=>location.href='https://canvas.duke.edu/courses',40)")
        with patch("ruin.auth.saved_login.WAIT_SECONDS", 1):
            result = await resume_saved_login(self.page)
        self.assertEqual(result["state"], "redirected")

    async def test_action_without_button_resumes_duo_and_returns_current_url(self):
        await self.show(DUO, '<button onclick="location.href=\'https://canvas.example.test/courses\'">Yes, trust browser</button>')
        result = await exact_action(self.context, DUO)
        self.assertEqual(result.authentication["state"], "redirected")
        self.assertEqual(result.authentication["actions"], ["trust_browser"])
        self.assertEqual(result.authentication["url"], "https://canvas.example.test/courses")
