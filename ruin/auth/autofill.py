from playwright.async_api import Page

from ruin.auth.totp import current_code
from ruin.auth.vault import credential, origin_of


async def fill_login(page: Page, url: str) -> bool:
    """Fill explicitly provisioned fields in the current top-level document."""
    origin = origin_of(url)
    if origin_of(page.url) != origin:
        return False
    fields = {
        "username": 'input[autocomplete=username]:visible',
        "password": 'input[type=password]:visible',
        "totp": 'input[autocomplete=one-time-code]:visible',
    }
    filled = False
    for key, selector in fields.items():
        inputs = await page.locator(selector).element_handles()
        if len(inputs) != 1:
            continue
        secret = credential(origin, key)
        if secret:
            value = current_code(secret) if key == "totp" else secret
            await inputs[0].fill(value)
            filled = True
    return filled
