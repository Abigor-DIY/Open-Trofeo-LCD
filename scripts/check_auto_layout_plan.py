#!/usr/bin/env python3
"""Validate Theme Designer auto-layout rectangles without starting the GUI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from designer.auto_layout import AutoLayoutEntry, auto_layout_metrics, auto_layout_plan, bucket_auto_layout_entries


def sample_entries() -> list[AutoLayoutEntry]:
    return [
        ("stats", 0, {"display": "gauge", "source": "cpu_usage"}),
        ("stats", 1, {"display": "gauge", "source": "ram_usage"}),
        ("stats", 2, {"display": "gauge", "source": "cpu_temp"}),
        ("widgets", 3, {"kind": "media_now_playing"}),
        ("stats", 4, {"display": "progress", "source": "gpu_usage"}),
        ("stats", 5, {"display": "sparkline", "source": "network_down"}),
        ("stats", 6, {"display": "text", "source": "game_fps"}),
        ("widgets", 7, {"kind": "weather_current"}),
        ("widgets", 8, {"kind": "weather_forecast_7d"}),
        ("images", 9, {"source": "analog_clock"}),
        ("stats", 10, {"display": "equalizer", "source": "audio_eq_bars"}),
        ("texts", 11, {"text": "OPEN TROFEO LCD"}),
        ("images", 12, {"source": "media_cover"}),
    ]


def rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def validate_plan(plan: dict[str, list[tuple[int, int, int, int]]], width: int, height: int) -> list[str]:
    errors: list[str] = []
    flattened: list[tuple[str, int, tuple[int, int, int, int]]] = []
    for section, rects in plan.items():
        for idx, (x, y, rect_w, rect_h) in enumerate(rects):
            flattened.append((section, idx, (x, y, rect_w, rect_h)))
            if x < 0 or y < 0 or rect_w <= 0 or rect_h <= 0:
                errors.append(f"{section}[{idx}] invalid rect {(x, y, rect_w, rect_h)}")
            if x + rect_w > width or y + rect_h > height:
                errors.append(f"{section}[{idx}] exceeds canvas {(x, y, rect_w, rect_h)} > {width}x{height}")
        for left_idx, left in enumerate(rects):
            for right_idx, right in enumerate(rects[left_idx + 1 :], start=left_idx + 1):
                if rects_overlap(left, right):
                    errors.append(f"{section}[{left_idx}] overlaps {section}[{right_idx}]")
    for left_pos, (left_section, left_idx, left_rect) in enumerate(flattened):
        for right_section, right_idx, right_rect in flattened[left_pos + 1 :]:
            if left_section == right_section:
                continue
            if rects_overlap(left_rect, right_rect):
                errors.append(f"{left_section}[{left_idx}] overlaps {right_section}[{right_idx}]")
    return errors


def build_report(width: int, height: int) -> dict[str, Any]:
    metrics = auto_layout_metrics(width, height)
    buckets = bucket_auto_layout_entries(sample_entries())
    plan = auto_layout_plan(metrics, buckets)
    errors = validate_plan(plan, metrics.canvas_width, metrics.canvas_height)
    return {
        "canvas": {"width": metrics.canvas_width, "height": metrics.canvas_height},
        "sections": {section: len(rects) for section, rects in plan.items() if rects},
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Theme Designer auto-layout plan geometry.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=462)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args.width, args.height)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        canvas = report["canvas"]
        print(f"Auto-layout plan check: {canvas['width']}x{canvas['height']}")
        print(f"Sections: {report['sections']}")
        if report["errors"]:
            print("Errors:")
            for error in report["errors"]:
                print(f"- {error}")
        else:
            print("OK")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
