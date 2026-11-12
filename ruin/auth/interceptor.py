import sys
from urllib.parse import urlsplit

from ruin.browser.driver import Page, TimeoutError as PlaywrightTimeoutError


async def authenticate(page: Page, origin: str, timeout: int):
    """Open one SSO attempt and wait for the school to return the browser."""
    await page.goto(origin + "/login/saml", wait_until="domcontentloaded")
    from ruin.auth.saved_login import resume_saved_login
    result = await resume_saved_login(page)
    if not result or result["state"] != "redirected":
        print("Complete sign-in in the browser. The course lookup will resume when Canvas opens.",
              file=sys.stderr)
    def returned(url: str) -> bool:
        location = urlsplit(url)
        return (location.scheme, location.netloc) == (
            urlsplit(origin).scheme, urlsplit(origin).netloc
        ) and not location.path.startswith("/login")

    await page.wait_for_url(returned, timeout=timeout * 1000)


async def verify_greenhouse(context, url, company, timeout, requested_at=None):
    from ruin.auth.email_otp_snatcher import verify_application
    from ruin.config import PROFILE

    try:
        await verify_application(context, url, company, timeout, PROFILE.parent, requested_at)
    except (TimeoutError, PlaywrightTimeoutError):
        raise RuntimeError("Verification timed out. Check the original application before retrying.") from None
