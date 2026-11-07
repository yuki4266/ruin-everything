import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from playwright.async_api import async_playwright

try:
    from ruin.agent.browser_task import Decision, browser_task
except ImportError:
    browser_task = None


@unittest.skipUnless(browser_task, "install .[agent] to test model tasks")
class AgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_click_then_done(self):
        async def decide(**kwargs):
            state = kwargs["messages"][-1]["content"]
            if "Finished" in state:
                decision = Decision(action="done", element_id=None)
            else:
                self.assertIn("Submit", state)
                decision = Decision(action="click", element_id=1)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=decision))])

        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            await context.route("https://portal.test/**", lambda route: route.fulfill(
                content_type="text/html",
                body="""<button onclick="document.title='Finished'; this.remove()">Submit</button>"""
            ))
            with patch("openai.AsyncOpenAI") as client:
                parse = AsyncMock(side_effect=decide)
                client.return_value.__aenter__.return_value.chat.completions.parse = parse
                await browser_task(context, "https://portal.test/", "Submit", "test")
                self.assertEqual(parse.await_count, 2)
            await browser.close()
