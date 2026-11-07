import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from playwright.async_api import async_playwright

from ruin.auth.auto_registrar import fill_contact_phone, signup, sms_code


class SignupTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_and_ordinary_phone(self):
        site = "https://signup.example/"
        profile = dict(auto_signup=True, phone="5550100", email="person@example.test",
                       default_password="fixture-only")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"))
            page = await browser.new_page()
            await page.route(site, lambda route: route.fulfill(body="<main></main>", content_type="text/html"))
            await page.goto(site)
            await page.set_content('<form method="post"><input type="tel"><button>Apply</button></form>')
            self.assertIsNone(await signup(page, site, profile))
            self.assertEqual(await page.locator("input").input_value(), "")
            await fill_contact_phone(page, site, profile)
            self.assertEqual(await page.locator("input").input_value(), profile["phone"])
            await page.set_content("""<form method="post" onsubmit="event.preventDefault();this.dataset.sent='yes'">
                <input type=email><input type=password><input type=tel>
                <label><input type=checkbox required>Accept Terms of Service</label>
                <button>Create Account</button></form>""")
            await page.locator("form").evaluate("f => f.action='https://elsewhere.example/'")
            self.assertIsNone(await signup(page, site, profile))
            await page.locator("form").evaluate("f => f.action='/'")
            self.assertIsNotNone(await signup(page, site, profile))
            self.assertEqual(await page.locator("form").get_attribute("data-sent"), "yes")
            self.assertEqual(await page.locator("input[type=tel]").input_value(), profile["phone"])
            await browser.close()

    def test_domain_bound_incoming_sms(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "chat.db"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE message (text, date, is_from_me)")
                conn.executemany("INSERT INTO message VALUES (?, ?, ?)", [
                    ("@example.com #123456", 1, 0), ("@example.com #222222", 2, 1),
                    ("@other.example #333333", 3, 0)])
            self.assertEqual(sms_code(db, "example.com", 978307200), "123456")
            self.assertIsNone(sms_code(db, "example.com", 978307201))
