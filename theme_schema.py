#!/usr/bin/env python3
"""
Theme schema and validation for Open Trofeo LCD.

Stage 3.1 introduces a real theme document that later stages can render,
edit in GUI and persist through the backend.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


THEME_SCHEMA_VERSION = 1
DEFAULT_CANVAS = {"width": 1920, "height": 462, "rotation": 180}
KNOWN_STAT_SOURCES = [
    "hostname", "ip_local", "time_hms", "date_ymd",
    "cpu_usage_percent", "cpu_core_avg_percent", "cpu_core_max_percent",
    "cpu_core_count", "cpu_freq_ghz", "cpu_temp_c", "load_average",
    "mem_used_mb", "mem_total_mb", "mem_percent",
    "disk_used_gb", "disk_total_gb", "disk_percent",
    "net_dl_kbps", "net_ul_kbps",
    "gpu_name", "gpu_temp", "gpu_load", "vram_used_mb", "vram_total_mb", "vram_percent",
    "uptime_human",
    "media_title", "media_artist", "media_app", "media_state",
]

KNOWN_ALIGN = {"left", "center", "right"}
KNOWN_FIT = {"contain", "cover", "stretch"}
KNOWN_BACKGROUND_KIND = {"generated", "image", "color"}
KNOWN_IMAGE_SOURCES = {"media_cover", "media_video_frame"}


class ThemeValidationError(RuntimeError):
    pass


def _fail(path: str, message: str) -> ThemeValidationError:
    return ThemeValidationError(f"{path}: {message}")


def _expect_type(value: Any, expected: type | tuple[type, ...], path: str) -> Any:
    if not isinstance(value, expected):
        if isinstance(expected, tuple):
            expected_name = "/".join(t.__name__ for t in expected)
        else:
            expected_name = expected.__name__
        raise _fail(path, f"expected {expected_name}, got {type(value).__name__}")
    return value


def _expect_number(value: Any, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(path, f"expected number, got {type(value).__name__}")
    return value


def _expect_str(value: Any, path: str) -> str:
    return _expect_type(value, str, path)


def _expect_bool(value: Any, path: str) -> bool:
    return _expect_type(value, bool, path)


def _expect_list(value: Any, path: str) -> list[Any]:
    return _expect_type(value, list, path)


def _expect_dict(value: Any, path: str) -> dict[str, Any]:
    return _expect_type(value, dict, path)


def _normalize_color(value: Any, path: str) -> list[int]:
    items = _expect_list(value, path)
    if len(items) not in (3, 4):
        raise _fail(path, "color must have 3 or 4 integer components")
    out = []
    for idx, item in enumerate(items):
        num = int(_expect_number(item, f"{path}[{idx}]"))
        if not (0 <= num <= 255):
            raise _fail(f"{path}[{idx}]", "color channel must be in range 0..255")
        out.append(num)
    return out


def _normalize_rect(value: Any, path: str) -> list[int]:
    items = _expect_list(value, path)
    if len(items) != 4:
        raise _fail(path, "rect must have 4 numbers: [x, y, width, height]")
    out = []
    for idx, item in enumerate(items):
        num = int(_expect_number(item, f"{path}[{idx}]"))
        out.append(num)
    if out[2] <= 0 or out[3] <= 0:
        raise _fail(path, "rect width and height must be > 0")
    return out


def _normalize_meta(raw: Any) -> dict[str, Any]:
    data = _expect_dict(raw, "meta")
    name = _expect_str(data.get("name", ""), "meta.name").strip()
    if not name:
        raise _fail("meta.name", "must not be empty")
    tags = data.get("tags", [])
    if tags is None:
        tags = []
    tags = _expect_list(tags, "meta.tags")
    out_tags = []
    for idx, tag in enumerate(tags):
        tag_text = _expect_str(tag, f"meta.tags[{idx}]").strip()
        if tag_text:
            out_tags.append(tag_text)
    return {
        "name": name,
        "description": str(data.get("description", "")).strip(),
        "author": str(data.get("author", "")).strip(),
        "tags": out_tags,
    }


def _normalize_canvas(raw: Any) -> dict[str, Any]:
    data = _expect_dict(raw, "canvas")
    width = int(_expect_number(data.get("width", DEFAULT_CANVAS["width"]), "canvas.width"))
    height = int(_expect_number(data.get("height", DEFAULT_CANVAS["height"]), "canvas.height"))
    rotation = int(_expect_number(data.get("rotation", DEFAULT_CANVAS["rotation"]), "canvas.rotation"))
    if width <= 0 or height <= 0:
        raise _fail("canvas", "width and height must be > 0")
    if rotation not in (0, 90, 180, 270):
        raise _fail("canvas.rotation", "must be one of 0, 90, 180, 270")
    return {"width": width, "height": height, "rotation": rotation}


def _normalize_background(raw: Any) -> dict[str, Any]:
    data = _expect_dict(raw, "background")
    kind = _expect_str(data.get("kind", "generated"), "background.kind").strip().lower()
    if kind not in KNOWN_BACKGROUND_KIND:
        raise _fail("background.kind", f"must be one of {sorted(KNOWN_BACKGROUND_KIND)}")

    out: dict[str, Any] = {
        "kind": kind,
        "base_color": _normalize_color(data.get("base_color", [9, 14, 22]), "background.base_color"),
        "accent_color": _normalize_color(data.get("accent_color", [20, 34, 48]), "background.accent_color"),
        "texture_alpha": float(_expect_number(data.get("texture_alpha", 0.40), "background.texture_alpha")),
        "panels": [],
    }
    if not (0.0 <= out["texture_alpha"] <= 1.0):
        raise _fail("background.texture_alpha", "must be in range 0.0..1.0")

    path_value = data.get("path")
    if kind == "image":
        path_text = _expect_str(path_value, "background.path").strip()
        if not path_text:
            raise _fail("background.path", "must not be empty when kind=image")
        fit = _expect_str(data.get("fit", "cover"), "background.fit").strip().lower()
        if fit not in KNOWN_FIT:
            raise _fail("background.fit", f"must be one of {sorted(KNOWN_FIT)}")
        out["path"] = path_text
        out["fit"] = fit
        out["opacity"] = float(_expect_number(data.get("opacity", 1.0), "background.opacity"))
        if not (0.0 <= out["opacity"] <= 1.0):
            raise _fail("background.opacity", "must be in range 0.0..1.0")

    panels = data.get("panels", [])
    if panels is None:
        panels = []
    for idx, panel in enumerate(_expect_list(panels, "background.panels")):
        p = _expect_dict(panel, f"background.panels[{idx}]")
        out["panels"].append(
            {
                "rect": _normalize_rect(p.get("rect"), f"background.panels[{idx}].rect"),
                "radius": int(_expect_number(p.get("radius", 0), f"background.panels[{idx}].radius")),
                "fill": _normalize_color(p.get("fill", [0, 0, 0]), f"background.panels[{idx}].fill"),
                "opacity": float(_expect_number(p.get("opacity", 1.0), f"background.panels[{idx}].opacity")),
                "z_index": int(_expect_number(p.get("z_index", 50), f"background.panels[{idx}].z_index")),
                "visible": bool(p.get("visible", True)),
                "locked": bool(p.get("locked", False)),
            }
        )
        if not (0.0 <= out["panels"][-1]["opacity"] <= 1.0):
            raise _fail(f"background.panels[{idx}].opacity", "must be in range 0.0..1.0")
    return out


def _normalize_text_item(raw: Any, idx: int) -> dict[str, Any]:
    path = f"texts[{idx}]"
    data = _expect_dict(raw, path)
    text = _expect_str(data.get("text", ""), f"{path}.text")
    if not text:
        raise _fail(f"{path}.text", "must not be empty")
    align = _expect_str(data.get("align", "left"), f"{path}.align").strip().lower()
    if align not in KNOWN_ALIGN:
        raise _fail(f"{path}.align", f"must be one of {sorted(KNOWN_ALIGN)}")
    return {
        "id": str(data.get("id", f"text_{idx}")).strip() or f"text_{idx}",
        "text": text,
        "x": int(_expect_number(data.get("x", 0), f"{path}.x")),
        "y": int(_expect_number(data.get("y", 0), f"{path}.y")),
        "box_width": int(_expect_number(data.get("box_width", 320), f"{path}.box_width")),
        "box_height": int(_expect_number(data.get("box_height", 48), f"{path}.box_height")),
        "font_family": str(data.get("font_family", "DejaVu Sans")).strip() or "DejaVu Sans",
        "font_size": int(_expect_number(data.get("font_size", 24), f"{path}.font_size")),
        "font_bold": bool(data.get("font_bold", False)),
        "font_italic": bool(data.get("font_italic", False)),
        "font_underline": bool(data.get("font_underline", False)),
        "marquee": bool(data.get("marquee", False)),
        "marquee_speed": float(data.get("marquee_speed", 55.0)),
        "color": _normalize_color(data.get("color", [255, 255, 255]), f"{path}.color"),
        "align": align,
        "z_index": int(_expect_number(data.get("z_index", 200), f"{path}.z_index")),
        "visible": bool(data.get("visible", True)),
        "locked": bool(data.get("locked", False)),
    }


def _normalize_stat_item(raw: Any, idx: int) -> dict[str, Any]:
    path = f"stats[{idx}]"
    data = _expect_dict(raw, path)
    source = _expect_str(data.get("source", ""), f"{path}.source").strip()
    if source not in KNOWN_STAT_SOURCES:
        raise _fail(f"{path}.source", f"unknown stat source '{source}'")
    align = _expect_str(data.get("align", "left"), f"{path}.align").strip().lower()
    if align not in KNOWN_ALIGN:
        raise _fail(f"{path}.align", f"must be one of {sorted(KNOWN_ALIGN)}")
    return {
        "id": str(data.get("id", f"stat_{idx}")).strip() or f"stat_{idx}",
        "label": str(data.get("label", "")).strip(),
        "source": source,
        "format": str(data.get("format", "{value}")).strip() or "{value}",
        "x": int(_expect_number(data.get("x", 0), f"{path}.x")),
        "y": int(_expect_number(data.get("y", 0), f"{path}.y")),
        "box_width": int(_expect_number(data.get("box_width", 320), f"{path}.box_width")),
        "box_height": int(_expect_number(data.get("box_height", 40), f"{path}.box_height")),
        "font_family": str(data.get("font_family", "DejaVu Sans")).strip() or "DejaVu Sans",
        "font_size": int(_expect_number(data.get("font_size", 24), f"{path}.font_size")),
        "font_bold": bool(data.get("font_bold", False)),
        "font_italic": bool(data.get("font_italic", False)),
        "font_underline": bool(data.get("font_underline", False)),
        "marquee": bool(data.get("marquee", False)),
        "marquee_speed": float(data.get("marquee_speed", 55.0)),
        "label_color": _normalize_color(data.get("label_color", [255, 255, 255]), f"{path}.label_color"),
        "value_color": _normalize_color(data.get("value_color", [220, 220, 220]), f"{path}.value_color"),
        "align": align,
        "z_index": int(_expect_number(data.get("z_index", 220), f"{path}.z_index")),
        "visible": bool(data.get("visible", True)),
        "locked": bool(data.get("locked", False)),
    }


def _normalize_image_item(raw: Any, idx: int) -> dict[str, Any]:
    path = f"images[{idx}]"
    data = _expect_dict(raw, path)
    src = _expect_str(data.get("path", ""), f"{path}.path").strip()
    source = _expect_str(data.get("source", ""), f"{path}.source").strip()
    if source and source not in KNOWN_IMAGE_SOURCES:
        raise _fail(f"{path}.source", f"must be one of {sorted(KNOWN_IMAGE_SOURCES)}")
    if not src and not source:
        raise _fail(f"{path}.path", "must not be empty when source is not set")
    fit = _expect_str(data.get("fit", "contain"), f"{path}.fit").strip().lower()
    if fit not in KNOWN_FIT:
        raise _fail(f"{path}.fit", f"must be one of {sorted(KNOWN_FIT)}")
    opacity = float(_expect_number(data.get("opacity", 1.0), f"{path}.opacity"))
    if not (0.0 <= opacity <= 1.0):
        raise _fail(f"{path}.opacity", "must be in range 0.0..1.0")
    glow_opacity = float(_expect_number(data.get("glow_opacity", 0.0), f"{path}.glow_opacity"))
    if not (0.0 <= glow_opacity <= 1.0):
        raise _fail(f"{path}.glow_opacity", "must be in range 0.0..1.0")
    return {
        "id": str(data.get("id", f"image_{idx}")).strip() or f"image_{idx}",
        "path": src,
        "source": source,
        "rect": _normalize_rect(data.get("rect"), f"{path}.rect"),
        "fit": fit,
        "opacity": opacity,
        "radius": int(_expect_number(data.get("radius", 0), f"{path}.radius")),
        "border_width": int(_expect_number(data.get("border_width", 0), f"{path}.border_width")),
        "border_color": _normalize_color(data.get("border_color", [255, 255, 255, 0]), f"{path}.border_color"),
        "glow_radius": int(_expect_number(data.get("glow_radius", 0), f"{path}.glow_radius")),
        "glow_opacity": glow_opacity,
        "rotation": int(_expect_number(data.get("rotation", 0), f"{path}.rotation")),
        "z_index": int(_expect_number(data.get("z_index", 100), f"{path}.z_index")),
        "visible": bool(data.get("visible", True)),
        "locked": bool(data.get("locked", False)),
    }


def _normalize_effects(raw: Any) -> dict[str, Any]:
    data = _expect_dict(raw, "effects")
    animation_raw = data.get("animation", {})
    animation_data = _expect_dict(animation_raw, "effects.animation") if animation_raw is not None else {}
    frame_paths = animation_data.get("frame_paths", [])
    if frame_paths is None:
        frame_paths = []
    normalized_frame_paths = []
    for idx, item in enumerate(_expect_list(frame_paths, "effects.animation.frame_paths")):
        path_text = _expect_str(item, f"effects.animation.frame_paths[{idx}]").strip()
        if path_text:
            normalized_frame_paths.append(path_text)
    frame_durations = animation_data.get("frame_durations_ms", [])
    if frame_durations is None:
        frame_durations = []
    normalized_frame_durations = []
    for idx, item in enumerate(_expect_list(frame_durations, "effects.animation.frame_durations_ms")):
        duration_ms = int(_expect_number(item, f"effects.animation.frame_durations_ms[{idx}]"))
        if duration_ms <= 0:
            raise _fail(f"effects.animation.frame_durations_ms[{idx}]", "must be > 0")
        normalized_frame_durations.append(duration_ms)
    fps = float(_expect_number(animation_data.get("fps", 12.0), "effects.animation.fps"))
    if fps <= 0.0:
        raise _fail("effects.animation.fps", "must be > 0")
    current_frame = int(_expect_number(animation_data.get("current_frame", 0), "effects.animation.current_frame"))
    if current_frame < 0:
        raise _fail("effects.animation.current_frame", "must be >= 0")
    default_duration = max(1, int(round(1000.0 / fps)))
    if len(normalized_frame_durations) < len(normalized_frame_paths):
        normalized_frame_durations.extend([default_duration] * (len(normalized_frame_paths) - len(normalized_frame_durations)))
    elif len(normalized_frame_durations) > len(normalized_frame_paths):
        normalized_frame_durations = normalized_frame_durations[: len(normalized_frame_paths)]
    motion_tracks_raw = data.get("motion_tracks", [])
    if motion_tracks_raw is None:
        motion_tracks_raw = []
    normalized_motion_tracks = []
    for idx, item in enumerate(_expect_list(motion_tracks_raw, "effects.motion_tracks")):
        track = _expect_dict(item, f"effects.motion_tracks[{idx}]")
        item_id = _expect_str(track.get("item_id", ""), f"effects.motion_tracks[{idx}].item_id").strip()
        if not item_id:
            raise _fail(f"effects.motion_tracks[{idx}].item_id", "must not be empty")
        frame_start = int(_expect_number(track.get("frame_start", 0), f"effects.motion_tracks[{idx}].frame_start"))
        frame_end = int(_expect_number(track.get("frame_end", frame_start), f"effects.motion_tracks[{idx}].frame_end"))
        if frame_start < 0:
            raise _fail(f"effects.motion_tracks[{idx}].frame_start", "must be >= 0")
        if frame_end < frame_start:
            raise _fail(f"effects.motion_tracks[{idx}].frame_end", "must be >= frame_start")
        opacity_to = float(_expect_number(track.get("opacity_to", 1.0), f"effects.motion_tracks[{idx}].opacity_to"))
        if not (0.0 <= opacity_to <= 1.0):
            raise _fail(f"effects.motion_tracks[{idx}].opacity_to", "must be in range 0.0..1.0")
        normalized_motion_tracks.append(
            {
                "item_id": item_id,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "x_to": int(_expect_number(track.get("x_to", 0), f"effects.motion_tracks[{idx}].x_to")),
                "y_to": int(_expect_number(track.get("y_to", 0), f"effects.motion_tracks[{idx}].y_to")),
                "opacity_to": opacity_to,
            }
        )
    out = {
        "show_grid": bool(data.get("show_grid", False)),
        "show_safe_area": bool(data.get("show_safe_area", False)),
        "animation": {
            "enabled": bool(animation_data.get("enabled", False)),
            "use_as_background": bool(animation_data.get("use_as_background", True)),
            "fps": fps,
            "current_frame": current_frame,
            "loop": bool(animation_data.get("loop", True)),
            "frame_paths": normalized_frame_paths,
            "frame_durations_ms": normalized_frame_durations,
        },
        "motion_tracks": normalized_motion_tracks,
        "import_report": _expect_dict(data.get("import_report", {}), "effects.import_report") if data.get("import_report", {}) is not None else {},
    }
    return out


@dataclass(frozen=True)
class ThemeDocument:
    data: dict[str, Any]

    @property
    def name(self) -> str:
        return self.data["meta"]["name"]

    def to_json(self, *, pretty: bool = True) -> str:
        if pretty:
            return json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        return json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))


def normalize_theme_document(raw: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(_expect_dict(raw, "theme"))
    version = int(_expect_number(data.get("schema_version", THEME_SCHEMA_VERSION), "schema_version"))
    if version != THEME_SCHEMA_VERSION:
        raise _fail("schema_version", f"expected {THEME_SCHEMA_VERSION}, got {version}")

    meta = _normalize_meta(data.get("meta", {}))
    canvas = _normalize_canvas(data.get("canvas", DEFAULT_CANVAS))
    background = _normalize_background(data.get("background", {}))
    texts = [_normalize_text_item(item, idx) for idx, item in enumerate(_expect_list(data.get("texts", []), "texts"))]
    stats = [_normalize_stat_item(item, idx) for idx, item in enumerate(_expect_list(data.get("stats", []), "stats"))]
    images = [_normalize_image_item(item, idx) for idx, item in enumerate(_expect_list(data.get("images", []), "images"))]
    effects = _normalize_effects(data.get("effects", {}))

    return {
        "schema_version": version,
        "meta": meta,
        "canvas": canvas,
        "background": background,
        "texts": texts,
        "stats": stats,
        "images": images,
        "effects": effects,
    }


def load_theme_document(path: str | Path) -> ThemeDocument:
    theme_path = Path(path)
    raw = json.loads(theme_path.read_text(encoding="utf-8"))
    return ThemeDocument(normalize_theme_document(raw))


def save_theme_document(path: str | Path, theme: ThemeDocument | dict[str, Any]) -> Path:
    theme_path = Path(path)
    doc = theme if isinstance(theme, ThemeDocument) else ThemeDocument(normalize_theme_document(theme))
    theme_path.parent.mkdir(parents=True, exist_ok=True)
    theme_path.write_text(doc.to_json(pretty=True), encoding="utf-8")
    return theme_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate Open Trofeo LCD theme JSON")
    parser.add_argument("paths", nargs="+", help="Theme JSON files")
    args = parser.parse_args()

    exit_code = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        try:
            theme = load_theme_document(path)
            print(f"OK {path} -> {theme.name}")
        except Exception as exc:
            exit_code = 1
            print(f"ERR {path}: {exc}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
