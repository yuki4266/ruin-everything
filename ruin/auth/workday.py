"""Handle a candidate sign-in or registration on the selected Workday tenant."""

import asyncio
import re
import time
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout

from ruin.browser.actions import click
from ruin.auth.auto_registrar import SIGNUP, signup
from ruin.auth.email_otp_snatcher import OUTLOOK, mailbox_lock, rows
from ruin.auth.vault import origin_of
from ruin.config import PROFILE
from ruin.rules_loader import load_rules

TENANT = re.compile(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com")
MISSING = re.compile(r"^(?:(?:your |the |this )?account (?:does not exist|not found)|"
                     r"no account (?:found|exists)(?: for (?:this|that) email(?: address)?)?|"
                     r"we (?:could not|couldn['’]t) find an account (?:with|for) (?:this|that) email address)[.!]?$", re.I)
ACTIVATE = re.compile(r"activate|activation|verification code|verify.{0,20}(?:email|account)", re.I)


EMAIL_CODE = re.compile(r"(?:verification|activation|security) code(?: is)?[\s:–-]*(\d{6})(?!\d)", re.I)
CODE_FIELD = 'input[autocomplete=one-time-code]:visible,input[data-automation-id=verificationCode]:visible'
CONFIRMED = re.compile(r"(?:email|account).{0,35}(?:has been |successfully |is now )(?:activated|verified)", re.I)


async def guard_account_button(button, site):
    eligible = await button.evaluate("""(b, origin) => {
        if (!b.isConnected || location.origin !== origin) return false;
        const f = b.form || b.closest('form');
        if (!f) return true;
        if (new URL(f.action).origin !== origin ||
            (b.hasAttribute('formaction') && new URL(b.formAction).origin !== origin)) return false;
        if ((b.getAttribute('formmethod') || f.method).toLowerCase() === 'post') return true;
        if (!['signInSubmitButton', 'createAccountSubmitButton', 'forgotPasswordSubmitButton',
              'resetPasswordSubmitButton'].includes(b.dataset.automationId) ||
            !f.closest('[role=dialog]') || f.hasAttribute('method') || f.hasAttribute('action') ||
            b.hasAttribute('formaction') || b.hasAttribute('formmethod')) return false;
        // Workday handles this form in JavaScript. Suppress a native GET of credentials.
        f.addEventListener('submit', e => e.preventDefault(), {capture:true});
        return true;
    }""", origin_of(site))
    if not eligible:
        raise RuntimeError("The Workday form destination changed. Check the open tab.")


async def activation_message(mail, site, started, rules, accept_code):
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
                return "link", valid.pop()
            if len(valid) > 1:
                raise RuntimeError("Multiple tenant activation links appeared in Outlook.")
            if accept_code and any(urlsplit(link).scheme == "https" and
                                   urlsplit(link).netloc == urlsplit(site).netloc for link in links):
                codes = set(EMAIL_CODE.findall(await body.inner_text()))
                if len(codes) == 1:
                    return "code", codes.pop()
                if codes:
                    raise RuntimeError("The tenant email contains multiple activation codes.")
        await asyncio.sleep(1)


async def verify_email_code(page, site, value):
    if origin_of(page.url) != origin_of(site):
        raise RuntimeError("The Workday verification destination changed.")
    field = await page.locator(CODE_FIELD).element_handle(timeout=5000)
    group = await field.evaluate_handle("e => e.closest('form, [role=dialog]')")
    if group.as_element() is None:
        raise RuntimeError("The Workday email verification form changed.")
    controls = await group.as_element().query_selector_all("button:visible")
    buttons = [b for b in controls if re.fullmatch(r"verify(?: email| code)?|activate(?: account)?",
                                                   (await b.inner_text()).strip(), re.I)]
    if len(buttons) != 1:
        raise RuntimeError("No unique email verification action in the Workday form.")
    await guard_account_button(buttons[0], site)
    await field.fill(value)
    await click(page, buttons[0])


async def submit_workday_registration(page, site, profile):
    requested = await signup(page, site, profile)
    if requested is not None:
        return requested
    submit = page.locator('[data-automation-id="createAccountSubmitButton"]:visible')
    if await submit.count() != 1:
        raise RuntimeError("The Workday registration form is unsupported. Check the open tab.")
    button = await submit.element_handle()
    await guard_account_button(button, site)
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
    wrapper = await dialog.query_selector('[data-automation-id=click_filter][aria-label="Create Account" i]:visible')
    await click(page, wrapper or button)
    return requested


async def workday_account(page, site, profile, timeout=60, allow_create=True):
    from .ats_accounts import INVALID, account_control, claim, fill_password, request_reset, workday_login_fallback

    profile = {**profile, "default_password": profile.get("ats_default_password") or profile.get("default_password")}
    if (profile.get("auto_signup") is not True or not TENANT.fullmatch(urlsplit(site).hostname or "")
            or origin_of(page.url) != origin_of(site)):
        return False
    dialogs = page.locator('[role=dialog]:visible').filter(has=page.locator('input[type=password]:visible'))
    scope = dialogs if await dialogs.count() == 1 else page
    passwords = scope.locator('input[type=password]:visible')
    if await dialogs.count() > 1:
        raise RuntimeError("Multiple Workday account dialogs are open.")
    if not await passwords.count():
        return False
    await page.bring_to_front()
    headings = ' '.join(await scope.locator('h1,h2,[role=heading]').all_inner_texts())
    if profile.get("ats_auto_recover") and await passwords.count() == 2 and re.search(r'reset|new password', headings, re.I):
        submit = await account_control(scope, re.compile(r'^(?:(?:reset|change|save) password|submit)$', re.I))
        if submit is None or not profile.get('default_password'):
            return {"state": "account_pending", "reason": "The Workday password setup controls are ambiguous."}
        await guard_account_button(await submit.element_handle(), site)
        if not await claim(page, profile, 'set_password'):
            return {"state": "account_pending", "reason": "Workday password setup was already attempted."}
        for field in await passwords.all():
            await fill_password(field, profile['default_password'])
        await click(page, submit)
        if await page.locator('input[type=password]:visible').count():
            return {"state": "account_pending", "reason": "Workday has not confirmed the password change."}
        return {"state": "account_step_completed"}
    sign_in = scope.get_by_role("button", name=re.compile("^sign in$", re.I))
    email = scope.locator('input[type=email]:visible,input[autocomplete=username]:visible,'
                         'input[data-automation-id=email]:visible')
    if (profile.get("ats_auto_recover") and profile.get("default_password") and profile.get("email") and
            await passwords.count() == 1 and await sign_in.count() == 1):
        result = await workday_login_fallback(page, site, scope, profile, allow_create)
        if result["state"] != "registration_open":
            return result
    if await passwords.count() == 1 and await sign_in.count() == 1:
        if await email.count() != 1 or not all(profile.get(k) for k in ("email", "default_password")):
            raise RuntimeError("Workday needs a matching email field and local credentials. Set the email and password with ruin identity.")
        email_field, password_field = await email.element_handle(), await passwords.element_handle()
        native = scope.locator('button[data-automation-id=signInSubmitButton]:visible')
        button = await (native if await native.count() == 1 else sign_in).element_handle()
        await guard_account_button(button, site)
        await email_field.fill(profile["email"])
        await password_field.fill(profile["default_password"])
        await click(page, sign_in)
        missing = page.get_by_text(MISSING).first
        try:
            await page.wait_for_function("""pattern => {
                const visible = e => e.getClientRects().length > 0;
                return ![...document.querySelectorAll('input[type=password]')].some(visible) ||
                    new RegExp(pattern, 'im').test(document.body.innerText) ||
                    /account (does not exist|not found)|no account (found|exists)/i.test(document.body.innerText) ||
                    [...document.querySelectorAll('[role=alert]')].some(e=>visible(e) && e.innerText.trim());
            }""", arg=MISSING.pattern, timeout=10000)
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
        create = scope.get_by_role("link", name=SIGNUP).or_(scope.get_by_role("button", name=SIGNUP))
        await click(page, create)
        await passwords.nth(1).wait_for(timeout=5000)
    if await passwords.count() != 2 or origin_of(page.url) != origin_of(site):
        return False
    if not allow_create:
        raise RuntimeError("Workday returned to registration after the account step.")
    with mailbox_lock(PROFILE.parent):
        started = await submit_workday_registration(page, site, profile)
        if profile.get("ats_auto_recover") and INVALID.search(await page.locator('body').inner_text()):
            signin = await account_control(page, re.compile(r'^sign in$', re.I))
            if signin is not None:
                await click(page, signin)
                return await workday_account(page, page.url, profile, timeout=timeout, allow_create=False)
            return await request_reset(page, profile)
        prompt = page.get_by_text(re.compile(r"check your (?:inbox|email)|activation email|verify your email", re.I)).first
        code_field = page.locator(CODE_FIELD)
        await prompt.or_(code_field).first.wait_for(timeout=15000)
        mail = await page.context.new_page()
        try:
            async with asyncio.timeout(timeout):
                await mail.goto(OUTLOOK, wait_until="domcontentloaded")
                kind, value = await activation_message(mail, site, started, await load_rules(),
                                                       await code_field.count() == 1)
                if origin_of(page.url) != origin_of(site):
                    raise RuntimeError("The original Workday tab changed.")
                if kind == "link":
                    await mail.goto(value, wait_until="domcontentloaded")
                    confirmation = mail
                else:
                    await verify_email_code(page, site, value)
                    confirmation = page
                await confirmation.get_by_text(CONFIRMED).first.wait_for()
                if origin_of(confirmation.url) != origin_of(site) or origin_of(page.url) != origin_of(site):
                    raise RuntimeError("The Workday activation destination changed.")
                await page.goto(site, wait_until="domcontentloaded")
        except (TimeoutError, BrowserTimeout):
            raise RuntimeError("Workday activation was not confirmed. The original job is still open.") from None
        finally:
            await mail.close()
    return True
