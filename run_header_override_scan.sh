#!/usr/bin/env bash
set -u

PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRIVER="$SCRIPT_DIR/trofeo_lcd.py"
JPEG_PATH="${1:-$SCRIPT_DIR/reference_frame_trcc.jpg}"
LOG_DIR="$SCRIPT_DIR/header_scan_logs"

if [[ ! -f "$JPEG_PATH" ]]; then
  echo "Brak pliku JPEG: $JPEG_PATH"
  exit 1
fi

mkdir -p "$LOG_DIR"

values=(
  "0x0"
  "0x1000"
  "0x7f0"
  "0x800"
  "0x78d8"
  "0x4daf1"
)

echo "Skan naglowka bytes 2-5 dla pliku: $JPEG_PATH"
echo "Logi: $LOG_DIR"
echo

index=1
for value in "${values[@]}"; do
  log_path="$LOG_DIR/scan_$(printf '%02d' "$index")_${value}.log"
  echo "Test $index header-size-override=$value"
  echo "Przepnij LCD, potem Enter."
  read -r
  {
    echo "===== TEST $index ====="
    echo "HEADER_SIZE_OVERRIDE: $value"
    echo "TIME: $(date -Is)"
    "$PYTHON_BIN" "$DRIVER" \
      --usb-reset-before-send \
      --recover-before-send \
      --raw-jpeg-passthrough \
      --packet-debug \
      --limit-packets 2 \
      --header-size-override "$value" \
      "$JPEG_PATH"
  } 2>&1 | tee "$log_path"
  echo
  index=$((index + 1))
done
