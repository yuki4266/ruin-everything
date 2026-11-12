"""General browser operations in the existing local Chrome context."""

import asyncio
import mimetypes
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from ruin.browser.driver import Error

from ruin.browser.actions import click
from ruin.auth.saved_login import resume_saved_login
from .background import new_agent_page, prepare_page, remember_page, tab_marker

Operation = Literal["tabs", "navigate", "inspect", "read", "click", "fill", "press", "select", "upload", "set_files"]


async def resume_login(page):
    from ruin.auth.ats_accounts import resume_ats_account
    from ruin.auth.vault_login import resume_vault_login
    return await resume_vault_login(page) or await resume_saved_login(page) or await resume_ats_account(page)


async def page_state(page):
    """Describe visible controls without reading input values or serialized form HTML."""
    await prepare_page(page)
    text = await page.locator("body").inner_text(timeout=5000)
    controls = await page.locator('body :is(a,button,input,select,textarea,[role])').evaluate_all('''elements =>
        elements.flatMap((e, i) => {
            if (!e.checkVisibility({visibilityProperty: true, opacityProperty: true})) return [];
            const label = e.getAttribute('aria-label') || [...(e.labels || [])].map(l => l.innerText).join(' ') ||
                (e.matches('input,textarea,select') ? '' : e.innerText) || '';
            return [{tag: e.tagName.toLowerCase(), type: e.getAttribute('type'),
                role: e.getAttribute('role'), label: label.trim().slice(0, 160),
                selector: `body :is(a,button,input,select,textarea,[role]) >> nth=${i}`,
                disabled: !!e.disabled, href: e.matches('a') ? e.href : null}];
        })''')
    return {"url": page.url, "title": await page.title(), "text": text[:24000],
            "controls": controls[:300], "truncated": len(text) > 24000 or len(controls) > 300}


def web_url(url):
    parsed = urlsplit(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Navigation requires an HTTP or HTTPS URL without embedded credentials.")
    return url


def exact_page(context, site):
    pages = [page for page in context.pages if page.url == site]
    if len(pages) != 1:
        raise RuntimeError("Select one unique current URL from the tabs operation.")
    return pages[0]


async def upload_file(page, site, selector, file_path):
    if not file_path:
        raise ValueError("Upload requires an absolute file_path.")
    path = Path(file_path)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("file_path must be an absolute path to an existing regular file.")

    targets = []
    for frame in page.frames:
        locator = frame.locator(selector or 'input[type="file"]')
        count = await locator.count()
        if count > 1 or (count and targets):
            raise ValueError("Multiple upload targets matched. Specify a unique selector.")
        if count:
            targets.append(locator)
    if not targets:
        raise ValueError("No upload target matched in the selected page or its frames.")
    target = targets[0]
    is_input = await target.evaluate("e => e.matches('input[type=file]')")
    if page.url != site:
        raise RuntimeError("The selected tab changed before the upload.")

    if is_input:
        if await target.is_disabled():
            raise ValueError("The file input is disabled.")
        try:
            await target.set_input_files(path, timeout=5000)
        except Error as exc:
            # Older CDP backends may lack the path-based method entirely.
            message = str(exc)
            if "DOM.setFileInputFiles" not in message or "wasn't found" not in message:
                raise
            await target.set_input_files({
                "name": path.name,
                "mimeType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "buffer": await asyncio.to_thread(path.read_bytes),
            }, timeout=5000)
        state = "file_selected"
    else:
        await target.drop({"files": [path]}, timeout=5000)
        state = "drop_dispatched"
    return {"url": page.url, "filename": path.name, "state": state}


async def browser_operation(context, operation: Operation, *, site=None, url=None, selector=None, value=None, file_path=None):
    result = await _browser_operation(context, operation, site=site, url=url, selector=selector, value=value, file_path=file_path)
    pages = [p for p in context.pages if p.url == result.get("url")]
    if len(pages) == 1:
        await remember_page(pages[0], previous_url=site if operation != "navigate" else None)
    return result


async def _browser_operation(context, operation: Operation, *, site=None, url=None, selector=None, value=None, file_path=None):
    """Keep tabs open across calls; use the same context for every destination."""
    if operation == "tabs":
        return {"tabs": [{"url": p.url, "title": await p.title(), **await tab_marker(p)} for p in context.pages]}
    if operation in {"upload", "set_files"}:
        page = exact_page(context, site)
        await prepare_page(page)
        return await upload_file(page, site, selector, file_path)
    if operation == "navigate":
        web_url(url)
        if site:
            page = exact_page(context, site)
        else:
            existing = [p for p in context.pages if p.url == url]
            if existing:
                page = exact_page(context, url)
            else:
                page = await new_agent_page(context, purpose="browser", reuse=True)
        await prepare_page(page)
        if page.url != url:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    else:
        if operation not in {"inspect", "read", "click", "fill", "press", "select"}:
            raise ValueError("Unknown browser operation.")
        page = exact_page(context, site)
        await prepare_page(page)
        if operation in {"click", "fill", "press", "select"} and not selector:
            raise ValueError("This operation requires a Playwright selector for one visible element.")
        if operation in {"fill", "press", "select"} and value is None:
            raise ValueError("This operation requires a value.")
        target = page.locator(selector or "body")
        if operation in {"click", "fill", "press", "select"}:
            target = target.filter(visible=True)
            if await target.count() != 1:
                raise RuntimeError("The selector must match exactly one visible element.")
        if operation == "click" or (operation == "press" and value == "Enter"):
            result = await click(page, target, enter=operation == "press")
            auth = await resume_login(page)
            return {"url": page.url, "title": await page.title(), "action": asdict(result),
                    **({"authentication": auth} if auth else {})}
        if operation == "fill":
            await target.fill(value, timeout=5000)
        elif operation == "press":
            await target.press(value, timeout=5000)
        elif operation == "select":
            await target.select_option(value, timeout=5000)
        elif operation == "read":
            auth = await resume_login(page)
            if auth and (auth["state"] == "redirected" or page.url != site):
                return {**await page_state(page), "authentication": auth}
            text = await target.inner_text(timeout=5000)
            return {"url": page.url, "title": await page.title(), "text": text[:24000], "truncated": len(text) > 24000,
                    **({"authentication": auth} if auth else {})}
    auth = await resume_login(page)
    return {**await page_state(page), **({"authentication": auth} if auth else {})}
