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
                    profile, channel=os.getenv("RUIN_TEST_CHANNEL"), args=["--remote-debugging-port=0"]
                )
                port = (profile / "DevToolsActivePort").read_text().splitlines()[0]
                await context.route("**/*", lambda route: route.fulfill(body="<main>Pending</main>", content_type="text/html"))
                page = context.pages[0]
                await page.goto(site)
                params = StdioServerParameters(command=sys.executable, args=[
                    "-m", "ruin.mcp_server", "--cdp", f"http://127.0.0.1:{port}"
                ], env={"HOME": temp, "USERPROFILE": temp})
                async with stdio_client(params) as streams, ClientSession(*streams) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    self.assertEqual({t.name for t in tools}, {"get_ashby_receipt", "watch_ashby_receipt"})
                    pending = await client.call_tool("get_ashby_receipt", {"site": site})
                    self.assertEqual(pending.structuredContent["state"], "unrecorded")
                    self.assertEqual(pending.structuredContent["site"], site)
                    self.assertFalse((Path(temp) / ".ruin-everything").exists())
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
