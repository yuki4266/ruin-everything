"""Local verification for an existing Greenhouse application in a CDP session."""

import asyncio
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import Page

OUTLOOK = "https://outlook.office.com/mail/"
MAIL_ROWS = '[role="option"][data-convid], [role="option"][data-itemid], [role="row"][data-convid]'
MAIL_BODY = '[aria-label="Message body"]:visible, [role="document"][aria-label*="Message"]:visible'
CODE_FIELD = (
    'input[autocomplete="one-time-code"]:visible, input[maxlength="1"]:visible, '
    'input[aria-label*="security code" i]:visible, input[name="security_code"]:visible, '
    'input[maxlength="8"]:visible, input[maxlength="6"]:visible'
)
PROMPT = re.compile(r"(?:security|verification) code", re.I)
EXPIRED = re.compile(r"(?:code.{0,30}expired|expired.{0,30}code)", re.I)
RESEND = re.compile(r"^(?:resend(?: (?:security |verification )?code)?|send (?:a )?new code)$", re.I)
RECEIPT = re.compile(r"(?:thank you for applying|your application has been (?:received|submitted))", re.I)


@contextmanager
def mailbox_lock(directory: Path):
    # Use one lock across employers because some senders reuse the same subject.
    import fcntl

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "outlook-verification.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another application is already waiting for Outlook.") from None
        yield


def job_key(url: str):
    parsed = urlsplit(url)
    if parsed.scheme == "https" and parsed.netloc in {
        "job-boards.greenhouse.io", "boards.greenhouse.io"
    }:
        if parsed.path.rstrip("/") == "/embed/job_app":
            query = parse_qs(parsed.query, keep_blank_values=True)
            employers, jobs = query.get("for", []), query.get("token", [])
            if (len(employers) == len(jobs) == 1 and
                    re.fullmatch(r"[A-Za-z0-9_-]+", employers[0]) and
                    re.fullmatch(r"[0-9]+", jobs[0])):
                return parsed.netloc, employers[0], jobs[0]
        match = re.fullmatch(r"/([\w-]+)/jobs/(\d+)/?", parsed.path)
        if match:
            return parsed.netloc, *match.groups()
    return None


def parse_code(body: str) -> str | None:
    # Require an explicit instruction followed by a standalone token. Ordinary
    # eight-letter words elsewhere in a message are not candidate codes.
    matches = re.findall(
        r"(?:code(?:\s+(?:is|below))?|code field on your application)"
        r"\s*:\s*([a-zA-Z0-9]{6,8})(?![a-zA-Z0-9])", body, re.I
    )
    return matches[0] if len(set(matches)) == 1 else None


async def rows(mail: Page):
    if urlsplit(mail.url).netloc not in {"outlook.office.com", "outlook.office365.com"}:
        raise RuntimeError("Sign in to Outlook in this Chrome profile before starting.")
    return await mail.locator(MAIL_ROWS).evaluate_all("""nodes => nodes.map(n => ({
        id: n.getAttribute('data-itemid') || n.getAttribute('data-convid'),
        label: n.getAttribute('aria-label') || n.innerText,
        received: Date.parse(n.querySelector('time[datetime]')?.dateTime ||
            Array.from(n.querySelectorAll('[title]')).map(el => el.title)
                .find(value => /[0-9]{4}/.test(value) && Number.isFinite(Date.parse(value))) || '') || 0
    }))""")


async def receive(mail: Page, seen: set, company: str, started: float, required_job=None):
    while True:
        current = await rows(mail)
        candidates = [r for r in current if (r["id"], r["received"]) not in seen and
                      r["received"] >= int(started * 1000) and
                      company.casefold() in r["label"].casefold() and PROMPT.search(r["label"])]
        if len(candidates) > 1:
            raise RuntimeError("Multiple matching messages appeared. The application is still open.")
        if candidates:
            item = candidates[0]
            target = mail.locator(MAIL_ROWS).nth(current.index(item))
            if item["id"] not in (await target.get_attribute("data-itemid"),
                                  await target.get_attribute("data-convid")):
                continue
            await target.click()
            body = mail.locator(MAIL_BODY)
            await body.wait_for(timeout=10000)
            # Outlook exposes the sender address in the opened message header.
            sender = mail.locator('[title="no-reply@us.greenhouse-mail.io" i], '
                                  '[aria-label*="<no-reply@us.greenhouse-mail.io>" i]')
            if not await sender.count() or not await sender.first.is_visible():
                raise RuntimeError("Could not verify the opened Greenhouse message sender.")
            body_text = await body.inner_text()
            if required_job and not re.search(r"(?<!\w)" + re.escape(required_job) + r"(?!\w)", body_text):
                raise RuntimeError("The existing message does not identify this job. "
                                   "Keep the original tab open; no code was entered.")
            code = parse_code(body_text)
            if not code:
                raise RuntimeError("The message has no unambiguous verification code.")
            return code
        await asyncio.sleep(1)


async def verify_application(context, url: str, company: str, timeout: int, directory: Path,
                             requested_at=None):
    key = job_key(url)
    if not key or not company.strip():
        raise ValueError("Supply an existing Greenhouse job URL and its employer name.")
    with mailbox_lock(directory):
        tabs = [page for page in context.pages if job_key(page.url) == key]
        if len(tabs) != 1:
            raise RuntimeError("Open exactly one tab for this Greenhouse job before starting.")
        app = tabs[0]
        group = app.get_by_role("group", name=re.compile("verification code was sent", re.I))
        prompt = app.get_by_text(PROMPT).first
        prompted = await group.is_visible() or (
            await prompt.is_visible() and await app.locator(CODE_FIELD).count() > 0
        )
        resend = app.get_by_role("button", name=RESEND).or_(app.get_by_role("link", name=RESEND))
        resume_existing = prompted and not await resend.count()
        if resume_existing and requested_at is None:
            raise RuntimeError("This form has no resend control. Supply --requested-at from the original "
                               "job's submission event, or complete verification in its tab.")
        if requested_at is not None and not 0 < requested_at <= time.time():
            raise ValueError("Use a past request timestamp from this application.")
        mail = await context.new_page()
        try:
            async with asyncio.timeout(timeout):
                await mail.goto(OUTLOOK, wait_until="domcontentloaded")
                await mail.locator(MAIL_ROWS).first.wait_for(timeout=15000)
                baseline = {(r["id"], r["received"]) for r in await rows(mail)}
                started = time.time()
                await app.bring_to_front()
                if job_key(app.url) != key:
                    raise RuntimeError("The original job tab changed.")
                if resume_existing:
                    started = requested_at
                    baseline.clear()
                if not prompted:
                    print("Outlook is ready. Waiting for the application verification prompt.", file=sys.stderr)
                    await prompt.wait_for(timeout=timeout * 1000)

                for attempt in range(2):
                    if job_key(app.url) != key:
                        raise RuntimeError("The original job tab changed.")
                    if attempt or (prompted and not resume_existing):
                        if not await resend.count():
                            raise RuntimeError("The code expired. The original form has no resend control.")
                        await mail.goto(OUTLOOK, wait_until="domcontentloaded")
                        await mail.locator(MAIL_ROWS).first.wait_for(timeout=10000)
                        baseline.update((r["id"], r["received"]) for r in await rows(mail))
                        started = time.time()
                        await resend.click(timeout=5000)
                    code = await receive(mail, baseline, company, started,
                                         required_job=key[2] if resume_existing and not attempt else None)
                    if job_key(app.url) != key:
                        raise RuntimeError("The original job tab changed.")
                    scoped = await group.is_visible()
                    fields = group.get_by_role("textbox") if scoped else app.locator(CODE_FIELD)
                    handles = await fields.element_handles()
                    if len(handles) == 1:
                        await handles[0].fill(code)
                    elif len(handles) == len(code) and (scoped or all(
                        [await h.get_attribute("maxlength") == "1" for h in handles]
                    )):
                        for handle, char in zip(handles, code):
                            await handle.fill(char)
                    else:
                        raise RuntimeError("Unrecognized code fields. The application is still open.")
                    if job_key(app.url) != key:
                        raise RuntimeError("The original job tab changed after filling.")
                    await app.get_by_role("button", name=re.compile(
                        r"^(?:submit(?: application)?|verify(?: code)?)$", re.I
                    )).click(timeout=5000)
                    receipt = app.get_by_text(RECEIPT).first
                    expired = app.get_by_text(EXPIRED).first
                    await receipt.or_(expired).first.wait_for(timeout=15000)
                    if await receipt.is_visible():
                        return
                    if (prompted and not resume_existing) or attempt:
                        break
                raise RuntimeError("Code expired after the resend. The application is still open.")
        finally:
            await mail.close()
