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
PCAP_FILE="${PCAP_FILE:-dzis.pcapng}"
FRAME_INDEX="${FRAME_INDEX:-0}"
ACK_TIMEOUT_MS="${ACK_TIMEOUT_MS:-500}"
INTER_PACKET_DELAY="${INTER_PACKET_DELAY:-0.01}"
FRAME_DELAY="${FRAME_DELAY:-0.02}"
CONNECT_RETRIES="${CONNECT_RETRIES:-20}"
CONNECT_RETRY_DELAY="${CONNECT_RETRY_DELAY:-0.5}"
AUTOSTART="${AUTOSTART:-1}"
THEMES_FILE="${THEMES_FILE:-.trofeo-themes.json}"
PLAYLIST_FILE="${PLAYLIST_FILE:-.trofeo-playlist.json}"

mkdir -p "${LOG_DIR}"
exec >> "${LOG_FILE}" 2>&1
echo "[$(date --iso-8601=seconds)] start backend: host=${HOST} port=${PORT} frame=${FRAME_INDEX}"

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

exec /usr/bin/python3 "${WORKDIR}/trofeo_backend.py" "${args[@]}"
