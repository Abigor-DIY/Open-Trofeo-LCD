#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${WORKDIR}/.venv-gui/bin/python" ]]; then
  PYTHON_BIN="${WORKDIR}/.venv-gui/bin/python"
elif [[ -x "${HOME}/trofeo-venv/bin/python" ]]; then
  PYTHON_BIN="${HOME}/trofeo-venv/bin/python"
else
  PYTHON_BIN="/usr/bin/python3"
fi

exec "${PYTHON_BIN}" "${WORKDIR}/main.py" --status
