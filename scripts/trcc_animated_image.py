#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Play animated frames on TRCC LCD")
    parser.add_argument("manifest")
    parser.add_argument("--device", default=None)
    parser.add_argument("--verbose-frames", action="store_true", help="Log every rendered frame path")
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

    manifest_path = Path(args.manifest).expanduser()
    if not manifest_path.exists():
        print(f"Error: manifest not found: {manifest_path}", flush=True)
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error: failed to parse manifest: {exc}", flush=True)
        return 1

    frame_paths = manifest.get("frame_paths", [])
    durations_ms = manifest.get("frame_durations_ms", [])
    overlay_path_raw = str(manifest.get("overlay_path", "")).strip()
    overlay_path = Path(overlay_path_raw).expanduser() if overlay_path_raw else None
    loop_enabled = bool(manifest.get("loop", True))
    if not isinstance(frame_paths, list) or not frame_paths:
        print("Error: manifest has no frames", flush=True)
        return 1
    if not isinstance(durations_ms, list):
        durations_ms = []

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

    loaded_frames = []
    for idx, raw in enumerate(frame_paths):
        frame_path = Path(str(raw)).expanduser()
        result = lcd.load_image(str(frame_path))
        if not result.get("success"):
            print(f"Error: failed to load frame {idx}: {result.get('error', 'unknown error')}", flush=True)
            return 1
        image = result.get("image")
        if image is None:
            print(f"Error: frame {idx} returned no image surface", flush=True)
            return 1
        duration_ms = 83
        if idx < len(durations_ms):
            try:
                duration_ms = max(1, int(durations_ms[idx]))
            except Exception:
                duration_ms = 83
        loaded_frames.append((image, duration_ms, str(frame_path)))

    overlay_image = None
    overlay_mtime_ns = None
    composited_frames = None

    def _load_overlay() -> bool:
        nonlocal overlay_image, overlay_mtime_ns, composited_frames
        if overlay_path is None or not overlay_path.exists():
            return False
        stat = overlay_path.stat()
        if overlay_mtime_ns == stat.st_mtime_ns:
            return False
        result = lcd.load_image(str(overlay_path))
        if result.get("success"):
            overlay_image = result.get("image")
            overlay_mtime_ns = stat.st_mtime_ns
            composited_frames = None
            return True
        return False

    def _active_frames():
        nonlocal composited_frames
        if overlay_image is None:
            return loaded_frames
        if composited_frames is not None:
            return composited_frames

        renderer = ImageService._r()
        built_frames = []
        for image, duration_ms, frame_path in loaded_frames:
            frame = renderer.copy_surface(image)
            frame = renderer.convert_to_rgba(frame)
            frame = renderer.composite(frame, overlay_image, (0, 0))
            frame = renderer.convert_to_rgb(frame)
            built_frames.append((frame, duration_ms, frame_path))
        composited_frames = built_frames
        return composited_frames

    _load_overlay()

    lcd.enable_overlay(False)
    print(f"Animation loaded: {len(loaded_frames)} frames", flush=True)

    try:
        next_frame_at = time.monotonic()
        while True:
            current_frames = _active_frames()
            frame_index = 0
            while frame_index < len(current_frames):
                if _load_overlay():
                    current_frames = _active_frames()
                    frame_index = min(frame_index, max(0, len(current_frames) - 1))
                frame, duration_ms, frame_path = current_frames[frame_index]
                lcd.send(frame)
                if args.verbose_frames:
                    print(f"Frame: {frame_path}", flush=True)
                next_frame_at += max(0.001, duration_ms / 1000.0)
                delay_s = next_frame_at - time.monotonic()
                if delay_s > 0:
                    time.sleep(delay_s)
                else:
                    next_frame_at = time.monotonic()
                frame_index += 1
            if not loop_enabled:
                break
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        return 0

    print("Animation finished.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
