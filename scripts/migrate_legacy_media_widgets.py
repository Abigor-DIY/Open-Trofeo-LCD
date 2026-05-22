#!/usr/bin/env python3
"""
Convert split Now Playing theme parts into one composite media widget.

Older themes modelled Now Playing as separate stats/images, which makes the
designer hard to use. This migration preserves the group bounding box and key
style values, then replaces the old pieces with a single media_now_playing
widget.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_json_with_comments import parse_theme_json_text
from theme_schema import ThemeDocument, normalize_theme_document


MEDIA_SOURCES = {
    "media_title",
    "media_artist",
    "media_album",
    "media_app",
    "media_state",
    "media_cover",
    "media_video_frame",
}


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _next_widget_id(document: dict[str, Any], prefix: str = "widget_media_now_playing") -> str:
    used = {
        str(item.get("id", "")).strip()
        for item in document.get("widgets", [])
        if isinstance(item, dict)
    }
    idx = 0
    while f"{prefix}_{idx}" in used:
        idx += 1
    return f"{prefix}_{idx}"


def _is_media_item(item: Any) -> bool:
    return isinstance(item, dict) and str(item.get("source", "")).strip() in MEDIA_SOURCES


def _item_box(section: str, item: dict[str, Any]) -> tuple[int, int, int, int]:
    if section == "stats":
        x = _int(item.get("x"))
        y = _int(item.get("y"))
        w = max(1, _int(item.get("box_width"), 1))
        h = max(1, _int(item.get("box_height"), 1))
        return x, y, w, h
    rect = item.get("rect", [0, 0, 1, 1])
    if not isinstance(rect, list) or len(rect) != 4:
        return 0, 0, 1, 1
    return _int(rect[0]), _int(rect[1]), max(1, _int(rect[2], 1)), max(1, _int(rect[3], 1))


def _color(item: dict[str, Any], key: str, fallback: list[int]) -> list[int]:
    value = item.get(key)
    if isinstance(value, list) and len(value) in (3, 4):
        out = []
        for channel in value:
            out.append(max(0, min(255, _int(channel))))
        return out
    return fallback


def _font_size(item: dict[str, Any], fallback: int) -> int:
    return max(6, _int(item.get("font_size"), fallback))


def _legacy_media_parts(document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stats = [item for item in document.get("stats", []) if _is_media_item(item)]
    images = [item for item in document.get("images", []) if _is_media_item(item)]
    return stats, images


def convert_document(document: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    stats, images = _legacy_media_parts(document)
    parts = [("stats", item) for item in stats] + [("images", item) for item in images]
    if not parts:
        return document, False

    xs: list[int] = []
    ys: list[int] = []
    xe: list[int] = []
    ye: list[int] = []
    z_values: list[int] = []
    by_source = {str(item.get("source", "")).strip(): item for _, item in parts}
    for section, item in parts:
        x, y, w, h = _item_box(section, item)
        xs.append(x)
        ys.append(y)
        xe.append(x + w)
        ye.append(y + h)
        z_values.append(_int(item.get("z_index"), 210))

    x = max(0, min(xs))
    y = max(0, min(ys))
    w = max(120, max(xe) - x)
    h = max(72, max(ye) - y)
    style = "mini" if h <= 110 or w <= 420 else "hero"
    title_item = by_source.get("media_title", {})
    artist_item = by_source.get("media_artist", {})
    detail_item = by_source.get("media_app") or by_source.get("media_state") or {}
    has_backdrop = "media_video_frame" in by_source

    settings = {
        "title_font_size": _font_size(title_item, 32 if style == "hero" else 20),
        "artist_font_size": _font_size(artist_item, 24 if style == "hero" else 16),
        "detail_font_size": _font_size(detail_item, 18),
        "title_color": _color(title_item, "value_color", [244, 248, 255]),
        "artist_color": _color(artist_item, "value_color", [210, 224, 240]),
        "detail_color": _color(detail_item, "value_color", [160, 196, 232]),
        "cover_enabled": True,
        "backdrop_enabled": True,
        "panel_fill": [8, 14, 24, 188 if has_backdrop else 210],
        "backdrop_opacity": 0.30 if has_backdrop else 0.24,
        "title_marquee": True,
        "title_marquee_speed": 55.0,
        "equalizer_enabled": True,
        "equalizer_bars": 24 if style == "hero" else 20,
        "equalizer_gap": 4,
        "equalizer_mirror": False,
    }
    widget = {
        "id": _next_widget_id(document),
        "kind": "media_now_playing",
        "style": style,
        "rect": [x, y, w, h],
        "settings": settings,
        "opacity": 1.0,
        "z_index": max(z_values) if z_values else 210,
        "visible": True,
        "locked": False,
    }

    migrated = json.loads(json.dumps(document))
    migrated["stats"] = [item for item in migrated.get("stats", []) if not _is_media_item(item)]
    migrated["images"] = [item for item in migrated.get("images", []) if not _is_media_item(item)]
    migrated.setdefault("widgets", [])
    if not isinstance(migrated["widgets"], list):
        migrated["widgets"] = []
    migrated["widgets"].append(widget)
    normalized = normalize_theme_document(migrated)
    return normalized, True


def convert_file(path: Path, *, dry_run: bool) -> bool:
    raw = parse_theme_json_text(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path}: root JSON value is not an object")
    converted, changed = convert_document(raw)
    if not changed:
        return False
    if not dry_run:
        path.write_text(ThemeDocument(converted).to_json(pretty=True), encoding="utf-8")
    return True


def _default_theme_paths(root: Path) -> list[Path]:
    return sorted((root / "themes").glob("*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert legacy split media parts into media_now_playing widgets.")
    parser.add_argument("paths", nargs="*", type=Path, help="theme JSON files; defaults to all themes/*.json")
    parser.add_argument("--root", default=ROOT, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    paths = args.paths or _default_theme_paths(root)
    changed = 0
    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        if convert_file(path, dry_run=args.dry_run):
            changed += 1
            print(f"{'would convert' if args.dry_run else 'converted'}: {path.relative_to(root)}")
    print(f"changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
