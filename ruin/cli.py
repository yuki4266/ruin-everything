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
        if args.site:
            try:
                from ruin.agent.browser_task import browser_task
                await browser_task(context, args.site, args.task, args.model, args.autofill)
            except ImportError as exc:
                raise RuntimeError("通用任务需要安装可选依赖 pip install '.[agent]'") from exc
            print("任务执行完成。")
            return
        result = await courses(context, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif result:
        for course in result:
            print(course["name"], course["url"], sep="\t")
    else:
        print("当前课程表中没有可打开的课程。")


def main():
    parser = argparse.ArgumentParser(description="使用本地浏览器读取 Duke Canvas 当前课程")
    parser.add_argument("task", help="courses、列出我的课程，或配合 --site 使用的任务描述")
    parser.add_argument("--site", help="通用点击任务的 HTTPS 入口")
    parser.add_argument("--autofill", action="store_true", help="从系统密码库填充指定网站的凭据")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--cdp", metavar="URL", help="连接已启用调试的本机 Chrome")
    parser.add_argument("--channel", choices=["chrome"], help="用已安装的 Chrome 打开专用配置")
    parser.add_argument("--timeout", type=int, default=180, help="等待学校验证的秒数")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.site and args.task not in {"courses", "列出我的课程"}:
        parser.error("通用任务需要 --site")
    if args.timeout <= 0:
        parser.error("--timeout 必须大于零")
    try:
        asyncio.run(run(args))
    except TimeoutError:
        sys.exit("等待页面或认证结果超时。请检查登录状态和 Canvas 页面。")
    except Error:
        sys.exit("浏览器连接或导航失败。请检查浏览器安装、网络和调试地址。")
    except (RuntimeError, ValueError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
