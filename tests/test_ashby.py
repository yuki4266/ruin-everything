import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from playwright.async_api import async_playwright

from ruin.agent.ashby import resume_ashby

JOB = "https://jobs.ashbyhq.com/example/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/application"
SUCCESS = """<section role="status"><h2>Success</h2>
<p>Your application was successfully submitted. We'll contact you if there are next steps.</p></section>"""


class AshbyWorkflow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        driver = await async_playwright().start()
        self.addAsyncCleanup(driver.stop)
        browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
        self.addAsyncCleanup(browser.close)
        self.context = await browser.new_context()
        await self.context.route("**/*", lambda route: route.fulfill(content_type="text/html", body="<main></main>"))
        self.tab = await self.context.new_page()
        await self.tab.goto(JOB)
        storage = tempfile.TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        self.store = Path(storage.name)

    async def test_challenge_resumes_same_form_and_receipt_survives_restart(self):
        await self.tab.set_content('<iframe src="https://www.google.com/recaptcha/api2/bframe"></iframe>')
        events = []
        async def approved_driver(page):
            self.assertIs(page, self.tab)
            await page.set_content(SUCCESS)
        first = await resume_ashby(self.context, JOB, 3, self.store, events.append, approved_driver)
        self.assertEqual(events[0]["state"], "challenge_visible")
        self.assertEqual(first["state"], "submitted")
        await self.tab.close()
        self.assertEqual(first, await resume_ashby(self.context, JOB, 3, self.store, events.append))

    async def test_ambiguous_result_stays_open_and_unrecorded(self):
        await self.tab.set_content(SUCCESS.replace('<section', '<section hidden') +
                                   '<button>Submit application</button><p>Success</p>')
        with self.assertRaisesRegex(RuntimeError, "No official receipt"):
            await resume_ashby(self.context, JOB, .35, self.store, lambda event: None)
        self.assertFalse(self.tab.is_closed())
        with sqlite3.connect(self.store / "ashby-receipts.sqlite3") as db:
            self.assertEqual(db.execute("select count(*) from receipts").fetchone()[0], 0)

    async def test_duplicate_tabs_and_job_change(self):
        second = await self.context.new_page()
        await second.goto(JOB)
        with self.assertRaisesRegex(RuntimeError, "Exactly one"):
            await resume_ashby(self.context, JOB, 2, self.store, lambda event: None)
        await second.close()
        await self.tab.set_content('<iframe src="https://www.google.com/recaptcha/api2/bframe"></iframe>')
        async def changed(page):
            await page.goto(JOB.replace("example", "other"))
            await page.set_content(SUCCESS)
        with self.assertRaisesRegex(RuntimeError, "left the authorized job"):
            await resume_ashby(self.context, JOB, 3, self.store, lambda event: None, changed)
