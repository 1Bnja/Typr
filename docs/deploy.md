# Deployment and backup

Typr runs as three containers (Caddy, frontend, backend) built with Docker Compose. The database is an external PostgreSQL instance reached through `DATABASE_URL`. This guide covers the automatic deploy, manual deploy, backups, and how to bring the whole thing up on another computer.

## Quick path

Bring up a copy on a new computer:

1. Install Docker (with Compose v2) and Git. Clone the repository.
2. Create `backend/.env` (see [Environment variables](#environment-variables)).
3. `docker compose build`
4. `docker compose run --rm --no-deps backend python -m app.commands.migrate`
5. `docker compose up -d`
6. Check `http://localhost/api/v1/health` returns `{"status":"ok"}` and `http://localhost/` loads the app.

Details, restore from a backup, and caveats are in [Bring up the backup on another computer](#bring-up-the-backup-on-another-computer).

## Architecture

```
Browser -> Cloudflare (TLS) -> Caddy :80 -> /api/*  -> backend:8000  (FastAPI)
                                         -> others  -> frontend:80   (static build)
                                                          backend -> PostgreSQL (DATABASE_URL)
```

| Piece | Notes |
|-------|-------|
| Public URL | `https://typr.cfuentes.dev`. Cloudflare terminates TLS at its edge. |
| Caddy | Serves plain HTTP for `typr.cfuentes.dev`, `localhost` and `127.0.0.1` (see `Caddyfile`). It does not manage certificates. Ports 80 and 443 are published by `docker-compose.yml`. |
| Frontend | React/Vite build served by its own container. |
| Backend | FastAPI on port 8000, internal only. Reads `backend/.env`. |
| Database | PostgreSQL outside Docker Compose, reached via `DATABASE_URL`. The schema is managed by Alembic (`backend/alembic`, baseline in `supabase/db/init.sql`). The repository ships no database container; the production database is a hosted PostgreSQL reached via `DATABASE_URL`. |

## Environment variables

Defined in `backend/.env` (template: `backend/.env.example`). Never commit this file; it is git-ignored.

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | yes | SQLAlchemy URL, format `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME` |
| `JWT_SECRET` | yes | Signs authentication tokens. Use a long random value. |
| `GEMINI_API_KEY` | no | Enables AI text generation |
| `GEMINI_MODEL` | no | Gemini model name |

In CI the same four names are stored as GitHub Actions secrets with identical names.

## Automatic deploy

`.github/workflows/deploy.yml` runs on every push to `main`, on the `self-hosted` runner (the machine that hosts production):

1. Checkout.
2. Write `backend/.env` from the four secrets above.
3. `docker compose build`
4. `docker compose run --rm --no-deps backend python -m app.commands.migrate`
5. `docker compose up -d --remove-orphans`

Runs are serialized (`concurrency: deploy`, no cancellation). Follow them in the repository's Actions tab.

## Manual deploy

`deploy.yml` deploys the self-hosted runner's checkout. Run manual deploys from that same directory (same compose project), otherwise a second stack will compete for ports 80 and 443. From the repository root, with `backend/.env` in place:

```bash
git pull --ff-only origin main
docker compose build
docker compose run --rm --no-deps backend python -m app.commands.migrate
docker compose up -d --remove-orphans
```

## Migrations

`python -m app.commands.migrate` upgrades the database to the latest Alembic revision. On a database created from `supabase/db/init.sql` without Alembic history, it stamps the matching revision first and refuses partial or ambiguous schemas without changing anything. It is safe to run repeatedly.

## Health check and logs

```bash
curl -i http://localhost/api/v1/health          # on the host
curl -i https://typr.cfuentes.dev/api/v1/health # public path
docker compose ps
docker compose logs -f --tail=100 backend       # also: frontend, caddy
```

## Rollback

There is no image registry; rolling back means redeploying an older commit. Run it from the same checkout and compose project that `deploy.yml` uses on the self-hosted runner, so you do not start a second stack that competes for ports 80 and 443.

```bash
git fetch origin
git checkout <previous-commit-sha>
docker compose build
docker compose up -d --remove-orphans
```

Do not run the migration step when going back unless you know the older code supports the current schema: migrations only move forward. Take a [backup](#database-backup) before any risky deploy. Return to the latest code with `git checkout main && git pull --ff-only` and redeploy. Note that a push to `main` triggers the automatic deploy again.

## Database backup

Use the official `postgres` image as the client, so nothing needs to be installed on the host. Check the server version with `SELECT version();` and set the image tag to that major version (the examples use `16`); the client major version must be equal to or newer than the server's.

`pg_dump` needs a plain `postgresql://` URL, so drop the `+psycopg` driver suffix from `DATABASE_URL`:

```bash
# Run in a shell where DATABASE_URL holds the value from backend/.env
export PG_URL="${DATABASE_URL/+psycopg/}"

docker run --rm postgres:16-alpine pg_dump \
  --format=custom --no-owner --no-privileges --schema=public \
  "$PG_URL" > "typr-$(date +%Y%m%d-%H%M%S).dump"
```

Notes:

- Passing the URL as an argument exposes the password in the process list while the command runs. To avoid it, use a URL without the password and pass `-e PGPASSWORD` (with the variable exported in your shell) to `docker run` instead.
- `--schema=public` keeps the dump to Typr's own tables and skips provider-internal schemas on hosted PostgreSQL.
- The dump includes `alembic_version`, so the restored database keeps its migration history.
- The dump contains user data and password hashes. Store it encrypted and outside the repository.
- If the provider requires it, add `?sslmode=require` to `PG_URL`.
- Take the first backup, then schedule it (for example with cron on the host), and keep copies off the machine.

## Database restore

Restore into an **empty** database. Create the empty database first with your provider, or locally with a `postgres` container.

**Warning: this is destructive.** The restore drops and recreates every Typr table in `TARGET_URL`. Never point it at production. Confirm the host first, and if the target holds anything you care about, take a fresh dump of it (see [Database backup](#database-backup)) before restoring.

```bash
export TARGET_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME"

# Confirm the target host (password stripped) before continuing
echo "$TARGET_URL" | sed -E 's#//[^@]*@#//#'

docker run --rm -i postgres:16-alpine pg_restore \
  --clean --if-exists --no-owner --no-privileges --exit-on-error \
  --dbname "$TARGET_URL" < typr-YYYYMMDD-HHMMSS.dump
```

On a fresh empty database, `--clean --if-exists` is needed because the dump contains `CREATE SCHEMA public`, which fails without it. The same flags are what make the command destructive on a populated database, so do not treat them as safe. Then point `DATABASE_URL` in `backend/.env` at the restored database (with the `+psycopg` form) and run the migration step. It is a no-op when the dump was already at the latest revision.

From inside a container, `localhost` is the container itself. To reach a database published on the host, use `host.docker.internal` (Docker Desktop; on Linux add `extra_hosts: ["host.docker.internal:host-gateway"]` to the backend service in a local override) or put both on a shared Docker network.

## Bring up the backup on another computer

Prerequisites: Docker with Compose v2, Git, a recent `.dump` file (if you need the data), and the secret values from a trusted source.

1. **Clone**

   ```bash
   git clone https://github.com/1Bnja/Typr.git
   cd Typr
   ```

2. **Provide a database.** Pick one:
   - Reuse the hosted PostgreSQL: use its `DATABASE_URL`. Both machines then share the same data; do not run two copies against production unintentionally.
   - Use a new empty PostgreSQL (hosted, or a local container):

     ```bash
     docker run -d --name typr-db -p 5432:5432 \
       -e POSTGRES_USER=typr -e POSTGRES_PASSWORD=change-me -e POSTGRES_DB=typr \
       -v typr_pgdata:/var/lib/postgresql/data postgres:16-alpine
     ```

     Its `DATABASE_URL` from inside the backend container is
     `postgresql+psycopg://typr:change-me@host.docker.internal:5432/typr`.

3. **Restore data (optional).** Applies **only** to the new, empty database option. **Skip it when reusing the hosted database**: the restore drops and recreates every Typr table. Skip it too if you want an empty schema. Otherwise run the [restore](#database-restore) against the new empty database.

4. **Create `backend/.env`** with the variables listed in [Environment variables](#environment-variables).

5. **Build and migrate**

   ```bash
   docker compose build
   docker compose run --rm --no-deps backend python -m app.commands.migrate
   ```

6. **Start**

   ```bash
   docker compose up -d
   ```

7. **Verify**

   ```bash
   curl -i http://localhost/api/v1/health   # expect 200 {"status":"ok"}
   curl -I http://localhost/                # expect 200 (frontend)
   ```

   Then open `http://localhost/` in a browser and sign in or register.

Things that differ from production on another computer:

- Only `localhost` and `127.0.0.1` resolve to the app. `typr.cfuentes.dev` points at Cloudflare and the production host, not at this machine.
- To serve it publicly, the Cloudflare side must be pointed at the new host (see below), and the production host decommissioned or switched off first.
- Ports 80 and 443 must be free on the new computer.
- Compose publishes 443, but Caddy only listens for HTTP; there is no HTTPS on the local copy.
- Re-register the self-hosted GitHub runner on the new machine if automatic deploys should continue from there.

## External configuration checklist

Managed outside this repository (Cloudflare dashboard and DNS). Confirm each item with whoever administers it; this document does not record their current state.

- [ ] DNS record for `typr.cfuentes.dev` points to the intended host (proxy or tunnel)
- [ ] Cloudflare SSL/TLS mode is compatible with Caddy serving plain HTTP
- [ ] "Always Use HTTPS" setting
- [ ] Tunnel versus proxied-record configuration, and which host it targets
- [ ] GitHub Actions secrets `DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`, `GEMINI_MODEL` are set
- [ ] A self-hosted runner is online on the deployment host
- [ ] Database provider backups or point-in-time recovery, if available, are enabled
