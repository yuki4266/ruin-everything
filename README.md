# Ruin Everything

**A local Chrome runtime for browser agents.**

Your agent fills out a form. The site asks for a code. The run ends. Starting over means typing the same answers again and wondering whether the first submission went through.

Ruin Everything keeps the original tab open in Chrome on your machine. A later run can reconnect, finish verification where the site allows it, and check the site's response. On Ashby, the runner can return the saved receipt for that job even after the tab closes.

![Ruin Everything connects a CLI to the local Chrome session. A later run can reattach and continue in an open application tab.](docs/figures/architecture.svg)

[Set up Chrome](#use-a-shared-local-chrome-window) · [Click tasks](#run-a-browser-click-task) · [Greenhouse](#verify-a-greenhouse-application-with-outlook-web) · [Ashby](#resume-an-authorized-ashby-application) · [Canvas example](#example-read-courses-after-school-sign-in)

## Choose a starting point

![Command guide mapping five starting states to browser, generic click tasks, verify-email, resume-ashby and courses.](docs/figures/command-guide.svg)

For a new task, start the shared browser and open the target site. For an interrupted application, choose the site-specific watcher and pass the original job URL. Generic click tasks open a new tab.

## Use a shared local Chrome window

![Two independent runner connections attach to a local Chrome profile and keep the same application tab open.](docs/figures/local-chrome.svg)

Install from the repository directory with Python 3.11+ and Google Chrome:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ruin browser
```

Run `ruin browser` to start or reconnect to the project browser. Every CLI task uses Python Playwright over CDP. The default endpoint is `http://127.0.0.1:9222`. The runner launches Chrome with a dedicated profile at `~/.ruin-everything/canvas-browser` when this port is free. The CDP connection preserves the existing browser context settings, including its download behavior. Chrome stays open after the command exits. Other local clients can attach to the same endpoint and locate the job tab by its full URL. Give one client ownership of submission for each application.

![Two commands connect to the same Chrome process. A later run can recover a live tab; closing it can discard unsaved form state.](docs/figures/tab-lifetime.svg)

Open Outlook Web in this profile and complete any required Microsoft sign-in before requesting a fresh email code. Closing the job tab, quitting Chrome or a site session expiring can still interrupt an application. A draft in a chat-specific browser must be recovered separately.

## Run a browser click task

![The model receives a task, title and control labels. It returns an action ID to the browser. The next observation creates a fresh snapshot.](docs/figures/actions.svg)

Install the optional dependencies with `python -m pip install -e '.[agent]'` and set `OPENAI_API_KEY`. Give the model an HTTPS starting page and a specific task:

```sh
ruin "Open the help page" --site https://example.org --channel chrome
```

The runner sends the task, page title and visible action labels to the selected model. It clicks the chosen control directly and observes the page again. A task can use one tab and up to 20 steps.

![An illustrative Help center button is assigned ID 1 in one snapshot. The model can request a click by that ID.](docs/figures/action-example.svg)

For example, if a visible button is labeled **Open guide**, the model can select its current ID. A changed URL or an ID missing from the snapshot stops that step. A blocked model decision leaves the page open for inspection.

### Local credential filling

![The system keyring supplies a matching credential to a sign-in field at the selected HTTPS origin.](docs/figures/autofill.svg)

For a supported sign-in form at the selected HTTPS origin, provision the relevant entries in the system keyring and add `--autofill` to the task command. The optional TOTP entry holds the site's Base32 seed. Complete any remaining sign-in steps in the browser.

```sh
keyring set ruin:https://example.org username
keyring set ruin:https://example.org password
keyring set ruin:https://example.org totp
```

## Verify a Greenhouse application with Outlook Web

![Two lanes track one request. The inbox supplies a matched code to the original job tab, which submits and checks for a receipt.](docs/figures/email-verification.svg)

On macOS or Linux, attach to a local debugging-enabled Chrome session that already has Outlook Web signed in and the original Greenhouse job tab open. Replace the example URL and employer with the exact job and the name used in its email. Start the watcher before the application requests a code. The existing application workflow still owns the initial submit.

```sh
ruin verify-email --cdp http://127.0.0.1:9222 \
  --site https://job-boards.greenhouse.io/example/jobs/12345 \
  --company "Example Employer" --timeout 180
```

The watcher takes a snapshot of visible Outlook inbox rows and waits for a new or updated row whose timestamp follows the request window. It checks the employer, subject wording and Greenhouse sender, reads the code from the opened message, and submits it in the original job tab. A local lock serializes watcher processes. Keep other applications for the same employer idle during verification.

![Example inbox timeline: an old row precedes watcher startup; a unique matching new row can be inspected. Two new candidates stop the run.](docs/figures/mail-window.svg)

In the example above, a 09:59 message already exists when the watcher starts at 10:00. The watcher checks the 10:01 candidate against the employer and verification wording in the row, then checks the sender in the opened message. If two new candidates match, it stops before selecting either one. These times illustrate ordering; the watcher uses the recorded timestamps from the live run.

### Recover an open challenge

![Recovery options depend on the form: resend once, supply the original request time, or inspect the original tab if the result is uncertain.](docs/figures/email-recovery.svg)

If a challenge is already open at startup and offers a resend control, it requests a fresh code there. It makes at most one resend per run.

![Two jobs can share a mail subject. Recovery without a resend requires the job ID in the body. A missing or different ID leaves the tab open.](docs/figures/job-match.svg)

![An example embed URL separates the employer parameter from the job ID. The watcher checks that exactly one matching tab is open.](docs/figures/embed-identity.svg)

For a direct Greenhouse embed, pass the full quoted URL (including both `for` and `token`). If an existing challenge has no resend control, supply `--requested-at UNIX_SECONDS` from that job’s original request. For this recovery path the message body must also identify the job ID. A subject shared by two roles at the same employer cannot establish which form owns the code. A tab in another chat’s isolated browser must be handled there.

The prototype supports English, top-level Greenhouse forms and Outlook layouts exposing message identifiers, timestamps, sender addresses and a message body. Missing evidence or an ambiguous match stops verification. Only a visible receipt counts as success. A timeout can also happen *after* submission; check the original tab before retrying. Message contents and codes stay outside the model loop. The integration has been tested with browser fixtures; compatibility with a live employer form and Outlook tenant remains unverified.

## Resume an authorized Ashby application

![Example of the Ashby status used as evidence: the visible Success heading and official submission text on the same job URL.](docs/figures/ashby-receipt.svg)

Use this workflow when a reviewed application has already reached verification. The original application driver owns the authorization for that job and completes the live challenge in the same tab. Start the receipt watcher alongside that driver, using the exact application URL:

```sh
ruin resume-ashby --cdp http://127.0.0.1:9222 \
  --site 'https://jobs.ashbyhq.com/EMPLOYER/JOB-UUID/application' --timeout 300
```

![The original driver handles the challenge in the existing tab; the receipt watcher observes that tab and emits state changes.](docs/figures/ashby-roles.svg)

The CLI attaches to one matching tab and emits JSON state changes on standard error. On `challenge_visible`, the authorized driver uses the current widget. A driver using the Python API can supply its own approved handler directly:

```python
receipt = await resume_ashby(context, application_url, timeout=300,
                             directory=receipt_directory, on_event=report_status,
                             on_challenge=complete_authorized_challenge)
```

Import `resume_ashby` from `ruin.agent.ashby`. The handler receives the original Playwright page once per run. The standalone CLI observes the browser; it requires an application driver or person to interact with the widget. A completed challenge may automatically submit the form. Leave any existing submission in flight and watch for its result. An enabled Submit button by itself is insufficient evidence to send another request.

### Receipt storage and retries

![Retrying a recorded application returns its saved receipt. An unrecorded application stays pending until the watcher sees official success.](docs/figures/resume.svg)

The watcher records success only when the same job displays Ashby's visible **Success** status with **Your application was successfully submitted**. It returns the receipt as JSON on standard output and stores one row per job in `~/.ruin-everything/ashby-receipts.sqlite3`. A retry returns that stored receipt. A timeout, changed job or ambiguous tab produces an error without marking the job submitted. An external application tracker should import only a returned receipt.

![After a timeout, inspect the pending tab or look for saved evidence. A missing receipt leaves the outcome unknown.](docs/figures/uncertain-result.svg)

For example, a challenge can disappear while the site is still processing the application. If the watcher times out then, check the original tab before taking another action. If that tab later displays the official receipt, rerun the watcher with the same URL to capture it.

The receipt pattern comes from a completed Baseten application. The reusable command was tested with simulated Ashby pages in Chrome, including a hidden receipt, a changed job, duplicate tabs and a retry after the tab closed.

## Example: read courses after school sign-in

![An active session returns the course list directly. If Canvas redirects, complete Duke sign-in to resume the same lookup.](docs/figures/session.svg)

The Duke Canvas adapter demonstrates how a task resumes after an interactive login. Run the lookup in the shared profile:

```sh
ruin courses
```

The result contains course names and links. Use `--json` for structured output:

![Illustrative JSON output with an example course name and abbreviated link.](docs/figures/course-output.svg)

To select an existing local debugging endpoint explicitly, run:

```sh
ruin courses --cdp http://127.0.0.1:9222 --json
```

The sign-in branch waits up to 180 seconds for the school to return the browser to Canvas. Set `--timeout 300` for a longer wait. Duo approval takes place on the school sign-in path. [Duke device recovery](https://oit.duke.edu/help/articles/kb0036398/)

## Verification

![Local tests exercise session reuse, control labels and model-directed clicks. Live checks cover course discovery and a repeat lookup.](docs/figures/checks.svg)

Runtime checks verified a shared Chrome tab across independent CDP connections. For browser tests, install the Playwright Chromium build or use installed Chrome. Run `python -m unittest discover -s tests -v`. Install the agent extras to include the mocked model test. For installed Chrome, prefix the command with `RUIN_TEST_CHANNEL=chrome`.

A live Duke run returned course links after sign-in. A second run with the same profile also returned the list after visiting the school login route. The number of Duo prompts was not measured. The general click loop has been exercised with a simulated model response.

[Development plan](PLAN.md) · [Contribution and figure guidelines](AGENTS.md) · [MIT license](LICENSE)
