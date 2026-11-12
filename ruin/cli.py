import argparse
import asyncio
import json
import sys

from ruin.browser.driver import Error, TimeoutError

from ruin.agent.executor import courses
from ruin.browser.context import browser_context
from ruin.config import PROFILE
from ruin.updater import start_update_check


async def run(args):
    if args.task == "ats-setup":
        from ruin.auth.ats_config import setup
        print(json.dumps(setup()))
        return
    if args.task == "ats-account":
        from ruin.auth.auto_registrar import identity
        from ruin.auth.ats_accounts import icims_account
        from ruin.auth.workday import workday_account
        from ruin.browser.universal import exact_page
        async with browser_context(PROFILE, args.cdp, launch_if_missing=False) as context:
            page = exact_page(context, args.site)
            profile = identity()
            result = await icims_account(page, args.site, profile)
            if result is None:
                result = await workday_account(page, args.site, profile)
            print(json.dumps(result if isinstance(result, dict) else {"state": "account_step_completed" if result else "no_match"}))
        return
    if args.task == "action":
        from dataclasses import asdict
        from ruin.browser.actions import exact_action
        async with browser_context(PROFILE, args.cdp, launch_if_missing=False) as context:
            print(json.dumps(asdict(await exact_action(context, args.site, args.button))))
        return
    if args.task == "identity":
        from ruin.auth.identity_setup import setup
        await setup()
        return
    if args.task == "watch":
        if args.install or args.uninstall:
            from ruin.browser.watch_service import configure
            configure(args.install)
            return
        if not args.site:
            from ruin.browser.academic_watch import watch
            await watch(args.cdp)
            return
        from ruin.agent.challenge import inspect_challenge
        print(json.dumps(await inspect_challenge(args.site, args.cdp, args.timeout)))
        return
    async with browser_context(PROFILE, args.cdp, args.channel) as context:
        if args.task == "keep-alive":
            from ruin.browser.session import keep_alive
            await keep_alive(context, args.site, args.signed_in_text, args.interval, args.timeout)
            print("Session check interval completed.")
            return
        if args.task == "verify-sms":
            from ruin.auth.auto_registrar import verify_sms
            tabs = [page for page in context.pages if page.url == args.site]
            if len(tabs) != 1:
                raise RuntimeError("Open exactly one tab at the selected SMS verification URL.")
            if not await verify_sms(tabs[0], args.site, args.requested_at):
                raise RuntimeError("Could not verify entry in the SMS code fields. Check the original tab.")
            print("Filled the code field in the original tab.")
            return
        if args.task == "browser":
            print("Connected to local Chrome. The browser will stay open.")
            return
        if args.task == "resume-ashby":
            from ruin.agent.ashby import resume_ashby
            def report(event):
                print(json.dumps(event), file=sys.stderr, flush=True)
            receipt = await resume_ashby(context, args.site, args.timeout, PROFILE.parent, report)
            print(json.dumps(receipt))
            return
        if args.task == "verify-email":
            from ruin.auth.interceptor import verify_greenhouse
            await verify_greenhouse(context, args.site, args.company, args.timeout, args.requested_at)
            print("Application confirmation appeared in the original tab.")
            return
        if args.site:
            try:
                from ruin.agent.browser_task import browser_task
                await browser_task(context, args.site, args.task, args.model, args.autofill)
            except ImportError as exc:
                raise RuntimeError("Install the optional agent dependencies with pip install '.[agent]'") from exc
            print("Task complete.")
            return
        result = await courses(context, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif result:
        for course in result:
            print(course["name"], course["url"], sep="\t")
    else:
        print("No courses with accessible links were found.")


def main():
    parser = argparse.ArgumentParser(description="Run browser tasks and resume verification in a shared local Chrome session.")
    parser.add_argument("task", help="Use ats-setup, ats-account, identity, browser, watch, verify-email, verify-sms, keep-alive, resume-ashby, courses, or a click task with --site.")
    parser.add_argument("--site", help="HTTPS starting URL for a click task")
    parser.add_argument("--button", help="Exact visible button label for an action. Omit to resume a challenge.")
    parser.add_argument("--autofill", action="store_true", help="Use keyring and configured trusted login actions for this task")
    parser.add_argument("--requested-at", type=float, metavar="UNIX_SECONDS",
                        help="Original code-request time for SMS or a Greenhouse form without a resend control")
    parser.add_argument("--company", help="Employer name for Greenhouse verification")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--cdp", metavar="URL", help="Connect to a local Chrome HTTP debugging endpoint")
    parser.add_argument("--channel", choices=["chrome"], help="Launch the dedicated profile in installed Chrome")
    parser.add_argument("--timeout", type=int, help="Seconds to wait for the requested workflow")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--interval", type=int, default=900, help="Seconds between session checks")
    parser.add_argument("--signed-in-text", help="Exact visible text unique to the signed-in status page")
    service = parser.add_mutually_exclusive_group()
    service.add_argument("--install", action="store_true", help="Start ruin watch at macOS login")
    service.add_argument("--uninstall", action="store_true", help="Stop and remove the macOS watcher")
    args = parser.parse_args()
    if (args.install or args.uninstall) and (args.task != "watch" or args.site or args.cdp):
        parser.error("Watcher installation requires watch without --site or --cdp")
    if args.timeout is None:
        args.timeout = 3600 if args.task == "keep-alive" else 180
    if args.task == "keep-alive" and not (args.site and args.signed_in_text and args.interval > 0):
        parser.error("keep-alive requires --site, --signed-in-text and a positive interval")
    if args.task == "verify-sms":
        import time
        if not args.site or not args.requested_at or not 0 <= time.time() - args.requested_at <= 300:
            parser.error("verify-sms requires --site and a request timestamp within the last five minutes")
    if args.task == "resume-ashby" and not args.site:
        parser.error(f"{args.task} requires --site")
    if args.task == "verify-email" and not (args.site and args.company):
        parser.error("verify-email requires --site and --company")
    if not args.site and args.task not in {"ats-setup", "identity", "browser", "courses", "list my courses", "watch"}:
        parser.error("Browser tasks require --site.")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero.")
    start_update_check()
    try:
        asyncio.run(run(args))
    except TimeoutError:
        sys.exit("Timed out waiting for Canvas or sign-in. Check the login page and try again.")
    except Error:
        sys.exit("Browser connection or navigation failed. Check the browser installation, network and debugging endpoint.")
    except (RuntimeError, ValueError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
