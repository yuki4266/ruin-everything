"""Inspect local application tabs and check Ashby receipts over stdio MCP."""

import argparse
from typing import Annotated, Literal

from ruin.agent.ashby import application_url, lookup_receipt, resume_ashby
from ruin.agent.challenge import Provider, State, inspect_challenge
from ruin.auth.auto_registrar import identity
from ruin.browser.context import browser_context
from ruin.browser.actions import ActionResult, exact_action
from ruin.config import PROFILE
from ruin.updater import start_update_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp", help="Local Chrome HTTP debugging endpoint for the receipt watcher")
    args = parser.parse_args()
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
        from pydantic import BaseModel, Field
    except ModuleNotFoundError as exc:
        if exc.name == "mcp":
            parser.exit(1, "Install the MCP extra with python -m pip install -e '.[mcp]'.\n")
        raise

    def signup_status():
        try:
            enabled = identity().get("auto_signup") is True
        except (ValueError, OSError):
            return "identity profile unavailable"
        return "Auto-signup and phone filling are strictly pre-authorized for the selected site" if enabled else "disabled"

    class LocalSettings(BaseModel):
        signup_policy: str = Field(default_factory=signup_status)

    class Registration(LocalSettings):
        sms_filled: bool = False
        state: Literal["submitted", "workday_account_step_completed", "phone_filled", "no_match",
                       "slider_pending", "sms_requested", "challenge_cleared", "challenge_pending", "navigated"]

    class Challenge(LocalSettings):
        provider: Provider
        state: State

    class Receipt(LocalSettings):
        state: Literal["submitted"]
        site: str
        observed_at: str
        message: str

    class Lookup(LocalSettings):
        state: Literal["unrecorded", "submitted"]
        site: str
        observed_at: str | None = None
        message: str | None = None

    server = FastMCP("Ruin Everything")

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False))
    async def ruin_action(site: str, button: str | None = None) -> ActionResult:
        """Execute an authorized form button by exact visible name on its exact open HTTPS URL.
        Use for every form submission. Automatically handle visual challenges after clicking.
        Omit button to resume a pending challenge. The action result is not a submission receipt."""
        async with browser_context(PROFILE, args.cdp, launch_if_missing=False) as context:
            return await exact_action(context, site, button)

    @server.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=False))
    async def ruin_auto_register(site: str) -> Registration:
        """Handle an open Workday Sign In or Create Account dialog at the exact job URL,
        a Feishu Jobs rotation slider, a ZhongAn Moka job with a visible Yidun jigsaw,
        or a supported signup form. Use the exact open URL, including the job fragment.
        Credentials come from the local profile."""
        from playwright.async_api import TimeoutError as BrowserTimeout
        from ruin.auth.auto_registrar import signup, fill_contact_phone, verify_sms
        from ruin.auth.feishu import feishu_slider
        from ruin.auth.yidun import moka_slider
        from ruin.auth.workday import workday_account
        from ruin.auth.vault import origin_of

        origin_of(site)
        profile = identity()
        async with browser_context(PROFILE, args.cdp, launch_if_missing=False) as context:
            tabs = [p for p in context.pages if p.url == site]
            if len(tabs) != 1:
                raise RuntimeError("Open exactly one tab at the selected registration URL.")
            slider = await feishu_slider(tabs[0], site, profile)
            if slider is None:
                slider = await moka_slider(tabs[0], site, profile)
            if slider:
                return Registration(state=slider)
            if profile.get("auto_signup") is True:
                visual = await exact_action(context, site)
                if visual.state != "no_challenge":
                    return Registration(state=visual.state)
            if await workday_account(tabs[0], site, profile):
                return Registration(state="workday_account_step_completed")
            requested = await signup(tabs[0], site, profile)
            if requested is not None:
                try:
                    await tabs[0].locator('input[autocomplete=one-time-code]:visible').first.wait_for(timeout=3000)
                except BrowserTimeout:
                    return Registration(state="submitted")
                return Registration(state="submitted", sms_filled=await verify_sms(tabs[0], site, requested))
            filled = await fill_contact_phone(tabs[0], site, profile)
            return Registration(state="phone_filled" if filled else "no_match")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
    async def inspect_application_challenge(
        site: str, wait_seconds: Annotated[int, Field(ge=0, le=300)] = 0
    ) -> Challenge:
        """Inspect the original Greenhouse or Ashby application tab at its exact job URL.
        Use when Greenhouse asks for an 8-character email security code, including reports of
        '[one-time authentication code withheld]', or Ashby displays a reCAPTCHA image grid.
        On a lost tab, report whether the shared local browser still has it. Return the visible
        state only. Mailbox contents, CAPTCHA solving, Duo 2FA, PayPal Security Challenge and
        payment actions are outside this tool's scope. A positive wait watches just this job.
        """
        return Challenge(**await inspect_challenge(site, args.cdp, wait_seconds))

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    def get_ashby_receipt(site: str) -> Lookup:
        """Check the exact Ashby job first when asked whether it was submitted, including at handoff or after a lost tab.
        A stored receipt confirms success even with Chrome closed. Unrecorded means the outcome is unknown.
        """
        site = application_url(site)
        receipt = lookup_receipt(site, PROFILE.parent)
        return Lookup(**receipt) if receipt else Lookup(state="unrecorded", site=site)

    @server.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
    async def watch_ashby_receipt(
        site: str, timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 15
    ) -> Receipt:
        """Watch the original Ashby form when a challenge clears or a submitted application has no receipt yet.
        Return saved evidence or record the official success message for this job. This never submits the form.
        """
        site = application_url(site)
        receipt = lookup_receipt(site, PROFILE.parent)
        if receipt:
            return Receipt(**receipt)
        async with browser_context(PROFILE, args.cdp) as context:
            evidence = await resume_ashby(context, site, timeout_seconds, PROFILE.parent, lambda event: None)
        return Receipt(**evidence)

    start_update_check()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
