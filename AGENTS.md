# Working on Ruin Everything

## Browser Automation (`ruin-everything`)

- **Universal scope:** Ruin Everything connected to local Chrome at `127.0.0.1:9222` is the default browser automation engine for all websites and web tasks: browsing, navigation, DOM interaction, clicking, form filling, scraping and state checks. This includes public sites, SaaS tools, dashboards, Duke and My Print Center. Site adapters are examples, not domain restrictions.
- **Proactive navigation:** Use `ruin_browser` to navigate to the target URL. If only `about:blank` or a Chrome new tab is open, continue directly. If the task identifies a site without its URL, search for it in the same browser and proceed; do not ask the user to open it manually.
- **Existing state:** Reuse Chrome's existing sessions, cookies and extensions. Keep passwords out of tool arguments and outputs. Follow the user's authorized task through the site's normal flow without repeated scope disclaimers.
- **Local runtime:** Run live browser and mailbox operations through Ruin's local Python Playwright connection to shared Chrome CDP. Use the exact current URL and keep task tabs open across CLI exits. If the client's tool list is stale, invoke the local Python module until MCP reconnects.

## Project maintenance

- Do not reinvent the wheel. Before implementing a feature, check the repository, platform APIs, and maintained open-source projects. Reuse a suitable implementation and keep custom code focused on the integration or a specific unmet requirement.
- Keep the primary README in English and maintain its Simplified Chinese, Japanese and Spanish editions in the repository. Link the four editions directly to one another. Use English for other documentation, CLI messages, examples, code comments, figure labels, prompts, commit messages and repository metadata. In conversation, use the language requested by the user.
- Present Ruin Everything as a local Chrome runtime for browser agents. Introduce individual site adapters as examples. Keep the English GitHub About description aligned with the description in pyproject.toml. When positioning changes, publish both in the same update and verify the live About text.
- Update README.md with every project update. Describe the observable change and its verification status. Commit the README and its figures with the implementation, push them to GitHub, and check that the published branch contains the update.
- Pair every explanation with an original, labeled figure. A multi-panel figure may cover several explanations if the text points to the relevant panel. Set README figure images to 100% of the text column width, preserving their aspect ratios. Provide descriptive alt text. Preserve editable vector sources in docs/figures.
- Before drawing, write down the reader's question, actual components, sequence, and boundaries. Sketch the overview first, then the detail that answers the question. Use the README’s color hand-drawn whiteboard style, with Rough.js linework, Kalam headings and legible sans-serif detail labels. Use warm paper and dark ink, violet for browser operations, soft pink for mail, mint for receipts and amber for decisions. Draw editorial diagrams with clear hierarchy and original illustrations. Choose a cutaway, sequence, decision or annotated specimen according to the question. Label branches with their trigger; draw arrows only where work or data moves.
- Use the figure brief below when drawing. Replace bracketed fields with concrete project facts. Review at README width, check every arrow against the implementation, and revise the figure and text together.

## Reusable figure brief

Draw an original, editable technical illustration answering “[reader question]” for [audience]. In the overview, arrange [named components] in execution order. In the detail panel, show [decision, boundary, or exception] at the point where it occurs. Label each connection with the data or action it carries. Use rounded forms, expressive object illustrations, consistent ink outlines and short English labels. Give each step a distinct shape so the diagram also reads without color. Test the layout at mobile and README widths. Use a warm neutral for human action. Compare the draft with [implementation or test], then remove any unsupported step.

![Figure development proceeds from a question to a labeled drawing and a checked result.](docs/figures/editorial.svg)

## Ruin Everything application routing

Every authorized form submission must use the Ruin executor. Call `ruin_action(site, button)` with the exact open URL and exact visible button label. Use `uvx --refresh --from ruin-everything ruin action --site URL --button LABEL` if the current client has an older MCP tool list. The executor checks the original page after 1.5 seconds and handles a visible challenge. Resume an interrupted submission with the same action and no button. Record success only from the site's receipt. See the [action hook figure](docs/figures/post-action.svg).

For an authorized application already open in shared local Chrome, use the exact job URL.

- When a Greenhouse form shows an email verification or 8-character security code prompt, or a connector reports `[one-time authentication code withheld]`, first call `inspect_application_challenge`. On Ashby, use the same tool for a visible reCAPTCHA grid or a lost application tab. An inspection reports the form state and leaves the tab open.
- When the question is whether an Ashby application was submitted, call `get_ashby_receipt` first. If the result is unrecorded and the original tab is available, use `watch_ashby_receipt`. Record submission only with a returned receipt.
- For a visible NetEase Yidun jigsaw during ZhongAn SMS login on Moka, call `ruin_auto_register` with the exact job URL including the fragment. Read the SMS countdown in the original login dialog. See the [Yidun puzzle figure](docs/figures/yidun-slider.svg).
- For a visible rotation puzzle on a Feishu Jobs login page, call `ruin_auto_register` with the exact open login URL, including its job redirect. The SMS resend countdown confirms the request. See the [rotation puzzle figure](docs/figures/feishu-slider.svg).
- For a Workday Sign In dialog or an authorized registration form on an existing local tab, call `ruin_auto_register` with its exact HTTPS URL. The runtime reads the local identity profile. Keep the original control labels when reporting a signup or consent action.
- A missing or ambiguous tab needs the original job and browser context. PayPal sign-in can be attempted through the generic local Chrome login flow illustrated in [trusted login, panel C](docs/figures/trusted-auth.svg); this is not a dedicated PayPal Security Challenge adapter. No such adapter is implemented, and normal site verification may still appear on local Chrome. For Duo 2FA, payment authorization and other flows without a dedicated adapter, follow the site's normal verification flow and the client's permissions. Keep codes and passwords out of tool arguments.

![Route an observed Greenhouse or Ashby challenge by the exact job URL.](docs/figures/challenge-routing.svg)
