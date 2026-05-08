#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep a static background with hot-reload overlay on TRCC LCD")
    parser.add_argument("image")
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    try:
        import trcc.cli as trcc_cli
        from trcc.cli._connect import connect_device
        from trcc.core.app import TrccApp
        from trcc.adapters.infra.diagnostics import StandardLoggingConfigurator
        from trcc.services import ImageService
    except Exception as exc:
        print(f"Error: failed to import trcc: {exc}", flush=True)
        return 1

    background_path = Path(args.image).expanduser()
    overlay_path = Path(args.overlay).expanduser()
    if not background_path.exists():
        print(f"Error: background not found: {background_path}", flush=True)
        return 1
    if not overlay_path.exists():
        print(f"Error: overlay not found: {overlay_path}", flush=True)
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

    background_result = lcd.load_image(str(background_path))
    if not background_result.get("success"):
        print(f"Error: failed to load background: {background_result.get('error', 'unknown error')}", flush=True)
        return 1
    background = background_result.get("image")
    if background is None:
        print("Error: background load returned no surface", flush=True)
        return 1

    renderer = ImageService._r()
    overlay_image = None
    overlay_mtime_ns = None
    composited = None

    def _refresh_overlay() -> bool:
        nonlocal overlay_image, overlay_mtime_ns, composited
        if not overlay_path.exists():
            return False
        stat = overlay_path.stat()
        if overlay_mtime_ns == stat.st_mtime_ns:
            return False
        result = lcd.load_image(str(overlay_path))
        if not result.get("success"):
            return False
        loaded = result.get("image")
        if loaded is None:
            return False
        overlay_image = loaded
        overlay_mtime_ns = stat.st_mtime_ns
        composited = None
        return True

    def _active_image():
        nonlocal composited
        if overlay_image is None:
            return background
        if composited is not None:
            return composited
        frame = renderer.copy_surface(background)
        frame = renderer.convert_to_rgba(frame)
        frame = renderer.composite(frame, overlay_image, (0, 0))
        composited = renderer.convert_to_rgb(frame)
        return composited

    _refresh_overlay()
    lcd.enable_overlay(False)
    lcd.set_background(background)
    lcd.send(_active_image())
    print(f"Static overlay image loaded: {background_path} + {overlay_path}", flush=True)

    deadline = time.monotonic() + max(0.0, float(args.duration)) if float(args.duration) > 0 else None
    sleep_s = max(0.05, float(args.interval))
    try:
        while True:
            if _refresh_overlay():
                lcd.send(_active_image())
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
