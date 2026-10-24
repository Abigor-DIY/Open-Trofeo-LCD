#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep a static image alive on TRCC LCD")
    parser.add_argument("image")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    from trcc_runtime import open_display

    try:
        lcd, renderer = open_display(args.device)
    except Exception as exc:
        print(f"Error: TRCC runtime: {exc}", flush=True)
        return 1

    result = lcd.load_image(args.image)
    if not result.get("success"):
        print(f"Error: {result.get('error', 'failed to load image')}", flush=True)
        return 1

    image = result.get("image")
    if image is None:
        print("Error: image load returned no surface", flush=True)
        return 1

    frame = renderer.copy_surface(image)
    frame = renderer.convert_to_rgb(frame)

    lcd.enable_overlay(False)
    lcd.set_background(frame)
    lcd.send(frame)
    print(f"Static image loaded: {args.image}", flush=True)

    deadline = time.monotonic() + max(0.0, float(args.duration)) if float(args.duration) > 0 else None
    sleep_s = max(0.05, float(args.interval))
    try:
        while True:
            lcd.send(frame)
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        return 0

    print("Done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
