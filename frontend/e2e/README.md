# Browser acceptance checks

Run from the repository root with Docker, Node.js 22 LTS or 24 LTS, and the
frontend dependencies installed:

```sh
npm ci --prefix frontend/e2e
(cd frontend/e2e && npx playwright install chromium)
bash scripts/test-registration-browser
```

Set `TYPR_CHROMIUM_PATH` to use an installed Chromium instead. Ports 5173 and 8000
must be free. The script starts Vite and the real API with a disposable
PostgreSQL database, then removes the containers and network. It uses no
production credentials.

Registration (`@TC-FUNC-02`) checks email-only and dual conflicts for the exact inline alert,
its accessible association, and retained values. It also checks that a
username-only conflict still shows the original form error.

Run `bash scripts/test-registration-browser --tags @active_expiry` for the
active-play expiry cases (`@RI-14`). The fixture seeds a typing text; Playwright
controls only the affected browser's clock and the revocation case uses the real
API and room socket.
