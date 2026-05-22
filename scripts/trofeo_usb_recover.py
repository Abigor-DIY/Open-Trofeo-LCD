#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Best-effort USB reset for Thermalright Trofeo LCD")
    parser.add_argument("--vid", default="0416", help="USB vendor id in hex")
    parser.add_argument("--pid", default="5408", help="USB product id in hex")
    parser.add_argument("--settle", type=float, default=2.0, help="Delay after reset, in seconds")
    args = parser.parse_args()

    try:
        import usb.core
        import usb.util
    except Exception as exc:
        print(f"Error: pyusb import failed: {exc}", flush=True)
        return 2

    try:
        vid = int(str(args.vid), 16)
        pid = int(str(args.pid), 16)
    except ValueError:
        print(f"Error: invalid vid/pid: {args.vid}:{args.pid}", flush=True)
        return 2

    try:
        dev = usb.core.find(idVendor=vid, idProduct=pid)
    except Exception as exc:
        print(f"Error: USB search failed: {exc}", flush=True)
        return 1
    if dev is None:
        print(f"Error: device not found: {vid:04x}:{pid:04x}", flush=True)
        return 1

    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass
    try:
        dev.reset()
    except Exception as exc:
        print(f"Error: USB reset failed: {exc}", flush=True)
        return 1
    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass
    time.sleep(max(0.0, float(args.settle)))
    print(f"USB reset ok: {vid:04x}:{pid:04x}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
