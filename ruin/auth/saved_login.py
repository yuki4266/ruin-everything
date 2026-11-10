"""Advance saved Duke credentials and Duo device trust on the task's own tab."""
import asyncio
import re

from playwright.async_api import Error

from ruin.browser.academic import AcademicFlow, DUKE, duke_login, host
from ruin.browser.actions import click

WAIT_SECONDS = 15


def is_duo(url):
    name = host(url)
    return name == "duosecurity.com" or name.endswith(".duosecurity.com")


def login_page(url):
    return host(url) == DUKE or is_duo(url)


async def click_once(page, element, url, *, kind="login"):
    """Keep a document-local attempt marker across independent CDP clients."""
    marker = f"data-ruin-{kind}-attempted"
    if page.url != url or not await element.evaluate("""(e, marker) => {
        const root = e.ownerDocument.documentElement;
        if (!e.isConnected || root.hasAttribute(marker)) return false;
        root.setAttribute(marker, 'true'); return true;
    }""", marker):
        return False
    try:
        await page.bring_to_front()
        await click(page, element, timeout=2500)
    except RuntimeError as exc:
        # The executor's lock rejects before clicking, so a later call may retry.
        if str(exc) == "Another Ruin action is in progress in shared Chrome.":
            await element.evaluate("(e, marker) => e.ownerDocument.documentElement.removeAttribute(marker)", marker)
        raise
    return True


async def duo_trust(page):
    if not login_page(page.url):
        return None
    for frame in page.frames:
        if not is_duo(frame.url):
            continue
        if frame != page.main_frame:
            owner = await frame.frame_element()
            try:
                if not await owner.is_visible():
                    continue
            finally:
                await owner.dispose()
        url = page.url
        buttons = frame.get_by_role("button", name=re.compile(
            r"^(?:Yes,? trust (?:this )?browser|Trust (?:this )?browser|Yes,? this is my device|Is this your device\?)$",
            re.I,
        )).filter(visible=True)
        if await buttons.count() == 0:
            question = frame.get_by_text(re.compile(r"^Is this your device\?$", re.I)).filter(visible=True)
            if await question.count() == 1:
                buttons = frame.get_by_role("button", name=re.compile(r"^Yes$", re.I)).filter(visible=True)
        if await buttons.count() != 1 or not await buttons.is_enabled():
            continue
        node = await buttons.element_handle()
        try:
            if node and await node.evaluate("""e => !e.form ||
                new URL(e.getAttribute('formaction') || e.form.action, location.href).origin === location.origin"""):
                if await click_once(page, node, url, kind="trust-browser"):
                    return "trust_browser"
        finally:
            if node:
                await node.dispose()
    return None


async def resume_saved_login(page):
    """Wait before handing off a code/push; never export credential values."""
    if not login_page(page.url):
        return None
    flow = AcademicFlow()
    flow.started()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + WAIT_SECONDS
    actions = []
    while not page.is_closed():
        if not login_page(page.url):
            return {"state": "redirected", "actions": actions}
        try:
            step = await duke_login(page, flow, saved_only=True) or await duo_trust(page)
            if step:
                actions.append(step)
                deadline = loop.time() + WAIT_SECONDS
        except Error:
            # Redirects can replace the document between inspection and click.
            if page.is_closed():
                break
        if loop.time() >= deadline:
            has_password = await page.locator('input[type=password]:visible').count()
            return {"state": "credentials_required" if has_password else "verification_required",
                    "actions": actions, "wait_seconds": WAIT_SECONDS,
                    "message": "Sign-in still needs input in the original Chrome tab."}
        await asyncio.sleep(min(.25, max(0, deadline - loop.time())))
    return {"state": "tab_closed", "actions": actions}
