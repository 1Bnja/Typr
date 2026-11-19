# Registration browser check (`@TC-FUNC-02`)

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

The browser checks email-only and dual conflicts for the exact inline alert,
its accessible association, and retained values. It also checks that a
username-only conflict still shows the original form error.
