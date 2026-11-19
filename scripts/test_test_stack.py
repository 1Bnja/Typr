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
                'echo private-diagnostic\ncase " $* " in *" up "*) exit 17;; esac\n'
            )
            docker.chmod(0o700)
            env = dict(PATH=f"{directory}:{os.defpath}", CALLS=str(calls), **overrides)
            result = subprocess.run(["bash", str(SCRIPT), *args], env=env,
                                    capture_output=True, text=True, cwd=directory)
            return result, calls.read_text().splitlines() if calls.exists() else []

    def test_refuses_external_configuration_before_docker(self):
        for args, env in [
            (("-f", "docker-compose.yml"), {}),
            ((), {"COMPOSE_FILE": "docker-compose.yml"}),
            ((), {"DATABASE_URL": "private-diagnostic"}),
            ((), {"GEMINI_API_KEY": "private-diagnostic"}),
        ]:
            with self.subTest(args=args, variables=tuple(env)):
                result, calls = self.run_stack(*args, **env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])
                self.assertNotIn("private-diagnostic", result.stdout + result.stderr)

    def test_failed_run_cleans_only_its_project_and_redacts_output(self):
        result, calls = self.run_stack()
        self.assertEqual(result.returncode, 17)
        up, down = calls
        prefix, _ = up.split(" up ", 1)
        self.assertRegex(prefix, r"--project-name typr-test-[0-9a-f]{32}\b")
        self.assertIn("/docker-compose.test.yml", prefix)
        self.assertEqual(down, f"{prefix} down --volumes")
        self.assertNotIn("private-diagnostic", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
