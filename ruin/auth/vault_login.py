"""Bounded vault login on the selected task tab through the Ruin executor."""
import asyncio
import hashlib
import re
import time

from playwright.async_api import Error

from .local_vault import ROOT, LocalVault, PrivateJSON, hostname

LOGIN = re.compile(r'^(log\s*in|sign\s*in|login|continue|登录|登入)$', re.I)


async def resume_vault_login(page, root=ROOT):
    from ruin.browser.actions import click
    vault = LocalVault(root)
    for frame in page.frames:
        before = frame.url
        if not hostname(before):
            continue
        password = frame.locator('input[type=password]:visible')
        if await password.count() != 1:
            continue
        eligible = await password.evaluate('''e => !e.disabled && !e.readOnly &&
            e.autocomplete !== 'new-password' && (!e.form ||
                new URL(e.form.action || location.href).origin === location.origin)''')
        if not eligible:
            continue
        saved = vault.lookup(before)
        if not saved or not saved.get('password'):
            continue
        scope = password.locator('xpath=ancestor::form[1]')
        if not await scope.count():
            scope = frame.locator('body')
        button = scope.get_by_role('button', name=LOGIN).filter(visible=True)
        if await button.count() != 1 or not await button.is_enabled():
            continue
        if not await button.evaluate('''b => !b.form ||
            new URL(b.getAttribute('formaction') || b.form.action || location.href, location.href).origin === location.origin'''):
            continue
        users = scope.locator('input[autocomplete=username]:visible, input[type=email]:visible')
        if await users.count() != 1:
            users = scope.locator('input:not([type]):visible, input[type=text]:visible').filter(
                visible=True)
        if saved.get('username') and await users.count() != 1:
            continue
        # Preserve a user-entered draft instead of substituting a different account.
        if await password.input_value() not in ('', saved['password']):
            continue
        if await users.count() == 1 and await users.evaluate('e => !!e.value') and await users.input_value() != saved['username']:
            continue
        stamp = hashlib.sha256((hostname(before) + '\0' + saved['username'] + '\0' + saved['password']).encode()).hexdigest()
        claimed = False
        def claim(data):
            nonlocal claimed
            if time.time() - data.get(stamp, 0) >= 900:
                data[stamp] = time.time()
                claimed = True
        PrivateJSON(root / 'vault_attempts.json').update(claim)
        if not claimed:
            return {'state': 'vault_retry_limited'}
        if frame.url != before:
            continue
        handles = []
        try:
            # Bind to this document's elements. Locators could otherwise resolve
            # on a different origin if navigation races a fill operation.
            secret_field = await password.element_handle()
            login_button = await button.element_handle()
            user_field = await users.element_handle() if await users.count() == 1 else None
            handles = [h for h in [secret_field, login_button, user_field] if h]
            if frame.url != before or not secret_field or not login_button:
                return None
            if await users.count() == 1 and saved.get('username'):
                await user_field.fill(saved['username'])
            await secret_field.fill(saved['password'])
            if frame.url != before:
                return None
            await click(page, login_button)
        except (Error, RuntimeError):
            # Playwright exception call logs can contain fill values.
            return {'state': 'vault_login_pending'}
        finally:
            for handle in handles:
                try:
                    await handle.dispose()
                except Error:
                    pass
        return {'state': 'redirected' if frame.is_detached() or frame.url != before else 'vault_login_attempted'}
    return None


async def wait_for_manual_login(page, timeout=180):
    """Keep an active task alive while the independent listener captures a login."""
    async def has_login():
        for frame in page.frames:
            try:
                if await frame.locator('input[type=password]:visible, input[autocomplete=one-time-code]:visible').count():
                    return True
            except Error:
                continue
        return False
    if not await has_login():
        return False
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.is_closed():
            break
        if not await has_login():
            await page.wait_for_load_state('domcontentloaded')
            return True
        await asyncio.sleep(0.5)
    raise RuntimeError('Login is still pending in the original tab; captured credentials remain local.')


async def has_password_login(page):
    for frame in page.frames:
        try:
            fields = frame.locator('input[type=password]:visible')
            if await fields.count() == 1 and await frame.get_by_role('button', name=LOGIN).filter(visible=True).count() == 1:
                if await fields.get_attribute('autocomplete') != 'new-password':
                    return True
        except Error:
            continue
    return False
