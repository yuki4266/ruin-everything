"""Background input and owned tabs without activating Chrome or a user tab."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from filelock import FileLock
from playwright.async_api import Error

BACKGROUND_FLAGS = (
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
)


async def prepare_page(page):
    """Keep the task renderer active; never request OS or tab activation."""
    if page.is_closed():
        return
    lock = getattr(page, "_ruin_background_lock", None)
    if lock is None:
        lock = page._ruin_background_lock = asyncio.Lock()
    async with lock:
        session = getattr(page, "_ruin_background_session", None)
        if session is None:
            session = await page.context.new_cdp_session(page)
            page._ruin_background_session = session
        try:
            await session.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
            await session.send("Page.setWebLifecycleState", {"state": "active"})
            from .compatibility import prepare_compatibility
            await prepare_compatibility(page, session)
        except Error:
            if page.is_closed():
                return
            raise RuntimeError("Chrome could not enable background page emulation; no foreground fallback was used.") from None


async def target_info(page):
    session = getattr(page, "_ruin_background_session", None)
    temporary = session is None
    if temporary:
        session = await page.context.new_cdp_session(page)
    try:
        return (await session.send("Target.getTargetInfo"))["targetInfo"]
    finally:
        if temporary:
            await session.detach()


def url_hash(url):
    return hashlib.sha256(url.encode()).hexdigest()


class AgentTabs:
    """Only runtime-created target IDs are owned; URLs are stored as hashes."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.memory = {}

    def read(self):
        if self.path is None:
            return dict(self.memory)
        if not self.path.exists():
            return {}
        if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise RuntimeError("The agent-tab registry must be a private regular file (mode 0600).")
        try:
            records = json.loads(self.path.read_text())
        except (ValueError, OSError):
            raise RuntimeError("The agent-tab registry is unreadable; no user tab was claimed.") from None
        if not isinstance(records, dict) or any(
            not isinstance(v, dict) or not isinstance(v.get("purpose"), str) or
            not isinstance(v.get("url_hash"), str) for v in records.values()
        ):
            raise RuntimeError("The agent-tab registry is invalid; no user tab was claimed.")
        return records

    def put(self, target, purpose, url):
        record = {"purpose": purpose, "url_hash": url_hash(url)}
        if self.path is None:
            self.memory[target] = record
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with FileLock(str(self.path) + ".lock", timeout=5):
            records = self.read()
            records[target] = record
            with NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                try:
                    json.dump(records, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                    os.replace(temporary, self.path)
                finally:
                    temporary.unlink(missing_ok=True)


def registry(context):
    value = getattr(context, "ruin_agent_tabs", None)
    if value is None:
        value = context.ruin_agent_tabs = AgentTabs()
    return value


async def tab_marker(page):
    info = await target_info(page)
    record = registry(page.context).read().get(info["targetId"])
    return {"agent_owned": bool(record), **({"purpose": record["purpose"]} if record else {})}


async def remember_page(page, *, previous_url=None):
    """Update only a known owned target after an authorized runtime operation."""
    if page.is_closed():
        return
    info = await target_info(page)
    records = registry(page.context)
    record = records.read().get(info["targetId"])
    if record and (previous_url is None or record["url_hash"] == url_hash(previous_url)):
        records.put(info["targetId"], record["purpose"], page.url)


async def new_agent_page(context, *, purpose="browser", reuse=False):
    records = registry(context)
    owned = records.read()
    infos = {}
    for page in context.pages:
        if not page.is_closed():
            info = await target_info(page)
            infos[info["targetId"]] = (page, info)
    if reuse:
        for target, record in owned.items():
            if record["purpose"] == purpose and target in infos:
                page, _ = infos[target]
                # A manual navigation relinquishes reuse; never overwrite it.
                if record["url_hash"] == url_hash(page.url):
                    await prepare_page(page)
                    return page
    browser = context.browser
    if browser is None:
        raise RuntimeError("Background tabs require a Chromium CDP browser connection.")
    session = await browser.new_browser_cdp_session()
    try:
        params = {"url": "about:blank", "background": True}
        if infos:
            context_id = next(iter(infos.values()))[1].get("browserContextId")
            if context_id:
                params["browserContextId"] = context_id
        else:
            ids = (await session.send("Target.getBrowserContexts"))["browserContextIds"]
            if len(ids) == 1 and len(browser.contexts) == 1:
                params["browserContextId"] = ids[0]
            elif ids:
                raise RuntimeError("Select a context with an existing tab before creating a background agent tab.")
        target = (await session.send("Target.createTarget", params))["targetId"]
    finally:
        await session.detach()
    deadline = asyncio.get_running_loop().time() + 10
    while asyncio.get_running_loop().time() < deadline:
        for page in context.pages:
            if not page.is_closed() and page not in [item[0] for item in infos.values()]:
                info = await target_info(page)
                if info["targetId"] == target:
                    await prepare_page(page)
                    records.put(target, purpose, page.url)
                    return page
        await asyncio.sleep(0.05)
    raise RuntimeError("Chrome created an agent target but did not expose its page; no foreground fallback was used.")
