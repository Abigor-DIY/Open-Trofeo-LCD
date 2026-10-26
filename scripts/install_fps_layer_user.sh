#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_TARGET_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/vulkan/implicit_layer.d"
USER_TARGET_JSON="${USER_TARGET_DIR}/VkLayer_OPEN_TROFEO_fps.json"
STEAM_FLATPAK_APP="com.valvesoftware.Steam"
STEAM_FLATPAK_SOCKET="xdg-run/open-trofeo-lcd"

configure_steam_flatpak_runtime_access() {
    if [[ "${OPEN_TROFEO_SKIP_STEAM_FLATPAK_OVERRIDE:-0}" == "1" ]]; then
        echo "[i] Skipping Steam Flatpak runtime socket override."
        return 0
    fi
    if ! command -v flatpak >/dev/null 2>&1; then
        echo "[i] Flatpak not found; skipping Steam Flatpak runtime socket override."
        return 0
    fi
    if ! flatpak info "${STEAM_FLATPAK_APP}" >/dev/null 2>&1; then
        echo "[i] Steam Flatpak is not installed; skipping Steam Flatpak runtime socket override."
        return 0
    fi
    if flatpak override --user --filesystem="${STEAM_FLATPAK_SOCKET}" "${STEAM_FLATPAK_APP}" >/dev/null 2>&1; then
        echo "[+] Steam Flatpak can access /run/user/\$UID/open-trofeo-lcd via ${STEAM_FLATPAK_SOCKET}."
        echo "[i] Restart Steam after changing Flatpak overrides."
    else
        echo "[!] Could not apply Steam Flatpak override automatically." >&2
        echo "    Run: flatpak override --user --filesystem=${STEAM_FLATPAK_SOCKET} ${STEAM_FLATPAK_APP}" >&2
    fi
}

BUILD_OUTPUT="$("${ROOT_DIR}/scripts/build_fps_probe.sh" --always-make)"
SOURCE_JSON="$(printf '%s\n' "${BUILD_OUTPUT}" | grep 'VkLayer_OPEN_TROFEO_fps\.json$' | tail -n 1)"
if [[ -z "${SOURCE_JSON}" || ! -f "${SOURCE_JSON}" ]]; then
    echo "[-] Vulkan layer manifest was not generated." >&2
    exit 2
fi
mkdir -p "${USER_TARGET_DIR}"
install -m 0644 "${SOURCE_JSON}" "${USER_TARGET_JSON}"
printf '%s\n' "${USER_TARGET_JSON}"

STEAM_FLATPAK_HOME="${HOME}/.var/app/${STEAM_FLATPAK_APP}"
if [[ -d "${STEAM_FLATPAK_HOME}" ]]; then
    STEAM_CACHE_HOME="${STEAM_FLATPAK_HOME}/.cache/open-trofeo-lcd/fps_probe"
    STEAM_DATA_DIR="${STEAM_FLATPAK_HOME}/.local/share/vulkan/implicit_layer.d"
    mkdir -p "${STEAM_CACHE_HOME}" "${STEAM_DATA_DIR}"
    cp -f "${ROOT_DIR}/native/fps_probe/Makefile" "${ROOT_DIR}/native/fps_probe/open_trofeo_fps_probe.c" "${STEAM_CACHE_HOME}/"
    make --always-make -C "${STEAM_CACHE_HOME}" >/dev/null
    STEAM_JSON="${STEAM_DATA_DIR}/VkLayer_OPEN_TROFEO_fps.json"
    sed "s#\"library_path\": \".*libopen_trofeo_fps_probe.so\"#\"library_path\": \"${STEAM_CACHE_HOME}/libopen_trofeo_fps_probe.so\"#" "${SOURCE_JSON}" > "${STEAM_JSON}"
    printf '%s\n' "${STEAM_JSON}"
    configure_steam_flatpak_runtime_access
fi
