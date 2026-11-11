"""Default universal browser agent connected to local Chrome via CDP (port 9222).
Use this tool for ANY web browsing, navigation, DOM interaction, form filling,
scraping, or multi-step web workflow across ALL websites.
"""

import argparse
from typing import Annotated, Any, Literal

from ruin.agent.ashby import application_url, lookup_receipt, resume_ashby
from ruin.agent.challenge import Provider, State, inspect_challenge
from ruin.auth.auto_registrar import identity
from ruin.browser.context import browser_context
from ruin.browser.actions import ActionResult, exact_action
from ruin.browser.universal import Operation, browser_operation
from ruin.config import PROFILE
from ruin.updater import start_update_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp", help="Local Chrome HTTP debugging endpoint (default: http://127.0.0.1:9222)")
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
                       "account_step_completed", "account_pending", "reset_email_requested", "email_verification_pending",
                       "slider_pending", "sms_requested", "challenge_cleared", "challenge_pending", "navigated"]
        reason: str | None = None

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

    server = FastMCP("Ruin Everything", instructions=__doc__ + """
Use ruin_browser as the default entry point. Reuse Chrome's existing session,
cookies and extensions. If only a blank tab is open, navigate directly to the
task URL; if the URL is unknown, navigate to a search engine and find the site.
Do not ask the user to open a page manually. Use returned URLs for subsequent
operations, including redirects across domains. Site adapters are optional helpers,
not restrictions on the runtime's scope. Keep passwords out of tool arguments.
Do not stop at a saved Duke login or Duo device-trust screen. On the selected
tab, ruin_browser and ruin_action submit already-filled Duke credentials and
confirm Duo's Yes, trust browser / Is this your device? controls through the
executor. They wait 15 seconds for automatic continuation before reporting
remaining code, phone-push or credential input. Use the returned current URL.
The fixed Chrome profile restores the previous session; sites control expiry.
""")

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False))
    async def ruin_browser(
        operation: Operation, site: str | None = None, url: str | None = None,
        selector: str | None = None, value: str | None = None,
    ) -> dict[str, Any]:
        """Default universal browser agent connected to local Chrome via CDP (port 9222).
        Use this tool for ANY web browsing, navigation, DOM interaction, form filling,
        scraping, or multi-step web workflow across ALL websites.
        tabs lists open pages. navigate uses url as destination, optionally site as the
        exact current tab URL; otherwise reuse the destination tab or a marked agent tab,
        or create a background tab. User blank tabs remain untouched. No OS activation.
        Navigate proactively, using search when needed.
        Other operations require site equal to the current URL returned by the last call.
        inspect returns visible text and control selectors without reading input values;
        read extracts visible text (selector defaults to body).
        click, fill, press and select require a unique visible Playwright
        selector, e.g. role=button[name="Continue"]. value supplies text, a key, or an option
        value. Clicks and Enter use the Ruin executor. Tabs and existing sessions stay open.
        Keep passwords out of arguments. Site-specific helpers are optional adapters.
        On Duke SSO and Duo, automatically advance already-filled login fields and
        device-trust controls, then wait 15 seconds before handing off remaining
        verification. inspect/read may advance these authorized login screens.
        When ATS_AUTO_RECOVER is enabled locally, also continue iCIMS/Workday account
        setup, bounded password retries and password recovery in the selected tenant.
        """
        async with browser_context(PROFILE, args.cdp) as context:
            return await browser_operation(context, operation, site=site, url=url, selector=selector, value=value)

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False))
    async def ruin_action(site: str, button: str | None = None) -> ActionResult:
        """Click an authorized form button on any website in local Chrome over CDP.
        Supply its exact open HTTPS URL and exact visible button name.
        Use for every form submission. Automatically handle visual challenges after clicking.
        Omit button to resume a pending challenge or saved Duke/Duo login.
        Saved login and device trust advance automatically; remaining verification
        is reported after 15 seconds. The action result is not a submission receipt."""
        async with browser_context(PROFILE, args.cdp, launch_if_missing=False) as context:
            return await exact_action(context, site, button)

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False))
    async def ruin_auto_register(site: str) -> Registration:
        """Handle iCIMS login/password setup or Workday Sign In/Create Account at the exact URL.
        With local ATS_AUTO_RECOVER enabled, try registration, retry the local ATS password
        once and request password recovery after an explicit credential error.
        Passwords stay in the local private env file; never pass them as tool arguments.
        Also handle
        a Feishu Jobs rotation slider, a ZhongAn Moka job with a visible Yidun jigsaw,
        or a supported signup form. Use the exact open URL, including the job fragment.
        Credentials come from the local profile."""
        from playwright.async_api import TimeoutError as BrowserTimeout
        from ruin.auth.auto_registrar import signup, fill_contact_phone, verify_sms
        from ruin.auth.feishu import feishu_slider
        from ruin.auth.yidun import moka_slider
        from ruin.auth.workday import workday_account
        from ruin.auth.ats_accounts import icims_account
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
                if visual.authentication and visual.authentication.get("state") in {
                    "account_step_completed", "account_pending", "reset_email_requested", "email_verification_pending"
                }:
                    return Registration(state=visual.authentication["state"], reason=visual.authentication.get("reason"))
                if visual.state != "no_challenge":
                    return Registration(state=visual.state)
            icims = await icims_account(tabs[0], site, profile)
            if icims:
                return Registration(**icims)
            workday = await workday_account(tabs[0], site, profile)
            if isinstance(workday, dict):
                return Registration(**workday)
            if workday:
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
