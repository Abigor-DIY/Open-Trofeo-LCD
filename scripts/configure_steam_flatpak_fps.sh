#!/usr/bin/env bash
set -euo pipefail

APP_ID="com.valvesoftware.Steam"
SOCKET_PERMISSION="xdg-run/open-trofeo-lcd"

if ! command -v flatpak >/dev/null 2>&1; then
    echo "[-] flatpak command not found."
    exit 2
fi

if ! flatpak info "${APP_ID}" >/dev/null 2>&1; then
    echo "[-] Steam Flatpak is not installed for this user/system."
    echo "    Steam from DEB does not need this Flatpak override."
    exit 0
fi

flatpak override --user --filesystem="${SOCKET_PERMISSION}" "${APP_ID}"
echo "[+] Steam Flatpak can access /run/user/\$UID/open-trofeo-lcd."
echo "[i] Restart Steam completely before testing Open Trofeo FPS layer."
