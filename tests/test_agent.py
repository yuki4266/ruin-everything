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
    async def test_signup_and_sms_before_model_decision(self):
        site = "https://portal.test/"
        profile = {"auto_signup": True, "default_password": "fixture-only", "email": "example@example.test"}
        form = """<form method="post" action="/sms"><input type=email><input type=password>
                  <button>Create Account</button></form>"""
        verify = """<input autocomplete="one-time-code"><button onclick="
            if (document.querySelector('input').value === '654321') {
              document.title='Verified';document.body.replaceChildren()
            }">Verify</button>"""
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            await context.route(site + "**", lambda r: r.fulfill(
                content_type="text/html", body=form if r.request.url == site else verify))
            with patch("ruin.agent.browser_task.identity", return_value=profile), patch(
                "ruin.auth.auto_registrar.sms_code", return_value="654321"
            ), patch("openai.AsyncOpenAI") as client:
                steps = [Decision(action="click", element_id=1), Decision(action="done", element_id=None)]
                parse = AsyncMock(side_effect=[
                    SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=s))]) for s in steps])
                client.return_value.__aenter__.return_value.chat.completions.parse = parse
                await browser_task(context, site, "Verify registration", "test")
                states = [c.kwargs["messages"][-1]["content"] for c in parse.await_args_list]
                self.assertIn("Verify", states[0])
                self.assertIn("Verified", states[1])
                for secret in ("654321", profile["default_password"], profile["email"]):
                    self.assertNotIn(secret, "".join(states))
            await browser.close()

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

    async def test_chrome_login_offer_stays_on_the_original_form(self):
        from ruin.auth.autofill import offer_chrome_login
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            site = "https://portal.test/"
            await context.route(site, lambda r: r.fulfill(content_type="text/html", body="<form><input type=password></form>"))
            page = await context.new_page()
            await page.goto(site)
            await page.evaluate("""() => {
                document.addEventListener('submit', e => {e.preventDefault(); window.submitted = true});
                document.addEventListener('keydown', () => {window.keyPressed = true});
            }""")
            self.assertFalse(await offer_chrome_login(page, "https://other.test/"))
            self.assertTrue(await offer_chrome_login(page, site))
            self.assertTrue(await page.locator("input").evaluate("e => document.activeElement === e"))
            self.assertFalse(await page.evaluate("Boolean(window.submitted || window.keyPressed)"))
            for form in ('<form><input type=password autocomplete=new-password></form>',
                         '<form><input type=password><input type=password></form>',
                         '<form action="https://other.test/"><input type=password></form>'):
                await page.set_content(form)
                self.assertFalse(await offer_chrome_login(page, site))
            await browser.close()

    async def test_autofill_resumes_on_a_page_with_strict_csp(self):
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel=os.getenv("RUIN_TEST_CHANNEL"))
            context = await browser.new_context()
            site = "https://portal.test/"
            await context.route(site, lambda r: r.fulfill(
                headers={"content-type": "text/html", "content-security-policy": "script-src 'self'"},
                body='<form><input type="password"></form>',
            ))
            # Simulate completion in the same tab after the user receives the sign-in prompt.
            await context.add_init_script("""document.addEventListener('focusin', event => {
                if (event.target.type === 'password') setTimeout(() => {
                    document.querySelector('form').remove(); document.title = 'Signed in';
                }, 80);
            });""")
            with patch("ruin.auth.autofill.credential", return_value=None), patch("openai.AsyncOpenAI") as client:
                message = SimpleNamespace(parsed=Decision(action="done", element_id=None))
                parse = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=message)]))
                client.return_value.__aenter__.return_value.chat.completions.parse = parse
                await browser_task(context, site, "Finish sign-in", "test", autofill=True)
                self.assertIn("Signed in", parse.await_args.kwargs["messages"][-1]["content"])
            await browser.close()
