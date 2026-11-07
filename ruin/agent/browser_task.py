import sys
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext
from pydantic import BaseModel
from typing import Literal

from ruin.auth.auto_registrar import fill_contact_phone, identity, signup, verify_sms
from ruin.auth.autofill import fill_login, offer_chrome_login
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
    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded")
    profile = identity()
    registered_at = None
    sms_filled = False
    async with AsyncOpenAI() as client:
        for _ in range(20):
            current = urlsplit(page.url)
            if (current.scheme, current.netloc) != (location.scheme, location.netloc):
                raise RuntimeError("The page left the selected site. Complete sign-in before running the task.")
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
                chrome_login = await offer_chrome_login(page, url)
                if filled or chrome_login:
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
                await page.close()
                return
            if step.element_id not in targets or urlsplit(page.url) != current:
                raise RuntimeError("The page or action changed. Execution stopped.")
            await targets[step.element_id].click(timeout=5000)
            await page.wait_for_load_state("domcontentloaded")
        raise RuntimeError("Reached the 20-step limit.")
