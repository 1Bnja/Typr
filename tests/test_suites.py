"""One JUnit testcase per canonical suite, not per subprocess testcase."""

import os
import re

import pytest

from suite_runner import SUITES, SuiteFailure, run_suite


@pytest.mark.parametrize("suite", list(SUITES))
def test_suite(suite, request):
    live = request.config.pluginmanager.get_plugin("typr_live_batch")
    counts = []
    ci_latency = suite == "latency" and os.environ.get("TYPR_CI_LATENCY_OUTPUT") == "1"
    measured = False

    def capture(line):
        nonlocal measured
        if live is not None:
            live.write(line)
        if ci_latency:
            print(line.decode("utf-8", errors="replace"), end="", flush=True)
            measured |= b"latencia de progress_update con " in line and b", p95=" in line
            return
        match = re.fullmatch(
            rb"Backend service branch coverage: ([0-9]+)/([0-9]+) "
            rb"\([0-9]+\.[0-9]{2}%; minimum 60%\)", line.rstrip(b"\r\n"),
        )
        if match and len(counts) < 2:
            counts.append(match.groups())

    # Only the local batch opts into xunit1 testcase properties.
    capture_coverage = suite == "backend-coverage" and request.config.getini("junit_family") == "xunit1"
    try:
        emit = capture if capture_coverage or ci_latency else live.write if live is not None else None
        run_suite(suite, emit_bytes=emit)
        if ci_latency and not measured:
            pytest.fail("Latency run produced no p95 measurement", pytrace=False)
    except SuiteFailure as error:
        pytest.fail(str(error), pytrace=False)
    finally:
        if len(counts) == 1:
            covered, total = counts[0]
            request.getfixturevalue("record_property")(
                "typr_service_branch_counts", f"{covered.decode()}/{total.decode()}",
            )
