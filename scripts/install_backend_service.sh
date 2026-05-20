#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
UNIT_TEMPLATE="${WORKDIR}/systemd/trofeo-backend.service"
UNIT_NAME="trofeo-backend.service"
USER_SYSTEMD_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
UNIT_TARGET="${USER_SYSTEMD_DIR}/${UNIT_NAME}"
ENV_FILE="${WORKDIR}/.trofeo-backend.env"
ENV_EXAMPLE="${WORKDIR}/.trofeo-backend.env.example"

if [[ ! -f "${UNIT_TEMPLATE}" ]]; then
  echo "Brak template: ${UNIT_TEMPLATE}" >&2
  exit 1
fi

mkdir -p "${USER_SYSTEMD_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "Utworzono ${ENV_FILE} (edytuj parametry przed startem usługi)."
fi

if [[ ("${OPEN_TROFEO_SYSTEM_PACKAGE:-0}" == "1" || -f "${WORKDIR}/.system-package-version") && -x /usr/bin/open-trofeo-lcd ]]; then
  cat > "${UNIT_TARGET}" <<'EOF'
[Unit]
Description=Open Trofeo LCD Backend API
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/open-trofeo-lcd --backend-service-run
Restart=on-failure
RestartSec=2
TimeoutStopSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
else
  escaped_workdir="$(printf '%s' "${WORKDIR}" | sed 's/[\/&]/\\&/g')"
  sed "s/__WORKDIR__/${escaped_workdir}/g" "${UNIT_TEMPLATE}" > "${UNIT_TARGET}"
fi

systemctl --user daemon-reload

cat <<EOF
Zainstalowano jednostkę user: ${UNIT_TARGET}

Następne kroki:
  1) systemctl --user restart ${UNIT_NAME}
  2) systemctl --user status ${UNIT_NAME} --no-pager
  3) journalctl --user -u ${UNIT_NAME} -f

API status:
  curl -s http://127.0.0.1:18777/v1/status
EOF
