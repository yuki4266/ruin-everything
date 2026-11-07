# Ruin Everything

List the courses you can open on Duke Canvas from your terminal. The runner keeps a dedicated browser profile and returns to the course lookup after school sign-in. Course discovery runs locally without a model or API key.

![A purple browser opens Canvas. An active session leads straight to the course list. A redirect takes the yellow school sign-in branch and rejoins the same list.](docs/figures/session.svg)

## Run a course lookup

From the repository directory, use Python 3.11 or later:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
ruin courses
```

The result contains course names and links. Use `--json` for structured output. To use installed Google Chrome, skip the Chromium download and run `ruin courses --channel chrome`. The profile lives in `~/.ruin-everything/canvas-browser`. To attach to a Chrome instance already exposing a local debugging endpoint, run:

```sh
ruin courses --cdp http://127.0.0.1:9222 --json
```

The sign-in branch in the figure above waits up to 180 seconds for the school to return the browser to Canvas. Set `--timeout 300` for a longer wait. Duo approval takes place on the school sign-in path. [Duke device recovery](https://oit.duke.edu/help/articles/kb0036398/)

## Run a browser click task

![The model receives a task, title and control labels. It returns an action ID to the browser. A separate local path supplies credentials to matching form fields.](docs/figures/actions.svg)

Install the optional dependencies with `python -m pip install -e '.[agent]'` and set `OPENAI_API_KEY`. Give the model an HTTPS starting page and a specific task:

```sh
ruin "Open the help page" --site https://example.org --channel chrome
```

The runner sends the task, page title and visible action labels to the selected model. It clicks the chosen control directly and observes the page again. A task can use one tab and up to 20 steps.

For a supported sign-in form at the selected HTTPS origin, provision the relevant entries in the system keyring and add `--autofill` to the task command. The optional TOTP entry holds the site's Base32 seed. Complete any remaining sign-in steps in the browser.

```sh
keyring set ruin:https://example.org username
keyring set ruin:https://example.org password
keyring set ruin:https://example.org totp
```

## Verify a Greenhouse application with Outlook Web

![From left to right: the original job tab, a pink Outlook envelope for fresh matching mail, and a receipt after the code is filled back in the job tab. An expired code allows one resend.](docs/figures/email-verification.svg)

On macOS or Linux, attach to a local debugging-enabled Chrome session that already has Outlook Web signed in and the original Greenhouse job tab open. Replace the example URL and employer with the exact job and the name used in its email. Start the watcher before the application requests a code. The existing application workflow still owns the initial submit.

```sh
ruin verify-email --cdp http://127.0.0.1:9222 \
  --site https://job-boards.greenhouse.io/example/jobs/12345 \
  --company "Example Employer" --timeout 180
```

The watcher takes a snapshot of visible Outlook inbox rows and waits for a new or updated row whose timestamp follows the request window. It checks the employer, subject wording and Greenhouse sender, reads the code from the opened message, and submits it in the original job tab. If a challenge is already open at startup and offers a resend control, it requests a fresh code there. It makes at most one resend per run. A local lock serializes watcher processes. Keep other applications for the same employer idle during verification.

For a direct Greenhouse embed, pass the full quoted URL (including both `for` and `token`). If an existing challenge has no resend control, supply `--requested-at UNIX_SECONDS` from that job’s original request. For this recovery path the message body must also identify the job ID. A subject shared by two roles at the same employer cannot establish which form owns the code. A tab in another chat’s isolated browser must be handled there.

The prototype supports English, top-level Greenhouse forms and Outlook layouts exposing message identifiers, timestamps, sender addresses and a message body. Missing evidence or an ambiguous match stops verification. Only a visible receipt counts as success. A timeout can also happen *after* submission; check the original tab before retrying. Message contents and codes stay outside the model loop. The integration has been tested with browser fixtures; compatibility with a live employer form and Outlook tenant remains unverified.

## Resume an authorized Ashby application

![An existing job tab leads to verification by the authorized driver and then to an official receipt. An uncertain result leaves the job unrecorded.](docs/figures/ashby-receipt.svg)

Use this workflow when a reviewed application has already reached verification. The original application driver owns the authorization for that job and completes the live challenge in the same tab. Start the receipt watcher alongside that driver, using the exact application URL:

```sh
ruin resume-ashby --cdp http://127.0.0.1:9222 \
  --site 'https://jobs.ashbyhq.com/EMPLOYER/JOB-UUID/application' --timeout 300
```

The CLI attaches to one matching tab and emits JSON state changes on standard error. On `challenge_visible`, the authorized driver uses the current widget. A driver using the Python API can supply its own approved handler directly:

```python
receipt = await resume_ashby(context, application_url, timeout=300,
                             directory=receipt_directory, on_event=report_status,
                             on_challenge=complete_authorized_challenge)
```

Import `resume_ashby` from `ruin.agent.ashby`. The handler receives the original Playwright page once per run. The standalone CLI observes the browser; it requires an application driver or person to interact with the widget. A completed challenge may automatically submit the form. Leave any existing submission in flight and watch for its result. An enabled Submit button by itself is insufficient evidence to send another request.

The watcher records success only when the same job displays Ashby's visible **Success** status with **Your application was successfully submitted**. It returns the receipt as JSON on standard output and stores one row per job in `~/.ruin-everything/ashby-receipts.sqlite3`. A retry returns that stored receipt. A timeout, changed job or ambiguous tab produces an error without marking the job submitted. An external application tracker should import only a returned receipt.

The receipt pattern comes from a completed Baseten application. The reusable command was tested with simulated Ashby pages in Chrome, including a hidden receipt, a changed job, duplicate tabs and a retry after the tab closed.

## Verification

![Local tests exercise session reuse, control labels and model-directed clicks. Live checks cover course discovery and a repeat lookup.](docs/figures/checks.svg)

Run `python -m unittest discover -s tests -v`. Install the agent extras to include the mocked model test. For installed Chrome, prefix the command with `RUIN_TEST_CHANNEL=chrome`.

A live Duke run returned course links after sign-in. A second run with the same profile also returned the list after visiting the school login route. The number of Duo prompts was not measured. The general click loop has been exercised with a simulated model response.

[Development plan](PLAN.md) · [Contribution and figure guidelines](AGENTS.md) · [MIT license](LICENSE)
