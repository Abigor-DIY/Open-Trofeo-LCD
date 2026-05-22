#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${WORKDIR}/.trofeo-service.env"
LOG_DIR="${HOME}/.local/state/open-trofeo-lcd"
LOG_FILE="${LOG_DIR}/service.log"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Brak pliku konfiguracyjnego: ${ENV_FILE}" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

PCAP_FILE="${PCAP_FILE:-dzis.pcapng}"
FRAME_INDEX="${FRAME_INDEX:-0}"
ACK_TIMEOUT_MS="${ACK_TIMEOUT_MS:-500}"
INTER_PACKET_DELAY="${INTER_PACKET_DELAY:-0.01}"
FRAME_DELAY="${FRAME_DELAY:-0.02}"
CONNECT_RETRIES="${CONNECT_RETRIES:-20}"
CONNECT_RETRY_DELAY="${CONNECT_RETRY_DELAY:-0.5}"

if [[ "${PCAP_FILE}" = /* ]]; then
  PCAP_PATH="${PCAP_FILE}"
else
  PCAP_PATH="${WORKDIR}/${PCAP_FILE}"
fi

if [[ ! -f "${PCAP_PATH}" ]]; then
  echo "Brak pliku pcap: ${PCAP_PATH}" >&2
  exit 3
fi

mkdir -p "${LOG_DIR}"
exec >> "${LOG_FILE}" 2>&1
echo "[$(date --iso-8601=seconds)] start replay service: pcap=${PCAP_PATH} frame=${FRAME_INDEX}"

cd "${WORKDIR}"
exec /usr/bin/python3 "${WORKDIR}/replay_from_pcap.py" \
  --pcap "${PCAP_PATH}" \
  --frame "${FRAME_INDEX}" \
  --send-init \
  --recover-before-send \
  --drain-in-before-send \
  --ack-every-packet \
  --ack-on-seq0-only \
  --ack-timeout-ms "${ACK_TIMEOUT_MS}" \
  --inter-packet-delay "${INTER_PACKET_DELAY}" \
  --loop \
  --frame-delay "${FRAME_DELAY}" \
  --connect-retries "${CONNECT_RETRIES}" \
  --connect-retry-delay "${CONNECT_RETRY_DELAY}"
