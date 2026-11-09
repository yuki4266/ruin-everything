"""General browser operations in the existing local Chrome context."""

from dataclasses import asdict
from typing import Literal
from urllib.parse import urlsplit

from ruin.browser.actions import click

Operation = Literal["tabs", "navigate", "inspect", "read", "click", "fill", "press", "select"]
BLANK = {"about:blank", "chrome://newtab/", "chrome://newtab", "chrome://new-tab-page/"}


async def page_state(page):
    """Describe visible controls without reading input values or serialized form HTML."""
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


async def browser_operation(context, operation: Operation, *, site=None, url=None, selector=None, value=None):
    """Keep tabs open across calls; use the same context for every destination."""
    if operation == "tabs":
        return {"tabs": [{"url": p.url, "title": await p.title()} for p in context.pages]}
    if operation == "navigate":
        web_url(url)
        if site:
            page = exact_page(context, site)
        else:
            existing = [p for p in context.pages if p.url == url]
            blank = [p for p in context.pages if p.url in BLANK]
            if existing:
                page = exact_page(context, url)
            else:
                page = blank[0] if len(blank) == 1 else await context.new_page()
        if page.url != url:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    else:
        if operation not in {"inspect", "read", "click", "fill", "press", "select"}:
            raise ValueError("Unknown browser operation.")
        page = exact_page(context, site)
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
            return {"url": page.url, "title": await page.title(), "action": asdict(result)}
        if operation == "fill":
            await target.fill(value, timeout=5000)
        elif operation == "press":
            await target.press(value, timeout=5000)
        elif operation == "select":
            await target.select_option(value, timeout=5000)
        elif operation == "read":
            text = await target.inner_text(timeout=5000)
            return {"url": page.url, "title": await page.title(), "text": text[:24000], "truncated": len(text) > 24000}
    return await page_state(page)
