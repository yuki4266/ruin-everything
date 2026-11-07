from urllib.parse import urlsplit
from playwright.async_api import BrowserContext

from ruin.auth.interceptor import authenticate
from ruin.config import CANVAS


async def courses(context: BrowserContext, origin=CANVAS, timeout=180):
    page = await context.new_page()
    try:
        target = origin + "/courses"
        for attempt in range(2):
            response = await page.goto(target, wait_until="domcontentloaded")
            if response and response.status >= 400:
                raise RuntimeError(f"Canvas returned HTTP {response.status} for the courses page.")
            if page.url.split("?")[0].rstrip("/") == target:
                table = page.locator("#my_courses_table")
                await table.wait_for(state="attached", timeout=10000)
                links = await table.locator("a[href]").evaluate_all(
                    "nodes => nodes.map(a => [a.innerText.trim(), a.href])"
                )
                result = {}
                for name, url in links:
                    if url.startswith(origin + "/courses/") and name:
                        course_id = urlsplit(url).path.removeprefix("/courses/")
                        if course_id.strip("/").isdigit():
                            result[url] = name
                return [{"name": name, "url": url} for url, name in result.items()]
            if attempt == 0:
                await authenticate(page, origin, timeout)
        raise RuntimeError("Canvas redirected again after sign-in. Check the browser's site data settings.")
    finally:
        if not page.is_closed():
            await page.close()
