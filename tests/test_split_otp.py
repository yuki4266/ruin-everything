import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.auth.auto_registrar import message_body, sms_code, verify_sms
from ruin.auth.otp_fields import fill_otp, sms_fields


def attributed(body):
    # Minimal NSArchiver fixture with an attributed string and its backing NSString.
    def name(value):
        return bytes([len(value)]) + value

    header = b"\x04\x0bstreamtyped\x81\xe8\x03"
    root = b"\x84\x01@\x84\x84\x84" + name(b"NSAttributedString") + b"\x00"
    root += b"\x84\x84" + name(b"NSObject") + b"\x00\x85"
    string = b"\x92\x84\x84\x84" + name(b"NSString") + b"\x01\x94"
    return header + root + string + b"\x84\x01+" + name(body.encode()) + b"\x86\x86"


class MessagesTests(unittest.TestCase):
    def test_archived_recruiting_sms_is_bound_to_host_and_request(self):
        body = "【携程】携程招聘 验证码：012345，请在5分钟内完成验证操作。"
        archive = attributed(body)
        self.assertEqual(message_body(None, archive), body)
        self.assertEqual(message_body(None, b"broken"), "")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chat.db"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE message (text, attributedBody, date, is_from_me)")
                db.executemany("INSERT INTO message VALUES (NULL, ?, ?, ?)", [
                    (archive, 1, 0), (attributed(body.replace("012345", "123456")), 2, 1)])
            self.assertEqual(sms_code(path, "careers.ctrip.com", 978307200), "012345")
            self.assertIsNone(sms_code(path, "elsewhere.example", 978307200))
            self.assertIsNone(sms_code(path, "careers.ctrip.com", 978307201))


class SplitOtpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.driver = await async_playwright().start()
        self.addAsyncCleanup(self.driver.stop)
        self.browser = await self.driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
        self.addAsyncCleanup(self.browser.close)
        self.page = await self.browser.new_page()
        self.url = "https://example.test/verify"
        await self.page.route(self.url, lambda r: r.fulfill(content_type="text/html", body="<main></main>"))
        await self.page.goto(self.url)

    async def test_sms_dialog_ignores_outside_fields_and_fires_input_events(self):
        inputs = '<input maxlength="1">' * 6
        await self.page.set_content(f"""<input maxlength="1"><input type="hidden">
            <div role="dialog">请输入手机验证码{inputs}</div>
            <script>document.oninput=e=>e.target.dataset.received=e.data</script>""")
        with patch("ruin.auth.auto_registrar.sms_code", return_value="012345"), \
                patch("ruin.auth.auto_registrar.identity", return_value={}):
            self.assertTrue(await verify_sms(self.page, self.url, time.time()))
        self.assertEqual(await self.page.locator("div input").evaluate_all(
            "es => es.map(e=>e.dataset.received).join('')"), "012345")
        self.assertEqual(await self.page.locator("input").first.input_value(), "")

    async def test_plain_inputs_inside_a_named_otp_group(self):
        await self.page.set_content('<input maxlength="1"><fieldset><legend>Verification code</legend>'
                                    + '<input>' * 6 + '</fieldset>')
        fields, labeled = await sms_fields(self.page)
        self.assertTrue(await fill_otp(fields, "012345", self.url, labeled_group=labeled))
        self.assertEqual(await self.page.locator("body > input").input_value(), "")

    async def test_paste_uses_react_otp_labels_without_touching_the_clipboard(self):
        await self.page.set_content(''.join(f'<input aria-label="Please enter OTP character {i+1}">'
                                            for i in range(6)) + """<script>
            document.onpaste=e=>{
                e.preventDefault();
                const text=e.clipboardData.getData('text');
                document.querySelectorAll('input').forEach((el,i)=>el.value=text[i]);
                document.body.dataset.paste='yes'
            };
            document.oninput=()=>document.body.dataset.replayed='yes'
            </script>""")
        self.assertTrue(await fill_otp((await sms_fields(self.page))[0], "012345", self.url))
        self.assertEqual(await self.page.locator("body").get_attribute("data-paste"), "yes")
        self.assertIsNone(await self.page.locator("body").get_attribute("data-replayed"))

    async def test_single_wrong_length_separate_forms_and_changed_url(self):
        await self.page.set_content('<input autocomplete="one-time-code">')
        self.assertTrue(await fill_otp((await sms_fields(self.page))[0], "123456", self.url))
        self.assertFalse(await fill_otp((await sms_fields(self.page))[0], "333333", self.url + "#other"))
        self.assertEqual(await self.page.locator("input").input_value(), "123456")
        cells = '<input maxlength="1">' * 3
        await self.page.set_content(f"<form>{cells}</form><form>{cells}</form>")
        fields, _ = await sms_fields(self.page)
        self.assertFalse(await fill_otp(fields, "123456", self.url))
        self.assertFalse(await fill_otp(fields, "1234", self.url))
        self.assertEqual(await fields.evaluate_all("es=>es.map(e=>e.value).join('')"), "")
