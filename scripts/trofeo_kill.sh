#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORT="${PORT:-18777}"
GRACE_SECONDS="${GRACE_SECONDS:-3}"

usage() {
  cat <<EOF
Uzycie: $0 [--port PORT] [--grace SEC] [--quiet]

Czyści procesy/uslugi Open-Trofeo-LCD:
  - trofeo-backend.service
  - trofeo-lcd.service
  - trofeo_backend.py
  - replay_from_pcap.py
  - trofeo_lcd.py
  - scripts/trcc_static_image.py
  - scripts/trcc_animated_image.py
  - run_backend_service.sh
  - run_replay_service.sh

Domyslny port API: 18777
EOF
}

QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --grace)
      GRACE_SECONDS="$2"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Nieznany argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log() {
  if [[ "${QUIET}" != "1" ]]; then
    echo "$@"
  fi
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

stop_user_unit() {
  local unit="$1"
  if ! have_cmd systemctl; then
    return 0
  fi
  if systemctl --user --quiet is-active "${unit}" 2>/dev/null; then
    log "stop unit: ${unit}"
    systemctl --user stop "${unit}" >/dev/null 2>&1 || true
  fi
  systemctl --user kill --kill-who=all "${unit}" >/dev/null 2>&1 || true
  systemctl --user reset-failed "${unit}" >/dev/null 2>&1 || true
}

collect_port_pids() {
  local port="$1"
  local pids=""

  if have_cmd lsof; then
    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  elif have_cmd fuser; then
    pids="$(fuser -n tcp "${port}" 2>/dev/null || true)"
  elif have_cmd ss; then
    pids="$(ss -ltnp 2>/dev/null | awk -v port=":${port}" '$4 ~ port {print $NF}' | grep -Eo 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  fi

  if [[ -n "${pids}" ]]; then
    printf '%s\n' "${pids}" | tr ' ' '\n' | awk 'NF' | sort -u | while read -r pid; do
      if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
        printf '%s\n' "${pid}"
      fi
    done
  fi
}

kill_pid_list() {
  local signal="$1"
  shift
  local pids=("$@")

  if [[ "${#pids[@]}" -eq 0 ]]; then
    return 0
  fi

  kill -"${signal}" "${pids[@]}" >/dev/null 2>&1 || true
}

wait_gone() {
  local deadline
  deadline=$((SECONDS + GRACE_SECONDS))
  while (( SECONDS < deadline )); do
    if ! pgrep -f "${WORKDIR}/trofeo_backend.py|${WORKDIR}/replay_from_pcap.py|${WORKDIR}/trofeo_lcd.py|${WORKDIR}/scripts/trcc_static_image.py|${WORKDIR}/scripts/trcc_animated_image.py|${WORKDIR}/scripts/run_backend_service.sh|${WORKDIR}/scripts/run_replay_service.sh" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

stop_user_unit "trofeo-backend.service"
stop_user_unit "trofeo-lcd.service"

log "term processes..."
pkill -TERM -f "${WORKDIR}/trofeo_backend.py" >/dev/null 2>&1 || true
pkill -TERM -f "${WORKDIR}/replay_from_pcap.py" >/dev/null 2>&1 || true
pkill -TERM -f "${WORKDIR}/trofeo_lcd.py" >/dev/null 2>&1 || true
pkill -TERM -f "${WORKDIR}/scripts/trcc_static_image.py" >/dev/null 2>&1 || true
pkill -TERM -f "${WORKDIR}/scripts/trcc_animated_image.py" >/dev/null 2>&1 || true
pkill -TERM -f "${WORKDIR}/scripts/run_backend_service.sh" >/dev/null 2>&1 || true
pkill -TERM -f "${WORKDIR}/scripts/run_replay_service.sh" >/dev/null 2>&1 || true

mapfile -t PORT_PIDS < <(collect_port_pids "${PORT}" || true)
if [[ "${#PORT_PIDS[@]}" -gt 0 ]]; then
  log "term port ${PORT}: ${PORT_PIDS[*]}"
  kill_pid_list TERM "${PORT_PIDS[@]}"
fi

if ! wait_gone; then
  log "kill -9 leftovers..."
  pkill -KILL -f "${WORKDIR}/trofeo_backend.py" >/dev/null 2>&1 || true
  pkill -KILL -f "${WORKDIR}/replay_from_pcap.py" >/dev/null 2>&1 || true
  pkill -KILL -f "${WORKDIR}/trofeo_lcd.py" >/dev/null 2>&1 || true
  pkill -KILL -f "${WORKDIR}/scripts/trcc_static_image.py" >/dev/null 2>&1 || true
  pkill -KILL -f "${WORKDIR}/scripts/trcc_animated_image.py" >/dev/null 2>&1 || true
  pkill -KILL -f "${WORKDIR}/scripts/run_backend_service.sh" >/dev/null 2>&1 || true
  pkill -KILL -f "${WORKDIR}/scripts/run_replay_service.sh" >/dev/null 2>&1 || true
  if [[ "${#PORT_PIDS[@]}" -gt 0 ]]; then
    kill_pid_list KILL "${PORT_PIDS[@]}"
  fi
fi

sleep 0.3
mapfile -t FINAL_PIDS < <(collect_port_pids "${PORT}" || true)
if [[ "${#FINAL_PIDS[@]}" -gt 0 ]]; then
  log "uwaga: port ${PORT} nadal zajety przez PID: ${FINAL_PIDS[*]}"
  exit 1
fi

log "OK: cleanup complete"
