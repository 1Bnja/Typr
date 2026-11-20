# Typr

Typr is a typing-speed app. Users practice alone on stored texts, climb a monthly leaderboard, track personal statistics, and race each other in real-time multiplayer rooms.

## Quick path

1. Create `backend/.env` (see [Environment variables](#environment-variables)).
2. Run `docker compose up --build`.
3. Open `http://localhost` for the app and `http://localhost/api/v1/health` to check the API.

## Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Realtime | FastAPI WebSocket (multiplayer rooms) |
| Text generation | Google Gemini (optional) |
| Frontend | React, Vite, Tailwind CSS |
| Edge | Caddy reverse proxy, nginx serving the frontend build |
| Tests | unittest, Behave (Gherkin), Playwright, Node test runner |

## Repository layout

| Path | Contents |
|------|----------|
| `backend/app` | API: `routers/` (HTTP), `ws/` (room WebSocket), `services/`, `models/`, `schemas/` |
| `backend/alembic` | Database migrations |
| `backend/tests` | Backend tests |
| `frontend/src` | React application |
| `frontend/tests` | Frontend unit tests |
| `frontend/e2e` | Browser acceptance tests (see its [README](frontend/e2e/README.md)) |
| `scripts/` | `test-stack` and the browser test runner |
| `docs/` | Project documentation |
| `docker-compose.yml` | Production-like stack: backend, frontend, Caddy |
| `docker-compose.test.yml` | Disposable test fixture used by `scripts/test-stack` |
| `.github/workflows` | CI and deploy workflows |

## Local setup

Requirements: Docker with Compose. Node.js 22 or 24 and pnpm 9 are only needed to work on the frontend outside Docker.

### Environment variables

The backend reads `backend/.env` (loaded by `docker compose` and by `app/config.py`). Do not commit it.

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes | SQLAlchemy connection URL for PostgreSQL |
| `JWT_SECRET` | Yes | Secret used to sign session tokens |
| `JWT_ALGORITHM` | No | Token algorithm (default `HS256`) |
| `JWT_EXPIRE_MINUTES` | No | Token lifetime in minutes (default 1440) |
| `GEMINI_API_KEY` | No | Enables AI phrase generation |
| `GEMINI_MODEL` | No | Gemini model used for generation |

## Running the app

**Full stack (Docker):**

```sh
docker compose up --build
```

Caddy serves the frontend on `http://localhost` and proxies `/api/*` to the backend. Apply migrations with:

```sh
docker compose run --rm --no-deps backend python -m app.commands.migrate
```

**Frontend with hot reload:**

```sh
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

Vite proxies `/api` (including WebSockets) to `http://127.0.0.1:8000`, so the backend must be running there.

## API documentation

FastAPI serves interactive docs from the backend:

| URL (behind Caddy) | What it is |
|--------------------|------------|
| `http://localhost/api/v1/health` | Health check |
| `/docs` and `/openapi.json` on the backend | Swagger UI and OpenAPI schema |

Caddy only forwards `/api/*`, so reach `/docs` on the backend port directly (for example `uvicorn app.main:app` from `backend/`, then `http://127.0.0.1:8000/docs`).

Swagger lists every HTTP endpoint with its error responses. The room WebSocket (`/api/v1/ws/rooms/{code}`) is not part of OpenAPI; its protocol is described in the API description at the top of `/docs`.

Authenticate with `POST /api/v1/auth/login`, then use the **Authorize** button with the returned token.

## Tests

| Command | What it runs |
|---------|--------------|
| `scripts/test-stack` | Backend unittests and Behave features against a disposable PostgreSQL |
| `scripts/test-stack --unittest` | Unittests only |
| `scripts/test-stack --behave` | Behave (Gherkin) features only |
| `scripts/test-stack --latency` | WebSocket race latency tests (SQLite, no Gemini) |
| `pnpm --dir frontend test` | Frontend unit tests |
| `pnpm --dir frontend lint` | ESLint |
| `bash scripts/test-registration-browser` | Browser E2E with Playwright |

Notes:

- `scripts/test-stack` needs Docker, builds its own fixture, and refuses to run if `COMPOSE_*`, `DATABASE_URL`, `JWT_SECRET`, `GEMINI_*` or Docker context variables are set in your shell. It cleans up after itself.
- Browser E2E needs extra setup (Chromium, ports 5173 and 8000 free). Follow [frontend/e2e/README.md](frontend/e2e/README.md).
- Lint the backend with `ruff check backend`.

## CI

| Workflow | Trigger | Jobs |
|----------|---------|------|
| `ci.yml` | Pull request to `main` | frontend tests and build, frontend lint, Behave and browser E2E, WebSocket latency, backend lint (ruff), Docker build |
| `backend-tests.yml` | Pull request to `main`, push to `main`, manual | Migration check and backend unittests via `docker-compose.test.yml` |
| `deploy.yml` | Push to `main` | Build, run migrations, restart the stack |

## Deployment

See [docs/deploy.md](docs/deploy.md).
