# Browser acceptance checks

Run from the repository root with Docker, Node.js 22 LTS or 24 LTS, and pnpm 9:

```sh
pnpm --dir frontend install --frozen-lockfile
npm ci --prefix frontend/e2e
(cd frontend/e2e && npx playwright install chromium)
bash scripts/test-registration-browser
```

Set `TYPR_CHROMIUM_PATH` to use a system Chromium (still run the Playwright
install command to get its video encoder). Ports 5173 and 8000
must be free. The script starts Vite and the real API with a disposable
PostgreSQL database, then removes the containers and network. It uses no
production credentials.

On pull requests to `main`, `behave-tests` runs `scripts/test-stack --behave`
against PostgreSQL, then runs the browser suite above in a fresh fixture.
The ordinary `backend-tests` job runs the migration check and Python unittests
without Behave. Locally, `scripts/test-stack` still runs the combined suite;
use `scripts/test-stack --unittest` to skip Behave.

Registration (`@TC-FUNC-02`) checks email-only and dual conflicts for the exact inline alert,
its accessible association, and retained values. It also checks that a
username-only conflict still shows the original form error.

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

To verify the diagnostics without starting the app:

```sh
npm --prefix frontend/e2e run test:diagnostics
```

Expect exit 1, one console error and one uncaught exception in
`frontend/e2e/test-results/diagnostics.html`, and retained trace/video files.
This synthetic scenario is excluded from the normal suite.
