import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.auth.auto_registrar import sms_code
from ruin.auth.email_otp_snatcher import OUTLOOK
from ruin.auth.workday import submit_workday_registration, workday_account
from ruin.browser.session import keep_alive


class LocalFlow(unittest.IsolatedAsyncioTestCase):
    async def test_workday_login_create_activate_resume(self):
        host = "https://fixture.wd1.myworkdayjobs.com"
        site = host + "/jobs/42"
        login = """<form method=post action="/signin"><input type=email><input type=password>
                   <button>Sign In</button></form>"""
        create = """<form method=post action="/register"><input type=email><input type=password>
                    <input type=password><button>Create Account</button></form>"""
        called = []

        async def route(request):
            url = request.request.url
            called.append(url)
            pages = {
                site: login,
                host + "/signin": login + '<p>Account not found</p><a href="/create">Create Account</a>',
                host + "/create": create,
                host + "/register": "<p>Check your email</p>",
                host + "/activate/fixture": "<p>Your account has been activated</p>",
                OUTLOOK: f"""<div role="option" data-itemid="new" aria-label="Activate your account">
                        Activate account<time datetime="{datetime.now(timezone.utc).isoformat()}"></time></div>
                        <div aria-label="Message body"><a href="{host}/activate/fixture">Activate</a>
                        <a href="https://other.example/activate">Other tenant</a></div>"""
            }
            await request.fulfill(content_type="text/html", body=pages[url])

        with tempfile.TemporaryDirectory() as tmp, patch("ruin.auth.workday.PROFILE", Path(tmp)/"chrome"):
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
                context = await browser.new_context()
                await context.route("**/*", route)
                page = await context.new_page()
                await page.goto(site)
                self.assertTrue(await workday_account(page, site, {
                    "auto_signup": True, "email": "fixture@example.test", "default_password": "fixture"
                }))
                self.assertEqual(page.url, site)
                self.assertEqual(called.count(host + "/register"), 1)
                self.assertIn(host + "/activate/fixture", called)
                self.assertEqual(len(context.pages), 1)
                await browser.close()

    async def test_workday_script_dialog_and_existing_account(self):
        site = "https://fixture.wd1.myworkdayjobs.com/jobs/42"
        profile = {"auto_signup": True, "email": "existing@example.test", "default_password": "fixture"}
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            await context.route(site, lambda route: route.fulfill(content_type="text/html", body="<main></main>"))
            page = await context.new_page()
            await page.goto(site)
            await page.set_content("""<form method="post" onsubmit="event.preventDefault();this.remove()">
                <input type=email><input type=password><button>Sign In</button></form>""")
            self.assertTrue(await workday_account(page, site, profile))
            self.assertEqual(len(context.pages), 1)
            await page.set_content("""<form method="post" onsubmit="event.preventDefault()">
                <input type=email><input type=password><button>Sign In</button></form>
                <p>Account not found or password incorrect</p><button>Create Account</button>""")
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                await workday_account(page, site, profile)
            await page.set_content("""<main><input type=email><input type=password><input type=password>
                <button data-automation-id="createAccountSubmitButton"
                onclick="document.title='submitted'">Create Account</button></main>""")
            self.assertTrue(await submit_workday_registration(page, site, profile))
            self.assertEqual(await page.title(), "submitted")
            await browser.close()

    async def test_session_checks_preserve_original_tab(self):
        site = "https://fixture.example/status"
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            original = await context.new_page()
            requests = []
            async def serve(route):
                requests.append(route.request.method)
                await route.fulfill(content_type="text/html", body="<p>Account dashboard</p>")
            await context.route(site, serve)
            await keep_alive(context, site, "Account dashboard", .05, .4)
            self.assertGreaterEqual(len(requests), 2)
            self.assertEqual(set(requests), {"GET"})
            self.assertEqual(context.pages, [original])
            await browser.close()

    def test_sender_matches_only_selected_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/"chat.db"
            with sqlite3.connect(db) as conn:
                conn.executescript("""CREATE TABLE message (handle_id, date, is_from_me, text);
                    CREATE TABLE handle (id); INSERT INTO handle VALUES ('12345');
                    INSERT INTO message VALUES (1, 1, 0, 'Your verification code is 123456');""")
            self.assertIsNone(sms_code(db, "example.test", 978307200, "other"))
            self.assertEqual(sms_code(db, "example.test", 978307200, "12345"), "123456")
