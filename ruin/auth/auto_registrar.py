"""Local signup for an explicit registration form on the selected site."""

import asyncio
import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

from ruin.browser.actions import click
from .vault import origin_of


def identity():
    from .ats_config import settings

    path = Path.home() / ".ruin/identity.json"
    if not path.exists():
        return settings()
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Set identity.json permissions to 0600 before using signup.")
    profile = json.loads(path.read_text())
    if not isinstance(profile, dict):
        raise ValueError("identity.json must contain an object.")
    return {**profile, **settings()}


SIGNUP = re.compile(r"^(create (an? |my )?account|sign up|register)$", re.I)
FIELDS = {
    "email": 'input[type=email],input[autocomplete=email],input[name=email i]',
    "first_name": 'input[autocomplete=given-name],input[name=firstName i],input[name=first_name]',
    "last_name": 'input[autocomplete=family-name],input[name=lastName i],input[name=last_name]',
    "phone": 'input[type=tel],input[autocomplete=tel],input[name=phone i]',
    "default_password": 'input[type=password]',
}


async def fill_contact_phone(page, url, profile):
    phone = profile.get("phone")
    if profile.get("auto_signup") is not True or not isinstance(phone, str) or not phone.strip():
        return
    inputs = await page.locator(FIELDS["phone"]).element_handles()
    visible = [field for field in inputs if await field.is_visible() and await field.is_editable()]
    if len(visible) != 1:
        return
    field = visible[0]
    eligible = await field.evaluate("""(el, origin) => location.origin === origin &&
        el.form && new URL(el.form.action).origin === origin && !el.value""", origin_of(url))
    if eligible:
        await field.fill(phone)
        return True
    return False


async def signup(page, url, profile):
    """Return the request timestamp once a single registration control is clicked."""
    if profile.get("auto_signup") is not True or origin_of(page.url) != origin_of(url):
        return None
    buttons = [button for button in await page.get_by_role("button", name=SIGNUP).element_handles()
               if await button.is_visible()]
    if len(buttons) != 1:
        return None
    button = buttons[0]
    eligible = """(b, origin) => b.isConnected && location.origin === origin &&
        b.type === 'submit' && b.form && (b.getAttribute('formmethod') || b.form.method).toLowerCase() === 'post' &&
        new URL(b.formAction || b.form.action).origin === origin &&
        new URL(b.form.action).origin === origin &&
        !b.form.querySelector('[autocomplete="current-password"]')"""
    if not await button.evaluate(eligible, origin_of(url)):
        return None
    form = await button.evaluate_handle("b => b.form")
    form = form.as_element()
    fields = []
    for key, selector in FIELDS.items():
        for field in await form.query_selector_all(selector):
            if not await field.is_visible() or not await field.is_editable():
                continue
            value = profile.get(key)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"Complete {key} in the local identity profile.")
            fields.append((field, value))
    if not fields:
        return None
    for field, value in fields:
        await field.fill(value)
    for box in await form.query_selector_all('input[type=checkbox]'):
        label = await box.evaluate("b => Array.from(b.labels, l => l.innerText).join(' ')")
        if re.search(r'\b(terms of (service|use)|privacy policy)\b', label, re.I) and await box.is_visible():
            await box.check()
    if not await button.evaluate(eligible, origin_of(url)) or not await form.evaluate("f => f.checkValidity()"):
        raise RuntimeError("The registration form needs attention in the open tab.")
    requested = time.time()
    await click(page, button)
    return requested


def sms_code(database, host, requested, sender=None):
    """Read a fresh domain-bound SMS using the @host #code format."""
    since = int((requested - 978307200) * 1_000_000_000)
    pattern = re.compile(r"(?:^|\n)@" + re.escape(host) + r" #(\d{4,8})\s*$", re.I)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("""SELECT text FROM message WHERE is_from_me=0 AND date >= ?
                             AND text IS NOT NULL ORDER BY date DESC LIMIT 100""", (since,))
        for (body,) in rows:
            match = pattern.search(body)
            if match:
                return match[1]
        if sender:
            row = db.execute("""SELECT message.text FROM message JOIN handle ON handle.ROWID=message.handle_id
                                WHERE handle.id=? AND message.is_from_me=0 AND message.date>=?
                                ORDER BY message.date DESC LIMIT 1""", (sender, since)).fetchone()
            if row and row[0] and re.search(r"\b(?:code|OTP)\b", row[0], re.I):
                digits = re.findall(r"(?<!\d)\d{6}(?!\d)", row[0])
                if len(digits) == 1 and not re.search(r"(?:^|\n)@\S+", row[0]):
                    return digits[0]
    return None


async def verify_sms(page, url, requested):
    field = page.locator('input[autocomplete=one-time-code]:visible')
    if await field.count() != 1:
        return False
    handle = await field.element_handle()
    database = Path.home() / "Library/Messages/chat.db"
    host = urlsplit(url).hostname
    senders = identity().get("sms_senders", {})
    if not isinstance(senders, dict) or not all(isinstance(v, str) for v in senders.values()):
        raise ValueError("sms_senders must map exact hostnames to sender strings.")
    sender = senders.get(host)
    if sender and list(senders.values()).count(sender) != 1:
        raise ValueError("A plain-code SMS sender must identify exactly one configured host.")
    for _ in range(30):
        if origin_of(page.url) != origin_of(url):
            raise RuntimeError("The verification page changed.")
        try:
            code = await asyncio.to_thread(sms_code, database, host, requested, sender)
        except sqlite3.Error:
            raise RuntimeError("Messages is unavailable. Complete verification in the open tab.") from None
        if code:
            await handle.fill(code)
            return True
        await asyncio.sleep(1)
    raise RuntimeError("No matching SMS arrived. Complete verification in the open tab.")
