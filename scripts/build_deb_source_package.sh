#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${1:-0.1.0~dev20260519}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/dist/deb-source}"
PACKAGE_NAME="open-trofeo-lcd"
WORK_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

if ! command -v dpkg-buildpackage >/dev/null 2>&1; then
  echo "[-] dpkg-buildpackage not found. Install dpkg-dev first." >&2
  exit 2
fi

if ! git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[-] This script must run from a Git checkout." >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"
SRC_DIR="${WORK_DIR}/${PACKAGE_NAME}-${VERSION}"
git -C "${ROOT_DIR}" archive --format=tar --prefix="${PACKAGE_NAME}-${VERSION}/" HEAD | tar -C "${WORK_DIR}" -xf -
rm -rf "${SRC_DIR}/debian"
cp -a "${SRC_DIR}/packaging/deb/debian" "${SRC_DIR}/debian"

export DEBEMAIL="${DEBEMAIL:-abigor-diy@users.noreply.github.com}"
export DEBFULLNAME="${DEBFULLNAME:-Abigor-DIY}"

(
  cd "${SRC_DIR}"
  sed -i "1s/([^)]*)/(${VERSION})/" debian/changelog
  dpkg-buildpackage -S -us -uc -d
)

find "${WORK_DIR}" -maxdepth 1 -type f \
  \( -name '*.dsc' -o -name '*.tar.*' -o -name '*.buildinfo' -o -name '*.changes' \) \
  -exec cp -a {} "${OUT_DIR}/" \;
printf '[+] Wrote DEB source artifacts to %s\n' "${OUT_DIR}"
