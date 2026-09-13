#!/usr/bin/env python3
"""Send FPS samples to the Open Trofeo LCD local FPS socket.

This is a development/test sender for the backend channel. The real gaming
probe will use the same JSON datagram schema from Vulkan/OpenGL hooks.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import time


def default_socket_path() -> str:
    configured = os.environ.get("OPEN_TROFEO_FPS_SOCKET", "").strip()
    if configured:
        return os.path.expanduser(configured)
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime_dir, "open-trofeo-lcd", "fps.sock")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send test FPS samples to Open Trofeo LCD.")
    parser.add_argument("--socket", default=default_socket_path(), help="Unix datagram socket path.")
    parser.add_argument("--fps", type=float, default=0.0, help="Fixed FPS value. 0 means animated test wave.")
    parser.add_argument("--hz", type=float, default=10.0, help="Samples per second.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run. 0 means until Ctrl+C.")
    parser.add_argument("--game-name", default="Trofeo FPS Probe")
    parser.add_argument("--process", default="trofeo_fps_probe")
    parser.add_argument("--launcher", default="Open Trofeo")
    args = parser.parse_args()

    interval = 1.0 / max(1.0, float(args.hz))
    started = time.time()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        while True:
            elapsed = time.time() - started
            if args.duration > 0 and elapsed >= args.duration:
                return 0
            fps = float(args.fps)
            if fps <= 0:
                fps = 90.0 + 35.0 * math.sin(elapsed * 1.7)
            payload = {
                "fps": round(fps, 3),
                "frametime_ms": round(1000.0 / fps, 3) if fps > 0 else 0.0,
                "source": "open-trofeo-test-probe",
                "game_name": args.game_name,
                "game_process": args.process,
                "game_launcher": args.launcher,
                "game_overlay": "none",
                "pid": os.getpid(),
                "timestamp": time.time(),
            }
            sock.sendto(json.dumps(payload, separators=(",", ":")).encode("utf-8"), args.socket)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
