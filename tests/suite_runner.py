"""Run Typr's canonical suites without importing pytest or Jupyter."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
from tempfile import TemporaryFile

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Suite:
    command: tuple[str, ...]
    seconds: int
    docker: bool = False
    browser_fixture: bool = False
    unset: tuple[str, ...] = ()
    overrides: tuple[tuple[str, str], ...] = ()
    diagnostic: bool = False


SUITES = {
    "frontend-unit": Suite(("npm", "--prefix", "frontend", "test"), 60),
    "harness-unit": Suite(
        ("python3", "-B", "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py", "-v"),
        30,
    ),
    "backend-unit-integration-migrations": Suite(
        ("scripts/test-stack", "--unittest"), 450, docker=True,
        overrides=(("TYPR_TEST_STREAM_OUTPUT", "1"),),
    ),
    "backend-gherkin": Suite(("scripts/test-stack", "--behave"), 450, docker=True),
    "browser-gherkin": Suite(
        ("bash", "scripts/test-registration-browser"), 450, docker=True, browser_fixture=True,
        overrides=(("DOCKER_CONTEXT", "default"),),
    ),
    "latency": Suite(("scripts/test-stack", "--latency"), 300, docker=True),
    "backend-coverage": Suite(
        ("bash", "scripts/test-backend-coverage"), 450, docker=True,
        unset=("TYPR_COVERAGE_PROJECT", "TYPR_TEST_SUITE", "TYPR_TEST_FAIL_AFTER_SMOKE", "TYPR_TEST_AUTH_ONLY"),
    ),
    "browser-diagnostics": Suite(
        ("npm", "--color=false", "--prefix", "frontend/e2e", "run", "test:diagnostics"), 90,
        unset=("FORCE_COLOR",), overrides=(("NO_COLOR", "1"),), diagnostic=True,
    ),
}


def local_fixture(env, browser=False):
    blocked = {
        "DATABASE_URL", "JWT_SECRET", "GEMINI_API_KEY", "GEMINI_MODEL",
        "GOOGLE_API_KEY", "DOCKER_HOST", "DOCKER_CONTEXT",
    }
    for key in sorted(env):
        if key in blocked or key.startswith(("COMPOSE_", "VITE_")):
            return f"Refusing external fixture configuration ({key})"
    if browser:
        for name in (".env", ".env.local", ".env.development", ".env.development.local"):
            path = ROOT / "frontend" / name
            if path.exists() or path.is_symlink():
                return f"Refusing browser fixture configuration (frontend/{name})"
    try:
        context = subprocess.run(
            ["docker", "context", "inspect", "default", "--format", "{{.Endpoints.docker.Host}}"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=10, check=True,
        )
        if context.stdout.strip() == b"unix:///var/run/docker.sock":
            return None
    except (OSError, subprocess.SubprocessError):
        pass
    return "A default local Docker socket at /var/run/docker.sock is required"


def stream(command, seconds, env, emit):
    # GNU timeout keeps the command in its process group for TERM-to-KILL escalation.
    with subprocess.Popen(
        ["timeout", "--kill-after=20s", f"{seconds}s", *command],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True,
    ) as child:
        try:
            for line in child.stdout:
                emit(line)
            return child.wait()
        except BaseException:
            def signal_group(value):
                try:
                    os.killpg(child.pid, value)
                except ProcessLookupError:
                    pass

            signal_group(signal.SIGTERM)
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                pass
            signal_group(signal.SIGKILL)
            raise


def verified_diagnostics(code, output):
    lines = output.splitlines()
    return (
        code == 1
        and b"1 scenario (1 failed)" in lines
        and b"3 steps (2 passed, 1 failed)" in lines
        and any(line.endswith(b"Unexpected browser console.error: 1") for line in lines)
        and any(line.endswith(b"Unexpected browser uncaught page error: 1") for line in lines)
        and b"Could not " not in output
    )


class SuiteFailure(Exception):
    """A bounded failure message suitable for JUnit XML."""


def run_suite(name, *, emit=None, emit_bytes=None):
    suite = SUITES[name]
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    if suite.docker:
        reason = local_fixture(env, suite.browser_fixture)
        if reason:
            raise SuiteFailure(reason)
    for key in suite.unset:
        env.pop(key, None)
    env.update(suite.overrides)

    # Keep subprocess output out of JUnit; interactive callers may stream it.
    with TemporaryFile() as diagnostic_output:
        def handle(line):
            if suite.diagnostic:
                diagnostic_output.write(line)
            if emit is not None:
                emit(line.decode("utf-8", errors="replace"))
            if emit_bytes is not None:
                emit_bytes(line)

        try:
            code = stream(suite.command, suite.seconds, env, handle)
        except OSError as error:
            raise SuiteFailure(f"Could not start suite runner (OS error {error.errno})") from None
        if code in (124, 137, -signal.SIGKILL):
            raise SuiteFailure(f"Suite timed out or was killed (limit {suite.seconds}s; exit {code})")
        if suite.diagnostic:
            diagnostic_output.seek(0)
            if not verified_diagnostics(code, diagnostic_output.read()):
                raise SuiteFailure(f"Expected synthetic failure not observed (exit {code})")
            return "EXPECTED FAILURE VERIFIED"
        if code:
            raise SuiteFailure(f"Suite exited with status {code}; rerun it locally for subprocess output")
        return "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=SUITES)
    args = parser.parse_args()
    try:
        print(run_suite(args.suite, emit=lambda line: print(line, end="", flush=True)))
    except SuiteFailure as error:
        parser.exit(1, f"{args.suite}: {error}\n")


if __name__ == "__main__":
    main()
