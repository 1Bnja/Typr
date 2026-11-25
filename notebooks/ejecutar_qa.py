"""Adapt the Typr local test runner for QA notebook cells."""

import os
from pathlib import Path
from runpy import run_path
from shlex import join

_RAIZ = Path(__file__).resolve().parents[1]
_EJECUTOR = run_path(str(_RAIZ / "tests" / "suite_runner.py"))
_SUITES = {
    "backend-unit-integration-migrations",
    "backend-gherkin",
    "browser-gherkin",
    "latency",
    "backend-coverage",
}


def ejecutar(suite, *, etiquetas=None):
    """Run a disposable test suite and stream its output to the cell."""
    if suite not in _SUITES or (etiquetas is not None and suite != "browser-gherkin"):
        raise ValueError("Unsupported QA notebook suite or tag filter.")

    config = _EJECUTOR["SUITES"][suite]
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    motivo = _EJECUTOR["local_fixture"](env, config.browser_fixture)
    if motivo:
        raise RuntimeError(f"Local suite did not start: {motivo}")
    for clave in config.unset:
        env.pop(clave, None)
    env.update(config.overrides)

    comando = config.command
    if config.browser_fixture:
        # Keep the local runner's browser visible.
        for clave in ("CI", "GITHUB_ACTIONS", "TYPR_HEADLESS"):
            env.pop(clave, None)
        if etiquetas is not None:
            comando += ("--tags", etiquetas)

    print(f"Running: {join(comando)}", flush=True)
    try:
        codigo = _EJECUTOR["stream"](
            comando, config.seconds, env,
            lambda linea: print(linea.decode("utf-8", errors="replace"), end="", flush=True),
        )
    except OSError as error:
        raise RuntimeError(f"Could not start the local test runner: {error}") from error
    if codigo:
        detalle = " (timed out or terminated)" if codigo in (124, 137, -9) else ""
        raise RuntimeError(f"Test run failed with exit code {codigo}{detalle}.")
    print("\nExit code: 0.", flush=True)
