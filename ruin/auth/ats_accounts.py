"""Bounded account fallback for the selected iCIMS or Workday tenant."""

import hashlib
import re
import time
from urllib.parse import urlsplit
from playwright.async_api import Error, Locator

from ruin.browser.actions import click
from ruin.auth.vault import origin_of

INVALID = re.compile(r"wrong (?:username|email)(?: or| and) password|invalid credentials|"
                     r"(?:email|username|password).{0,40}(?:incorrect|invalid)|"
                     r"incorrect.{0,30}(?:email|username|password)|account.{0,25}(?:already exists|not found|does not exist)", re.I)
CREATE = re.compile(r"^(?:create (?:an? |my )?account|sign up|register|new user)$", re.I)
RESET = re.compile(r"^(?:forgot (?:your )?password\??|reset (?:your )?password)$", re.I)
SENT = re.compile(r"check your (?:email|inbox)|(?:email|link|instructions).{0,60}(?:sent|on its way)|"
                  r"sent.{0,60}(?:email|link|instructions)", re.I)


async def claim(page, profile, step):
    """Persist retry limits across CLI reconnects, scoped to tenant and identity."""
    tenant = origin_of(page.url)
    if urlsplit(page.url).hostname == "login.icims.com":
        tenant += ":" + await page.title()
        reset = page.locator('a[href*="password-reset-start"]')
        if await reset.count() == 1:
            match = re.search(r'/password-reset-start/([^/]+)', await reset.get_attribute('href'))
            if match:
                tenant += ":" + match[1]
    key = "ruin:ats:" + hashlib.sha256((tenant + ":" + profile["email"]).encode()).hexdigest()
    return await page.evaluate("""({key,step,now})=>{
        let state;try{state=JSON.parse(sessionStorage.getItem(key)||'{}')}catch{state={}}
        if(!state.started || now-state.started>900)state={started:now};
        if(state[step])return false;
        state[step]=true;sessionStorage.setItem(key,JSON.stringify(state));return true;
    }""", {"key": key, "step": step, "now": time.time()})


async def account_control(scope, pattern):
    target = scope.get_by_role("button", name=pattern).or_(scope.get_by_role("link", name=pattern)).filter(visible=True)
    return target if await target.count() == 1 else None


async def icims_scope(page):
    outer = page.locator('#icims_content_iframe:visible')
    if await outer.count() == 1:
        handle = await outer.element_handle()
        try:
            frame = await handle.content_frame()
            host = urlsplit(frame.url).hostname if frame else ''
            if host and host.endswith('.icims.com'):
                return frame
        finally:
            await handle.dispose()
    return page


async def guarded_submit(page, target):
    """Credentials go only to the current HTTPS origin through the executor."""
    allowed = await target.evaluate("""b=>{
        const f=b.form || b.closest('form');
        if(!f || location.protocol!=='https:')return false;
        const action=new URL(f.getAttribute('action')||location.href,location.href);
        const override=new URL(b.getAttribute('formaction')||action.href,location.href);
        return action.origin===location.origin && override.origin===location.origin &&
            (b.getAttribute('formmethod')||f.method).toLowerCase()==='post';
    }""")
    if not allowed:
        raise RuntimeError("The ATS credential form must submit to the same HTTPS origin using POST.")
    await page.bring_to_front()
    return await click(page, target, timeout=15000)


async def fill_password(field, secret):
    try:
        await field.fill(secret, timeout=5000)
    except Error:
        raise RuntimeError("The ATS password field could not be filled.") from None


async def request_reset(page, profile, scope=None):
    scope = scope or page
    reset = await account_control(scope, RESET)
    if reset is None:
        return {"state": "account_pending", "reason": "No unique password reset control is visible."}
    if not await claim(page, profile, "reset_requested"):
        return {"state": "email_verification_pending", "reason": "Password recovery was already requested in this session."}
    await click(page, reset)
    for _ in range(3):
        if (urlsplit(page.url).hostname or '').endswith('.icims.com'):
            scope = await icims_scope(page)
        else:
            dialogs = page.locator('[role=dialog]:visible')
            scope = dialogs if await dialogs.count() == 1 else page
        text = await scope.inner_text() if isinstance(scope, Locator) else await scope.locator('body').inner_text()
        if SENT.search(text):
            return {"state": "reset_email_requested"}
        if await scope.locator('input[type=password]:visible').count():
            return {"state": "account_pending", "reason": "The reset flow still requires account verification."}
        email = scope.locator('input[type=email]:visible,input[autocomplete=username]:visible')
        if await email.count() == 1:
            await email.fill(profile["email"])
        send = await account_control(scope, re.compile(r"^(?:continue|submit|send(?: (?:reset |password reset )?(?:email|link|instructions))?|reset password)$", re.I))
        if send is None:
            break
        # Workday uses a JavaScript dialog; retain its existing form guard.
        if '.myworkdayjobs.com' in urlsplit(page.url).netloc:
            from .workday import guard_account_button
            await guard_account_button(await send.element_handle(), page.url)
            await click(page, send)
        else:
            await guarded_submit(page, send)
        if SENT.search(await page.locator('body').inner_text()):
            return {"state": "reset_email_requested"}
        break
    return {"state": "email_verification_pending", "reason": "Password recovery needs verification in the original tab."}


async def icims_account(page, site, profile):
    """Continue only observed login, registration or recovery controls."""
    host = urlsplit(site).hostname or ""
    if (page.url != site or not (host == 'login.icims.com' or host.endswith('.icims.com')) or
            not profile.get('ats_auto_recover') or not profile.get('email') or not profile.get('ats_default_password')):
        return None
    start_origin = origin_of(site)
    secret = profile['ats_default_password']
    for _ in range(8):
        if origin_of(page.url) != start_origin:
            return {"state": "account_step_completed"}
        scope = await icims_scope(page)
        body = await scope.locator('body').inner_text()
        if SENT.search(body) and re.search(r'password|reset|verify', body, re.I):
            return {"state": "email_verification_pending"}
        if await scope.locator('input[autocomplete=one-time-code]:visible').count():
            return {"state": "email_verification_pending"}
        fields = scope.locator('input[type=password]:visible')
        count = await fields.count()
        email = scope.locator('input[type=email]:visible,input[autocomplete=username]:visible')
        usernames = scope.locator('input[autocomplete=username]')
        if count and await email.count() == 0 and await usernames.count() == 1:
            if (await usernames.input_value()).casefold() != profile['email'].casefold():
                return {"state": "account_pending", "reason": "The login identity differs from the local ATS profile."}
        if not count:
            proceed = await account_control(scope, re.compile('^(?:continue|next)$', re.I))
            if await email.count() != 1 or proceed is None:
                return {"state": "account_step_completed"} if '/u/' not in urlsplit(page.url).path else None
            await email.fill(profile['email'])
            if not await claim(page, profile, 'identifier'):
                return {"state": "account_pending", "reason": "The identifier step did not advance."}
            await guarded_submit(page, proceed)
            continue
        headings = ' '.join(await scope.locator('h1,h2,[role=heading]').all_inner_texts())
        new_password = (count == 2 or await fields.first.get_attribute('autocomplete') == 'new-password' or
                        re.search(r'(?:create|set|choose|reset) (?:a |your |new )?password', headings, re.I))
        if new_password and re.search(r'account.{0,30}already exists|email.{0,30}already (?:registered|in use)', body, re.I):
            signin = await account_control(scope, re.compile(r'^(?:log in|sign in)$', re.I))
            if signin is not None and await claim(page, profile, 'existing_account'):
                await click(page, signin)
                continue
            return await request_reset(page, profile, scope)
        if new_password:
            submit = await account_control(scope, re.compile(r'^(?:create (?:an? )?account|sign up|register|continue|submit|save|(?:set|reset|change) password)$', re.I))
            if submit is None or count > 2:
                return {"state": "account_pending", "reason": "The password setup controls are ambiguous."}
            if await email.count() == 1:
                await email.fill(profile['email'])
            for field in await fields.all():
                await fill_password(field, secret)
            for box in await scope.locator('input[type=checkbox]:visible').all():
                label = await box.evaluate("e=>[...(e.labels||[])].map(l=>l.innerText).join(' ')")
                if re.search(r'terms (?:of|and)|privacy policy', label, re.I):
                    await box.check()
            if not await claim(page, profile, 'set_password'):
                return {"state": "account_pending", "reason": "Password setup did not advance."}
            await guarded_submit(page, submit)
            continue
        if INVALID.search(body):
            create = await account_control(scope, CREATE)
            if create is not None and await claim(page, profile, 'open_registration'):
                await click(page, create)
                continue
        login = await account_control(scope, re.compile(r'^(?:log in|sign in|continue)$', re.I))
        if login is None:
            return {"state": "account_pending", "reason": "No unique login control is visible."}
        if await email.count() == 1:
            await email.fill(profile['email'])
        saved = await fields.first.input_value()
        if saved and saved != secret and not INVALID.search(body) and await claim(page, profile, 'saved_login'):
            await guarded_submit(page, login)
            continue
        if await claim(page, profile, 'default_login'):
            await fill_password(fields.first, secret)
            await guarded_submit(page, login)
            continue
        if INVALID.search(body):
            return await request_reset(page, profile, scope)
        return {"state": "account_pending", "reason": "Login has not confirmed success; no credential retry was repeated."}
    return {"state": "account_pending", "reason": "The account flow reached its bounded step limit."}


async def workday_login_fallback(page, site, scope, profile, allow_create):
    from .workday import guard_account_button

    for _ in range(3):
        if origin_of(page.url) != origin_of(site):
            return {"state": "account_pending", "reason": "Workday left the selected tenant."}
        body = await page.locator('body').inner_text()
        passwords = scope.locator('input[type=password]:visible')
        if not await passwords.count():
            return {"state": "account_step_completed"}
        if INVALID.search(body) and allow_create:
            create = await account_control(scope, CREATE)
            if create is not None and await claim(page, profile, 'open_registration'):
                await click(page, create)
                await scope.locator('input[type=password]:visible').nth(1).wait_for(timeout=5000)
                return {"state": "registration_open"}
        email = scope.locator('input[type=email]:visible,input[autocomplete=username]:visible,input[data-automation-id=email]:visible')
        login = await account_control(scope, re.compile('^sign in$', re.I))
        if await passwords.count() != 1 or await email.count() != 1 or login is None:
            return {"state": "account_pending", "reason": "Workday login controls changed."}
        await guard_account_button(await login.element_handle(), site)
        await email.fill(profile['email'])
        saved = await passwords.input_value()
        secret = profile['default_password']
        if saved and saved != secret and not INVALID.search(body) and await claim(page, profile, 'saved_login'):
            await click(page, login)
            continue
        if await claim(page, profile, 'default_login'):
            await fill_password(passwords, secret)
            await click(page, login)
            continue
        if INVALID.search(body):
            return await request_reset(page, profile, scope)
        return {"state": "account_pending", "reason": "Workday did not confirm sign-in."}
    return {"state": "account_pending", "reason": "Workday reached its bounded login limit."}


async def resume_ats_account(page):
    """Opted-in continuation shared by action and general browser entry points."""
    from .auto_registrar import identity
    from .workday import TENANT, workday_account

    host = urlsplit(page.url).hostname or ''
    if host != 'login.icims.com' and not host.endswith('.icims.com') and not TENANT.fullmatch(host):
        return None
    profile = identity()
    if not profile.get('ats_auto_recover'):
        return None
    result = await icims_account(page, page.url, profile)
    if result is None and TENANT.fullmatch(host):
        result = await workday_account(page, page.url, profile)
    if result:
        return result if isinstance(result, dict) else {"state": "account_step_completed"}
    return None
