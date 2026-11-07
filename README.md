# Ruin Everything

用本机浏览器打开 Duke Canvas，列出当前可访问的课程。运行时先尝试课程页；遇到登录跳转才打开学校的 NetID 入口。用户在浏览器内完成学校要求的验证后，原任务自动继续。课程查询在本地运行，无需模型或 API 密钥。

## 运行

需要 Python 3.11+。在仓库目录运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
ruin "列出我的课程"
```

已有 Google Chrome 时，可跳过 Chromium 下载，运行 `ruin courses --channel chrome`。首次打开的是专用浏览器配置，保存在 `~/.ruin-everything/canvas-browser`。下次使用同一配置。若已单独启动支持 CDP 调试的 Chrome，可复用该会话：

```sh
ruin courses --cdp http://127.0.0.1:9222 --json
```

输出包含课程名和课程链接。遇到认证时在浏览器内操作，默认等待 180 秒，可用 `--timeout 300` 调整。换手机后无法验证时，参见 [Duke Duo 恢复说明](https://oit.duke.edu/help/articles/kb0036398/)。

## 可选的模型点击模式

安装 `python -m pip install -e '.[agent]'` 并设置 `OPENAI_API_KEY` 后，可给出 HTTPS 入口和点击任务。例如：

```sh
ruin "打开帮助页面" --site https://example.org --channel chrome
```

此模式向指定模型发送任务、页面标题和可点击控件的标签。每一步通过数字编号定位原控件，保留真实操作名称。程序会直接点击选中的控件，最多执行 20 步。请给出明确的任务目标。模型依赖可见标签判断完成状态。当前支持单标签页点击任务。

同源标准登录表单支持可选的 `--autofill`。通过系统密码库预先设置相应条目，再次运行时程序会在本地填写；如果登录跳转至其他来源，请先在该浏览器完成登录。下列命令会交互式录入值：

```sh
keyring set ruin:https://example.org username
keyring set ruin:https://example.org password
keyring set ruin:https://example.org totp
```

其中 totp 用于提供标准 TOTP 的站点，填入该站点签发的 Base32 种子。Duke Duo Push 由用户在学校验证流程中批准。

## 验证范围

`python -m unittest discover -s tests -v` 使用本地模拟门户与真实 Chromium 测试首次验证、重启复用和控件快照。若使用已安装的 Chrome，在命令前加 `RUIN_TEST_CHANNEL=chrome`。学校入口已检查。真实 Duke 账号登录与在线模型任务仍待实测。

[开发计划](PLAN.md) · [MIT 许可证](LICENSE)
