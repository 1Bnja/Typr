# Run Typr tests and analyze the report

## Run the suites

Use Linux, Bash, GNU `timeout`, Python 3.11+, Node.js 24 LTS, pnpm 9, and Docker Compose v2 with the `default` context and `/var/run/docker.sock`. Leave loopback ports 8000 and 5173 free for the browser fixture.

From the repository root:

```bash
python3 -m venv test/.venv
source test/.venv/bin/activate
python -m pip install -r tests/requirements.txt
pnpm --dir frontend install --frozen-lockfile
npm ci --prefix frontend/e2e
(cd frontend/e2e && npx playwright install chromium --with-deps)
./test/run-batch.bash
```

In a terminal, the Spanish menu lets you run all suites, choose one, or exit without changing the previous report. During the run, the viewport shows up to five complete lines and advances the progress bar when a suite wrapper finishes, even if it fails. It does not count individual tests inside a suite. The viewport can stay still while a tool buffers output, Cucumber prints dots without a newline, or fixture output is redirected. For example, the browser suite does not stream its Vite server log; it shows a tail if startup fails. The complete output available to the runner is saved in a per-run `test/results/lote-*.log` file, not in JUnit. The launcher prints the log path, pytest's exit code, and the report path (or notes that no report was generated).

With redirected input or output, or a nonempty `CI` variable, the command runs all suites without prompting or creating a viewport log. The launcher takes no arguments.

Each run replaces `reporte_tests.xml` in the repository root and returns pytest's exit code. When running all suites, the wrappers run sequentially; JUnit durations are for whole wrappers, not individual tests. GitHub Actions uploads only the XML, including when pytest reports failures. If setup fails before pytest, there is no XML to upload.

The backend uses `backend/Dockerfile`, `backend/requirements.txt` and the standalone Compose fixture. Tests use disposable data and do not need application `.env` files, live Gemini, Supabase, or production credentials. Do not run fixture suites concurrently or supply external Docker, Compose, application, or Vite settings. A forced kill may prevent cleanup; inspect only resources from that run before removing anything.

## Debug one suite

```bash
python tests/suite_runner.py frontend-unit
python tests/suite_runner.py --help
```

The runner streams subprocess output to the terminal; the notebook's manual helper uses the same runner. A browser diagnostics pass means the intentional failure matched the expected Cucumber counts and both browser errors. Chromium traces, videos and reports remain in ignored `frontend/e2e/test-results/`. Human visual, accessibility, and device checks are not part of this run.

## Read or export the report

With the test environment active, install the separate analysis dependencies and register its kernel:

```bash
python -m pip install -r notebooks/requirements.txt
python -m ipykernel install --sys-prefix --name python3
./test/run.bash
```

The launcher opens the [QA index](../tests.ipynb). Follow its link to the historical analysis notebook to read `reporte_tests.xml`. Keep the local Jupyter URL private.

To export an interactive, offline HTML report without notebook source, place `reporte_tests.xml` in the repository root, then run:

```bash
jupyter nbconvert --to html --no-input --execute \
  --config=notebooks/nbconvert_config.py \
  --ExecutePreprocessor.kernel_name=python3 \
  notebooks/analisis_tests.ipynb
```

The export writes `notebooks/analisis_tests.html` without modifying the notebook. The manual debug cell only defines a helper; exporting does not rerun tests. If you add your own debug call, remove it before exporting.

## Strip outputs at commit

With the analysis environment active, run `pre-commit install` once per clone. The shared hook uses `nbstripout` on staged notebooks. If it cleans a notebook, review and restage it, then retry the commit. If your clone already manages hooks, integrate the shared hook with that setup rather than replacing it.
