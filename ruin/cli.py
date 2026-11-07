import argparse
import asyncio
import json
import sys

from playwright.async_api import Error, TimeoutError

from ruin.agent.executor import courses
from ruin.browser.context import browser_context
from ruin.config import PROFILE


async def run(args):
    async with browser_context(PROFILE, args.cdp, args.channel) as context:
        if args.task == "verify-email":
            from ruin.auth.interceptor import verify_greenhouse
            await verify_greenhouse(context, args.site, args.company, args.timeout)
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
    parser = argparse.ArgumentParser(description="List current Duke Canvas courses using a local browser.")
    parser.add_argument("task", help="Use courses, or describe a browser task and supply --site.")
    parser.add_argument("--site", help="HTTPS starting URL for a click task")
    parser.add_argument("--autofill", action="store_true", help="Fill credentials for this origin from the system keyring")
    parser.add_argument("--company", help="Employer name for Greenhouse verification")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--cdp", metavar="URL", help="Connect to a local Chrome HTTP debugging endpoint")
    parser.add_argument("--channel", choices=["chrome"], help="Launch the dedicated profile in installed Chrome")
    parser.add_argument("--timeout", type=int, default=180, help="Seconds to wait for school verification")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.task == "verify-email" and not (args.cdp and args.site and args.company):
        parser.error("verify-email requires --cdp, --site and --company")
    if not args.site and args.task not in {"courses", "list my courses"}:
        parser.error("Browser tasks require --site.")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero.")
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
