#!/usr/bin/env python3
"""
Offline smoke tests for Open Trofeo LCD.

This does not talk to the LCD, does not need network access, and does not build
Flatpak. It validates Python syntax, loads theme documents, renders themes, and
checks that composite weather/media widgets can render with synthetic data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preview_stats import preview_stats_values
from theme_renderer import render_theme_document
from theme_schema import ThemeDocument, load_theme_document, normalize_theme_document


def _synthetic_stats() -> dict[str, str]:
    stats = preview_stats_values()
    stats.update(
        {
            "hostname": "smoke",
            "ip_local": "127.0.0.1",
            "time_hms": "12:34:56",
            "date_ymd": "2026-05-16",
            "media_title": "Synthetic Track",
            "media_artist": "Open Trofeo",
            "media_app": "playerctl",
            "weather_location": "Warszawa",
        }
    )
    return stats


class SyntheticStatsProvider:
    def __init__(self) -> None:
        self.values = _synthetic_stats()

    def snapshot(self) -> Any:
        return type("Snapshot", (), {"values": self.values})()


def check_python(root: Path) -> tuple[bool, str]:
    started = time.perf_counter()
    errors = []
    for path in sorted(root.glob("*.py")) + sorted((root / "scripts").glob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except Exception as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return not errors, f"{(time.perf_counter() - started):.2f}s" + ("" if not errors else " " + "; ".join(errors[:5]))


def check_theme_loads(root: Path) -> tuple[list[Path], list[str]]:
    themes = sorted((root / "themes").glob("*.json"))
    errors = []
    for path in themes:
        try:
            load_theme_document(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return themes, errors


def check_theme_renders(root: Path, themes: list[Path], limit: int | None) -> list[str]:
    errors = []
    provider = SyntheticStatsProvider()
    selected = themes if limit is None else themes[:limit]
    for path in selected:
        try:
            image = render_theme_document(load_theme_document(path), base_dir=path.parent, stats_provider=provider)
            if image.size[0] <= 0 or image.size[1] <= 0:
                errors.append(f"{path.relative_to(root)}: invalid render size {image.size}")
        except Exception as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return errors


def check_composite_widgets(root: Path) -> list[str]:
    base = {
        "schema_version": 1,
        "meta": {"name": "Smoke Composite", "style": "Dashboard"},
        "canvas": {"width": 1920, "height": 462, "rotation": 180},
        "background": {"kind": "color", "base_color": [0, 0, 0]},
        "texts": [],
        "stats": [],
        "images": [],
        "widgets": [
            {
                "id": "weather",
                "kind": "weather_current",
                "rect": [20, 20, 520, 170],
                "style": "compact",
                "settings": {"panel_enabled": False, "animate_icons": True},
            },
            {
                "id": "forecast",
                "kind": "weather_forecast_7d",
                "rect": [20, 210, 900, 190],
                "style": "strip",
                "settings": {"panel_enabled": True, "animate_icons": True},
            },
            {
                "id": "media",
                "kind": "media_now_playing",
                "rect": [980, 60, 820, 210],
                "style": "cover",
                "settings": {"panel_enabled": True},
            },
        ],
        "effects": {"animation": {"enabled": False}},
    }
    errors = []
    try:
        document = ThemeDocument(normalize_theme_document(base))
        image = render_theme_document(document, base_dir=root, stats_provider=SyntheticStatsProvider())
        if image.size != (1920, 462):
            errors.append(f"composite widgets rendered unexpected size {image.size}")
    except Exception as exc:
        errors.append(f"composite widgets: {exc}")
    return errors


def check_video_import_prereq() -> dict[str, Any]:
    # Full video import is GUI-owned today. Smoke-test only records ffmpeg presence
    # so regressions are visible without creating large temporary frame sets.
    import shutil

    ffmpeg = shutil.which("ffmpeg")
    return {"ffmpeg": ffmpeg, "available": bool(ffmpeg)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline Open Trofeo LCD smoke tests.")
    parser.add_argument("--root", default=ROOT, type=Path)
    parser.add_argument("--render-limit", type=int, default=None, help="limit rendered themes for faster local checks")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    py_ok, py_time = check_python(root)
    themes, load_errors = check_theme_loads(root)
    render_errors = check_theme_renders(root, themes, args.render_limit)
    widget_errors = check_composite_widgets(root)
    video = check_video_import_prereq()

    report = {
        "root": str(root),
        "python_compile": {"ok": py_ok, "duration": py_time},
        "theme_load": {"count": len(themes), "errors": load_errors},
        "theme_render": {"checked": len(themes if args.render_limit is None else themes[: args.render_limit]), "errors": render_errors},
        "composite_widgets": {"errors": widget_errors},
        "video_import_prereq": video,
    }
    ok = py_ok and not load_errors and not render_errors and not widget_errors
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Open Trofeo LCD smoke test")
        print(f"Python compile: {'ok' if py_ok else 'failed'} ({py_time})")
        print(f"Theme load: {len(themes)} checked, errors={len(load_errors)}")
        print(f"Theme render: {report['theme_render']['checked']} checked, errors={len(render_errors)}")
        print(f"Composite widgets: errors={len(widget_errors)}")
        print(f"ffmpeg: {video['ffmpeg'] or 'not found'}")
        for section, errors in (("load", load_errors), ("render", render_errors), ("widgets", widget_errors)):
            if errors:
                print(f"\n{section} errors:")
                for error in errors[:20]:
                    print(f"- {error}")
                if len(errors) > 20:
                    print(f"- ... {len(errors) - 20} more")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
