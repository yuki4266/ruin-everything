"""Handle a candidate sign-in or registration on the selected Workday tenant."""

import asyncio
import re
import time
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout

from ruin.auth.auto_registrar import SIGNUP, signup
from ruin.auth.email_otp_snatcher import OUTLOOK, mailbox_lock, rows
from ruin.auth.vault import origin_of
from ruin.config import PROFILE
from ruin.rules_loader import load_rules

TENANT = re.compile(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com")
MISSING = re.compile(r"^(?:(?:your |the |this )?account (?:does not exist|not found)|"
                     r"no account (?:found|exists)(?: for (?:this|that) email(?: address)?)?)[.!]?$", re.I)
ACTIVATE = re.compile(r"activate|activation|verify.{0,20}(?:email|account)", re.I)


async def activation_link(mail, site, started, rules):
    while True:
        items = await rows(mail, rules)
        matches = [i for i, row in enumerate(items) if row["id"] and
                   row["received"] >= started * 1000 and ACTIVATE.search(row["label"])]
        if len(matches) > 1:
            raise RuntimeError("Multiple fresh Outlook activation messages appeared. Check the original job.")
        for index in matches:
            target = mail.locator(rules["outlook"]["rows"]).nth(index)
            if items[index]["id"] not in (await target.get_attribute("data-convid"),
                                          await target.get_attribute("data-itemid")):
                continue
            await target.click()
            body = mail.locator(rules["outlook"]["body"])
            await body.wait_for(timeout=5000)
            links = await body.locator("a[href]").evaluate_all("els => els.map(e => e.href)")
            valid = {link for link in links if urlsplit(link).scheme == "https"
                     and urlsplit(link).netloc == urlsplit(site).netloc
                     and ACTIVATE.search(urlsplit(link).path)}
            if len(valid) == 1:
                return valid.pop()
            if len(valid) > 1:
                raise RuntimeError("Multiple tenant activation links appeared in Outlook.")
        await asyncio.sleep(1)


async def submit_workday_registration(page, site, profile):
    requested = await signup(page, site, profile)
    if requested is not None:
        return requested
    submit = page.locator('[data-automation-id="createAccountSubmitButton"]:visible')
    if await submit.count() != 1:
        raise RuntimeError("The Workday registration form is unsupported. Check the open tab.")
    button = await submit.element_handle()
    # Some tenant dialogs submit through a script and have no native form action.
    if not await button.evaluate("(b, origin) => location.origin === origin && !b.closest('form')", origin_of(site)):
        raise RuntimeError("The Workday registration destination changed.")
    scope = await button.evaluate_handle("b => b.closest('[role=dialog]') || b.closest('main')")
    dialog = scope.as_element()
    if dialog is None:
        raise RuntimeError("Could not identify the Workday registration dialog.")
    emails = await dialog.query_selector_all('input[type=email]:visible,input[data-automation-id=email]:visible')
    passwords = await dialog.query_selector_all('input[type=password]:visible')
    if len(emails) != 1 or len(passwords) != 2 or not all(profile.get(k) for k in ("email", "default_password")):
        raise RuntimeError("Complete the local credentials and check the Workday registration fields.")
    await emails[0].fill(profile["email"])
    for field in passwords:
        await field.fill(profile["default_password"])
    for box in await dialog.query_selector_all('input[type=checkbox]:visible'):
        label = await box.evaluate("b => Array.from(b.labels, l => l.textContent).join(' ')")
        if re.search(r"terms (?:of|and)|privacy policy", label, re.I):
            await box.check()
    requested = time.time()
    await button.click(timeout=5000)
    return requested


async def workday_account(page, site, profile, timeout=60, allow_create=True):
    if (profile.get("auto_signup") is not True or not TENANT.fullmatch(urlsplit(site).hostname or "")
            or origin_of(page.url) != origin_of(site)):
        return False
    passwords = page.locator('input[type=password]:visible')
    if not await passwords.count():
        return False
    sign_in = page.get_by_role("button", name=re.compile("^sign in$", re.I))
    email = page.locator('input[type=email]:visible,input[autocomplete=username]:visible,'
                         'input[data-automation-id=email]:visible')
    if await passwords.count() == 1 and await sign_in.count() == 1:
        if await email.count() != 1 or not all(profile.get(k) for k in ("email", "default_password")):
            raise RuntimeError("Workday sign-in needs an email field and local credentials.")
        email_field, password_field = await email.element_handle(), await passwords.element_handle()
        button = await sign_in.element_handle()
        if not await button.evaluate("""(b, origin) => location.origin === origin &&
            (!b.form || ((b.getAttribute('formmethod') || b.form.method).toLowerCase() === 'post' &&
            new URL(b.form.action).origin === origin &&
            (!b.hasAttribute('formaction') || new URL(b.formAction).origin === origin)))""", origin_of(site)):
            raise RuntimeError("The Workday sign-in destination changed.")
        await email_field.fill(profile["email"])
        await password_field.fill(profile["default_password"])
        await button.click()
        missing = page.get_by_text(MISSING).first
        try:
            await page.wait_for_function("""() => ![...document.querySelectorAll('input[type=password]')]
                .some(e=>e.getClientRects().length) || /account (does not exist|not found)|no account (found|exists)/i.test(document.body.innerText)""",
                                         timeout=10000)
        except BrowserTimeout:
            raise RuntimeError("Workday did not confirm sign-in or an absent account. Check the open tab.") from None
        if origin_of(page.url) != origin_of(site):
            raise RuntimeError("Workday left the selected tenant during sign-in.")
        if not await missing.is_visible():
            if await passwords.count():
                raise RuntimeError("Workday returned an ambiguous sign-in error. Check the open tab.")
            return True
        if not allow_create:
            raise RuntimeError("Workday still reports a missing account after activation.")
        create = page.get_by_role("link", name=SIGNUP).or_(page.get_by_role("button", name=SIGNUP))
        await create.click(timeout=5000)
        await passwords.nth(1).wait_for(timeout=5000)
    if await passwords.count() != 2 or origin_of(page.url) != origin_of(site):
        return False
    if not allow_create:
        raise RuntimeError("Workday returned to registration after the account step.")
    with mailbox_lock(PROFILE.parent):
        started = await submit_workday_registration(page, site, profile)
        prompt = page.get_by_text(re.compile(r"check your (?:inbox|email)|activation email|verify your email", re.I)).first
        await prompt.wait_for(timeout=15000)
        mail = await page.context.new_page()
        try:
            async with asyncio.timeout(timeout):
                await mail.goto(OUTLOOK, wait_until="domcontentloaded")
                link = await activation_link(mail, site, started, await load_rules())
                await mail.goto(link, wait_until="domcontentloaded")
                await mail.get_by_text(re.compile(r"(?:email|account).{0,35}(?:has been |successfully |is now )(?:activated|verified)", re.I)).first.wait_for()
                if origin_of(mail.url) != origin_of(site) or origin_of(page.url) != origin_of(site):
                    raise RuntimeError("The Workday activation destination changed.")
                await page.goto(site, wait_until="domcontentloaded")
        except (TimeoutError, BrowserTimeout):
            raise RuntimeError("Workday activation was not confirmed. The original job is still open.") from None
        finally:
            await mail.close()
    return True
