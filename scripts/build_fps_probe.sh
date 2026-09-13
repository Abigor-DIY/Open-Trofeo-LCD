#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_PROBE_DIR="${ROOT_DIR}/native/fps_probe"
if [[ -w "${SOURCE_PROBE_DIR}" ]]; then
    PROBE_DIR="${SOURCE_PROBE_DIR}"
else
    CACHE_ROOT="${XDG_CACHE_HOME:-${HOME}/.cache}/open-trofeo-lcd/fps_probe"
    mkdir -p "${CACHE_ROOT}"
    cp -f "${SOURCE_PROBE_DIR}/Makefile" "${SOURCE_PROBE_DIR}/open_trofeo_fps_probe.c" "${CACHE_ROOT}/"
    PROBE_DIR="${CACHE_ROOT}"
fi
LAYER_DIR="${PROBE_DIR}/implicit_layer.d"
LAYER_JSON="${LAYER_DIR}/VkLayer_OPEN_TROFEO_fps.json"

make -C "${PROBE_DIR}" "$@"
if [[ "${1:-}" != "clean" ]]; then
    mkdir -p "${LAYER_DIR}"
    cat > "${LAYER_JSON}" <<JSON
{
  "file_format_version": "1.0.0",
  "layer": {
    "name": "VK_LAYER_OPEN_TROFEO_fps",
    "type": "GLOBAL",
    "api_version": "1.3.0",
    "library_path": "${PROBE_DIR}/libopen_trofeo_fps_probe.so",
    "implementation_version": "1",
    "description": "Open Trofeo LCD no-overlay FPS probe",
    "functions": {
      "vkNegotiateLoaderLayerInterfaceVersion": "vkNegotiateLoaderLayerInterfaceVersion",
      "vkGetInstanceProcAddr": "open_trofeo_GetInstanceProcAddr",
      "vkGetDeviceProcAddr": "open_trofeo_GetDeviceProcAddr"
    },
    "enable_environment": {
      "OPEN_TROFEO_FPS_LAYER": "1"
    },
    "disable_environment": {
      "DISABLE_OPEN_TROFEO_FPS_LAYER": "1"
    }
  }
}
JSON
    printf '%s\n' "${LAYER_JSON}"
fi
printf '%s\n' "${PROBE_DIR}/libopen_trofeo_fps_probe.so"
