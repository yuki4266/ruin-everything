import sys
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext
from pydantic import BaseModel
from typing import Literal

from ruin.browser.actions import click
from ruin.auth.auto_registrar import fill_contact_phone, identity, signup, verify_sms
from ruin.auth.workday import workday_account
from ruin.auth.vault import origin_of
from ruin.auth.autofill import fill_login, offer_chrome_login, click_trusted_login
from ruin.agent.prompts import SYSTEM
from ruin.browser.dom_sanitizer import snapshot


class Decision(BaseModel):
    action: Literal["click", "done", "blocked"]
    element_id: int | None


async def browser_task(context: BrowserContext, url: str, task: str, model: str, autofill=False):
    from openai import AsyncOpenAI
    import json

    location = urlsplit(url)
    if location.scheme != "https" or not location.hostname or location.username:
        raise ValueError("Use an HTTPS URL to start the task.")
    existing = [tab for tab in context.pages if tab.url == url]
    if len(existing) > 1:
        raise RuntimeError("More than one tab matches the task URL. Select a unique original tab.")
    page = existing[0] if existing else await context.new_page()
    if not existing:
        await page.goto(url, wait_until="domcontentloaded")
    profile = identity()
    registered_at = None
    sms_filled = False
    workday_actions = 0
    trusted_attempts = set()
    chrome_attempted = False
    clients = getattr(context, "ruin_trusted_oauth_clients", []) if autofill else []
    async with AsyncOpenAI() as client:
        for _ in range(20):
            action_origin = origin_of(page.url)
            action = await click_trusted_login(page, url, clients, trusted_attempts)
            if action:
                print(f"Trusted login action: {action}", file=sys.stderr)
                if action_origin != origin_of(url):
                    await page.wait_for_url(lambda target: origin_of(target) == origin_of(url), timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
                continue
            current = urlsplit(page.url)
            if (current.scheme, current.netloc) != (location.scheme, location.netloc):
                raise RuntimeError("The page left the selected site. Complete sign-in before running the task.")
            if workday_actions < 2 and await workday_account(page, url, profile, allow_create=workday_actions == 0):
                workday_actions += 1
                continue
            if registered_at is None:
                registered_at = await signup(page, url, profile)
                if registered_at is not None:
                    continue
            elif not sms_filled and await verify_sms(page, url, registered_at):
                sms_filled = True
                continue
            if registered_at is None and autofill and await page.locator(
                'input[type=password]:visible, input[autocomplete=one-time-code]:visible'
            ).count():
                filled = await fill_login(page, url)
                chrome_login = False
                if not chrome_attempted:
                    chrome_attempted = True
                    chrome_login = await offer_chrome_login(page, url, clients=clients)
                if filled or chrome_login:
                    action = await click_trusted_login(page, url, clients, trusted_attempts)
                    if action:
                        print(f"Trusted login action: {action}", file=sys.stderr)
                    print("Complete sign-in in the open Chrome tab. The task will resume here.", file=sys.stderr)
                    await page.locator(
                        'input[type=password]:visible, input[autocomplete=one-time-code]:visible'
                    ).first.wait_for(state="hidden", timeout=180000)
                    continue
            for frame in page.frames:
                protected = "input[type=password]:visible"
                if frame != page.main_frame or not sms_filled:
                    protected += ", input[autocomplete=one-time-code]:visible"
                if await frame.locator(protected).count():
                    raise RuntimeError("Sign in using this browser before running the task.")
            await fill_contact_phone(page, url, profile)
            labels, targets = await snapshot(page)
            payload = {"task": task, "title": await page.title(), "actions": labels}
            reply = await client.chat.completions.parse(
                model=model,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": json.dumps(payload)}],
                response_format=Decision,
            )
            step = reply.choices[0].message.parsed
            if step is None or step.action == "blocked":
                raise RuntimeError("The page does not provide enough information to continue.")
            if step.action == "done":
                if not existing:
                    await page.close()
                return
            if step.element_id not in targets or urlsplit(page.url) != current:
                raise RuntimeError("The page or action changed. Execution stopped.")
            await click(page, targets[step.element_id])
            await page.wait_for_load_state("domcontentloaded")
        raise RuntimeError("Reached the 20-step limit.")
