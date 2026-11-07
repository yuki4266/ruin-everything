import sys
from urllib.parse import urlsplit

from playwright.async_api import Page


async def authenticate(page: Page, origin: str, timeout: int):
    """Open one SSO attempt and wait for the school to return the browser."""
    print("请在浏览器内完成学校要求的验证。返回 Canvas 后将继续读取课程。",
          file=sys.stderr)
    await page.goto(origin + "/login/saml", wait_until="domcontentloaded")
    def returned(url: str) -> bool:
        location = urlsplit(url)
        return (location.scheme, location.netloc) == (
            urlsplit(origin).scheme, urlsplit(origin).netloc
        ) and not location.path.startswith("/login")

    await page.wait_for_url(returned, timeout=timeout * 1000)
