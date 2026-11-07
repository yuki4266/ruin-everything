import sys
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext
from pydantic import BaseModel
from typing import Literal

from ruin.auth.autofill import fill_login
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
    async with AsyncOpenAI() as client:
        for _ in range(20):
            current = urlsplit(page.url)
            if (current.scheme, current.netloc) != (location.scheme, location.netloc):
                raise RuntimeError("The page left the selected site. Complete sign-in before running the task.")
            if autofill and await page.locator(
                'input[type=password]:visible, input[autocomplete=one-time-code]:visible'
            ).count():
                if await fill_login(page, url):
                    print("Credentials filled locally. Complete sign-in in the browser.", file=sys.stderr)
                    await page.wait_for_function(
                        """() => !Array.from(document.querySelectorAll(
                            'input[type=password], input[autocomplete=one-time-code]'
                        )).some(el => el.getClientRects().length)""", timeout=180000
                    )
                    continue
            for frame in page.frames:
                if await frame.locator('input[type=password]:visible, input[autocomplete=one-time-code]:visible').count():
                    raise RuntimeError("Sign in using this browser before running the task.")
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
