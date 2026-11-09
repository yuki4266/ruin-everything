"""Watch existing and newly opened academic tabs on shared local Chrome."""
import asyncio
import sys

from filelock import FileLock, Timeout
from playwright.async_api import Error

from ruin.browser.academic import AcademicFlow, academic_step, host, WATCHED
from ruin.browser.context import browser_context
from ruin.config import PROFILE


async def listen(context, report=print):
    browser = context.browser
    flows = {}
    workers = {}
    stopped = asyncio.Event()
    browser.on("disconnected", stopped.set)

    async def inspect(page):
        flow = flows[page]
        if not flow.active() and not flow.checked_opener:
            opener = await page.opener()
            flow.checked_opener = True
            if opener in flows and flows[opener].active():
                flow.started()
        try:
            step = await academic_step(page, flow)
            if step:
                report(f"Institutional access: {step}.")
        except Error:
            # Frames can disappear between discovery and interaction.
            return
        except RuntimeError:
            report("Institutional action unavailable; observing the page.")

    def finish(page, task):
        workers.pop(page, None)
        if not task.cancelled() and task.exception():
            report("Could not inspect a page.")

    try:
        report("Watching shared Chrome for institutional access.")
        while browser.is_connected():
            pages = {page for ctx in browser.contexts for page in ctx.pages}
            for page in flows.keys() - pages:
                flows.pop(page)
            for page in pages:
                if page in workers:
                    continue
                if host(page.url) not in WATCHED:
                    flows.pop(page, None)
                    continue
                if page not in flows:
                    flows[page] = AcademicFlow()
                # Only the shared profile's locally configured Chrome login policy is used.
                page.context.ruin_trusted_oauth_clients = context.ruin_trusted_oauth_clients
                task = workers[page] = asyncio.create_task(inspect(page))
                task.add_done_callback(lambda finished, p=page: finish(p, finished))
            try:
                await asyncio.wait_for(stopped.wait(), timeout=0.5)
                break
            except TimeoutError:
                pass
    finally:
        browser.remove_listener("disconnected", stopped.set)
        pending = list(workers.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def watch(cdp=None):
    def report(message):
        print(message, file=sys.stderr, flush=True)

    PROFILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with FileLock(PROFILE.parent / "academic-watch.lock", timeout=0):
            offline = False
            while True:
                try:
                    async with browser_context(PROFILE, cdp, launch_if_missing=False) as context:
                        offline = False
                        await listen(context, report)
                except (OSError, RuntimeError, Error):
                    if not offline:
                        report("Waiting for shared Chrome.")
                    offline = True
                await asyncio.sleep(1)
    except Timeout:
        raise RuntimeError("An institutional access watcher is already running.") from None
