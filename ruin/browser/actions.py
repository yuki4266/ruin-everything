"""Execute one authorized action on its original tab and settle any visual challenge."""

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Literal

from filelock import FileLock
from filelock import Timeout as LockBusy
from ruin.browser.driver import Error

from ruin.auth.vault import origin_of
from ruin.config import PROFILE

from .puzzles import detect, solve
from .background import prepare_page


@dataclass
class ActionResult:
    state: Literal["no_challenge", "navigated", "challenge_cleared", "challenge_pending"]
    kind: str | None = None
    attempts: int = 0
    reason: str | None = None
    authentication: dict | None = None


async def settle(page, site):
    """Resume a pending action. Only the widget itself may be retried."""
    from .turnstile import settle_turnstile
    if not page.is_closed() and page.url == site:
        turnstile = await settle_turnstile(page, site)
        if turnstile is not None:
            return ActionResult(**turnstile)
    kind = None
    attempts = 0
    reason = None
    previous_source = None
    for attempt in range(1, 4):
        if page.is_closed() or page.url != site:
            return ActionResult("navigated", kind, attempts)
        async with AsyncExitStack() as handles:
            try:
                widget = await detect(page, handles)
                if not widget:
                    return ActionResult("challenge_cleared" if kind else "no_challenge", kind, attempts)
                board = widget.parts.get("board")
                source = await board.evaluate("e => e.currentSrc || null") if board else None
                if attempt > 1 and widget.parts.get("refresh") and (
                    widget.kind == "geetest_icon" or (source and source == previous_source)
                ):
                    await widget.parts["refresh"].click(timeout=2000)
                    await asyncio.sleep(0.75)
                    widget = await detect(page, handles)
                    if page.url != site:
                        return ActionResult("navigated", kind, attempts)
                    if not widget:
                        return ActionResult("challenge_cleared", kind, attempts)
                    board = widget.parts.get("board")
                    source = await board.evaluate("e=>e.currentSrc || null") if board else None
                previous_source = source
                kind = widget.kind
                attempts = attempt
                acted = await solve(page, widget, site)
                reason = (
                    "Widget still visible after gesture." if acted else
                    f"No reliable gesture for {widget.kind}; the task may be unsupported, changed, or uncertain."
                )
                await asyncio.sleep(1.5)
            except (Error, TimeoutError, OSError, ValueError, RuntimeError, KeyError) as exc:
                if page.is_closed() or page.url != site:
                    return ActionResult("navigated", kind, attempts)
                if not kind:
                    raise
                reason = (
                    str(exc)
                    if isinstance(exc, RuntimeError) and not isinstance(exc, Error)
                    else type(exc).__name__
                )
                await asyncio.sleep(0.5)
    if page.is_closed() or page.url != site:
        return ActionResult("navigated", kind, attempts)
    async with AsyncExitStack() as handles:
        if not await detect(page, handles):
            return ActionResult("challenge_cleared", kind, attempts)
    return ActionResult("challenge_pending", kind, attempts, reason)


async def execute(page, site, target=None, *, timeout=5000, enter=False, completion=None):
    """With no target, resume the open widget without replaying a prior click."""
    if page.url != site or page.is_closed():
        raise RuntimeError("The selected tab changed before the action.")
    await prepare_page(page)
    PROFILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with FileLock(PROFILE.parent / "browser-action.lock", timeout=0):
            # A previous click may already have opened the widget.
            prior = await settle(page, site)
            if target is None or prior.state != "no_challenge":
                return prior
            if page.url != site:
                raise RuntimeError("The selected tab changed before the click.")
            if enter:
                await target.press("Enter", timeout=timeout)
            else:
                await target.click(timeout=timeout)
            # Verification SDKs may fetch configuration before mounting an iframe.
            # Start at 1.5 seconds and keep observing the same action. Never replay it.
            deadline = asyncio.get_running_loop().time() + 6
            await asyncio.sleep(1.5)
            while True:
                result = await settle(page, site)
                if result.state != "no_challenge" or (
                    completion is not None and await completion.is_visible()
                ):
                    return result
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return result
                await asyncio.sleep(min(0.25, remaining))
    except LockBusy:
        raise RuntimeError("Another Ruin action is in progress in shared Chrome.") from None


async def click(page, target, *, timeout=5000, enter=False, completion=None):
    result = await execute(page, page.url, target, timeout=timeout, enter=enter, completion=completion)
    if result.state == "challenge_pending":
        raise RuntimeError(f"{result.kind} pending after {result.attempts} attempts. {result.reason}")
    return result


async def exact_action(context, site, button=None):
    origin_of(site)
    tabs = [p for p in context.pages if p.url == site]
    if len(tabs) != 1:
        raise RuntimeError("Open exactly one tab at the selected action URL.")
    page = tabs[0]
    target = page.get_by_role("button", name=button, exact=True).filter(visible=True) if button else None
    result = await execute(page, site, target)
    from ruin.auth.saved_login import resume_saved_login
    from ruin.auth.ats_accounts import resume_ats_account
    from ruin.auth.vault_login import resume_vault_login
    result.authentication = await resume_vault_login(page) or await resume_saved_login(page)
    if result.authentication is None:
        result.authentication = await resume_ats_account(page)
    if result.authentication is not None:
        result.authentication["url"] = page.url
    return result
