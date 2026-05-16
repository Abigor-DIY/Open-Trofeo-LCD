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
    parser.add_argument(
        "--no-drop-late-frames",
        action="store_true",
        help="Disable adaptive frame skipping when USB sends fall behind animation timing",
    )
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

    try:
        from trcc.adapters.system.linux.setup import LinuxSetup

        LinuxSetup.needs_setup = lambda self: False
        LinuxSetup.auto_setup = lambda self: None
    except Exception:
        pass

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
    frame_roles = manifest.get("frame_roles", [])
    overlay_path_raw = str(manifest.get("overlay_path", "")).strip()
    overlay_path = Path(overlay_path_raw).expanduser() if overlay_path_raw else None
    try:
        overlay_min_interval_s = max(0.0, float(manifest.get("overlay_min_interval_s", 0.0)))
    except Exception:
        overlay_min_interval_s = 0.0
    loop_enabled = bool(manifest.get("loop", True))
    if not isinstance(frame_paths, list) or not frame_paths:
        print("Error: manifest has no frames", flush=True)
        return 1
    if not isinstance(durations_ms, list):
        durations_ms = []
    if not isinstance(frame_roles, list):
        frame_roles = []
    StandardLoggingConfigurator().configure(verbosity=0)
    app = TrccApp.init()
    app.init_platform(verbosity=0, renderer_factory=trcc_cli._make_cli_renderer)

    rc = connect_device(args.device)
    if rc != 0:
        return rc

    # Brief settle after enumeration / first control transfers — reduces rare USBTimeout on first bulk write.
    time.sleep(0.25)

    lcd = TrccApp.get().device(0)
    if lcd is None:
        print("Error: no LCD device", flush=True)
        return 1

    loaded_frames = []
    for idx, raw in enumerate(frame_paths):
        frame_path = Path(str(raw)).expanduser()
        try:
            st = frame_path.stat()
        except OSError as exc:
            print(f"Error: frame {idx} path not accessible {frame_path}: {exc}", flush=True)
            return 1
        if st.st_size < 32:
            print(f"Error: frame {idx} file empty or too small: {frame_path}", flush=True)
            return 1
        result = lcd.load_image(str(frame_path))
        if not result.get("success"):
            err = str(result.get("error", "unknown error"))
            print(
                f"Error: failed to load frame {idx}: {err}. If the file exists but LCD reports (0,0) resolution, "
                f"unplug/replug USB or retry — the previous transfer may have timed out.",
                flush=True,
            )
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

    if overlay_path is not None and overlay_min_interval_s <= 0.0:
        try:
            min_dur_ms = min(item[1] for item in loaded_frames)
        except Exception:
            min_dur_ms = 83
        overlay_min_interval_s = max(0.08, (max(1, int(min_dur_ms)) / 1000.0) * 0.42)

    overlay_image = None
    overlay_mtime_ns = None
    overlay_revision = 0
    composed_cache: dict[int, tuple[int, object]] = {}

    def _load_overlay() -> bool:
        nonlocal overlay_image, overlay_mtime_ns, overlay_revision, composed_cache
        if overlay_path is None or not overlay_path.exists():
            return False
        stat = overlay_path.stat()
        if overlay_mtime_ns == stat.st_mtime_ns:
            return False
        result = lcd.load_image(str(overlay_path))
        if result.get("success"):
            overlay_image = result.get("image")
            overlay_mtime_ns = stat.st_mtime_ns
            overlay_revision += 1
            composed_cache = {}
            return True
        return False

    def _compose_frame(image, frame_index: int):
        if overlay_image is None:
            return image
        cached = composed_cache.get(frame_index)
        if cached is not None and cached[0] == overlay_revision:
            return cached[1]
        renderer = ImageService._r()
        frame = renderer.copy_surface(image)
        frame = renderer.convert_to_rgba(frame)
        frame = renderer.composite(frame, overlay_image, (0, 0))
        composed = renderer.convert_to_rgb(frame)
        composed_cache[frame_index] = (overlay_revision, composed)
        return composed

    _load_overlay()

    lcd.enable_overlay(False)
    print(f"Animation loaded: {len(loaded_frames)} frames", flush=True)

    try:
        last_overlay_send_at = 0.0
        send_ema_s = 0.0
        slow_send_threshold_s = 0.8
        overlay_send_guard_s = 0.12
        next_frame_at = 0.0
        drop_late_frames = not args.no_drop_late_frames
        dropped_since_log = 0
        last_drop_log_at = 0.0

        def _send_image(image, label: str, frame_index: int) -> float:
            nonlocal send_ema_s
            started = time.monotonic()
            lcd.send(image)
            elapsed = time.monotonic() - started
            send_ema_s = elapsed if send_ema_s <= 0.0 else (send_ema_s * 0.75) + (elapsed * 0.25)
            if elapsed >= slow_send_threshold_s:
                print(f"Warning: slow send {int(elapsed * 1000)}ms frame={frame_index} role={label}", flush=True)
            return elapsed

        def _wait_frame_gap(
            *,
            duration_s: float,
            frame_index: int,
            composed_frame,
        ) -> None:
            nonlocal last_overlay_send_at, next_frame_at

            next_frame_at += duration_s
            while True:
                delay_s = next_frame_at - time.monotonic()
                if delay_s <= 0:
                    break
                if overlay_path is not None and delay_s > 0.20:
                    overlay_changed = _load_overlay()
                    if overlay_changed:
                        now = time.monotonic()
                        effective_overlay_min_interval_s = overlay_min_interval_s
                        enough_time_before_next_frame = delay_s > max(0.20, send_ema_s + overlay_send_guard_s)
                        if now - last_overlay_send_at >= effective_overlay_min_interval_s and enough_time_before_next_frame:
                            _send_image(_compose_frame(composed_frame, frame_index), "overlay", frame_index)
                            last_overlay_send_at = now
                time.sleep(min(0.05, delay_s))
            if not drop_late_frames and next_frame_at < time.monotonic():
                next_frame_at = time.monotonic()

        while True:
            # Resync schedule each cycle so timing does not drift across loop wraps.
            next_frame_at = time.monotonic()
            frame_index = 0
            while frame_index < len(loaded_frames):
                frame, duration_ms, frame_path = loaded_frames[frame_index]
                role = str(frame_roles[frame_index]).strip().lower() if frame_index < len(frame_roles) else ""
                duration_s = max(0.001, duration_ms / 1000.0)
                if drop_late_frames and len(loaded_frames) > 1:
                    late_s = time.monotonic() - next_frame_at
                    if late_s > max(duration_s * 1.25, send_ema_s * 0.35):
                        skip_count = min(
                            len(loaded_frames) - frame_index - 1,
                            max(1, int(late_s / duration_s)),
                        )
                        if skip_count > 0:
                            frame_index += skip_count
                            next_frame_at += duration_s * skip_count
                            dropped_since_log += skip_count
                            now = time.monotonic()
                            if now - last_drop_log_at >= 5.0:
                                print(
                                    f"Info: dropped {dropped_since_log} late animation frames"
                                    f" send_ema_ms={int(send_ema_s * 1000)}",
                                    flush=True,
                                )
                                dropped_since_log = 0
                                last_drop_log_at = now
                            continue
                _load_overlay()
                _send_image(_compose_frame(frame, frame_index), role or "frame", frame_index)
                if args.verbose_frames:
                    print(f"Frame: {frame_path}", flush=True)
                _wait_frame_gap(
                    duration_s=duration_s,
                    frame_index=frame_index,
                    composed_frame=frame,
                )
                frame_index += 1
            if not loop_enabled:
                # If we exit here, the TRCC process dies and the panel stops getting composited frames;
                # live overlay (EQ, media, etc.) appears frozen on the last bitmap. Keep the worker alive
                # and refresh the final frame + overlay on the same cadence as during playback.
                last_idx = len(loaded_frames) - 1
                hold_frame, hold_ms, hold_path = loaded_frames[last_idx]
                hold_s = max(0.05, min(0.5, hold_ms / 1000.0))
                if overlay_path is not None:
                    hold_s = max(hold_s, min(0.35, overlay_min_interval_s + 0.02))
                print(
                    f"Animation sequence done (loop disabled). Holding last frame ({hold_path}) — quit with Ctrl+C.",
                    flush=True,
                )
                while True:
                    _load_overlay()
                    _send_image(_compose_frame(hold_frame, last_idx), "hold", last_idx)
                    _wait_frame_gap(
                        duration_s=hold_s,
                        frame_index=last_idx,
                        composed_frame=hold_frame,
                    )
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
