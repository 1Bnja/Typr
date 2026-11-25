import pytest

import suite_runner


DIAGNOSTICS = (
    b"1 scenario (1 failed)\n"
    b"3 steps (2 passed, 1 failed)\n"
    b"   Unexpected browser console.error: 1\n"
    b"   Unexpected browser uncaught page error: 1\n"
)


@pytest.mark.parametrize(
    ("code", "output", "valid"),
    [
        (1, DIAGNOSTICS, True),
        (0, DIAGNOSTICS, False),
        (1, DIAGNOSTICS.replace(b"2 passed", b"1 passed"), False),
        (1, DIAGNOSTICS.replace(b"console.error", b"console.warn"), False),
        (1, DIAGNOSTICS.replace(b"uncaught page error", b"page error"), False),
        (1, DIAGNOSTICS + b"Could not start browser\n", False),
    ],
)
def test_diagnostic_contract(code, output, valid):
    assert suite_runner.verified_diagnostics(code, output) is valid


def test_external_environment_is_rejected_before_launch(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "do-not-print-this-value")
    monkeypatch.setattr(suite_runner, "stream", lambda *_: pytest.fail("unexpected launch"))
    with pytest.raises(suite_runner.SuiteFailure, match=r"\(DATABASE_URL\)$"):
        suite_runner.run_suite("backend-gherkin")


def test_browser_refuses_a_dangling_env_file(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / ".env.local").symlink_to(frontend / "missing")
    monkeypatch.setattr(suite_runner, "ROOT", tmp_path)
    assert suite_runner.local_fixture({}, browser=True).endswith("(frontend/.env.local)")


def test_diagnostic_keeps_output_local_and_forces_no_color(monkeypatch, capsys):
    monkeypatch.setenv("FORCE_COLOR", "1")

    def fake_stream(command, seconds, env, emit):
        assert command == suite_runner.SUITES["browser-diagnostics"].command
        assert seconds == 90
        assert "FORCE_COLOR" not in env
        assert env["NO_COLOR"] == "1"
        for line in DIAGNOSTICS.splitlines(keepends=True):
            emit(line)
        return 1

    monkeypatch.setattr(suite_runner, "stream", fake_stream)
    raw = []
    assert suite_runner.run_suite("browser-diagnostics", emit_bytes=raw.append) == "EXPECTED FAILURE VERIFIED"
    assert b"".join(raw) == DIAGNOSTICS
    assert not capsys.readouterr().out


def test_timeout_does_not_expose_subprocess_output(monkeypatch):
    def fake_stream(_command, _seconds, _env, emit):
        emit(b"raw subprocess output\n")
        return 124

    monkeypatch.setattr(suite_runner, "stream", fake_stream)
    with pytest.raises(suite_runner.SuiteFailure, match=r"limit 60s; exit 124"):
        suite_runner.run_suite("frontend-unit")
