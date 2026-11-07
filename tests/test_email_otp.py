import os
import tempfile
import unittest
from pathlib import Path

from playwright.async_api import async_playwright

from ruin.auth.email_otp_snatcher import mailbox_lock, parse_code, verify_application


class MailVerification(unittest.IsolatedAsyncioTestCase):
    def test_code_and_lock(self):
        self.assertIsNone(parse_code("security password Greenhouse"))
        self.assertIsNone(parse_code("Code: [one-time authentication code withheld]"))
        self.assertIsNone(parse_code("Code: X1234567; Code: Z1234567"))
        self.assertEqual(parse_code("Security code: 0AbC123X"), "0AbC123X")
        with tempfile.TemporaryDirectory() as folder, mailbox_lock(Path(folder)):
            with self.assertRaisesRegex(RuntimeError, "already waiting"), mailbox_lock(Path(folder)):
                self.fail("Mailbox lock admitted a second job")

    async def test_original_tab_receipt(self):
        url = "https://job-boards.greenhouse.io/demo/jobs/42"
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            await context.route(url, lambda route: route.fulfill(content_type="text/html", body="""
                <p>Enter your security code</p><input maxlength="8">
                <button onclick="window.name='sent'">Resend code</button>
                <button onclick="if(document.querySelector('input').value==='0AbC123X')
                    document.body.innerText='Thank you for applying'">Submit</button>"""))
            app = await context.new_page()
            await app.goto(url)
            async def inbox(route):
                await route.fulfill(content_type="text/html", body="""
                    <div role="option" data-convid="old">Demo security code</div>
                    <script>setInterval(async () => {
                        if (!await window.sent() || document.querySelector('#fresh')) return;
                        let el=document.createElement('div'); el.id='fresh';
                        el.setAttribute('role','option'); el.dataset.convid='new';
                        el.innerHTML='Demo security code <time datetime="'+new Date().toISOString()+'"></time>';
                        el.onclick=()=>document.body.insertAdjacentHTML('beforeend',
                          '<span title="no-reply@us.greenhouse-mail.io">Greenhouse</span><p aria-label="Message body">Code: 0AbC123X</p>');
                        document.body.appendChild(el);
                    },100)</script>""")
            await context.expose_binding("sent", lambda _: app.evaluate("window.name==='sent'"))
            await context.route("https://outlook.office.com/mail/", inbox)
            with tempfile.TemporaryDirectory() as folder:
                await verify_application(context, url, "Demo", 12, Path(folder))
            self.assertEqual(context.pages, [app])
            self.assertEqual(await app.locator("body").inner_text(), "Thank you for applying")
            await browser.close()
