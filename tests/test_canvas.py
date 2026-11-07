import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import os
import tempfile
import unittest

from playwright.async_api import async_playwright

from ruin.agent.executor import courses
from ruin.browser.dom_sanitizer import snapshot


class CanvasTest(unittest.IsolatedAsyncioTestCase):
    async def test_login_resume_and_reopen(self):
        logins = []

        class Portal(BaseHTTPRequestHandler):
            def do_GET(self):
                status, headers, html = 200, {}, ""
                if self.path == "/courses":
                    if "session=ok" in self.headers.get("Cookie", ""):
                        html = '<table id="my_courses_table"><tr><td><a href="/courses/42">Test course</a></td></tr></table>'
                    else:
                        status, headers = 302, {"Location": "/welcome"}
                elif self.path == "/login/saml":
                    logins.append(self.path)
                    html = '<form action="/verified"><button>Approve test login</button></form>'
                elif self.path.startswith("/verified"):
                    headers = {"Set-Cookie": "session=ok; Path=/; Max-Age=3600; HttpOnly"}
                    html = "Welcome"
                self.send_response(status)
                self.send_header("Content-Type", "text/html")
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(html.encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Portal)
        Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"

        async with async_playwright() as driver:
            with tempfile.TemporaryDirectory() as profile:
                for first_run in (True, False):
                    context = await driver.chromium.launch_persistent_context(
                        profile, headless=True, channel=os.getenv("RUIN_TEST_CHANNEL")
                    )
                    try:
                        task = asyncio.create_task(courses(context, origin, timeout=5))
                        if first_run:
                            page = await context.wait_for_event("page")
                            await page.get_by_role("button").click(timeout=5000)
                        result = await task
                        self.assertEqual(result, [{"name": "Test course", "url": origin + "/courses/42"}])
                    finally:
                        await context.close()
        self.assertEqual(len(logins), 1)

    async def test_snapshot(self):
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            page = await browser.new_page()
            await page.set_content('<input type=password value="secret"><button>Submit</button>')
            labels, targets = await snapshot(page)
            self.assertEqual(labels, [{"id": 1, "label": "Submit"}])
            self.assertEqual(await targets[1].inner_text(), "Submit")
            await browser.close()
