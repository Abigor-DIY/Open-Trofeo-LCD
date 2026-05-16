#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

pick_python() {
  if [[ -x "${WORKDIR}/.venv-gui/bin/python" ]]; then
    echo "${WORKDIR}/.venv-gui/bin/python"
    return 0
  fi
  if [[ -x "${HOME}/trofeo-venv/bin/python" ]]; then
    echo "${HOME}/trofeo-venv/bin/python"
    return 0
  fi
  echo "/usr/bin/python3"
}

PYTHON_BIN="$(pick_python)"

cd "${WORKDIR}"

if [[ "${OPEN_TROFEO_GUI_ONLY:-0}" == "1" || "${1:-}" == "--gui-only" ]]; then
  shift || true
  BACKEND_URL="${1:-http://127.0.0.1:18777}"
  exec "${PYTHON_BIN}" "${WORKDIR}/trofeo_gui.py" --url "${BACKEND_URL}"
fi

exec "${PYTHON_BIN}" "${WORKDIR}/main.py" "$@"
