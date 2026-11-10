import json
import os
import tempfile
import unittest
from pathlib import Path

from playwright.async_api import async_playwright

from ruin.browser.context import prepare_profile


class ProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_preserves_other_preferences_and_session_cookie_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "persistent-chrome"
            prefs = profile / "Default" / "Preferences"
            prefs.parent.mkdir(parents=True)
            prefs.write_text(json.dumps({"download": {"prompt_for_download": True}, "session": {"restore_on_startup": 5}}))
            prepare_profile(profile)
            data = json.loads(prefs.read_text())
            self.assertEqual(data["session"]["restore_on_startup"], 1)
            self.assertTrue(data["download"]["prompt_for_download"])
            async with async_playwright() as pw:
                for first in (True, False):
                    # Use full Chrome/Chromium, not Playwright's headless shell,
                    # which does not implement browser session restoration.
                    context = await pw.chromium.launch_persistent_context(
                        profile, channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"), args=["--restore-last-session"])
                    try:
                        if first:
                            await context.route("https://example.test/**", lambda r: r.fulfill(body="<title>Session fixture</title><p>Restored</p>", content_type="text/html"))
                            await context.pages[0].goto("https://example.test/")
                            await context.add_cookies([{"name": "session", "value": "fixture", "url": "https://example.test/"}])
                            self.assertEqual((await context.cookies())[0]["expires"], -1)
                        else:
                            cookies = await context.cookies("https://example.test/")
                            self.assertEqual([(c["name"], c["value"]) for c in cookies], [("session", "fixture")])
                    finally:
                        await context.close()

    async def test_invalid_preferences_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            prefs = Path(directory) / "Default" / "Preferences"
            prefs.parent.mkdir()
            prefs.write_text("broken")
            with self.assertRaises(json.JSONDecodeError):
                prepare_profile(Path(directory))
            self.assertEqual(prefs.read_text(), "broken")
