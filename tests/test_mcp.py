import asyncio
import os
import sys
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from playwright.async_api import async_playwright


@unittest.skipUnless(find_spec("mcp"), "Install the MCP extra for the stdio integration test.")
class ReceiptMCP(unittest.IsolatedAsyncioTestCase):
    async def test_handoff_through_stdio(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        site = "https://jobs.ashbyhq.com/example/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/application"
        success = "<section role='status'><h2>Success</h2><p>Your application was successfully submitted.</p></section>"
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp) / "chrome"
            async with async_playwright() as pw:
                context = await pw.chromium.launch_persistent_context(
                    profile, channel=os.getenv("RUIN_TEST_CHANNEL", "chromium"), args=["--remote-debugging-port=0"]
                )
                port_file = profile / "DevToolsActivePort"
                async with asyncio.timeout(10):
                    while not (port_file.exists() and port_file.read_text().splitlines()):
                        await asyncio.sleep(0.05)
                port = port_file.read_text().splitlines()[0]
                await context.route("**/*", lambda route: route.fulfill(body="<main>Pending</main>", content_type="text/html"))
                page = context.pages[0]
                await page.goto(site)
                params = StdioServerParameters(command=sys.executable, args=[
                    "-m", "ruin.mcp_server", "--cdp", f"http://127.0.0.1:{port}"
                ], env={"HOME": temp, "USERPROFILE": temp, "RUIN_AUTO_UPDATE": "0", "RUIN_RULE_UPDATES": "0"})
                async with stdio_client(params) as streams, ClientSession(*streams) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    self.assertEqual({t.name for t in tools}, {"ruin_action", "ruin_auto_register", "inspect_application_challenge", "get_ashby_receipt", "watch_ashby_receipt"})
                    registration = await client.call_tool("ruin_auto_register", {"site": site})
                    self.assertEqual(registration.structuredContent["state"], "no_match")
                    inspect = "inspect_application_challenge"
                    board = "https://job-boards.greenhouse.io/example/jobs/12345"
                    args = {"site": board}
                    missing = await client.call_tool(inspect, args)
                    self.assertEqual(missing.structuredContent["state"], "tab_missing")
                    greenhouse = await context.new_page()
                    await greenhouse.goto(board)
                    await greenhouse.set_content('<div hidden><p>Security code</p><input autocomplete="one-time-code"></div>')
                    before = await client.call_tool(inspect, args)
                    self.assertEqual(before.structuredContent["state"], "pending")
                    await greenhouse.evaluate("setTimeout(() => document.querySelector('div').hidden = false, 250)")
                    challenge = await client.call_tool(inspect, {**args, "wait_seconds": 5})
                    self.assertEqual(challenge.structuredContent, {"state": "email_verification", "provider": "greenhouse", "signup_policy": "disabled"})
                    duplicate = await context.new_page()
                    await duplicate.goto(board)
                    ambiguous = await client.call_tool(inspect, args)
                    self.assertEqual(ambiguous.structuredContent["state"], "ambiguous_tabs")
                    await duplicate.close()
                    self.assertEqual(await greenhouse.locator("input").input_value(), "")
                    await page.set_content('<iframe src="https://www.google.com/recaptcha/api2/bframe"></iframe>')
                    challenge = await client.call_tool(inspect, {"site": site})
                    self.assertEqual(challenge.structuredContent["state"], "challenge_visible")
                    await page.set_content("<main>Pending</main>")
                    unsupported = await client.call_tool(inspect, {"site": "https://www.paypal.com/signin"})
                    self.assertTrue(unsupported.isError)
                    pending = await client.call_tool("get_ashby_receipt", {"site": site})
                    self.assertEqual(pending.structuredContent["state"], "unrecorded")
                    self.assertEqual(pending.structuredContent["site"], site)
                    self.assertFalse((Path(temp) / ".ruin-everything").exists())
                    await page.set_content('<button onclick="this.remove()">Apply</button>')
                    action = await client.call_tool("ruin_action", {"site": site, "button": "Apply"})
                    self.assertFalse(action.isError, action.content)
                    self.assertEqual(action.structuredContent["state"], "no_challenge")
                    self.assertEqual(await page.get_by_role("button").count(), 0)
                    missed = await client.call_tool("watch_ashby_receipt", {"site": site, "timeout_seconds": 1})
                    self.assertTrue(missed.isError)
                    self.assertIn("No official receipt", missed.content[0].text)
                    await page.set_content(success)
                    captured = await client.call_tool("watch_ashby_receipt", {"site": site})
                    self.assertFalse(captured.isError, captured.content)
                    self.assertEqual(captured.structuredContent["state"], "submitted")
                    await context.close()
                async with stdio_client(params) as streams, ClientSession(*streams) as client:
                    await client.initialize()
                    for tool in ["get_ashby_receipt", "watch_ashby_receipt"]:
                        saved = await client.call_tool(tool, {"site": site})
                        self.assertFalse(saved.isError)
                        self.assertEqual(saved.structuredContent, captured.structuredContent)
                    other = await client.call_tool("get_ashby_receipt", {"site": site.replace("example", "other")})
                    self.assertEqual(other.structuredContent["state"], "unrecorded")
