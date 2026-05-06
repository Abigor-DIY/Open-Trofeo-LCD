#!/usr/bin/env bash
set -euo pipefail

UNIT="trofeo-lcd.service"
LOG_FILE="${HOME}/.local/state/open-trofeo-lcd/service.log"

usage() {
  cat <<EOF
Użycie: $0 <command>

Komendy:
  install   Instalacja/odświeżenie user unit + daemon-reload
  start     Start usługi
  stop      Stop usługi
  restart   Restart usługi
  status    Status usługi
  logs      Podgląd logu plikowego (tail -f)
  journal   Podgląd journald (journalctl -f)
  enable    Włącz autostart usługi
  disable   Wyłącz autostart usługi
EOF
}

cmd="${1:-}"

case "${cmd}" in
  install)
    "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install_user_service.sh"
    ;;
  start)
    if ! systemctl --user start "${UNIT}"; then
      systemctl --user --no-pager --full status "${UNIT}" || true
      journalctl --user -u "${UNIT}" -n 80 --no-pager || true
      exit 1
    fi
    systemctl --user --no-pager --full status "${UNIT}" || true
    ;;
  stop)
    if ! timeout 15s systemctl --user stop "${UNIT}"; then
      echo "Stop timeout - wymuszam cleanup..."
      "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/trofeo_kill.sh"
    fi
    ;;
  restart)
    systemctl --user restart "${UNIT}"
    systemctl --user --no-pager --full status "${UNIT}" || true
    ;;
  status)
    systemctl --user --no-pager --full status "${UNIT}"
    ;;
  logs)
    mkdir -p "$(dirname "${LOG_FILE}")"
    touch "${LOG_FILE}"
    tail -n 100 -f "${LOG_FILE}"
    ;;
  journal)
    journalctl --user -u "${UNIT}" -f
    ;;
  enable)
    systemctl --user enable "${UNIT}"
    ;;
  disable)
    systemctl --user disable "${UNIT}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
