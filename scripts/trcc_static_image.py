#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep a static image alive on TRCC LCD")
    parser.add_argument("image")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    try:
        import trcc.cli as trcc_cli
        from trcc.cli._connect import connect_device
        from trcc.core.app import TrccApp
        from trcc.adapters.infra.diagnostics import StandardLoggingConfigurator
    except Exception as exc:
        print(f"Error: failed to import trcc: {exc}", flush=True)
        return 1

    StandardLoggingConfigurator().configure(verbosity=0)
    app = TrccApp.init()
    app.init_platform(verbosity=0, renderer_factory=trcc_cli._make_cli_renderer)

    rc = connect_device(args.device)
    if rc != 0:
        return rc

    lcd = TrccApp.get().device(0)
    if lcd is None:
        print("Error: no LCD device", flush=True)
        return 1

    result = lcd.load_image(args.image)
    if not result.get("success"):
        print(f"Error: {result.get('error', 'failed to load image')}", flush=True)
        return 1

    image = result.get("image")
    if image is None:
        print("Error: image load returned no surface", flush=True)
        return 1

    lcd.enable_overlay(False)
    lcd.set_background(image)
    lcd.send(image)
    print(f"Static image loaded: {args.image}", flush=True)

    try:
        loop_result = lcd.keep_alive_loop(interval=max(0.05, float(args.interval)), duration=max(0.0, float(args.duration)))
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        return 0

    if not loop_result or not loop_result.get("success", False):
        print(f"Error: {loop_result.get('error', 'keep_alive_loop failed') if isinstance(loop_result, dict) else 'keep_alive_loop failed'}", flush=True)
        return 1

    print(loop_result.get("message", "Done"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
