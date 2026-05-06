#!/usr/bin/env bash
set -u

PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRIVER="$SCRIPT_DIR/trofeo_lcd.py"
JPEG_PATH="${1:-$SCRIPT_DIR/reference_frame_trcc.jpg}"
LOG_DIR="$SCRIPT_DIR/reference_protocol_logs"
TEST_TIMEOUT_SECONDS="${TEST_TIMEOUT_SECONDS:-300}"

if [[ ! -f "$JPEG_PATH" ]]; then
  echo "Brak pliku JPEG: $JPEG_PATH"
  exit 1
fi

mkdir -p "$LOG_DIR"

COMMON_ARGS="--usb-reset-before-send --recover-before-send --raw-jpeg-passthrough --packet-debug --ack-every-packet --ack-on-seq0-only --ack-timeout-ms 1000 --inter-packet-delay 0.01"

tests=(
  "$COMMON_ARGS --header-size-override 0x4daf1 --final-packet-mode auto \"$JPEG_PATH\""
  "$COMMON_ARGS --header-size-override 0x4daf1 --final-packet-mode pad-4096 \"$JPEG_PATH\""
  "$COMMON_ARGS --header-size-override 0x78d8 --final-packet-mode pad-4096 \"$JPEG_PATH\""
  "$COMMON_ARGS --header-size-override 0x4daf1 --final-packet-mode auto --send-commit --commit-mode scan \"$JPEG_PATH\""
)

echo "Macierz protokolu dla: $JPEG_PATH"
echo "Logi: $LOG_DIR"
echo "Timeout testu: ${TEST_TIMEOUT_SECONDS}s"
echo

index=1
for args in "${tests[@]}"; do
  log_path="$LOG_DIR/test_$(printf '%02d' "$index").log"
  echo "Test $index:"
  echo "$PYTHON_BIN $DRIVER $args"
  echo "Przepnij LCD, potem Enter."
  read -r
  {
    echo "===== TEST $index ====="
    echo "TIME: $(date -Is)"
    echo "ARGS: $args"
    eval "PYTHONUNBUFFERED=1 timeout --foreground ${TEST_TIMEOUT_SECONDS}s \"$PYTHON_BIN\" -u \"$DRIVER\" $args"
    rc=$?
    if [[ $rc -eq 124 ]]; then
      echo "TIMEOUT: test przekroczyl ${TEST_TIMEOUT_SECONDS}s"
    fi
    exit $rc
  } 2>&1 | tee "$log_path"
  echo
  index=$((index + 1))
done
