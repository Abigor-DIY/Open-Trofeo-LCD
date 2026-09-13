#!/usr/bin/env bash
set -euo pipefail

TARGET_JSON="${XDG_DATA_HOME:-${HOME}/.local/share}/vulkan/implicit_layer.d/VkLayer_OPEN_TROFEO_fps.json"
if [[ -f "${TARGET_JSON}" ]]; then
    rm -f "${TARGET_JSON}"
fi
printf '%s\n' "${TARGET_JSON}"

STEAM_TARGET_JSON="${HOME}/.var/app/com.valvesoftware.Steam/.local/share/vulkan/implicit_layer.d/VkLayer_OPEN_TROFEO_fps.json"
if [[ -f "${STEAM_TARGET_JSON}" ]]; then
    rm -f "${STEAM_TARGET_JSON}"
fi
printf '%s\n' "${STEAM_TARGET_JSON}"

if [[ "${OPEN_TROFEO_KEEP_STEAM_FLATPAK_OVERRIDE:-0}" != "1" ]] && command -v flatpak >/dev/null 2>&1; then
    if flatpak info com.valvesoftware.Steam >/dev/null 2>&1; then
        flatpak override --user --nofilesystem=xdg-run/open-trofeo-lcd com.valvesoftware.Steam >/dev/null 2>&1 || true
        echo "[i] Removed Steam Flatpak access to xdg-run/open-trofeo-lcd."
    fi
fi
