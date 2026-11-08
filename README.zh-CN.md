<p align="right"><a href="README.md">English</a> &nbsp;·&nbsp; <strong>简体中文</strong> &nbsp;·&nbsp; <a href="README.ja.md">日本語</a> &nbsp;·&nbsp; <a href="README.es.md">Español</a></p>

# <img src="docs/figures/tab-wave.webp" alt="Ruin Everything：一张回执在蓝色和淡紫色的浏览器标签页中冲浪" width="100%">

<p align="center">
  <a href="https://github.com/yuki4266/ruin-everything/stargazers"><img src="docs/figures/badges/stars.svg" alt="GitHub 星标"></a>
  <a href="#use-a-shared-local-chrome-window"><img src="docs/figures/badges/python.svg" alt="需要 Python 3.11 或更高版本"></a>
  <a href="#connect-an-agent-over-mcp"><img src="docs/figures/badges/mcp.svg" alt="通过 stdio 的 MCP"></a>
  <a href="LICENSE"><img src="docs/figures/badges/license.svg" alt="MIT 许可证"></a>
</p>

**接着上一个智能体停下的地方，继续浏览器任务。** Ruin 连接本机 Chrome。新的 CLI 进程或 MCP 客户端可以找到原先打开的申请标签页，完成受支持的验证步骤，并检查网站的确认信息。

[设置Chrome](#use-a-shared-local-chrome-window) · [连接 MCP 客户端](#connect-an-agent-over-mcp) · [查看已测试的内容](#verification) · [试用第一个 MCP 工具](#first-mcp-call) · [参与贡献](#community)

| 在您的浏览器中 | Ruin 可以做什么 |
| --- | --- |
| Greenhouse 求职申请要求输入邮箱验证码 | [在 Outlook 中找到与申请对应的新邮件并填入验证码。](#verify-a-greenhouse-application-with-outlook-web) |
| 提交后关闭了 Ashby 标签页 | [用职位的完整 URL 查询已保存的提交回执。](#receipt-storage-and-retries) |
| Workday 要求登录 | [使用本机身份档案登录，或在支持的网站激活账号后回到职位页。](#workday-accounts-and-signed-in-sessions) |
| 有多个国家或地区的手机号 | [在离线身份编辑器中选择默认号码。](#local-account-registration) |

<a name="choose-a-starting-point"></a>

## 选择一个起点

<img src="docs/figures/command-guide.svg" alt="五个终端命令以及何时使用每个命令，从启动 Chrome 到查看现有应用程序的接收。" width="100%">

对于新任务，启动共享浏览器并打开目标站点。对于中断的应用程序，选择特定于站点的观察程序并传递原始职位 URL。通用点击任务会打开一个新标签页。

<img src="docs/figures/architecture.svg" alt="独立客户端重新连接到共享 Chrome 中的原始标签页。" width="100%">

<a name="use-a-shared-local-chrome-window"></a>

## 使用共享的本地 Chrome 窗口

<img src="docs/figures/local-chrome.svg" alt="两个独立的运行器连接连接到本地 Chrome 配置文件，并保持相同的应用程序标签页打开。" width="100%">

使用 Python 3.11+ 和 Google Chrome 从存储库目录安装：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ruin browser
```

运行 `ruin browser` 启动或重新连接到项目浏览器。每个 CLI 任务都使用 Python Playwright over CDP。默认端点是 `http://127.0.0.1:9222` 。当该端口空闲时，运行程序会在 `~/.ruin-everything/canvas-browser` 上启动带有专用配置文件的 Chrome。 CDP 连接保留现有的浏览器上下文设置，包括其下载行为。命令退出后，Chrome 保持打开状态。其他本地客户端可以连接到同一端点并通过其完整 URL 找到作业标签页。授予一名客户对每份申请的提交所有权。

<img src="docs/figures/tab-lifetime.svg" alt="两个命令连接到同一个 Chrome 进程。稍后运行可以恢复实时标签页；关闭它可以丢弃未保存的表单状态。" width="100%">

在此配置文件中打开 Outlook Web 并完成任何所需的 Microsoft 登录，然后再请求新的电子邮件代码。关闭作业标签页、退出 Chrome 或站点会话过期仍然会中断应用程序。聊天专用浏览器中的草稿必须单独恢复。

<a name="run-a-browser-click-task"></a>

## 运行浏览器点击任务

<img src="docs/figures/actions.svg" alt="该模型接收任务、标题和控制标签。它向浏览器返回一个操作 ID。下一个观察将创建一个新的快照。" width="100%">

使用 `python -m pip install -e '.[agent]'` 安装可选依赖项并设置 `OPENAI_API_KEY` 。为模型提供一个 HTTPS 起始页面和一个特定任务：

```sh
ruin "Open the help page" --site https://example.org --channel chrome
```

运行器将任务、页面标题和可见操作标签发送到所选模型。它直接单击所选控件并再次观察页面。一项任务可以使用一个标签页和最多 20 个步骤。

<img src="docs/figures/action-example.svg" alt="在一个快照中，说明性帮助中心按钮被分配了 ID 1。该模型可以通过该 ID 请求点击。" width="100%">

例如，如果可见按钮标记为 **Open guide** ，则模型可以选择其当前 ID。 URL 更改或快照中缺少 ID 会停止该步骤。被阻止的模型决策使页面保持开放状态以供检查。

<a name="local-credential-filling"></a>

### 本地凭证填写

<img src="docs/figures/autofill.svg" alt="在选定的 HTTPS 源处，密钥环可以填充凭据，并且 Chrome 可以在原始表单上提供保存的登录信息。" width="100%">

添加`--autofill`以使用系统密钥环和Chrome的登录表单。对于具有一个提交到所选 HTTPS 源的可见密码字段的表单，运行器单击空白字段，以便 Chrome 可以提供保存在 **浏览器配置文件** 中的凭据。在打开的标签页中完成登录。运行程序最多等待三分钟，让凭据字段消失，然后继续执行任务。它将帐户选择和表单提交留给登录 UI。 Chrome 模拟测试使用限制性脚本策略来验证相同标签页的连续性。

<a name="local-account-registration"></a>

#### 本地账户注册

<img src="docs/figures/signup.svg" alt="检查所选表单是否有明确的注册操作。匹配表单使用本地配置文件，后续代码字段可以使用新的域绑定 SMS。" width="100%">

运行 `ruin identity` 按名称选择电话区域、保存多个号码、选择默认值并在编辑时显示密码。离线编辑器使用浏览器的本机选择控件和电话号码库来进行拨号代码和国际格式设置。[python-电话号码](https://github.com/daviddrysdale/python-phonenumbers)

要使用 `--site` 手动设置浏览器任务，请创建具有仅限所有者权限 ( `chmod 600` ) 的 `~/.ruin/identity.json`。将 `auto_signup` 设置为 `true`，并为 `first_name`、`last_name`、`email`、`phone` 和 `default_password` 提供字符串值。该文件以纯文本形式存储密码。本地运行器在每个模型决策之前都会检查所选的 HTTPS 源，直到提交注册。它可以识别同源 POST 表单上的一个可见的 **Create Account** 、 **Create an Account** 、 **Register** 或 **Sign Up** 提交按钮，填写识别的字段，并检查标记的服务条款、使用条款和隐私政策框。在普通的同源表单上，它还可以填写一个空的、可编辑的联系电话字段。缺少配置文件值的可见匹配注册字段使标签页保持打开状态以供完成。

对于后续的单个一次性代码字段，运行器将检查 macOS Messages 长达 30 秒的时间，以检查自提交以来收到的传入文本并以 `@hostname #code` 结尾。需要对消息数据库的读取访问权限。 MCP 质询和接收结果包括报告本地设置的 `signup_policy` 字段。 Chrome 和 SQLite 装置练习表单提交、普通电话输入、跨源操作、消息年龄、方向和域匹配。

<a name="workday-accounts-and-signed-in-sessions"></a>

#### Workday 帐户和登录会话

<img src="docs/figures/account-session.svg" alt="Workday 分支在帐户创建和 Outlook 激活之前检查登录。会话分支定期检查单独的状态标签页。" width="100%">

在支持的英语 Workday 租户表单上，CLI 浏览器任务首先尝试本地电子邮件和密码。明确的缺少帐户消息将打开注册。一般登录失败会导致原始作业空缺。注册后，Ruin 检查登录的 Outlook 邮箱中是否有新的激活消息，遵循确切租户主机上的直接激活链接，等待可见的确认并返回职位 URL。该适配器支持本机 POST 表单和脚本驱动的 Workday 对话框，并具有可识别的提交控件。本地Chrome固定装置涵盖现有帐户、注册、激活和返回工作。生产租户布局和包装的电子邮件链接可能有所不同。

即使页头也有 Sign In 按钮，Ruin 也会定位当前 Workday 登录弹窗内的提交控件。遇到六位邮箱验证码时，它在 Outlook 新邮件中核对租户链接，只把唯一且明确标注的验证码填回原标签页，并等待网站确认激活。已在共享 Chrome 中核对 Jain Global 的真实弹窗控件，六位码激活流程使用模拟邮箱验证。

对于发送到现有标签页的代码，请使用站点发送 SMS 时记录的请求时间。可以选择将 `sms_senders` 添加到本地身份文件，将确切的主机名映射到其专用的发件人字符串。纯六位数代码必须来自该发件人。域绑定消息无需发件人条目即可工作。这两个路径都需要对 Mac Messages 数据库的读取访问权限。

```sh
ruin verify-sms --site "$VERIFICATION_URL" --requested-at "$REQUEST_UNIX_SECONDS"
ruin keep-alive --site "$STATUS_URL" --signed-in-text "Account overview" --interval 900 --timeout 86400
```

Keep-alive 会为选定的 HTTPS 状态页面打开一个单独的标签页。使用只读页面，其中包含登录视图特有的文本。该过程在每次访问后检查文本，在重定向或丢失文本时停止，并在完成后关闭自己的标签页。运行命令所需的持续时间。站点控制自己的会话生命周期。模拟 Chrome 检查涵盖重复的 GET 请求和原始标签页的保留。



要为本地填写提供凭据，请使用以下条目。可选的 TOTP 条目保存该站点的 Base32 种子。

```sh
keyring set ruin:https://example.org username
keyring set ruin:https://example.org password
keyring set ruin:https://example.org totp
```

<a name="verify-a-greenhouse-application-with-outlook-web"></a>

## 使用 Outlook Web 验证 Greenhouse 求职申请

<img src="docs/figures/email-verification.svg" alt="两条通道跟踪一个请求。收件箱向原始作业标签页提供匹配的代码，该标签页提交并检查回执。" width="100%">

在 macOS 或 Linux 上，附加到已启用 Outlook Web 并已打开原始 Greenhouse 作业标签页的本地启用调试的 Chrome 会话。将示例 URL 和雇主替换为确切的职位及其电子邮件中使用的姓名。在应用程序请求代码之前启动观察程序。现有的应用程序工作流程仍然拥有初始提交。

```sh
ruin verify-email --cdp http://127.0.0.1:9222 \
  --site https://job-boards.greenhouse.io/example/jobs/12345 \
  --company "Example Employer" --timeout 180
```

观察器拍摄可见 Outlook 收件箱行的快照，并等待其时间戳遵循请求窗口的新行或更新行。它检查雇主、主题措辞和 Greenhouse 发件人，从打开的消息中读取代码，并将其提交到原始作业标签页中。本地锁序列化观察者进程。在验证期间保持同一雇主的其他申请处于闲置状态。

<img src="docs/figures/mail-window.svg" alt="收件箱时间线示例：观察程序启动之前有一个旧行；可以检查唯一匹配的新行。两名新候选人停止了竞选。" width="100%">

在收件箱图中，当观察者于 10:00 开始时，09:59 消息已存在。观察者根据行中的雇主和验证措辞检查 10:01 候选人，然后检查打开的消息中的发件人。如果两个新的候选者匹配，它会在选择其中之一之前停止。这些时间说明了顺序；观察者使用实时运行中记录的时间戳。

<a name="recover-an-open-challenge"></a>

### 继续处理已打开的验证页面

<img src="docs/figures/email-recovery.svg" alt="恢复选项取决于表单：重新发送一次、提供原始请求时间或在结果不确定时检查原始标签页。" width="100%">

如果挑战在启动时已打开并提供重新发送控制，则它会在那里请求新代码。每次运行最多重新发送一次。

<img src="docs/figures/job-match.svg" alt="两个工作可以共享一个邮件主题。无需重新发送的恢复需要正文中的作业 ID。 ID 丢失或不同会使标签页保持打开状态。" width="100%">

<img src="docs/figures/embed-identity.svg" alt="示例嵌入 URL 将雇主参数与职位 ID 分开。观察者检查是否正好打开了一个匹配的标签页。" width="100%">

对于直接 Greenhouse 嵌入，请传递完整的引用 URL（包括 `for` 和 `token` ）。如果现有挑战没有重发控制，则从该职位的原始请求中提供 `--requested-at UNIX_SECONDS`。对于此恢复路径，消息正文还必须标识作业 ID。同一雇主的两个角色共享的主题无法确定哪个表单拥有该代码。另一个聊天的独立浏览器中的标签页必须在那里处理。

该原型支持英语、顶级 Greenhouse 表单和 Outlook 布局，公开消息标识符、时间戳、发件人地址和消息正文。缺少证据或不明确的匹配会导致验证停止。只有可见的回执才算成功。 *提交后，*也可能发生超时；重试之前请检查原始标签页。消息内容和代码位于模型循环之外。集成已通过浏览器装置进行了测试；与实时雇主表格和 Outlook 租户的兼容性尚未得到验证。

<a name="resume-an-authorized-ashby-application"></a>

## 继续处理已获授权的 Ashby 申请

<img src="docs/figures/ashby-receipt.svg" alt="用作证据的 Ashby 状态示例：同一职位 URL 上可见的 Success 标题和正式提交文本。" width="100%">

当审核的申请已达到验证时使用此工作流程。原始应用程序驱动程序拥有该职位的授权，并在同一标签页中完成实时挑战。使用确切的应用程序 URL 与该驱动程序一起启动回执观察程序：

```sh
ruin resume-ashby --cdp http://127.0.0.1:9222 \
  --site 'https://jobs.ashbyhq.com/EMPLOYER/JOB-UUID/application' --timeout 300
```

<img src="docs/figures/ashby-roles.svg" alt="原始驱动程序处理现有标签页中的挑战；回执观察者观察该标签页并发出状态更改。" width="100%">

CLI 附加到一个匹配的标签页，并在标准错误时发出 JSON 状态更改。在 `challenge_visible` 上，授权驱动程序使用当前小部件。使用 Python API 的驱动程序可以直接提供自己认可的处理程序：

```python
receipt = await resume_ashby(context, application_url, timeout=300,
                             directory=receipt_directory, on_event=report_status,
                             on_challenge=complete_authorized_challenge)
```

从 `ruin.agent.ashby` 导入 `resume_ashby`。处理程序每​​次运行都会接收一次原始 Playwright 页面。独立的 CLI 观察浏览器；它需要应用程序驱动程序或人员与小部件交互。完成的挑战可能会自动提交表格。保留任何现有的提交内容并观察其结果。启用的 Submit 按钮本身不足以证明发送另一个请求。

<a name="receipt-storage-and-retries"></a>

### 回执存储和重试

<img src="docs/figures/resume.svg" alt="重试已记录的应用程序会返回其保存的回执。未记录的申请将保持待处理状态，直到观察者看到正式成功为止。" width="100%">

仅当同一职位显示 Ashby 的可见 **Success** 状态和 **Your application was successfully submitted** 时，观察者才会记录成功。它在标准输出上以 JSON 形式返回回执，并在 `~/.ruin-everything/ashby-receipts.sqlite3` 中为每个职位存储一行。重试会返回存储的回执。超时、职位变更或不明确的标签页会产生错误，而不标记已提交的作业。外部申请跟踪工具应仅导入返回的回执。

<img src="docs/figures/uncertain-result.svg" alt="超时后，检查待处理的标签页或查找已保存的证据。回执丢失导致结果未知。" width="100%">

例如，当站点仍在处理申请时，挑战可能会消失。如果观察者超时，请在采取其他操作之前检查原始标签页。如果该标签页稍后显示正式回执，请使用相同的 URL 重新运行观察程序以捕获它。

所示回执是一个例子。回执图案来自已完成的 Baseten 应用程序。可重用命令在 Chrome 中使用模拟 Ashby 页面进行了测试，包括隐藏回执、职位变更、重复标签页以及标签页关闭后的重试。

<a name="connect-an-agent-over-mcp"></a>

## 通过 MCP 连接代理

<img src="docs/figures/mcp-receipts.svg" alt="代理通过职位 URL 检查本地 Ashby 日志。它可以离线返回保存的证据或查看原始标签页以获取新回执。" width="100%">

正式版本默认包含 MCP 服务。支持目录安装的客户端可直接运行 `uvx ruin-everything@0.2.0`。 [GitHub 发布记录](https://github.com/yuki4266/ruin-everything/releases)

向客户提供准确的工作 URL 并描述您所看到的内容。如果问题是Ashby申请是否通过，客户首先检查回执日志。如果表单正在等待验证，客户端将检查打开的标签页。

<img src="docs/figures/challenge-routing.svg" alt="对于一个确切的职位 URL，检查员会识别 Greenhouse 电子邮件代码提示或 Ashby reCAPTCHA 框架并返回观察到的状态。" width="100%">

| 工具 | 什么时候调用它 | 结果 |
| --- | --- | --- |
| `ruin_auto_register` | 所选的注册或联系表单将在其确切的 HTTPS URL 上打开。 | 本地配置文件操作和当前注册政策。提交的表格仍然需要验证。 |
| `inspect_application_challenge` | Greenhouse 要求提供八个字符的电子邮件代码，连接器报告 `[one-time authentication code withheld]` ，或者 Ashby 显示 reCAPTCHA 网格。还可以使用它来查找丢失的受支持表单。 | 提供者和可见状态。丢失或重复的标签页会得到自己的结果。该表格保持打开状态。 |
| `get_ashby_receipt` | 切换时，即使 Chrome 关闭 | 已保存的回执或 `unrecorded` 。记录缺失导致结果未知。 |
| `watch_ashby_receipt` | 原申请表仍然打开，结果不确定 | 现有回执或同一工作的新证据。超时是一个工具错误。观察者将表格保持打开状态。 |

安装[紫外线](https://docs.astral.sh/uv/getting-started/installation/)一次。在具有 JSON 配置的 MCP 客户端中，此示例运行最新的[PyPI 发布](https://pypi.org/project/ruin-everything/)。客户端必须能够在其 PATH 上找到 `uvx`。 `uvx` 的绝对路径也适用。

```json
{
  "mcpServers": {
    "ruin-everything": {
      "command": "uvx",
      "args": [
        "--isolated", "--refresh",
        "--from", "ruin-everything[mcp]",
        "ruin-mcp"
      ],
      "env": { "RUIN_AUTO_UPDATE": "0" }
    }
  }
}
```

要直接跟踪 GitHub 分支，请将 `--from` 设置为 `ruin-everything[mcp] @ git+https://github.com/yuki4266/ruin-everything.git@main` 。两种配置都会启动实际的 `ruin-mcp` 可执行文件。两个版本的冒烟测试验证了 Git 和包路径上的刷新。现有的可编辑安装仍然可以直接启动它。

要为您的用户帐户注册服务器，请为您的客户端运行命令。打开一个新会话以获取工具列表。

```sh
codex mcp add ruin-everything --env RUIN_AUTO_UPDATE=0 -- uvx --isolated --refresh --from 'ruin-everything[mcp]' ruin-mcp
claude mcp add --scope user --transport stdio ruin-everything -e RUIN_AUTO_UPDATE=0 -- uvx --isolated --refresh --from 'ruin-everything[mcp]' ruin-mcp
```

<a id="first-mcp-call"></a>

### 试用第一个 MCP 工具

连接客户端后，可以复制下面这句话试用。示例使用虚构的职位网址，关着 Chrome 也能运行，无需注册或填写个人资料。

> 请对 `https://jobs.ashbyhq.com/example/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/application` 调用 `get_ashby_receipt`，告诉我返回的状态。

首次安装时应返回 `unrecorded`，表示工具已查询本机记录，没有找到这个示例的回执。我们已用 PyPI 发布版验证这次只读调用。

该存储库包括[路由指令](AGENTS.md#ruin-everything-application-routing)用于 Codex 并从以下位置导入它们[克劳德.md](CLAUDE.md)。要将它们应用到其他工作区，请将应用程序路由部分复制到用户级 `~/.codex/AGENTS.md` 或 `~/.claude/CLAUDE.md` 中。客户端权限和站点验证仍然适用于 Duo 、 PayPal 和其他不受支持的提供商。

所有四个工具均采用 `site`。检查员默认检查一次。将 `wait_seconds` 设置为 1–300 以观察同一标签页中 `pending` 的变化。在 CLI 中，使用 `ruin watch --site "$JOB_URL" --timeout 30` 。手表在检测到受支持的状态、丢失原始标签页或达到时间限制后结束。

在本地 Chrome 模拟中，仅给出 Greenhouse URL 和八字符代码症状的新 Codex CLI 会话选择 `inspect_application_challenge` 作为其第一个工具调用并返回 `email_verification` 。模拟表格保持空白。

Ashby 回执观察器采用 `timeout_seconds`（默认 15，范围 1–300）。返回的回执包含 `state` 、 `site` 、 `observed_at` 和站点的确认 `message` 。应用程序驱动程序拥有表单交互。超时后，请在考虑再次提交之前再次检查同一 URL。

服务器在 stdio 上使用官方 Python MCP SDK。浏览器自动化客户端（例如 Playwright MCP）可以通过与 `--cdp-endpoint http://127.0.0.1:9222` 连接到同一本地 Chrome 来与其一起运行。集成测试等待 Chrome 通告其本地调试端口，然后将两个连续的 SDK 客户端连接到模拟雇主页面。[Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) · [Playwright MCP 连接选项](https://github.com/microsoft/playwright-mcp#configuration)

<a name="how-updates-reach-your-machine"></a>

## 更新如何到达您的计算机

<img src="docs/figures/updates.svg" alt="三个更新计划：uvx 在 MCP 启动时解析软件包，启动时每六个小时检查一次直接安装，以及在每个工作流程开始时刷新站点规则。" width="100%">

| 有什么变化 | 何时更新 |
| --- | --- |
| 通过 uvx 进行 MCP 封装 | 在下一次服务器启动时，uv 会解析配置源中可用的最新版本。长时间运行的服务器会保留其加载的代码，直到重新启动。初始安装和在线刷新需要网络访问。 |
| 直接安装 | CLI 和 MCP 启动计划每次安装最多每六个小时进行一次安静的背景检查。如果本地 `main` 跟踪 `origin/main` 且工作区干净，就会执行快进更新。常规 pip 安装会检查 PyPI 是否有更新版本。安装的 uv 工具使用自己的升级命令。设置`RUIN_AUTO_UPDATE=0`自行管理版本。 |
| 网站规则 | 每个新的 Greenhouse 验证或实时 Ashby 观测都要求项目的[选择器文件](ruin/rules/sites.json)有两秒的网络超时。工作流在完成过程中都会保留其初始快照。脱机或无效更新回退到 `~/.ruin/sites.json` 处的最后一个有效缓存，然后回退到打包的默认值。将 `RUIN_RULE_UPDATES=0` 设置为使用捆绑副本。 |

规则文件描述 Ashby 回执元素、Greenhouse 验证输入和电子邮件代码模式以及 Outlook 行和消息正文。安装的适配器强制执行可信来源、发件人身份、作业匹配和回执措辞。对这些检查的更改需要发布代码。

对于维护人员，配置一个[PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)对于项目 `ruin-everything`，所有者 `yuki4266`，存储库 `ruin-everything`，工作流程 `publish.yml` 和环境 `pypi`。推送到 main 会在 `pyproject.toml` 中构建版本，并将工作流程运行号作为第四个发布组件。对于标记版本，设置项目版本并推送匹配的标记（例如 `0.2.0` 和 `v0.2.0` ）。两条路线都运行浏览器测试，构建并检查轮子和源代码分发，然后使用 GitHub 的 OIDC 身份进行发布。[发布工作流程](.github/workflows/publish.yml) · [uv工具更新](https://docs.astral.sh/uv/concepts/tools/)

<a name="example-read-courses-after-school-sign-in"></a>

## 示例：登录学校账户后获取课程列表

<img src="docs/figures/session.svg" alt="活动会话直接返回课程列表。如果 Canvas 重定向，请完成 Duke 登录以恢复相同的查找。" width="100%">

Duke Canvas 适配器演示了交互式登录后如何恢复任务。在共享配置文件中运行查找：

```sh
ruin courses
```

结果包含课程名称和链接。使用`--json`进行结构化输出：

<img src="docs/figures/course-output.svg" alt="说明性 JSON 输出，带有示例课程名称和缩写链接。" width="100%">

要显式选择现有的本地调试端点，请运行：

```sh
ruin courses --cdp http://127.0.0.1:9222 --json
```

登录分支最多等待 180 秒，以便学校将浏览器返回到 Canvas 。将 `--timeout 300` 设置为更长的等待时间。 Duo 批准在学校登录路径上进行。[Duke设备恢复](https://oit.duke.edu/help/articles/kb0036398/)

<a name="verification"></a>

## 验证

<img src="docs/figures/checks.svg" alt="本地测试练习会话重用、控制标签和模型引导的点击。实时检查包括课程发现和重复查找。" width="100%">

更新测试涵盖重叠启动检查、规则快照之间的更改、无效下载和离线回退。运行时检查验证了跨独立 CDP 连接的共享 Chrome 标签页。对于浏览器测试，请安装 Playwright Chromium 版本或使用已安装的 Chrome 。运行`python -m unittest discover -s tests -v`。安装代理附加组件以包括模拟模型测试。对于已安装的 Chrome，请在命令前加上 `RUIN_TEST_CHANNEL=chrome` 前缀。

登录后，实时 Duke 运行会返回课程链接。在访问学校登录路线后，使用相同配置文件的第二次运行也返回了列表。没有测量Duo提示的数量。一般点击循环已通过模拟模型响应进行了测试。

手绘图表是可编辑的 SVG。他们使用 Rough.js 线条和 Kalam 字体。[图源](docs/figures) · [粗糙.js](https://roughjs.com/) · [卡拉姆字体许可](docs/figures/Kalam-LICENSE.txt)

[发展规划](PLAN.md) · [贡献和数字指南](AGENTS.md) · [MIT 许可证](LICENSE)

<a id="community"></a>

## 参与 Ruin Everything

<img src="docs/figures/community.svg" alt="在 GitHub 报告问题、分享用法和提交修改的三个入口。" width="100%">

你用哪个 MCP 客户端跑通了 Ruin？欢迎[分享配置和一次工具返回的结果](https://github.com/yuki4266/ruin-everything/discussions/categories/show-and-tell)，方便下一位用户复现。如果卡在安装或连接环节，可以[在问答区提问](https://github.com/yuki4266/ruin-everything/discussions/categories/q-a)。

[报告问题](https://github.com/yuki4266/ruin-everything/issues/new?template=bug.yml) · [提出想法](https://github.com/yuki4266/ruin-everything/discussions/categories/ideas) · [贡献翻译、测试或修复](CONTRIBUTING.md)

### 贡献者

感谢每一位试跑流程、回答问题和提交修改的人。下方头像来自 GitHub 的提交贡献记录。

<a href="https://github.com/yuki4266/ruin-everything/graphs/contributors"><img src="https://contrib.rocks/image?repo=yuki4266/ruin-everything" alt="查看 GitHub 提交贡献者"></a>

## Star 历史

<a href="https://www.star-history.com/?repos=yuki4266%2Fruin-everything&amp;type=date"><img src="docs/figures/repository-activity.svg" alt="Ruin Everything 的 GitHub 活动快照，展示 Star、Fork、贡献者及最近七天的活动。" width="100%"></a>

点击快照可查看最新的 Star 走势。

⭐ [如果 Ruin 帮你找回了中断的浏览器任务，欢迎到 GitHub 点一颗 Star。](https://github.com/yuki4266/ruin-everything)
