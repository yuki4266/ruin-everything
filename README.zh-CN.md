<p align="right"><a href="README.md">English</a> &nbsp;·&nbsp; <strong>简体中文</strong> &nbsp;·&nbsp; <a href="README.ja.md">日本語</a> &nbsp;·&nbsp; <a href="README.es.md">Español</a></p>

# <img src="docs/figures/tab-wave.webp" alt="Ruin Everything：一张回执在蓝色和淡紫色的浏览器标签页中冲浪" width="100%">

<p align="center">
  <a href="https://github.com/yuki4266/ruin-everything/stargazers"><img src="docs/figures/badges/stars.svg" alt="GitHub 星标"></a>
  <a href="#use-a-shared-local-chrome-window"><img src="docs/figures/badges/python.svg" alt="需要 Python 3.11 或更高版本"></a>
  <a href="#connect-an-agent-over-mcp"><img src="docs/figures/badges/mcp.svg" alt="通过 stdio 的 MCP"></a>
  <a href="LICENSE"><img src="docs/figures/badges/license.svg" alt="MIT 许可证"></a>
</p>

**所有网站共用的默认本机 Chrome 运行时。** Ruin 通过 `127.0.0.1:9222` 连接浏览器智能体与 Chrome，执行浏览、导航、DOM 交互、填表、内容提取和多步骤网页任务，复用已有会话、Cookie 和扩展程序。求职及学术机构适配器是可选示例。

[设置Chrome](#use-a-shared-local-chrome-window) · [连接 MCP 客户端](#connect-an-agent-over-mcp) · [查看已测试的内容](#verification) · [试用第一个 MCP 工具](#first-mcp-call) · [参与贡献](#community)

## 本地 ATS 密码与账号恢复

图 A：运行一次 `ruin ats-setup`，在权限为 `0600` 的 `~/.ruin/.env` 中生成固定的 24 位密码并启用 `ATS_AUTO_RECOVER`。已有有效 `ATS_DEFAULT_PASSWORD` 会保留；环境变量优先，`RUIN_ATS_ENV_FILE` 可指定其他私有配置文件。密码不出现在命令参数或设置结果中。邮箱与自动注册偏好继续使用本地身份档案，其他账号的密码不变。

图 B：在选定的 iCIMS / Workday 租户内，根据实际字段和标题区分登录与首次设密，支持 iCIMS 内嵌表单。明确的凭据错误出现后，优先使用可见注册入口；账号已存在则回到登录；统一 ATS 密码只重试一次，仍失败才点击可见的忘记／重置密码入口。尚未报错时可先尝试 Chrome 已填密码。每个步骤按租户和邮箱限制在十五分钟内执行一次，重连 CDP 后仍有效；不会猜测注册地址。凭据表单须提交到同一 HTTPS 来源，操作经过 Ruin 执行器。

该流程已接入 `ruin_browser`、`ruin_action`、`ruin_auto_register` 和模型浏览器任务；也可直接运行 `ruin ats-account --site 'EXACT_CURRENT_HTTPS_URL'`。图 C：`reset_email_requested` 只表示网站接受了重置请求，不等于邮件送达、登录或申请成功。邮件／验证码未完成时保留 `email_verification_pending`；可见的设密表单自动使用本地密码；申请仍以网站回执为准。原有 Workday 邮箱激活流程继续保留。

<img src="docs/figures/ats-recovery.svg" alt="本地私有 ATS 密码、选定租户内的注册与单次密码重试、邮件恢复边界及申请回执。" width="100%">

验证：新增十一项配置／浏览器测试和原有五项 Workday 测试通过，覆盖配置权限与稳定性、环境变量优先级、错误分支、账号已存在、嵌套表单、身份与同源检查、重复抑制。Planview 5149 实测为登录表单，统一密码被拒绝，网站确认重置请求；Outlook 和垃圾邮件中尚未找到对应邮件，因此不声称已重置密码、上传简历或提交申请。提供方行为参见 [iCIMS 候选人帮助](https://team.icims.com/jobseekerhelp)。本次为仓库更新，未发布新版 PyPI 包。


## 嵌套 hCaptcha 挑战

图 A：优先识别 hCaptcha，再使用通用滑块规则。九宫格使用 `.task-image` 的明确索引；画布支持坐标点选和二维拖拽；未勾选的复选框点击控件中心。隐藏的外层 iframe 会被排除。无法识别或答案不确定时保留待处理状态，不再误报“无法定位唯一目标”。

图 B：逐层换算 iframe 内容区原点，计入边框、内边距、滚动和正向轴对齐 CSS 缩放。通过 Playwright 的 Chromium 鼠标事件按顶层视口坐标操作，最后点击 `.button-submit`。图 C：验证通过或跳转不等于申请提交成功；仍以网站回执为准，不重复执行待处理的表单提交。

<img src="docs/figures/hcaptcha.svg" alt="嵌套 iCIMS 与 hCaptcha 的检测、九宫格和画布分支、内容区坐标换算以及验证与申请回执的区别。" width="100%">

验证：新增七项隔离 Chromium 测试及原有七项提交后处理测试通过，覆盖跨域嵌套、隐藏副本和祖先、复选框、二维拖拽、缩放画布、不确定及不支持的题型。Planview 5149 原标签页的画布拖拽此前被误判为水平滑块；修复后的执行器使用助手核对的坐标完成拖拽，网站跳转到 iCIMS 登录。本地 Ollama 仍为默认视觉模型，本次实测不代表无人值守识别准确率。现有凭据被登录页拒绝，尚未上传简历，也没有申请回执。更新位于本仓库，已安装的 MCP 服务需重新连接加载；未发布新版 PyPI 包。


## 通用浏览器自动化

所有网站默认使用 `ruin_browser`。图 A 展示共享本地运行时，图 B 展示标签页选择：`navigate` 优先复用目标网址的现有标签页，其次复用唯一的空白页，否则新建标签页。可用 `site` 明确指定当前标签页。任务给出站点名称但没有网址时，直接导航到搜索引擎查找，不等待用户手动打开页面。

```json
{"operation":"navigate","url":"https://example.org"}
```

图 C 展示后续操作。把返回的当前 URL 作为 `site`，执行 `inspect`、`read`、`click`、`fill`、`press` 或 `select`。检查返回可见文本和控件选择器，不读取输入框值。修改操作必须匹配唯一可见元素；`value` 提供文本、按键或选项值。点击和 Enter 经过现有 Ruin 执行器。`tabs` 列出当前网址。跨域跳转和后续调用继续使用同一浏览器，标签页保持打开。文本最多返回 24,000 字符、控件最多 300 个；可通过 `read` 和更精确的选择器读取详情。

<img src="docs/figures/universal-browser.svg" alt="Ruin 连接智能体与共享 Chrome，选择目标页或空白页，再返回当前 URL、可见文本和控件供后续操作。" width="100%">

验证：五项隔离浏览器测试和 stdio MCP 集成测试通过，覆盖空白页复用、会话 Cookie、普通表单、跨域继续、标签页歧义及其他页面保留。还在本机 Chrome 实测了从空白页导航到搜索页。本次更新已进入仓库；使用本地检出或 Git 源重新连接 MCP 后可加载 `ruin_browser`，尚未发布新的 PyPI 版本。


| 在您的浏览器中 | Ruin 可以做什么 |
| --- | --- |
| Greenhouse 求职申请要求输入邮箱验证码 | [在 Outlook 中找到与申请对应的新邮件并填入验证码。](#verify-a-greenhouse-application-with-outlook-web) |
| 提交后关闭了 Ashby 标签页 | [用职位的完整 URL 查询已保存的提交回执。](#receipt-storage-and-retries) |
| Workday 要求登录 | [使用本机身份档案登录，或在支持的网站激活账号后回到职位页。](#workday-accounts-and-signed-in-sessions) |
| 有多个国家或地区的手机号 | [在离线身份编辑器中选择默认号码。](#local-account-registration) |

<a name="choose-a-starting-point"></a>

## 在后台处理学术机构登录

运行 `ruin watch` 后，监听器每 500 毫秒检查共享 Chrome 中已有和新开的标签页。它可以在 IEEE Xplore、ACM Digital Library 和 Springer Nature Link 查找并选择 Duke University，跟随出版商跳转到 Duke SSO，由 Chrome 提供已保存的登录信息。已有的信任配置可关闭密码下拉选择。Duo 按浏览器中的正常流程进行。

macOS 上从长期保留的安装环境运行 `ruin watch --install`，服务会随用户登录启动，并在共享 Chrome 恢复后重连。运行 `ruin watch --uninstall` 可移除服务。`ruin watch --site URL` 继续用于检查单份申请的验证状态。

<img src="docs/figures/academic-watch.svg" alt="后台巡检学术标签页并通过 Duke 获取机构访问。" width="100%">

已在 IEEE 实测机构查询、跳转 Duke，以及通过现有 Duke 会话下载出版商 PDF。ACM 和 Springer 的机构查找、新开标签页及重复操作抑制已通过隔离浏览器测试。

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

#### 飞书招聘的旋转拼图

旋转拼图出现后，在本地配置中启用 `auto_signup`，将当前飞书招聘登录页的完整网址传给 `ruin_auto_register`。如下图所示，工具比对内外圆环的边缘，拖动一次滑块。在乐信圣文招聘网站实测时，页面提示“验证通过”，随后显示“重新获取(30s)”。工具看到倒计时后返回 `sms_requested`，拼图仍待确认时返回 `slider_pending`。

<img src="docs/figures/feishu-slider.svg" alt="在原登录页拖动滑块，对齐内外圆环。重新获取短信的倒计时确认请求已发出。" width="100%">

#### 众安校园招聘的短信登录

在众安校园招聘的 Moka 职位页看到网易易盾拼图后，启用本地 `auto_signup`，把包含 `#/job/…` 的完整网址传给 `ruin_auto_register`。如下图所示，插件在原标签页比对拼块轮廓与缺口，再横向拖动。众安实测中，登录框显示了“重新获取（56）”。插件确认短信倒计时后返回 `sms_requested`，验证结果待确认时返回 `slider_pending`。

<img src="docs/figures/yidun-slider.svg" alt="拼块横向移动至匹配的缺口，登录框随后显示重新获取短信的倒计时。" width="100%">

### 表单提交后的自动验证

已授权的表单提交统一调用 `ruin_action(site, button)`，命令行可用 `ruin action --site URL --button LABEL`。传入原标签页的完整网址和按钮名称。执行器点击一次，从第 1.5 秒开始检查原页及可见子框架，持续观察至第 6 秒以接住延迟加载的验证。只传网址可接管已出现的验证。重试只操作验证组件，投递结果以官网回执为准。

如下图，横向拼图使用 ddddocr 和 OpenCV 在原图上定位缺口，换算显示比例、扣除拼块起点，并在松手前校正位置。浏览器回归用例覆盖延迟跨域弹窗、缩放和偏移、双层 Canvas、带头像横幅的普通预览及九宫格控件。图片九宫格与单层视觉拼图使用本机 Ollama 视觉模型，默认安装命令为 `ollama pull qwen3-vl:2b-instruct`。三轮后验证仍在时返回 `challenge_pending` 并保留原页。 众安实测已取得官网成功回执，投递记录确认进入初筛。

<img src="docs/figures/post-action.svg" alt="提交一次后自动检查验证组件，处理拼图并另行核验官网回执。" width="100%">


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
| `ruin_browser` | 所有网站的默认浏览、导航、交互和提取入口。 | 共享 Chrome 中的当前 URL、可见页面状态或操作结果。 |
| `ruin_action` | 已授权表单的完整网址与可见按钮名称。 | 点击后自动处理验证。只传网址可继续当前验证。 |
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

该存储库包括[路由指令](AGENTS.md#ruin-everything-application-routing)用于 Codex 并从以下位置导入它们[克劳德.md](CLAUDE.md)。要将它们应用到其他工作区，请将应用程序路由部分复制到用户级 `~/.codex/AGENTS.md` 或 `~/.claude/CLAUDE.md` 中。可以通过通用的本机 Chrome 登录流程尝试登录 PayPal（[受信任登录示意图 C](docs/figures/trusted-auth.svg)）。目前尚未实现 PayPal Security Challenge 专用适配器；本机 Chrome 仍可能出现正常的站点验证。这是基于代码检查的文档澄清，并不表示已经验证实际 PayPal 登录成功。Duo 验证码和手机推送仍使用正常的站点验证；下方“持久会话与 Duke 已保存凭据登录”说明已填表单和设备信任的自动推进。

五个专用工具采用 `site`；`ruin_browser` 还支持无需已打开目标页的标签列表和导航。检查员默认检查一次。将 `wait_seconds` 设置为 1–300 以观察同一标签页中 `pending` 的变化。在 CLI 中，使用 `ruin watch --site "$JOB_URL" --timeout 30` 。手表在检测到受支持的状态、丢失原始标签页或达到时间限制后结束。

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

### 受信任登录配置

<img src="docs/figures/trusted-auth.svg" alt="当前任务精确匹配登录规则后点击一次；Chrome 密码快捷键需单独开启。" width="100%">

图 A 展示新增的 `~/.ruin-everything/trusted-auth.json` 中的 `trusted_oauth_clients`。开启 `--autofill` 后，当前任务可执行已配置的登录、SSO、Stay signed in 或 Trust this browser 按钮。规则匹配 HTTPS 来源、路径和按钮，每条只尝试一次。图 D 新增 `https://*.greenhouse.io`、`https://*.myworkdayjobs.com` 和 `https://*.duke.edu`，支持多级子域名；精确条目优先。凭据与动作仍绑定当前任务的租户来源。[配置示例](docs/trusted-auth.example.json) 包含 Glama、Greenhouse、Workday 和 Duke SSO，尚未验证的按钮规则留空。

图 B 中的 GitHub OAuth 授权还需匹配应用 ID、完整回调地址和权限范围；任务文字不会扩大权限。图 C 为可选 Chrome 密码下拉：keyring 无密码时聚焦并发送 ArrowDown、Enter。没有建议项时 Enter 可能提交表单，因此这只是一次键盘尝试，不保证自动填充或永久登录。

Chrome 模拟页面已验证匹配、权限变更拒绝、单次尝试及密码框排除规则；原生密码建议和生产授权页尚未实测。详见[配置说明](docs/trusted-auth.md)。现有浏览器权限要求仍然适用。

GitHub 授权按钮可使用默认标准选择器，无需预填按钮名称；应用 ID、回调和权限校验仍为必需。Chrome 模拟页面已验证域名边界、端口、跨租户拒绝及默认选择器。Glama 实际提交尚未验证。

示例现包含 `https://paypal.com` 和 `https://*.paypal.com` 的密码下拉选择（图 C）。操作列表为空，不预先放行登录、支付或外部授权按钮。边界测试覆盖根域、多级子域、伪装后缀、HTTP 和其他端口；尚未验证真实 PayPal 登录。

## 持久会话与 Duke 已保存凭据登录

<img src="docs/figures/saved-login.svg" alt="A: persistent Chrome profile. B: filled Duke login and Duo device trust. C: wait 15 seconds before reporting remaining verification." width="100%">

图 A：Chrome 使用固定目录 `~/.ruin-everything/canvas-browser`。Ruin 在浏览器未运行时保留现有配置，写入 `session.restore_on_startup = 1` 并用 `--restore-last-session` 启动。连接已运行的 Chrome 时不改写其配置文件；请在 `chrome://settings/onStartup` 选择“继续浏览上次打开的网页”。新版 Chrome 可能将此设置存入 Secure Preferences。

图 B：`ruin_browser`（包括 inspect/read）、`ruin_action` 和 CLI 任务在当前任务标签中自动提交已填好用户名和密码的 Duke 登录表单，经由执行器点击唯一的 `#Submit` 或已识别登录按钮，且表单必须提交到 Duke 同源地址。支持 HTTPS `*.duosecurity.com` 上的设备信任按钮，包括 Duke 内可见的 Duo iframe。学术监听器仅在已开始的机构登录流程中确认信任。同一文档不会重复提交，凭据不输出到工具结果。

图 C：等待自动填充或验证 15 秒，每次自动登录或信任点击后再等待 15 秒。验证码、手机推送或空凭据表单仍未完成时才提示，并保留原标签页。跳转不等于登录成功证明；会话与设备信任期限由学校决定，不保证永久登录或固定 30 天。

验证：隔离浏览器测试覆盖真实重启后的 Session Cookie 恢复、已保存登录、延迟填充、信任按钮、iframe、域名检查、重复点击抑制及完整 15 秒等待。本机 Chrome 已修改并重新加载验证启动设置。当前没有打开的 Duke/Duo 验证页，尚未完成真实端到端验证。重新连接 MCP 可加载新工具说明。 本机安装的 Google Chrome 重启测试也通过；完整回归通过 67 项，最终集成后补测的动作恢复和重新绘制场景均通过。
