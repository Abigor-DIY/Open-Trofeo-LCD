#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${1:-0.1.0}"
RELEASE="${2:-0.dev1}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/dist/rpm}"
PACKAGE_NAME="open-trofeo-lcd"
WORK_DIR="$(mktemp -d)"
RPM_TOPDIR="${WORK_DIR}/rpmbuild"

cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "[-] rpmbuild not found. Install rpm-build first." >&2
  exit 2
fi

if ! git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[-] This script must run from a Git checkout." >&2
  exit 2
fi

mkdir -p "${RPM_TOPDIR}/"{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} "${OUT_DIR}"

tarball="${RPM_TOPDIR}/SOURCES/${PACKAGE_NAME}-${VERSION}.tar.gz"
git -C "${ROOT_DIR}" archive --format=tar.gz --prefix="${PACKAGE_NAME}-${VERSION}/" HEAD > "${tarball}"
cp -a "${ROOT_DIR}/packaging/rpm/open-trofeo-lcd.spec" "${RPM_TOPDIR}/SPECS/"

rpmbuild \
  --define "_topdir ${RPM_TOPDIR}" \
  --define "version ${VERSION}" \
  --define "release ${RELEASE}" \
  -ba "${RPM_TOPDIR}/SPECS/open-trofeo-lcd.spec"

find "${RPM_TOPDIR}/RPMS" "${RPM_TOPDIR}/SRPMS" -type f \( -name '*.rpm' -o -name '*.src.rpm' \) -exec cp -a {} "${OUT_DIR}/" \;
printf '[+] Wrote RPM artifacts to %s\n' "${OUT_DIR}"
