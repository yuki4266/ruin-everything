"""Resume an authorized application in place and journal official receipts."""

import asyncio
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from ruin.browser.driver import BrowserContext, Error, Page

from ruin.rules_loader import load_rules

ROOT = "https://jobs.ashbyhq.com"
JOURNAL = "ashby-receipts.sqlite3"
JOB_PATH = re.compile(
    r"/[\w.-]+/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}/application/?",
    re.ASCII,
)


def application_url(url: str) -> str:
    location = urlsplit(url)
    if (location.scheme != "https" or location.netloc != "jobs.ashbyhq.com"
            or not JOB_PATH.fullmatch(location.path)):
        raise ValueError("Use the original jobs.ashbyhq.com job application URL.")
    return ROOT + location.path.rstrip("/")


def recorded_receipt(db: sqlite3.Connection, site: str):
    row = db.execute("SELECT evidence FROM receipts WHERE site = ?", (site,)).fetchone()
    return json.loads(row[0]) if row else None


def lookup_receipt(url: str, directory: Path):
    site = application_url(url)
    journal = directory / JOURNAL
    if not journal.exists():
        return None
    with closing(sqlite3.connect(journal.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        # A concurrent writer may have created the file but not yet created the table.
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='receipts'").fetchone():
            return None
        return recorded_receipt(db, site)


async def observe(page: Page, site: str, rules):
    # Read the URL and receipt from one document snapshot. A navigation cannot
    # pair a different job's receipt with the requested application.
    return await page.evaluate("""([site, rules]) => {
        const visible = el => el && el.getClientRects().length > 0 &&
            getComputedStyle(el).visibility === 'visible';
        if (location.origin + location.pathname.replace(/\\/$/, '') !== site)
            return {state: 'changed_tab'};
        for (const region of document.querySelectorAll(rules.status)) {
            if (!visible(region)) continue;
            const heading = [...region.querySelectorAll(rules.heading)]
                .find(h => visible(h) && h.innerText.trim() === 'Success');
            const message = [...region.querySelectorAll(rules.message)].find(p =>
                visible(p) && /^Your application was successfully submitted[.!](?:\\s|$)/.test(p.innerText.trim()));
            if (heading && message) return {state: 'submitted', message: message.innerText.trim()};
        }
        const challenge = [...document.querySelectorAll('iframe')].some(frame => {
            if (!visible(frame)) return false;
            const url = new URL(frame.src || 'about:blank', location.href);
            return ['www.google.com','www.recaptcha.net','recaptcha.google.com'].includes(url.hostname)
                && /^\\/recaptcha\\/(?:api2|enterprise)\\/bframe$/.test(url.pathname);
        });
        return {state: challenge ? 'challenge_visible' : 'awaiting_receipt'};
    }""", [site, rules])


async def resume_ashby(context: BrowserContext, url: str, timeout: float, directory: Path,
                       on_event, on_challenge=None):
    """The caller owns authorization and any browser interaction with the challenge.

    on_challenge receives the original Playwright Page at most once per run.
    on_event receives status dictionaries. Only returned receipts count as submitted.
    """
    site = application_url(url)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(directory / JOURNAL)
    lock = None
    try:
        db.execute("CREATE TABLE IF NOT EXISTS receipts (site TEXT PRIMARY KEY, evidence TEXT NOT NULL)")
        previous = recorded_receipt(db, site)
        if previous:
            return previous
        if on_challenge:
            import fcntl
            job_id = urlsplit(site).path.split("/")[-2]
            lock = (directory / f"{job_id}.lock").open("a")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("This job already has an active verification driver.") from None
        pages = [page for page in context.pages if
                 page.url.split("?")[0].split("#")[0].rstrip("/") == site]
        if len(pages) != 1:
            raise RuntimeError("Exactly one original application tab must be open. No submission recorded.")
        rules = (await load_rules())["ashby"]
        page = pages[0]
        last = None
        handled = False
        async with asyncio.timeout(timeout):
            while not page.is_closed():
                try:
                    result = await observe(page, site, rules)
                except Error as exc:
                    if page.is_closed():
                        break
                    if "Execution context was destroyed" not in str(exc):
                        raise
                    await asyncio.sleep(0.25)
                    continue
                state = result["state"]
                if state == "submitted":
                    evidence = dict(result, site=site, observed_at=datetime.now(timezone.utc).isoformat())
                    with db:
                        db.execute("INSERT OR IGNORE INTO receipts VALUES (?, ?)", (site, json.dumps(evidence)))
                    return recorded_receipt(db, site)
                if state == "changed_tab":
                    raise RuntimeError("The original tab left the authorized job. No submission recorded.")
                if state != last:
                    on_event({"state": state, "site": site})
                    last = state
                if state == "challenge_visible" and on_challenge and not handled:
                    handled = True
                    await on_challenge(page)
                await asyncio.sleep(0.25)
        raise RuntimeError("The original application tab closed before a receipt was observed.")
    except TimeoutError:
        raise RuntimeError("No official receipt observed before timeout. Check the original tab.") from None
    finally:
        if lock is not None:
            lock.close()
        db.close()
