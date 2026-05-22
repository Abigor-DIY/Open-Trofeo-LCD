#!/usr/bin/env bash
set -u

PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRIVER="$SCRIPT_DIR/trofeo_lcd.py"
LOG_DIR="$SCRIPT_DIR/live_test_logs"

mkdir -p "$LOG_DIR"

tests=(
  "--test --packet-debug --recover-before-send"
  "--test --packet-debug --recover-before-send --send-commit"
  "--test --packet-debug --recover-before-send --subsampling 4:2:2"
  "--test --packet-debug --recover-before-send --subsampling 4:4:4"
  "--test --packet-debug --recover-before-send --subsampling 4:2:0 --progressive"
  "--test --packet-debug --recover-before-send --final-packet-mode pad-4096"
  "--test --packet-debug --recover-before-send --header-size-mode chunk-size"
)

echo "Logi beda zapisane w: $LOG_DIR"
echo

index=1
for args in "${tests[@]}"; do
  log_path="$LOG_DIR/test_$(printf '%02d' "$index").log"
  echo "Test $index: $args"
  echo "Przepnij LCD, potem nacisnij Enter aby uruchomic test."
  read -r
  {
    echo "===== TEST $index ====="
    echo "ARGS: $args"
    echo "TIME: $(date -Is)"
    "$PYTHON_BIN" "$DRIVER" $args
  } 2>&1 | tee "$log_path"
  echo
  index=$((index + 1))
done
