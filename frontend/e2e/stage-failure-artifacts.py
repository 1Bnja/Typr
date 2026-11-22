"""Stage browser diagnostics without uploading raw Cucumber or Playwright data."""

import html
import json
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def messages(path):
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            yield json.loads(line)


def write_report(source, target):
    pickles, cases, started, outcomes = {}, {}, {}, {}
    for envelope in messages(source / "results.ndjson"):
        if row := envelope.get("pickle"):
            pickles[row["id"]] = row
        elif row := envelope.get("testCase"):
            cases[row["id"]] = row["pickleId"]
        elif row := envelope.get("testCaseStarted"):
            started[row["id"]] = cases[row["testCaseId"]]
        elif row := envelope.get("testStepFinished"):
            result = row["testStepResult"]
            outcomes.setdefault(row["testCaseStartedId"], []).append(result["status"])

    rows = []
    for attempt, statuses in outcomes.items():
        failed = [str(i) for i, status in enumerate(statuses, 1)
                  if status not in {"PASSED", "SKIPPED"}]
        if failed:
            case = pickles[started[attempt]]
            rows.append(f"<li>{html.escape(case['uri'])}: {html.escape(case['name'])}"
                        f" — failing step/hook positions: {', '.join(failed)}</li>")
    summary = ("<ul>" + "".join(rows) + "</ul>" if rows else
               "<p>No failing scenario result was recorded. The fixture may have failed before a scenario ran.</p>")
    target.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>Browser failure report</title><h1>Browser failure report</h1>"
        + summary + "<p>Raw error messages, attachments and network bodies are omitted. "
        "Trace files retain action names and timing only.</p></html>",
        encoding="utf-8",
    )


TRACE_FIELDS = {
    "context-options": ("version", "origin", "browserName", "playwrightVersion",
                        "platform", "wallTime", "monotonicTime", "sdkLanguage",
                        "testIdAttributeName", "contextId"),
    "before": ("callId", "startTime", "class", "method", "pageId"),
    "after": ("callId", "endTime"),
}


def write_trace(source, target):
    # Rebuild the archive instead of filtering secrets from opaque payloads.
    # In particular omit params, results, error strings, logs, DOM and network data.
    with ZipFile(source) as raw, ZipFile(target, "w", ZIP_DEFLATED) as safe:
        with raw.open("trace.trace") as original, safe.open("trace.trace", "w") as output:
            for line in original:
                event = json.loads(line)
                kind = event["type"]
                if kind in TRACE_FIELDS:
                    row = {key: event[key] for key in TRACE_FIELDS[kind] if key in event}
                    if kind == "after" and event.get("error"):
                        row["error"] = {"name": "Error", "message": "Action failed (details omitted)"}
                    if kind == "context-options":
                        row["options"] = {}
                    if kind == "before":
                        row["params"] = {}
                    output.write((json.dumps({"type": kind, **row}) + "\n").encode())


def stage(source, target):
    target.mkdir(mode=0o700)
    write_report(source, target / "report.html")
    for scenario in sorted(source.glob("scenario-*")):
        if not scenario.is_dir() or scenario.is_symlink():
            continue
        for trace in sorted(scenario.glob("trace-*.zip")):
            if trace.is_file() and not trace.is_symlink() and re.fullmatch(r"trace-\d+\.zip", trace.name):
                output = target / scenario.name
                output.mkdir(exist_ok=True)
                write_trace(trace, output / trace.name)
        # Video is only collected against the disposable, synthetic CI fixture;
        # the account password inputs are masked and there are no real accounts.
        for video in sorted(scenario.glob("context-*/*.webm")):
            if video.is_file() and not video.is_symlink() and not video.parent.is_symlink():
                output = target / scenario.name / video.parent.name
                output.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(video, output / video.name)


if __name__ == "__main__":
    stage(Path(sys.argv[1]), Path(sys.argv[2]))
