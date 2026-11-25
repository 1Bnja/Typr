"""Enforce the backend service branch-exit floor from a scoped coverage.py report."""

import json
import sys
from pathlib import Path

MIN_PERCENT = 60


def main():
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    measured = {Path(name) for name in report["files"]}
    expected = set(Path("backend/app/services").rglob("*.py"))
    if not expected or measured != expected:
        sys.exit(f"Unexpected service coverage scope: missing={expected - measured}, extra={measured - expected}")
    covered = report["totals"].get("covered_branches")
    total = report["totals"].get("num_branches")
    if report["meta"].get("branch_coverage") is not True or not (
        type(covered) is int and type(total) is int and total > 0 and 0 <= covered <= total
    ):
        sys.exit("No valid branch counts in the service coverage report.")

    print(f"Backend service branch coverage: {covered}/{total} ({100 * covered / total:.2f}%; minimum {MIN_PERCENT}%)")
    if 100 * covered < MIN_PERCENT * total:
        sys.exit("Backend service branch coverage is below the CI floor.")


if __name__ == "__main__":
    main()
