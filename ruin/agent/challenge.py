"""Observe verification on one existing application without interacting with its form."""

import asyncio
from typing import Literal, TypedDict

from playwright.async_api import Error, Page

from ruin.agent.ashby import application_url, observe
from ruin.auth.email_otp_snatcher import job_key, verification_prompt_visible
from ruin.browser.context import browser_context
from ruin.config import PROFILE
from ruin.rules_loader import load_rules


Provider = Literal["ashby", "greenhouse"]
State = Literal["tab_missing", "ambiguous_tabs", "tab_changed", "pending",
                "email_verification", "challenge_visible", "receipt_visible"]


class Observation(TypedDict):
    provider: Provider
    state: State


async def inspect_challenge(site: str, cdp: str | None, wait_seconds: int = 0) -> Observation:
    key = job_key(site)
    provider = "greenhouse" if key else "ashby"
    if not key:
        try:
            site = application_url(site)
        except ValueError as exc:
            raise ValueError("Use an exact Ashby application URL or Greenhouse job URL.") from exc

    def matches(page: Page):
        if key:
            return job_key(page.url) == key
        return page.url.split("?")[0].split("#")[0].rstrip("/") == site

    async with browser_context(PROFILE, cdp, launch_if_missing=False) as context:
        tabs = [p for p in context.pages if matches(p)]
        if len(tabs) != 1:
            return {"provider": provider, "state": "ambiguous_tabs" if tabs else "tab_missing"}
        page = tabs[0]
        rules = await load_rules()
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while True:
            if page.is_closed() or not matches(page):
                return {"provider": provider, "state": "tab_changed"}
            if any(other != page and matches(other) for other in context.pages):
                return {"provider": provider, "state": "ambiguous_tabs"}
            try:
                if key:
                    visible = await verification_prompt_visible(page, rules)
                    state = "email_verification" if visible else "pending"
                else:
                    observed = await observe(page, site, rules["ashby"])
                    state = {"submitted": "receipt_visible", "awaiting_receipt": "pending",
                             "changed_tab": "tab_changed", "challenge_visible": "challenge_visible"}[observed["state"]]
            except Error as exc:
                if page.is_closed() or not matches(page):
                    return {"provider": provider, "state": "tab_changed"}
                if "Execution context was destroyed" not in str(exc):
                    raise
                state = "pending"
            if page.is_closed() or not matches(page):
                state = "tab_changed"
            remaining = deadline - asyncio.get_running_loop().time()
            if state != "pending" or remaining <= 0:
                return {"provider": provider, "state": state}
            await asyncio.sleep(min(0.5, remaining))
