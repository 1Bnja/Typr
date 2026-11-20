import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("test-stack")


class TestStackTests(unittest.TestCase):
    def run_stack(self, *args, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            docker = Path(directory) / "docker"
            calls = Path(directory) / "calls"
            docker.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n'
                'echo private-diagnostic\ncase " $* " in *" up "*|*" run "*) '
                'printf "%s:%s:%s\\n" "$TYPR_TEST_SUITE" "$TYPR_TEST_AUTH_ONLY" '
                '"$TYPR_TEST_FAIL_AFTER_SMOKE" > "$CALLS.mode"; exit 17;; esac\n'
            )
            docker.chmod(0o700)
            env = dict(PATH=f"{directory}:{os.defpath}", CALLS=str(calls), **overrides)
            result = subprocess.run(["bash", str(SCRIPT), *args], env=env,
                                    capture_output=True, text=True, cwd=directory)
            mode = calls.with_suffix(".mode")
            return (result, calls.read_text().splitlines() if calls.exists() else [],
                    mode.read_text().strip() if mode.exists() else None)

    def test_refuses_external_configuration_before_docker(self):
        for args, env in [
            (("-f", "docker-compose.yml"), {}),
            ((), {"COMPOSE_FILE": "docker-compose.yml"}),
            ((), {"DATABASE_URL": "private-diagnostic"}),
            ((), {"GEMINI_API_KEY": "private-diagnostic"}),
        ]:
            with self.subTest(args=args, variables=tuple(env)):
                result, calls, _ = self.run_stack(*args, **env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])
                self.assertNotIn("private-diagnostic", result.stdout + result.stderr)

    def test_failed_run_cleans_only_its_project_and_redacts_output(self):
        result, calls, _ = self.run_stack()
        self.assertEqual(result.returncode, 17)
        up, down = calls
        prefix, _ = up.split(" up ", 1)
        self.assertRegex(prefix, r"--project-name typr-test-[0-9a-f]{32}\b")
        self.assertIn("/docker-compose.test.yml", prefix)
        self.assertEqual(down, f"{prefix} down --volumes")
        self.assertNotIn("private-diagnostic", result.stdout + result.stderr)

    def test_modes_select_suite_without_reusing_inherited_controls(self):
        for args, expected in [
            ((), "combined:0:0"),
            (("--auth",), "combined:1:0"),
            (("--sessions",), "combined:2:0"),
            (("--verify-cleanup",), "combined:0:1"),
            (("--behave",), "behave:0:0"),
            (("--unittest",), "unittest:0:0"),
            (("--latency",), "latency:0:0"),
        ]:
            with self.subTest(args=args):
                result, calls, mode = self.run_stack(
                    *args, TYPR_TEST_SUITE="unexpected", TYPR_TEST_AUTH_ONLY="9",
                    TYPR_TEST_FAIL_AFTER_SMOKE="9",
                )
                self.assertEqual(mode, expected)
                self.assertEqual(result.returncode, 17)
                self.assertEqual(len(calls), 2)

    def test_latency_runs_only_the_uninstrumented_sqlite_suite_and_cleans_up(self):
        result, calls, _ = self.run_stack("--latency")
        self.assertEqual(result.returncode, 17)
        run, down = calls
        prefix, command = run.split(" run ", 1)
        self.assertEqual(down, f"{prefix} down --volumes")
        self.assertIn("--rm --no-deps -T", command)
        self.assertIn("-e DATABASE_URL=sqlite+pysqlite://", command)
        self.assertTrue(command.endswith(
            "test-runner python -u -m unittest backend.tests.latency.test_race_load -v"
        ))
        self.assertIn("private-diagnostic", result.stdout)


if __name__ == "__main__":
    unittest.main()
