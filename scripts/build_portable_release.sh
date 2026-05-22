#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${1:-0.1.0-dev}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/dist}"
PACKAGE_NAME="open-trofeo-lcd-${VERSION}-portable"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${OUT_DIR}"

if ! git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[-] This script must run from a Git checkout." >&2
  exit 2
fi

git -C "${ROOT_DIR}" archive --format=tar --prefix="${PACKAGE_NAME}/" HEAD | tar -C "${TMP_DIR}" -xf -

{
  printf 'Open Trofeo LCD portable package\n'
  printf 'version=%s\n' "${VERSION}"
  printf 'commit=%s\n' "$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"
  printf 'built_at_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf '\nRun from extracted directory:\n'
  printf '  ./scripts/run_trofeo_gui.sh --check-runtime\n'
  printf '  ./scripts/run_trofeo_gui.sh\n'
} > "${TMP_DIR}/${PACKAGE_NAME}/BUILD_INFO.txt"

tarball="${OUT_DIR}/${PACKAGE_NAME}.tar.gz"
checksum="${tarball}.sha256"
tar -C "${TMP_DIR}" -czf "${tarball}" "${PACKAGE_NAME}"
sha256sum "${tarball}" > "${checksum}"

printf '[+] Wrote %s\n' "${tarball}"
printf '[+] Wrote %s\n' "${checksum}"
