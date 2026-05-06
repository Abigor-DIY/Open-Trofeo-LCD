#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORT="${PORT:-18777}"

usage() {
  cat <<EOF
Użycie: $0 [--quiet]

Twardy cleanup Open-Trofeo-LCD:
  - zatrzymuje user units:
      trofeo-backend.service
      trofeo-lcd.service
  - ubija procesy:
      trofeo_gui.py
      trofeo_backend.py
      trofeo_lcd.py
      replay_from_pcap.py
      scripts/trcc_static_image.py
      scripts/trcc_animated_image.py
      .venv-trcc/bin/trcc
      run_backend_service.sh
      run_replay_service.sh
  - czyści port API: ${PORT}

Uwaga: to jest agresywny cleanup przeznaczony do sytuacji,
gdy GUI/backend/tray się rozjadą albo zostaną osierocone procesy.
EOF
}

QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
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
  systemctl --user stop "${unit}" >/dev/null 2>&1 || true
  systemctl --user kill --kill-who=all "${unit}" >/dev/null 2>&1 || true
  systemctl --user reset-failed "${unit}" >/dev/null 2>&1 || true
}

kill_pattern_term_then_kill() {
  local pattern="$1"
  pkill -TERM -f "${pattern}" >/dev/null 2>&1 || true
  sleep 0.4
  pkill -KILL -f "${pattern}" >/dev/null 2>&1 || true
}

collect_port_pids() {
  local port="$1"
  local pids=""

  if have_cmd lsof; then
    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  elif have_cmd fuser; then
    pids="$(fuser -n tcp "${port}" 2>/dev/null || true)"
  fi

  if [[ -n "${pids}" ]]; then
    printf '%s\n' "${pids}" | tr ' ' '\n' | awk 'NF' | sort -u | while read -r pid; do
      if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
        printf '%s\n' "${pid}"
      fi
    done
  fi
}

log "nuke: stop user units..."
stop_user_unit "trofeo-backend.service"
stop_user_unit "trofeo-lcd.service"

log "nuke: kill repo processes..."
kill_pattern_term_then_kill "${WORKDIR}/trofeo_gui.py"
kill_pattern_term_then_kill "${WORKDIR}/trofeo_backend.py"
kill_pattern_term_then_kill "${WORKDIR}/trofeo_lcd.py"
kill_pattern_term_then_kill "${WORKDIR}/replay_from_pcap.py"
kill_pattern_term_then_kill "${WORKDIR}/scripts/trcc_static_image.py"
kill_pattern_term_then_kill "${WORKDIR}/scripts/trcc_animated_image.py"
kill_pattern_term_then_kill "${WORKDIR}/scripts/run_backend_service.sh"
kill_pattern_term_then_kill "${WORKDIR}/scripts/run_replay_service.sh"
kill_pattern_term_then_kill "${WORKDIR}/.venv-trcc/bin/trcc"

mapfile -t PORT_PIDS < <(collect_port_pids "${PORT}" || true)
if [[ "${#PORT_PIDS[@]}" -gt 0 ]]; then
  log "nuke: kill port ${PORT}: ${PORT_PIDS[*]}"
  kill -TERM "${PORT_PIDS[@]}" >/dev/null 2>&1 || true
  sleep 0.5
  kill -KILL "${PORT_PIDS[@]}" >/dev/null 2>&1 || true
fi

sleep 0.5
mapfile -t FINAL_PIDS < <(collect_port_pids "${PORT}" || true)
if [[ "${#FINAL_PIDS[@]}" -gt 0 ]]; then
  log "uwaga: port ${PORT} nadal zajety przez PID: ${FINAL_PIDS[*]}"
  exit 1
fi

log "OK: nuke complete"
