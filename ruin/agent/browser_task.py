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
        raise ValueError("任务入口需要 HTTPS 网站地址。")
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        async with AsyncOpenAI() as client:
            for _ in range(20):
                current = urlsplit(page.url)
                if (current.scheme, current.netloc) != (location.scheme, location.netloc):
                    raise RuntimeError("页面已离开指定网站，请先完成站点登录。")
                if autofill and await page.locator(
                    'input[type=password]:visible, input[autocomplete=one-time-code]:visible'
                ).count():
                    if await fill_login(page, url):
                        print("凭据已在本地填写。请在浏览器中完成登录。", file=sys.stderr)
                        await page.wait_for_function(
                            """() => !Array.from(document.querySelectorAll(
                                'input[type=password], input[autocomplete=one-time-code]'
                            )).some(el => el.getClientRects().length)""", timeout=180000
                        )
                        continue
                for frame in page.frames:
                    if await frame.locator('input[type=password]:visible, input[autocomplete=one-time-code]:visible').count():
                        raise RuntimeError("请先在此浏览器中完成登录，再执行通用任务。")
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
                    raise RuntimeError("当前页面的信息不足以继续。")
                if step.action == "done":
                    return
                if step.element_id not in targets or urlsplit(page.url) != current:
                    raise RuntimeError("页面或动作已变化，已停止执行。")
                await targets[step.element_id].click(timeout=5000)
                await page.wait_for_load_state("domcontentloaded")
            raise RuntimeError("已达到 20 步上限。")
    finally:
        if not page.is_closed():
            await page.close()
