# Typr coverage baseline

The `backend-coverage` PR job enforces an interim **60% branch coverage floor** for `backend/app/services/`. This is a deliberate deviation for CI only; the official Master Test Plan’s **80% domain coverage target is unchanged**. The job does not change branch protection.

## Reproduce the CI check

From the repository root, with Docker and Compose available and no external database or application credentials in the environment:

```bash
bash scripts/test-backend-coverage
```

The script uses the existing disposable PostgreSQL fixture and coverage.py `7.13.5`, installed only for this run. It runs the text-service, PostgreSQL integration, and ordinary backend `unittest` suites. Migration and smoke setup are not measured. TC-AUTO-02 latency, Behave, browser E2E, and frontend tests are excluded.

The check divides covered branch exits by total branch exits in all Python files under `backend/app/services/`. The threshold uses the exact counts, not the rounded display or coverage.py’s combined statement-and-branch total. The command exits nonzero if setup or tests fail, the report is invalid, or coverage is below 60%; it cleans up the temporary output and Compose resources on exit.

Verified locally on 2026-11-20 from `bcdf85a` plus the CI changes: **267 / 336 branch exits (79.46%)** across 23 service Python files, with **201 tests passed** (107 text-service, 8 PostgreSQL integration, 86 ordinary backend). This passes the interim CI floor but is below 80% on this branch-only metric.

## Historical baseline (before the CI gate)

The historical backend run measured **89.74% statement coverage** and **81.63% branch coverage** on the proposed services-only scope, but the ten-client race failed its latency assertion under instrumentation. The frontend’s 38 Node tests passed; they covered **62.56% of lines** across the `.js` files in `frontend/src`, not the full React application.

Measured on 2026-11-19 against local checkout `dbed554` plus existing working-tree changes. The figures below predate the CI gate.

## Backend: what the 80% comparison counts

| Scope | Executable statements hit | Branch exits taken | Combined |
| --- | ---: | ---: | ---: |
| **Proposed domain:** `backend/app/services/**` (all 23 Python files) | 1,120 / 1,248 (**89.74%**) | 271 / 332 (**81.63%**) | **88.04%** |
| Whole `backend/app` (all 59 Python files), for context | 2,084 / 2,332 (**89.37%**) | 369 / 470 (**78.51%**) | **87.54%** |

The proposed denominator includes auth, sessions, metrics, practice, race, rooms, stats, and the entire text handler tree, including generation and persistence. It excludes application code outside `services` (including HTTP/WebSocket adapters, security helpers, models, schemas, and commands). The QA plan names domain logic but does not specify this file list or the threshold metric. Use executable statements as the proposed primary comparison, with branch exits reported separately; a whole-app **branch** gate at 80% would not pass. Coverage.py statement coverage counts executable source lines after standard exclusions, not physical lines; branch coverage counts possible transitions taken. The combined percentage pools statement and branch counts, not their percentages. The report’s file lists were checked against the Python files on disk, including unexecuted files. Tests and Alembic scripts are outside both denominators.

| Measured `unittest` discovery suite | Result |
| --- | --- |
| `backend/tests/services/texts_handler`: text processing, generation with doubles, persistence, and chain tests | 107 passed |
| `backend/tests/integration`: disposable PostgreSQL text, room, and practice tests | 8 passed |
| `backend/tests`: top-level tests for metrics, practice, scoring, API, WebSocket behavior, and the ten-client race | 86 passed, 1 failed |

Coverage includes execution from the failed test: p95 was **281.9 ms** (limit **<200 ms**), out of 2,700 updates. No retry was run. This is an instrumented observation, not a production or uninstrumented latency assessment. The database migration and smoke setup ran outside coverage. Behave features, Playwright/Cucumber browser E2E, and live Gemini were not measured.

**Highest-priority gaps:** `services/auth.py` hit 13/41 statements and 0/10 branch exits (registration, collision handling, login); `services/sessions.py` hit 47/61 and 8/16 (revocation and renewal edge cases); `services/texts_handler/load.py` hit 50/77 and 9/16 (quota rejection and saving/error paths). By contrast, `metrics.py`, `race.py`, and `texts_handler/processing/classiffy/__init__.py` hit every measured statement and branch exit.

## Frontend: JavaScript helpers, not browser UI

| Node v26.13.1 report scope (`src/**`) | Lines | Branches | Functions |
| --- | ---: | ---: | ---: |
| Loaded source only (10 `.js` files) | 94.55% | 96.48% | 81.82% |
| Including 15 never-loaded `.js` files (25 total) | **62.56%** | 96.48% | 81.82% |

Both runs passed all 38 tests from `dashboard`, `practice`, `rooms`, `speed-history`, and `stats` (`frontend/tests/*.test.mjs`). The include-all report adds zero line coverage for unloaded files such as `authService.js`, `use-room-socket.js`, and `textService.js`. It does not add meaningful branch/function denominators for those files; the unchanged branch and function percentages do not establish coverage of unloaded code. Among loaded files, `session-fetch.js` had 40% branch coverage. Neither run covered the 40 `.jsx` files, browser rendering, or E2E flows. Node and coverage.py percentages use different counting rules.

## Reproduce locally

Run `scripts/test-stack --latency` from the repository root to run TC-AUTO-02
alone, without coverage or PostgreSQL. The test still uses its temporary SQLite
database; the command logs the p95 for all 2,700 updates and requires it to be
below 200 ms. The `websocket-latency-tests` PR check runs the same command on a
separate GitHub-hosted runner. Timing can still vary by host.

Use `scripts/test-stack --unittest` for the ordinary backend unit and PostgreSQL
integration suites without latency or coverage, or `scripts/test-stack` to keep
the combined local run, including latency. The legacy reporting recipe below
now excludes TC-AUTO-02 by discovery; the historical figures above still include
its instrumented run. Use the CI command above to reproduce the gate.

Run from the repository root in Bash. The backend run used Docker, Compose, PostgreSQL `16-alpine`, Python `3.11.18`, and coverage.py `7.13.5`. Use a local image from the existing `backend/Dockerfile` `test-runner` target (the exact cached image tag used is below; if unavailable, build the target locally and substitute its tag). Only the wheel download needs access to the package index; the runner and ephemeral database use the fixture’s internal network. No repository `.env` or real credentials are passed to the runner.

```bash
# Run within a subshell so the cleanup trap is scoped to this run.
(
set -eu
out=$(mktemp -d /tmp/opencode/typr-coverage.XXXXXX)
chmod 755 "$out"
image=typr-test-fe068e80bdf34dcb80328b4dd8e27551-test-runner:latest
project=typr-coverage-$(basename "$out" | cut -d. -f2 | tr '[:upper:]' '[:lower:]')

timeout 45s docker run --rm -u "$(id -u):$(id -g)" \
  --mount "type=bind,src=$out,dst=/out" "$image" \
  python -m pip download --disable-pip-version-check \
  --only-binary=:all: --no-deps -d /out coverage==7.13.5

compose() {
  env -i PATH="$PATH" HOME="$HOME" docker compose --env-file /dev/null \
    -p "$project" -f docker-compose.test.yml "$@"
}
trap 'compose down --volumes --remove-orphans' EXIT
compose up -d --wait --wait-timeout 60 postgres
status=0
timeout 150s env -i PATH="$PATH" HOME="$HOME" docker run --rm \
  --name "$project-runner" --network "${project}_test" \
  -u "$(id -u):$(id -g)" --workdir /workspace \
  --mount "type=bind,src=$PWD/backend/app,dst=/workspace/backend/app,readonly" \
  --mount "type=bind,src=$PWD/backend/alembic,dst=/workspace/backend/alembic,readonly" \
  --mount "type=bind,src=$PWD/backend/alembic.ini,dst=/workspace/backend/alembic.ini,readonly" \
  --mount "type=bind,src=$PWD/backend/tests,dst=/workspace/backend/tests,readonly" \
  --mount "type=bind,src=$PWD/supabase/db/init.sql,dst=/workspace/supabase/db/init.sql,readonly" \
  --mount "type=bind,src=$out,dst=/out" \
  -e DATABASE_URL=postgresql+psycopg://typr_test:local_test_only@postgres:5432/typr_texts_test \
  -e JWT_SECRET=local-integration-test-only -e TYPR_POSTGRES_INTEGRATION=1 \
  -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/out/tool:/workspace/backend \
  -e COVERAGE_FILE=/out/.coverage "$image" sh -ec '
    python -V
    python -m pip install --disable-pip-version-check --no-index --no-deps --target /out/tool /out/coverage-*.whl
    python -m coverage --version
    python -c '"'"'import sys; sys.path.insert(0, "backend/tests/integration"); from test_text_postgresql import require_local_fixture; require_local_fixture()'"'"'
    python -m app.commands.migrate
    python backend/tests/fixtures/smoke_stack.py
    python -m coverage run --branch --source=backend/app -m unittest discover -s backend/tests/services/texts_handler -v
    python -m coverage run --append --branch --source=backend/app -m unittest discover -s backend/tests/integration -v
    python -m coverage run --append --branch --source=backend/app -m unittest discover -s backend/tests -v
  ' >"$out/backend.log" 2>&1 || status=$?

printf 'Backend runner exit: %s; log and data: %s\n' "$status" "$out"
# Report persisted data without rerunning tests. Check the log for completed
# suites first; if a suite stopped early, the resulting coverage is partial.
if [ -f "$out/.coverage" ]; then
  timeout 30s docker run --rm --network none -u "$(id -u):$(id -g)" \
    --workdir /workspace \
    --mount "type=bind,src=$PWD/backend/app,dst=/workspace/backend/app,readonly" \
    --mount "type=bind,src=$out,dst=/out" \
    -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/out/tool \
    -e COVERAGE_FILE=/out/.coverage "$image" sh -ec '
      python -m coverage report --precision=2 -m
      python -m coverage report --include="backend/app/services/**" --precision=2 -m
      python -m coverage json -o /out/backend.json
      python -m coverage json --include="backend/app/services/**" -o /out/domain.json
    '
fi
exit "$status"
)
```

```bash
(
  cd frontend
  env -u NODE_OPTIONS -u NODE_V8_COVERAGE timeout 45s node --test \
    --experimental-test-coverage --test-coverage-include='src/**' tests/*.test.mjs
  env -u NODE_OPTIONS -u NODE_V8_COVERAGE timeout 45s node --test \
    --experimental-test-coverage --test-coverage-include-all \
    --test-coverage-include='src/**' tests/*.test.mjs
)
```

If `node --help` does not show `--test-coverage-include-all`, use the loaded-only command and label the denominator accordingly; do not compare it directly with the include-all baseline. The working tree has no coverage dependencies or configuration added by this run.
