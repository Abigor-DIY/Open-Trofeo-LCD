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

escaped_workdir="$(printf '%s' "${WORKDIR}" | sed 's/[\/&]/\\&/g')"
sed "s/__WORKDIR__/${escaped_workdir}/g" "${UNIT_TEMPLATE}" > "${UNIT_TARGET}"

systemctl --user daemon-reload

cat <<EOF
Zainstalowano jednostkę user: ${UNIT_TARGET}

Następne kroki:
  1) scripts/trofeo_backend_service.sh start
  2) scripts/trofeo_backend_service.sh status
  3) scripts/trofeo_backend_service.sh logs

API status:
  curl -s http://127.0.0.1:18777/v1/status
EOF
