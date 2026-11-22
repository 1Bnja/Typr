"""Display a rolling terminal view of the interactive pytest run."""

from collections import deque
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import shutil
import signal
import sys
from tempfile import NamedTemporaryFile
import unicodedata


def terminal_line(raw, width):
    """Limit display cells and replace controls without altering the log."""
    result = []
    for char in raw.removesuffix(b"\r").decode("utf-8", errors="replace"):
        category = unicodedata.category(char)
        if category.startswith(("C", "M")) or category in ("Zl", "Zp"):
            char = "?"
        width -= 2 if unicodedata.east_asian_width(char) in ("W", "F", "A") else 1
        if width < 0:
            break
        result.append(char)
    return "".join(result)


class LiveBatch(io.RawIOBase):
    __name__ = "typr_live_batch"  # The pluggy registration name used by the suite wrapper.

    def __init__(self, terminal, log):
        super().__init__()
        self.terminal = terminal
        self.log = log
        self.recent = deque(maxlen=5)
        self.pending = bytearray()
        self.total = None
        self.completed = 0
        self.rows = 0

    def writable(self):
        return True

    def write(self, data):
        self.log.write(data)
        self.log.flush()
        *lines, remainder = bytes(data).split(b"\n")
        if lines:
            self.recent.append((bytes(self.pending) + lines[0])[:4096])
            self.recent.extend(line[:4096] for line in lines[1:])
            self.pending.clear()
        # Only the log retains arbitrarily long lines.
        self.pending.extend(remainder[: max(0, 4096 - len(self.pending))])
        if lines:
            self.draw()
        return len(data)

    def draw(self):
        cols, height = shutil.get_terminal_size()
        width = max(0, cols - 1)
        visible = max(0, min(5, height - 2))
        if self.total is None:
            progress = "Recopilando suites..."
        else:
            label = f"{self.completed}/{self.total} suites completadas"
            size = min(24, max(0, width - len(label) - 3))
            filled = size * self.completed // max(1, self.total)
            bar = "#" * filled + "-" * (size - filled)
            progress = f"{label} [{bar}]" if size else label
        lines = ([""] * 5 + list(self.recent))[-visible:] if visible else []
        rows = [progress[:width], *(terminal_line(line or b"", width) for line in lines)]
        # Leave the cursor on the last row, not a newline that could scroll the viewport.
        rewind = f"\x1b[{self.rows - 1}A" if self.rows > 1 else ""
        self.rows = len(rows)
        self.terminal.write(f"\r{rewind}\x1b[J" + "\r\n".join(rows))
        self.terminal.flush()

    def pytest_collection_finish(self, session):
        self.total = len(session.items)
        self.draw()

    def pytest_runtest_logreport(self, report):
        if report.when == "teardown":
            self.completed += 1
            self.draw()


def main():
    report, *args = sys.argv[1:]
    terminal = sys.stdout
    results = Path("test/results")
    results.mkdir(parents=True, exist_ok=True)
    terminated = None

    def interrupt(signum, _frame):
        nonlocal terminated
        terminated = signum
        raise KeyboardInterrupt

    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupt)

    sys.path.insert(0, str(Path.cwd()))  # Match `python -m pytest`.
    with NamedTemporaryFile(prefix="lote-", suffix=".log", dir=results, delete=False) as log:
        log_path = results / Path(log.name).name
        print(f"Registro completo: {log_path}", flush=True)
        live = LiveBatch(terminal, log)
        stream = io.TextIOWrapper(live, encoding="utf-8", errors="backslashreplace", write_through=True)
        try:
            live.draw()
            with redirect_stdout(stream), redirect_stderr(stream):
                try:
                    import pytest
                except ModuleNotFoundError as error:
                    if error.name != "pytest":
                        raise
                    print(f"{sys.executable}: No se encontró pytest.", file=sys.stderr)
                    status = 1
                else:
                    status = pytest.main([*args, "-s", "--color=no"], plugins=[live])
        except KeyboardInterrupt:
            status = 130
        finally:
            # No terminal modes were changed; leave the last frame and resume scrolling.
            print(file=terminal, flush=True)
            print(f"Registro completo: {log_path}", file=terminal, flush=True)
        if terminated is not None:
            status = 128 + terminated
    print(f"Código de salida: {status}")
    label = "Informe JUnit" if Path(report).is_file() else "No se generó el informe JUnit"
    print(f"{label}: {Path(report).resolve()}")
    return status


if __name__ == "__main__":
    sys.exit(main())
