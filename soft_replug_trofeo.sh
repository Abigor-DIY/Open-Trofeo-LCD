#!/usr/bin/env bash
set -euo pipefail

VID="0416"
PID="5408"

find_dev_path() {
  local dev
  for dev in /sys/bus/usb/devices/*; do
    [[ -f "${dev}/idVendor" && -f "${dev}/idProduct" ]] || continue
    if [[ "$(cat "${dev}/idVendor")" == "${VID}" && "$(cat "${dev}/idProduct")" == "${PID}" ]]; then
      echo "${dev}"
      return 0
    fi
  done
  return 1
}

if [[ "${EUID}" -ne 0 ]]; then
  echo "Uruchom jako root, np.: sudo $0" >&2
  exit 1
fi

DEV_PATH="$(find_dev_path || true)"
if [[ -z "${DEV_PATH}" ]]; then
  echo "Nie znaleziono urządzenia ${VID}:${PID} w /sys/bus/usb/devices" >&2
  exit 2
fi

echo "Soft replug: ${DEV_PATH} (${VID}:${PID})"
echo 0 > "${DEV_PATH}/authorized"
sleep 1
echo 1 > "${DEV_PATH}/authorized"
sleep 1
echo "OK"
