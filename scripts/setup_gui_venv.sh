#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${WORKDIR}/.venv-gui"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/pip" install PySide6

if ! command -v playerctl >/dev/null 2>&1; then
  cat <<EOF
UWAGA: Nie znaleziono 'playerctl'.
Widget "Now Playing" (Spotify / Chromium / YT Music) wymaga playerctl + MPRIS.
Zainstaluj:
  sudo apt install playerctl
EOF
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  cat <<EOF
UWAGA: Nie znaleziono 'ffmpeg'.
Tryb "Now Playing Hero Video" dla lokalnych playerów używa ffmpeg do wyciągania klatki z pliku wideo.
Zainstaluj:
  sudo apt install ffmpeg
EOF
fi

if ! command -v cava >/dev/null 2>&1; then
  cat <<EOF
UWAGA: Nie znaleziono 'cava'.
Realne pasma EQ w widżetach Now Playing / Graphic EQ wymagają cava.
Bez cava aplikacja użyje syntetycznego fallbacku EQ.
Zainstaluj:
  sudo apt install cava
EOF
fi

cat <<EOF
GUI venv gotowy:
  ${VENV_DIR}

Uruchom GUI:
  scripts/run_trofeo_gui.sh
EOF
