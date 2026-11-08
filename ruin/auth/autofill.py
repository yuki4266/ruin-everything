from playwright.async_api import Page

from ruin.browser.actions import click
from ruin.auth.totp import current_code
from ruin.auth.vault import credential, origin_of
from ruin.auth.trusted import matches_action, trusted_client


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


async def offer_chrome_login(page: Page, url: str, *, clients=()) -> bool:
    """Focus a single login password field so Chrome can offer a saved sign-in."""
    origin = origin_of(url)
    if origin_of(page.url) != origin:
        return False
    fields = await page.locator('input[type=password]:visible').element_handles()
    if len(fields) != 1:
        return False
    field = fields[0]
    eligible = await field.evaluate("""(el, origin) =>
        location.origin === origin && el.form && new URL(el.form.action).origin === origin &&
        !el.form.querySelector('input[autocomplete~="new-password" i]') &&
        !el.disabled && !el.readOnly""", origin)
    if not eligible:
        return False
    if not await field.evaluate("el => Boolean(el.value)"):
        await field.click(timeout=3000)
        client = trusted_client(clients, url)
        if client and client.get("chrome_password_dropdown") and not credential(origin, "password"):
            # Chrome owns its popup. Enter may submit if no suggestion is offered.
            if origin_of(page.url) != origin or not await field.evaluate(
                "el => document.activeElement === el && !el.value"
            ):
                return True
            await field.press("ArrowDown")
            if origin_of(page.url) == origin and await field.evaluate(
                "el => document.activeElement === el"
            ):
                await click(page, field, timeout=3000, enter=True)
    return True


async def click_trusted_login(page: Page, task_url: str, clients, attempted: set) -> str | None:
    """Execute at most one configured action, once per task, on the selected tab."""
    client = trusted_client(clients, task_url)
    if client is None:
        return None
    for index, action in enumerate(client.get("actions", [])):
        if index in attempted or not matches_action(action, page.url):
            continue
        if action["kind"] != "oauth" and origin_of(page.url) != origin_of(task_url):
            # A wildcard selects a tenant; it never authorizes moving to another tenant.
            continue
        if action["kind"] == "login" and await page.locator('input[type=password]:visible').evaluate_all(
            "fields => fields.some(el => !el.value)"
        ):
            continue
        before = page.url
        if action["kind"] == "oauth" and "name" not in action:
            button = page.locator('button#js-oauth-authorize-btn, button[name="authorize"]')
        else:
            button = page.get_by_role("button", name=action["name"], exact=True)
        if await button.count() != 1 or not await button.is_visible() or not await button.is_enabled():
            continue
        if not await button.evaluate("""el =>
            !el.form || new URL(el.form.action).origin === location.origin"""):
            continue
        label = (await button.inner_text()).strip() or action.get("name", "Authorize")
        # Recheck after asynchronous DOM queries. Do not force or retry clicks.
        if page.url != before or not matches_action(action, page.url):
            return None
        attempted.add(index)
        await click(page, button, timeout=3000)
        return label
    return None
