#!/usr/bin/env bash
set -u

PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRIVER="$SCRIPT_DIR/trofeo_lcd.py"
JPEG_PATH="${1:-$SCRIPT_DIR/reference_frame_trcc.jpg}"
LOG_DIR="$SCRIPT_DIR/reference_timing_logs"
TEST_TIMEOUT_SECONDS="${TEST_TIMEOUT_SECONDS:-240}"
ACK_TIMEOUT_MS="${ACK_TIMEOUT_MS:-1000}"
LIMIT_PACKETS="${LIMIT_PACKETS:-20}"

if [[ ! -f "$JPEG_PATH" ]]; then
  echo "Brak pliku JPEG: $JPEG_PATH"
  exit 1
fi

mkdir -p "$LOG_DIR"

COMMON_ARGS="--usb-reset-before-send --recover-before-send --raw-jpeg-passthrough --packet-debug --header-size-override 0x78d8"
LIMIT_ARGS=""
if [[ -n "$LIMIT_PACKETS" ]]; then
  LIMIT_ARGS="--limit-packets ${LIMIT_PACKETS}"
fi

tests=(
  "$COMMON_ARGS --ack-every-packet --ack-timeout-ms ${ACK_TIMEOUT_MS} ${LIMIT_ARGS} \"$JPEG_PATH\""
  "$COMMON_ARGS --ack-at-end-only --inter-packet-delay 0.01 ${LIMIT_ARGS} \"$JPEG_PATH\""
  "$COMMON_ARGS --ack-every-packet --ack-on-seq0-only --ack-timeout-ms ${ACK_TIMEOUT_MS} --inter-packet-delay 0.01 --drain-in-after-packet --send-commit --commit-mode scan \"$JPEG_PATH\""
)

echo "Testy timingowe dla: $JPEG_PATH"
echo "Logi: $LOG_DIR"
echo "Timeout testu: ${TEST_TIMEOUT_SECONDS}s | ACK timeout: ${ACK_TIMEOUT_MS}ms | limit-packets (test 1-2): ${LIMIT_PACKETS}"
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
