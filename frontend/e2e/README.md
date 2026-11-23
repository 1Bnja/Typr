# Browser acceptance checks

Run from the repository root with Docker, Node.js 24 LTS (the workflow version), and pnpm 9:

```sh
pnpm --dir frontend install --frozen-lockfile
npm ci --prefix frontend/e2e
(cd frontend/e2e && npx playwright install chromium)
bash scripts/test-registration-browser
```

Chromium opens visibly by default for local terminal, batch, and notebook runs.
On a machine without a desktop, run `TYPR_HEADLESS=1 bash scripts/test-registration-browser`
or set `TYPR_HEADLESS=1` in the batch or notebook environment. GitHub Actions
always runs headless.

Set `TYPR_CHROMIUM_PATH` to use a system Chromium (still run the Playwright
install command to get its video encoder). Ports 5173 and 8000
must be free. The script starts Vite and the real API with a disposable
PostgreSQL database, then removes the containers and network. It uses no
production credentials.

The local workflow configuration defines `behave-tests` for PRs to `main`.
It runs `scripts/test-stack --behave`, then the browser suite in a fresh fixture
even if Behave fails, unless canceled. The separate `backend-tests` workflow
runs migrations and Python unittests without Behave or latency. Locally,
`scripts/test-stack --unittest` runs that backend subset; `scripts/test-stack`
runs the combined backend suite. Current live checks and required-check
settings have not been verified.

Registration (`@TC-FUNC-02`) checks email-only and dual conflicts for the exact inline alert,
its accessible association, and retained values. It also checks that a
username-only conflict still shows the original form error.

To select one scenario or group, pass a Cucumber tag expression; positional
paths do not narrow the configured feature glob. For example, the account
lifecycle lands on `/profile` (`/dashboard` redirects there) and checks
`GET /api/v1/users/me` when reloading:

```sh
bash scripts/test-registration-browser --tags '@TC-AUTO-01 and @TC-FUNC-01' --retry 0
```

Use `--tags '@TC-FUNC-10 or @TC-FUNC-12'` for monthly ranking at
`/practice/leaderboard`. The [QA index](../../tests.ipynb) links to the observed
results and their limits.

Run `bash scripts/test-registration-browser --tags @active_expiry` for the
active-play expiry cases (`@RI-14`). The fixture seeds a typing text; Playwright
controls only the affected browser's clock and the revocation case uses the real
API and room socket.

## Reports and failure recordings

Open `frontend/e2e/test-results/report.html` locally. Each failed scenario
lists its own `test-results/scenario-*` directory in the report. Inside it,
`trace-N.zip` records browser context N and `context-N/*.webm` contains a
video for each page. Inspect a trace from `frontend/e2e` with
`npx playwright show-trace test-results/scenario-…/trace-1.zip`.

Unexpected console errors and uncaught exceptions fail the scenario,
including those from secondary tabs and peer contexts. Explicit error-path
steps can allow an expected Chromium resource error once per matching URL and
message; uncaught exceptions are never allowed. The failure summary shows
categories and counts, not raw browser messages. Traces and videos can still
contain request data, tokens, or typed values: use synthetic accounts only and
keep the Git-ignored output local. Passing scenarios discard their recordings;
older failures remain until you delete them. The HTML report is overwritten.

The PR workflow is configured to upload a seven-day failure artifact with a
sanitized HTML summary, action/timing-only traces, and recordings from the
disposable synthetic fixture, if staging succeeds. It does not upload the
raw report, network bodies, or raw logs. Videos are not rewritten by staging;
review publication access and recorded content rather than assuming every
file is sanitized. Live artifact publication remains unverified.

To verify the diagnostics without starting the app:

```sh
npm --prefix frontend/e2e run test:diagnostics
```

Expect exit 1, one console error and one uncaught exception in
`frontend/e2e/test-results/diagnostics.html`, and retained trace/video files.
This synthetic scenario is excluded from the normal suite.
