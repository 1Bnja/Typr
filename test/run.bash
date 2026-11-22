#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ $# -ne 0 ]]; then
    echo "Usage: $0" >&2
    exit 2
fi

local_env="$(pwd -P)/test/.venv"
python="$local_env/bin/python"
if [[ ! -x "$python" ]] || ! "$python" -c 'import jupyterlab' >/dev/null 2>&1; then
    echo 'JupyterLab is not installed in test/.venv. See test/README.md for setup.' >&2
    exit 1
fi

export JUPYTER_PREFER_ENV_PATH=1
export JUPYTER_PATH="$local_env/share/jupyter${JUPYTER_PATH:+:$JUPYTER_PATH}"
exec "$python" -m jupyterlab --ip=127.0.0.1 --port=8888 --port-retries=0 \
    --notebook-dir="$(pwd -P)" --ServerApp.open_browser=True tests.ipynb
