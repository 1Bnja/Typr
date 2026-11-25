#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
exec "${TYPR_TEST_PYTHON:-python3}" tests/suite_runner.py "$@"
