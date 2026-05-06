#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image


MARKER_NAMES = {
    0xC0: "SOF0",
    0xC2: "SOF2",
    0xC4: "DHT",
    0xDB: "DQT",
    0xDA: "SOS",
    0xD9: "EOI",
    0xD8: "SOI",
    0xDD: "DRI",
    0xE0: "APP0",
    0xE1: "APP1",
    0xFE: "COM",
}


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_markers(data: bytes) -> list[str]:
    markers: list[str] = []
    i = 0
    in_scan = False
    while i + 1 < len(data):
        if not in_scan and data[i] != 0xFF:
            i += 1
            continue

        if in_scan:
            # Inside entropy-coded scan: handle byte-stuffing and only keep
            # structural markers (RSTn/EOI), otherwise keep moving.
            if data[i] != 0xFF:
                i += 1
                continue
            if i + 1 >= len(data):
                break
            nxt = data[i + 1]
            if nxt == 0x00:
                i += 2
                continue
            if 0xD0 <= nxt <= 0xD7:
                i += 2
                continue
            if nxt == 0xD9:
                markers.append("EOI")
                break
            i += 1
            continue

        j = i + 1
        while j < len(data) and data[j] == 0xFF:
            j += 1
        if j >= len(data):
            break

        marker = data[j]
        if marker == 0x00:
            i = j + 1
            continue

        name = MARKER_NAMES.get(marker, f"0x{marker:02X}")
        markers.append(name)

        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            i = j + 1
            continue

        if j + 2 >= len(data):
            break
        seg_len = int.from_bytes(data[j + 1:j + 3], "big")
        if seg_len < 2:
            break
        i = j + 1 + seg_len
        if marker == 0xDA:
            in_scan = True
    return markers


def image_summary(path: Path) -> dict[str, object]:
    data = read_bytes(path)
    with Image.open(path) as img:
        info = {
            "path": str(path),
            "size_bytes": len(data),
            "sha256": sha256(data),
            "format": img.format,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "progressive": bool(img.info.get("progression") or img.info.get("progressive")),
            "jfif": img.info.get("jfif"),
            "markers": parse_markers(data),
        }
    return info


def print_summary(label: str, summary: dict[str, object]) -> None:
    print(label)
    print(f"  path        : {summary['path']}")
    print(f"  size_bytes  : {summary['size_bytes']}")
    print(f"  sha256      : {summary['sha256']}")
    print(f"  format/mode : {summary['format']} / {summary['mode']}")
    print(f"  dimensions  : {summary['width']}x{summary['height']}")
    print(f"  progressive : {summary['progressive']}")
    print(f"  jfif        : {summary['jfif']}")
    print(f"  markers     : {' '.join(summary['markers'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two JPEG payloads for Trofeo LCD debugging")
    parser.add_argument("left", help="First JPEG path")
    parser.add_argument("right", help="Second JPEG path")
    args = parser.parse_args()

    left = image_summary(Path(args.left))
    right = image_summary(Path(args.right))

    print_summary("LEFT", left)
    print_summary("RIGHT", right)
    print()
    print("DIFF")
    for key in ("size_bytes", "format", "mode", "width", "height", "progressive", "jfif", "markers"):
        same = left[key] == right[key]
        print(f"  {key:11}: {'same' if same else 'different'}")
    print(f"  sha256      : {'same' if left['sha256'] == right['sha256'] else 'different'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
