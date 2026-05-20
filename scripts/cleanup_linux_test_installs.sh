#!/usr/bin/env bash
set -euo pipefail

APP_ID="io.github.AbigorDIY.OpenTrofeoLCD"
APPLY=0

if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: $0 [--apply]

Without --apply this prints the cleanup actions only.
With --apply it removes stale user-level Flatpak/test launcher artifacts and
refreshes AppStream/KDE caches. It does not use sudo and does not remove the
APT/DEB package.
EOF
  exit 0
fi

run() {
  printf '+'
  for arg in "$@"; do
    printf ' %q' "${arg}"
  done
  printf '\n'
  if [[ "${APPLY}" -eq 1 ]]; then
    "$@" >/dev/null 2>&1 || true
  fi
}

remove_path() {
  local path="$1"
  printf '+ rm -rf %q\n' "$path"
  if [[ "${APPLY}" -eq 1 ]]; then
    rm -rf "$path"
  fi
}

if [[ "${APPLY}" -eq 0 ]]; then
  echo "[dry-run] Add --apply to execute these cleanup steps."
fi

if command -v flatpak >/dev/null 2>&1; then
  run flatpak uninstall --user -y "${APP_ID}"
fi

remove_path "${HOME}/.local/share/applications/open-trofeo-lcd.desktop"
remove_path "${HOME}/.local/share/flatpak/exports/share/applications/${APP_ID}.desktop"
remove_path "${HOME}/.local/share/flatpak/exports/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
remove_path "${HOME}/.var/app/${APP_ID}"
remove_path "${HOME}/.cache/appstream/user"
remove_path "${HOME}/.cache/Discover"
remove_path "${HOME}/.cache/plasma-discover"

if command -v appstreamcli >/dev/null 2>&1; then
  run appstreamcli refresh --force --verbose
fi

if command -v pkcon >/dev/null 2>&1; then
  run pkcon refresh force
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  run kbuildsycoca6
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
  run kbuildsycoca5
fi

echo "[done] Cleanup pass finished."
