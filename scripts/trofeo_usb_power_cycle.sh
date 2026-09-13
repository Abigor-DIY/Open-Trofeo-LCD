#!/usr/bin/env bash
set -euo pipefail

VID="${TROFEO_USB_VID:-0416}"
PID="${TROFEO_USB_PID:-5408}"
SETTLE_OFF="${TROFEO_USB_OFF_S:-5}"
SETTLE_ON="${TROFEO_USB_ON_S:-3}"
MODE="${TROFEO_USB_RECOVERY_MODE:-safe}"

usage() {
  cat >&2 <<'EOF'
Usage: trofeo_usb_power_cycle.sh [--mode safe|power|full]

Modes:
  safe   USBDEVFS_RESET only. Default and safest after suspend.
  power  USBDEVFS_RESET plus device unbind/bind and authorized cycle.
  full   Power mode plus parent hub reset when the Trofeo LCD is the only child.

The power/full modes can leave some boards with a black, unenumerated LCD until
AC power is removed. Use them only when safe mode does not recover the display.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      MODE="$2"
      shift 2
      ;;
    --mode=*)
      MODE="${1#--mode=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

case "${MODE}" in
  safe|power|full) ;;
  *)
    echo "Invalid TROFEO_USB_RECOVERY_MODE/--mode: ${MODE}" >&2
    usage
    exit 2
    ;;
esac

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root, for example:" >&2
  echo "  sudo $0 --mode safe" >&2
  exit 2
fi

find_device_dir() {
  local candidate
  for candidate in /sys/bus/usb/devices/*; do
    [[ -f "${candidate}/idVendor" && -f "${candidate}/idProduct" ]] || continue
    if [[ "$(tr '[:upper:]' '[:lower:]' < "${candidate}/idVendor")" == "${VID}" \
       && "$(tr '[:upper:]' '[:lower:]' < "${candidate}/idProduct")" == "${PID}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

usbdevfs_reset() {
  local device_dir="$1"
  local busnum devnum devnode

  [[ -f "${device_dir}/busnum" && -f "${device_dir}/devnum" ]] || return 1
  busnum="$(printf '%03d' "$(cat "${device_dir}/busnum")")"
  devnum="$(printf '%03d' "$(cat "${device_dir}/devnum")")"
  devnode="/dev/bus/usb/${busnum}/${devnum}"
  [[ -e "${devnode}" ]] || return 1

  python3 - "${devnode}" <<'PY'
import fcntl
import os
import sys

USBDEVFS_RESET = ord("U") << (4 * 2) | 20
path = sys.argv[1]
fd = os.open(path, os.O_WRONLY)
try:
    fcntl.ioctl(fd, USBDEVFS_RESET, 0)
finally:
    os.close(fd)
PY
}

unbind_bind() {
  local device_dir="$1"
  local devname

  devname="$(basename "${device_dir}")"
  [[ -w /sys/bus/usb/drivers/usb/unbind && -w /sys/bus/usb/drivers/usb/bind ]] || return 1

  echo "${devname}" > /sys/bus/usb/drivers/usb/unbind
  sleep "${SETTLE_OFF}"
  echo "${devname}" > /sys/bus/usb/drivers/usb/bind
  sleep "${SETTLE_ON}"
}

authorized_cycle() {
  local device_dir="$1"
  [[ -f "${device_dir}/authorized" ]] || return 1

  echo 0 > "${device_dir}/authorized"
  sleep "${SETTLE_OFF}"
  echo 1 > "${device_dir}/authorized"
  sleep "${SETTLE_ON}"
}

parent_hub_cycle_if_exclusive() {
  local device_dir="$1"
  local devname parent_name parent_dir child_count child

  devname="$(basename "${device_dir}")"
  [[ "${devname}" == *.* ]] || return 1
  parent_name="${devname%.*}"
  parent_dir="/sys/bus/usb/devices/${parent_name}"
  [[ -d "${parent_dir}" ]] || return 1
  [[ -w /sys/bus/usb/drivers/usb/unbind && -w /sys/bus/usb/drivers/usb/bind ]] || return 1

  child_count=0
  for child in /sys/bus/usb/devices/"${parent_name}".*; do
    [[ -e "${child}" ]] || continue
    [[ -f "${child}/devnum" && -f "${child}/idVendor" && -f "${child}/idProduct" ]] || continue
    child_count=$((child_count + 1))
  done

  if [[ "${child_count}" -ne 1 ]]; then
    echo "Parent hub ${parent_name} has ${child_count} children; skipping hub reset" >&2
    return 1
  fi

  echo "Parent hub ${parent_name} is exclusive; resetting hub port"
  echo "${parent_name}" > /sys/bus/usb/drivers/usb/unbind
  sleep "${SETTLE_OFF}"
  echo "${parent_name}" > /sys/bus/usb/drivers/usb/bind
  sleep "${SETTLE_ON}"
}

device_dir="$(find_device_dir || true)"

if [[ -z "${device_dir}" ]]; then
  echo "Trofeo LCD USB device not found: ${VID}:${PID}" >&2
  exit 1
fi

echo "Recovering Trofeo LCD USB at ${device_dir} (${VID}:${PID}) with mode=${MODE}"
if [[ "${MODE}" != "safe" ]]; then
  echo "Warning: mode=${MODE} may fully drop USB power on some boards; try safe mode first." >&2
fi

if usbdevfs_reset "${device_dir}"; then
  echo "USBDEVFS_RESET ok"
  sleep "${SETTLE_ON}"
else
  echo "USBDEVFS_RESET skipped or failed" >&2
fi

if [[ "${MODE}" == "power" || "${MODE}" == "full" ]]; then
  device_dir="$(find_device_dir || true)"
  if [[ -n "${device_dir}" ]] && unbind_bind "${device_dir}"; then
    echo "USB driver unbind/bind ok"
  else
    echo "USB driver unbind/bind skipped or failed" >&2
  fi

  device_dir="$(find_device_dir || true)"
  if [[ -n "${device_dir}" ]] && authorized_cycle "${device_dir}"; then
    echo "USB authorized power-cycle ok"
  else
    echo "USB authorized power-cycle skipped or failed" >&2
  fi
else
  echo "Safe mode: skipped USB driver unbind/bind and authorized power-cycle"
fi

if [[ "${MODE}" == "full" ]]; then
  device_dir="$(find_device_dir || true)"
  if [[ -n "${device_dir}" ]] && parent_hub_cycle_if_exclusive "${device_dir}"; then
    echo "Parent hub reset ok"
  else
    echo "Parent hub reset skipped or failed" >&2
  fi
else
  echo "Mode ${MODE}: skipped parent hub reset"
fi

device_dir="$(find_device_dir || true)"
if [[ -z "${device_dir}" ]]; then
  echo "Trofeo LCD USB did not reappear after recovery" >&2
  exit 1
fi

echo "Trofeo LCD USB recovery complete at ${device_dir}"
