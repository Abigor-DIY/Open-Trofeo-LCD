#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${WORKDIR}/.trofeo-backend.env"
LOG_DIR="${HOME}/.local/state/open-trofeo-lcd"
LOG_FILE="${LOG_DIR}/backend.log"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Brak pliku konfiguracyjnego: ${ENV_FILE}" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18777}"
PYTHON_BIN="${PYTHON_BIN:-${WORKDIR}/.venv-trcc/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="/usr/bin/python3"
fi
export PYTHON_BIN
PCAP_FILE="${PCAP_FILE:-dzis.pcapng}"
FRAME_INDEX="${FRAME_INDEX:-0}"
ACK_TIMEOUT_MS="${ACK_TIMEOUT_MS:-500}"
INTER_PACKET_DELAY="${INTER_PACKET_DELAY:-0.01}"
FRAME_DELAY="${FRAME_DELAY:-0.02}"
CONNECT_RETRIES="${CONNECT_RETRIES:-20}"
CONNECT_RETRY_DELAY="${CONNECT_RETRY_DELAY:-0.5}"
AUTOSTART="${AUTOSTART:-0}"
STARTUP_THEME="${STARTUP_THEME:-}"
TAKEOVER_EXISTING="${TAKEOVER_EXISTING:-1}"
TAKEOVER_WAIT_ATTEMPTS="${TAKEOVER_WAIT_ATTEMPTS:-48}"
THEMES_FILE="${THEMES_FILE:-.trofeo-themes.json}"
PLAYLIST_FILE="${PLAYLIST_FILE:-.trofeo-playlist.json}"

backend_responding() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 1 "http://${HOST}:${PORT}/health" >/dev/null 2>&1
    return $?
  fi
  "${PYTHON_BIN}" - <<PY >/dev/null 2>&1
import sys, urllib.request
try:
    with urllib.request.urlopen("http://${HOST}:${PORT}/health", timeout=1) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

backend_workdir() {
  "${PYTHON_BIN}" - "${HOST}" "${PORT}" <<'PY' 2>/dev/null
import json
import sys
import urllib.request

host, port = sys.argv[1], sys.argv[2]
try:
    with urllib.request.urlopen(f"http://{host}:{port}/v1/status", timeout=1.5) as resp:
        payload = json.load(resp)
except Exception:
    sys.exit(1)

config = payload.get("config") or {}
workdir = config.get("workdir") or ""
if workdir:
    print(workdir)
PY
}

request_backend_shutdown() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 3 -X POST \
      -H "Content-Type: application/json" \
      -d '{}' \
      "http://${HOST}:${PORT}/v1/shutdown" >/dev/null
    return $?
  fi
  "${PYTHON_BIN}" - "${HOST}" "${PORT}" <<'PY' >/dev/null
import sys
import urllib.request

host, port = sys.argv[1], sys.argv[2]
req = urllib.request.Request(f"http://{host}:{port}/v1/shutdown", data=b"{}", method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, timeout=3) as resp:
    sys.exit(0 if 200 <= resp.status < 300 else 1)
PY
}

wait_backend_stopped() {
  local attempts="${1:-48}"
  while (( attempts > 0 )); do
    if ! backend_responding; then
      return 0
    fi
    sleep 0.25
    attempts=$((attempts - 1))
  done
  return 1
}

same_workdir() {
  local other="${1:-}"
  if [[ -z "${other}" ]]; then
    return 1
  fi
  local current_resolved other_resolved
  current_resolved="$(cd "${WORKDIR}" && pwd -P)"
  other_resolved="$(cd "${other}" 2>/dev/null && pwd -P || printf '%s' "${other}")"
  [[ "${current_resolved}" == "${other_resolved}" ]]
}

mkdir -p "${LOG_DIR}"
exec >> "${LOG_FILE}" 2>&1
echo "[$(date --iso-8601=seconds)] start backend: host=${HOST} port=${PORT} frame=${FRAME_INDEX}"
trap 'echo "[$(date --iso-8601=seconds)] backend wrapper interrupted"; exit 0' INT TERM

cd "${WORKDIR}"

args=(
  --workdir "${WORKDIR}"
  --host "${HOST}"
  --port "${PORT}"
  --pcap "${PCAP_FILE}"
  --frame-index "${FRAME_INDEX}"
  --ack-timeout-ms "${ACK_TIMEOUT_MS}"
  --inter-packet-delay "${INTER_PACKET_DELAY}"
  --frame-delay "${FRAME_DELAY}"
  --connect-retries "${CONNECT_RETRIES}"
  --connect-retry-delay "${CONNECT_RETRY_DELAY}"
  --themes-file "${THEMES_FILE}"
  --playlist-file "${PLAYLIST_FILE}"
)

if [[ "${AUTOSTART}" == "1" || "${AUTOSTART}" == "true" || "${AUTOSTART}" == "TRUE" ]]; then
  args+=(--autostart)
fi
if [[ -n "${STARTUP_THEME}" ]]; then
  args+=(--startup-theme "${STARTUP_THEME}")
fi

if backend_responding; then
  existing_workdir="$(backend_workdir || true)"
  if [[ "${TAKEOVER_EXISTING}" == "1" || "${TAKEOVER_EXISTING}" == "true" || "${TAKEOVER_EXISTING}" == "TRUE" ]]; then
    if [[ -n "${existing_workdir}" ]] && ! same_workdir "${existing_workdir}"; then
      echo "[$(date --iso-8601=seconds)] backend already active on ${HOST}:${PORT} from another workdir: ${existing_workdir}" >&2
      echo "[$(date --iso-8601=seconds)] refusing takeover; stop the other backend first" >&2
      exit 3
    fi
    echo "[$(date --iso-8601=seconds)] backend already active on ${HOST}:${PORT}; requesting graceful takeover"
    if ! request_backend_shutdown; then
      echo "[$(date --iso-8601=seconds)] graceful takeover failed: /v1/shutdown did not succeed" >&2
      exit 1
    fi
    if ! wait_backend_stopped "${TAKEOVER_WAIT_ATTEMPTS}"; then
      echo "[$(date --iso-8601=seconds)] graceful takeover failed: backend still responds on ${HOST}:${PORT}" >&2
      exit 1
    fi
    echo "[$(date --iso-8601=seconds)] graceful takeover complete; port ${PORT} is free"
  else
    echo "[$(date --iso-8601=seconds)] backend already active on ${HOST}:${PORT}; entering standby guard"
    while backend_responding; do
      sleep 2
    done
    echo "[$(date --iso-8601=seconds)] standby guard released; port ${PORT} is free"
  fi
fi

exec "${PYTHON_BIN}" "${WORKDIR}/trofeo_backend.py" "${args[@]}"
