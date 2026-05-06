#!/usr/bin/env python3
"""
Best-effort importer for themes from the Windows TTCR application.

The importer is intentionally conservative:
- backgrounds and image assets are imported whenever possible,
- text/stat/layout are imported only when the source exposes explicit
  coordinates or layout-like data,
- unsupported animation assets are preserved in the theme asset folder
  and reported back to the caller.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from theme_schema import normalize_theme_document, save_theme_document


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
ANIMATION_SUFFIXES = {".gif", ".mp4", ".webm", ".avi", ".mov", ".mkv"}
LAYOUT_SUFFIXES = {".json", ".xml"}
TTCR_LAYOUT_SUFFIXES = {".dc"}
TTCR_CONTAINER_SUFFIXES = {".zt"}
DEFAULT_CANVAS = (1920, 462)
TTCR_FONT_BYTES = "微软雅黑".encode("utf-8")

TTCR_STAT_MAP = {
    "host": "hostname",
    "hostname": "hostname",
    "pc_name": "hostname",
    "computer_name": "hostname",
    "local_ip": "ip_local",
    "ip_address": "ip_local",
    "time": "time_hms",
    "clock": "time_hms",
    "hour": "time_hms",
    "date": "date_ymd",
    "day": "date_ymd",
    "cpu": "cpu_usage_percent",
    "cpu_usage": "cpu_usage_percent",
    "cpu_load": "cpu_usage_percent",
    "processor": "cpu_usage_percent",
    "cpu_avg": "cpu_core_avg_percent",
    "cpu_average": "cpu_core_avg_percent",
    "cpu_max": "cpu_core_max_percent",
    "cpu_peak": "cpu_core_max_percent",
    "cpu_core_count": "cpu_core_count",
    "core_count": "cpu_core_count",
    "cores": "cpu_core_count",
    "cpu_freq": "cpu_freq_ghz",
    "cpu_clock": "cpu_freq_ghz",
    "cpu_temp": "cpu_temp_c",
    "cpu_temperature": "cpu_temp_c",
    "package_temp": "cpu_temp_c",
    "temperature": "cpu_temp_c",
    "mem": "mem_percent",
    "memory": "mem_percent",
    "ram": "mem_percent",
    "memory_usage": "mem_percent",
    "ram_usage": "mem_percent",
    "mem_used": "mem_used_mb",
    "ram_used": "mem_used_mb",
    "memory_used": "mem_used_mb",
    "mem_total": "mem_total_mb",
    "ram_total": "mem_total_mb",
    "memory_total": "mem_total_mb",
    "gpu": "gpu_load",
    "gpu_load": "gpu_load",
    "gpu_usage": "gpu_load",
    "graphics": "gpu_load",
    "gpu_temp": "gpu_temp",
    "gpu_temperature": "gpu_temp",
    "gfx_temp": "gpu_temp",
    "gpu_name": "gpu_name",
    "vram": "vram_percent",
    "gpu_mem": "vram_percent",
    "video_memory": "vram_percent",
    "vram_used": "vram_used_mb",
    "vram_total": "vram_total_mb",
    "uptime": "uptime_human",
    "running_time": "uptime_human",
    "disk": "disk_percent",
    "storage": "disk_percent",
    "disk_used": "disk_used_gb",
    "disk_total": "disk_total_gb",
    "storage_used": "disk_used_gb",
    "storage_total": "disk_total_gb",
    "download": "net_dl_kbps",
    "down": "net_dl_kbps",
    "rx": "net_dl_kbps",
    "upload": "net_ul_kbps",
    "up": "net_ul_kbps",
    "tx": "net_ul_kbps",
    "network_down": "net_dl_kbps",
    "network_up": "net_ul_kbps",
    "ip": "ip_local",
}

TTCR_STAT_HINTS = (
    "cpu",
    "gpu",
    "ram",
    "mem",
    "memory",
    "temp",
    "temperature",
    "vram",
    "disk",
    "uptime",
    "clock",
    "time",
    "date",
    "host",
    "download",
    "upload",
    "network",
    "net",
    "fan",
    "fps",
)


def _slugify(text: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or "motyw"


def _humanize_stem(path: Path) -> str:
    match = re.fullmatch(r"Theme(\d{3,4})(\d{3,4})", path.stem, re.IGNORECASE)
    if match:
        return f"TTCR {match.group(1)}x{match.group(2)}"
    stem = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", path.stem)
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else "Motyw TTCR"


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


def _is_ttcr_variant_dir(path: Path) -> bool:
    return path.is_dir() and (path / "Theme.png").exists() and (path / "config1.dc").exists()


def _find_ttcr_variant_dirs(root: Path) -> list[Path]:
    if _is_ttcr_variant_dir(root):
        return [root]
    variants = []
    for child in sorted(root.iterdir()):
        if _is_ttcr_variant_dir(child):
            variants.append(child)
    return variants


def _copy_asset(source: Path, target_dir: Path, prefix: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".bin"
    stem = _slugify(f"{prefix}_{source.stem}")
    candidate = target_dir / f"{stem}{suffix}"
    index = 2
    while candidate.exists():
        candidate = target_dir / f"{stem}_{index}{suffix}"
        index += 1
    shutil.copy2(source, candidate)
    return candidate


def _choose_ttcr_background_source(
    theme_dir: Path,
    *,
    prefer_animation_frame: bool = False,
) -> Path | None:
    candidates = {
        "base": theme_dir / "00.png",
        "overlay": theme_dir / "01.png",
        "preview": theme_dir / "Theme.png",
    }
    if prefer_animation_frame:
        if candidates["base"].exists() and candidates["base"].stat().st_size > 1024:
            return candidates["base"]
        return None
    if candidates["base"].exists() and candidates["base"].stat().st_size > 1024:
        return candidates["base"]
    if candidates["preview"].exists() and candidates["preview"].stat().st_size > 1024:
        return candidates["preview"]
    return None


def _sanitize_theme_name(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("_", " ").replace("-", " ")).strip() or "Motyw TTCR"


def _summarize_detected_stats(items: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for item in items:
        source = str(item.get("source", "")).strip()
        if source and source not in seen:
            seen.append(source)
    return seen


def _stat_entries_from_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        source = str(item.get("source", "")).strip()
        label = str(item.get("label", "")).strip()
        if not source:
            continue
        key = (label or source, source)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "label": key[0],
                "source": source,
                "x": int(item.get("x", 0) or 0),
                "y": int(item.get("y", 0) or 0),
                "box_width": int(item.get("box_width", 0) or 0),
                "box_height": int(item.get("box_height", 0) or 0),
            }
        )
    return entries


def _looks_like_ttcr_stat_label(*values: str) -> bool:
    for value in values:
        key = _normalize_key(value)
        if not key:
            continue
        if any(token in key for token in TTCR_STAT_HINTS):
            return True
    return False


def _summarize_unmapped_stat_labels(labels: list[str]) -> list[str]:
    seen: list[str] = []
    for label in labels:
        if isinstance(label, dict):
            cleaned = str(label.get("label", "")).strip()
        else:
            cleaned = str(label).strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _iter_text_runs(data: bytes):
    idx = 0
    while idx < len(data):
        byte = data[idx]
        if 32 <= byte <= 126:
            end = idx
            while end < len(data) and 32 <= data[end] <= 126:
                end += 1
            if end - idx >= 3:
                yield idx, data[idx:end].decode("ascii", "ignore")
            idx = end
            continue
        if byte >= 0x80:
            end = idx
            while end < len(data) and data[end] >= 0x80:
                end += 1
            if end - idx >= 3:
                try:
                    decoded = data[idx:end].decode("utf-8")
                except Exception:
                    decoded = ""
                if decoded:
                    yield idx, decoded
            idx = end
            continue
        idx += 1


def _extract_ttcr_text_color(data: bytes, font_offset: int) -> list[int]:
    try:
        raw = data[font_offset + len(TTCR_FONT_BYTES) + 10 : font_offset + len(TTCR_FONT_BYTES) + 14]
        if len(raw) == 4:
            return [raw[0], raw[1], raw[2]]
    except Exception:
        pass
    return [255, 255, 255]


def _parse_ttcr_dc(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    font_offsets: list[int] = []
    cursor = 0
    while True:
        pos = data.find(TTCR_FONT_BYTES, cursor)
        if pos < 0:
            break
        font_offsets.append(pos)
        cursor = pos + 1

    parsed_texts: list[dict[str, Any]] = []
    parsed_stats: list[dict[str, Any]] = []
    unmapped_stats: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for text_offset, text in _iter_text_runs(data):
        cleaned = text.strip().strip("\x00")
        if not cleaned or cleaned == "微软雅黑":
            continue
        font_offset = None
        for candidate in font_offsets:
            if candidate < text_offset and text_offset - candidate <= 40:
                font_offset = candidate
        if font_offset is None:
            continue
        try:
            x = struct.unpack_from("<I", data, font_offset - 17)[0]
            y = struct.unpack_from("<I", data, font_offset - 13)[0]
        except struct.error:
            continue
        if not (0 <= x <= 1919 and 0 <= y <= 461):
            continue

        key = (x, y, cleaned)
        if key in seen:
            continue
        seen.add(key)

        label = cleaned
        color = _extract_ttcr_text_color(data, font_offset)
        font_size = 44 if any(ch.isdigit() for ch in label) and ":" in label else 28
        if "/" in label or any("\u4e00" <= ch <= "\u9fff" for ch in label):
            font_size = 24
        stat_source = _maybe_map_stat(label)
        if stat_source:
            parsed_stats.append(
                {
                    "label": label,
                    "source": stat_source,
                    "x": x,
                    "y": y,
                    "box_width": 220 if y >= 250 else 260,
                    "box_height": 72 if y >= 250 else 52,
                    "font_size": 26 if y >= 250 else 30,
                    "color": color,
                }
            )
        elif _looks_like_ttcr_stat_label(label):
            unmapped_stats.append(
                {
                    "label": label,
                    "x": x,
                    "y": y,
                    "box_width": 220 if y >= 250 else 260,
                    "box_height": 72 if y >= 250 else 52,
                    "font_size": 26 if y >= 250 else 30,
                }
            )
        else:
            parsed_texts.append(
                {
                    "text": label,
                    "x": x,
                    "y": y,
                    "box_width": max(140, min(480, len(label) * (font_size // 2 + 6))),
                    "box_height": 58 if font_size >= 32 else 46,
                    "font_size": font_size,
                    "color": color,
                }
            )

    return {
        "canvas": DEFAULT_CANVAS,
        "texts": parsed_texts,
        "stats": parsed_stats,
        "unmapped_stats": unmapped_stats,
        "images": [],
        "panels": [],
    }


def _build_ttcr_variant_document(
    theme_dir: Path,
    output_theme: Path,
    theme_name: str,
    assets_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    background_dir = assets_root / "background"
    image_dir = assets_root / "images"
    animation_dir = assets_root / "animations"

    overlay_png = theme_dir / "01.png"
    dc_path = theme_dir / "config1.dc"
    zt_path = theme_dir / "Theme.zt"

    overlay_rel = ""
    if overlay_png.exists() and overlay_png.stat().st_size > 1024:
        copied_overlay = _copy_asset(overlay_png, image_dir, f"{output_theme.stem}_overlay")
        overlay_rel = str(copied_overlay.relative_to(output_theme.parent))

    preserved_animations: list[str] = []
    extracted_frames: list[str] = []
    if zt_path.exists():
        copied_zt = _copy_asset(zt_path, animation_dir, f"{output_theme.stem}_theme_zt")
        preserved_animations.append(str(copied_zt.relative_to(output_theme.parent)))
        frame_dir = animation_dir / f"{_slugify(output_theme.stem)}_frames"
        for frame in _extract_ttcr_zt_frames(zt_path, frame_dir, f"{output_theme.stem}_frame"):
            extracted_frames.append(str(frame.relative_to(output_theme.parent)))

    background_rel = ""
    background_source = _choose_ttcr_background_source(
        theme_dir,
        prefer_animation_frame=bool(extracted_frames),
    )
    if background_source is not None:
        copied_bg = _copy_asset(background_source, background_dir, f"{output_theme.stem}_background")
        background_rel = str(copied_bg.relative_to(output_theme.parent))
    elif extracted_frames:
        background_rel = extracted_frames[0]

    parsed = _parse_ttcr_dc(dc_path) if dc_path.exists() else {"canvas": DEFAULT_CANVAS, "texts": [], "stats": [], "images": [], "panels": []}

    document: dict[str, Any] = {
        "schema_version": 1,
        "meta": {
            "name": theme_name,
            "description": "Motyw zaimportowany z TTCR (Windows).",
            "author": "TTCR Import",
            "tags": ["ttcr-import", "windows", theme_dir.name.lower()],
        },
        "canvas": {"width": 1920, "height": 462, "rotation": 180},
        "background": {
            "kind": "image" if background_rel else "generated",
            "base_color": [9, 14, 22],
            "accent_color": [20, 34, 48],
            "texture_alpha": 0.35,
            "panels": [],
        },
        "texts": [],
        "stats": [],
        "images": [],
        "effects": {
            "animation": {
                "enabled": bool(extracted_frames),
                "use_as_background": bool(extracted_frames),
                "fps": 12.0,
                "current_frame": 0,
                "loop": True,
                "frame_paths": extracted_frames,
                "frame_durations_ms": [83] * len(extracted_frames),
            },
            "import_report": {
                "source_path": str(theme_dir),
                "source_canvas": [1920, 462],
                "imported_layout_files": [str(dc_path.name)] if dc_path.exists() else [],
                "preserved_animations": preserved_animations,
                "extracted_frames": extracted_frames,
                "ttcr_variant": theme_dir.name,
            }
        },
    }
    if background_rel:
        document["background"]["path"] = background_rel
        document["background"]["fit"] = "cover"
        document["background"]["opacity"] = 1.0

    if overlay_rel:
        document["images"].append(
            {
                "id": "ttcr_overlay",
                "path": overlay_rel,
                "rect": [0, 0, 1920, 462],
                "fit": "cover",
                "opacity": 1.0,
                "rotation": 0,
                "z_index": 180,
                "visible": True,
                "locked": False,
            }
        )

    for idx, item in enumerate(parsed.get("texts", [])[:20]):
        text_value = str(item["text"])[:120]
        literal_source = _maybe_map_literal_stat(text_value)
        if literal_source:
            document["stats"].append(
                {
                    "id": f"stat_auto_{idx}",
                    "label": "",
                    "source": literal_source,
                    "format": "{value}",
                    "x": int(item["x"]),
                    "y": int(item["y"]),
                    "box_width": int(item["box_width"]),
                    "box_height": int(item["box_height"]),
                    "font_family": "DejaVu Sans",
                    "font_size": int(item["font_size"]),
                    "label_color": item.get("color", [255, 255, 255]),
                    "value_color": item.get("color", [220, 220, 220]),
                    "align": "left",
                    "z_index": 220 + idx,
                    "visible": True,
                    "locked": False,
                }
            )
            continue
        document["texts"].append(
            {
                "id": f"text_{idx}",
                "text": text_value,
                "x": int(item["x"]),
                "y": int(item["y"]),
                "box_width": int(item["box_width"]),
                "box_height": int(item["box_height"]),
                "font_family": "DejaVu Sans",
                "font_size": int(item["font_size"]),
                "color": item.get("color", [255, 255, 255]),
                "align": "left",
                "z_index": 220 + idx,
                "visible": True,
                "locked": False,
            }
        )

    for idx, item in enumerate(parsed.get("stats", [])[:20]):
        document["stats"].append(
            {
                "id": f"stat_{idx}",
                "label": str(item["label"])[:80],
                "source": item["source"],
                "format": "{value}",
                "x": int(item["x"]),
                "y": int(item["y"]),
                "box_width": int(item["box_width"]),
                "box_height": int(item["box_height"]),
                "font_family": "DejaVu Sans",
                "font_size": int(item["font_size"]),
                "label_color": item.get("color", [255, 255, 255]),
                "value_color": item.get("color", [220, 220, 220]),
                "align": "left",
                "z_index": 240 + idx,
                "visible": True,
                "locked": False,
            }
        )

    normalized = normalize_theme_document(document)
    report = {
        "background_imported": bool(background_rel),
        "background_source": (
            "animation_frame"
            if extracted_frames and (background_source is None or str(background_source.name) == "Theme.png")
            else (background_source.name if background_source is not None else "")
        ),
        "texts": len(normalized.get("texts", [])),
        "stats": len(normalized.get("stats", [])),
        "detected_stats": _summarize_detected_stats(normalized.get("stats", [])),
        "stat_entries": _stat_entries_from_items(normalized.get("stats", [])),
        "unmapped_stats": _summarize_unmapped_stat_labels(parsed.get("unmapped_stats", [])),
        "images": len(normalized.get("images", [])),
        "panels": len(normalized.get("background", {}).get("panels", [])),
        "preserved_animations": preserved_animations,
        "extracted_frames": extracted_frames,
        "layout_files": [str(dc_path)] if dc_path.exists() else [],
        "ttcr_variant": theme_dir.name,
    }
    return normalized, report


def _iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _try_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _extract_rect(data: dict[str, Any]) -> tuple[int, int, int, int] | None:
    x = _try_int(data.get("x", data.get("left")))
    y = _try_int(data.get("y", data.get("top")))
    w = _try_int(data.get("width", data.get("w")))
    h = _try_int(data.get("height", data.get("h")))
    if x is None or y is None:
        return None
    if w is None:
        w = 320
    if h is None:
        h = 40
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def _maybe_map_stat(*values: str) -> str | None:
    for value in values:
        key = _normalize_key(value)
        if not key:
            continue
        for probe, stat_source in TTCR_STAT_MAP.items():
            if probe == key or probe in key or key in probe:
                return stat_source
    return None


def _maybe_map_literal_stat(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
        return "time_hms"
    if re.fullmatch(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", text):
        return "date_ymd"
    return None


def _extract_canvas_hint(raw: dict[str, Any]) -> tuple[int, int] | None:
    for data in _iter_dicts(raw):
        width = _try_int(data.get("canvas_width", data.get("canvasWidth", data.get("width"))))
        height = _try_int(data.get("canvas_height", data.get("canvasHeight", data.get("height"))))
        if width and height and width > 64 and height > 32:
            return (width, height)
    return None


def _parse_layout_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"canvas": None, "texts": [], "stats": [], "images": [], "panels": []}
    if not isinstance(raw, (dict, list)):
        return {"canvas": None, "texts": [], "stats": [], "images": [], "panels": []}

    texts: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    unmapped_stats: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    panels: list[dict[str, Any]] = []
    canvas = _extract_canvas_hint(raw) if isinstance(raw, dict) else None

    for obj in _iter_dicts(raw):
        rect = _extract_rect(obj)
        kind_hint = " ".join(
            str(obj.get(key, ""))
            for key in ("type", "kind", "widget", "component", "role", "name")
        ).strip()
        label = str(obj.get("label", obj.get("title", obj.get("name", "")))).strip()
        text_value = str(obj.get("text", obj.get("value", ""))).strip()
        source_value = str(obj.get("source", obj.get("metric", obj.get("stat", "")))).strip()
        path_value = str(
            obj.get("path", obj.get("image", obj.get("image_path", obj.get("src", ""))))
        ).strip()

        if path_value:
            if rect is None:
                rect = (0, 0, 960, 231)
            images.append({"path": path_value, "rect": rect})
            continue

        stat_source = _maybe_map_stat(source_value, label, text_value, kind_hint)
        if stat_source and rect is not None:
            stats.append({"label": label or text_value or stat_source, "source": stat_source, "rect": rect})
            continue
        if _looks_like_ttcr_stat_label(source_value, label, text_value, kind_hint):
            candidate = label or text_value or source_value or kind_hint
            if candidate:
                unmapped_stats.append({"label": candidate, "rect": rect or (0, 0, 220, 52)})

        lowered_kind = kind_hint.lower()
        if any(token in lowered_kind for token in ("panel", "card", "box", "container")) and rect is not None:
            panels.append({"rect": rect})
            continue

        if (text_value or label) and rect is not None:
            texts.append({"text": text_value or label, "rect": rect})

    return {
        "canvas": canvas,
        "texts": texts,
        "stats": stats,
        "unmapped_stats": unmapped_stats,
        "images": images,
        "panels": panels,
    }


def _parse_layout_xml(path: Path) -> dict[str, Any]:
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except Exception:
        return {"canvas": None, "texts": [], "stats": [], "images": [], "panels": []}

    raw: list[dict[str, Any]] = []
    canvas = None
    for element in root.iter():
        attrs = dict(element.attrib)
        if element.text and element.text.strip():
            attrs["text"] = element.text.strip()
        attrs.setdefault("type", element.tag)
        raw.append(attrs)
        if canvas is None:
            width = _try_int(attrs.get("width"))
            height = _try_int(attrs.get("height"))
            if width and height and width > 64 and height > 32:
                canvas = (width, height)

    pseudo = {"items": raw}
    parsed = _parse_layout_json(Path("/dev/null"))
    parsed.update(_parse_layout_json_from_raw(pseudo))
    if canvas is not None:
        parsed["canvas"] = canvas
    return parsed


def _parse_layout_json_from_raw(raw: Any) -> dict[str, Any]:
    texts: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    unmapped_stats: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    panels: list[dict[str, Any]] = []
    canvas = _extract_canvas_hint(raw) if isinstance(raw, dict) else None
    for obj in _iter_dicts(raw):
        rect = _extract_rect(obj)
        label = str(obj.get("label", obj.get("title", obj.get("name", "")))).strip()
        text_value = str(obj.get("text", obj.get("value", ""))).strip()
        source_value = str(obj.get("source", obj.get("metric", obj.get("stat", "")))).strip()
        kind_hint = str(obj.get("type", obj.get("kind", ""))).strip()
        path_value = str(
            obj.get("path", obj.get("image", obj.get("image_path", obj.get("src", ""))))
        ).strip()
        if path_value:
            if rect is None:
                rect = (0, 0, 960, 231)
            images.append({"path": path_value, "rect": rect})
            continue
        stat_source = _maybe_map_stat(source_value, label, text_value, kind_hint)
        if stat_source and rect is not None:
            stats.append({"label": label or text_value or stat_source, "source": stat_source, "rect": rect})
            continue
        if _looks_like_ttcr_stat_label(source_value, label, text_value, kind_hint):
            candidate = label or text_value or source_value or kind_hint
            if candidate:
                unmapped_stats.append({"label": candidate, "rect": rect or (0, 0, 220, 52)})
        lowered_kind = kind_hint.lower()
        if any(token in lowered_kind for token in ("panel", "card", "box", "container")) and rect is not None:
            panels.append({"rect": rect})
            continue
        if (text_value or label) and rect is not None:
            texts.append({"text": text_value or label, "rect": rect})
    return {
        "canvas": canvas,
        "texts": texts,
        "stats": stats,
        "unmapped_stats": unmapped_stats,
        "images": images,
        "panels": panels,
    }


def _scale_rect(rect: tuple[int, int, int, int], scale_x: float, scale_y: float) -> list[int]:
    x, y, w, h = rect
    return [
        int(round(x * scale_x)),
        int(round(y * scale_y)),
        max(1, int(round(w * scale_x))),
        max(1, int(round(h * scale_y))),
    ]


def _extract_source_tree(source_path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    suffix = source_path.suffix.lower()
    if source_path.is_dir():
        return source_path, None
    if suffix in IMAGE_SUFFIXES | ANIMATION_SUFFIXES | TTCR_LAYOUT_SUFFIXES | TTCR_CONTAINER_SUFFIXES:
        return source_path.parent, None
    if suffix == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="ttcr-import-")
        with zipfile.ZipFile(source_path) as archive:
            archive.extractall(tmp.name)
        return Path(tmp.name), tmp
    return source_path.parent, None


def _extract_ttcr_zt_frames(source: Path, target_dir: Path, prefix: str) -> list[Path]:
    data = source.read_bytes()
    target_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    cursor = 0
    frame_index = 0
    while True:
        soi = data.find(b"\xff\xd8\xff", cursor)
        if soi < 0:
            break
        eoi = data.find(b"\xff\xd9", soi + 3)
        if eoi < 0:
            break
        payload = data[soi : eoi + 2]
        if len(payload) >= 1024:
            frame_path = target_dir / f"{_slugify(prefix)}_{frame_index:04d}.jpg"
            frame_path.write_bytes(payload)
            frames.append(frame_path)
            frame_index += 1
        cursor = eoi + 2
    return frames


def extract_ttcr_zt_frames(source: str | Path, target_dir: str | Path, prefix: str) -> list[Path]:
    return _extract_ttcr_zt_frames(Path(source), Path(target_dir), prefix)


def import_ttcr_theme(source_path: str | Path, output_theme_path: str | Path, theme_name: str | None = None) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    output_theme = Path(output_theme_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    resolved_name = theme_name.strip() if theme_name else _humanize_stem(source)
    output_theme.parent.mkdir(parents=True, exist_ok=True)
    date_tag = time.strftime("%Y-%m-%d")

    variant_dirs = _find_ttcr_variant_dirs(source) if source.is_dir() else []
    if variant_dirs:
        generated_themes: list[dict[str, Any]] = []
        primary_document: dict[str, Any] | None = None
        primary_output: Path | None = None
        primary_report: dict[str, Any] | None = None

        for index, variant_dir in enumerate(variant_dirs, start=1):
            if len(variant_dirs) == 1:
                variant_output = output_theme
                variant_name = resolved_name
            else:
                suffix = _slugify(variant_dir.name)
                variant_output = output_theme.parent / f"{output_theme.stem}_{suffix}.json"
                variant_name = f"{_humanize_stem(source)} {_humanize_stem(variant_dir)}"
            assets_root = variant_output.parent / f"{variant_output.stem}_assets" / date_tag / "ttcr_import"
            document, report = _build_ttcr_variant_document(
                variant_dir,
                variant_output,
                _sanitize_theme_name(variant_name),
                assets_root,
            )
            saved = save_theme_document(variant_output, document)
            generated_themes.append(
                {
                    "theme_name": _sanitize_theme_name(variant_name),
                    "output_theme_path": str(saved),
                    "document": document,
                    "report": report,
                    "asset_root": str(assets_root),
                }
            )
            if index == 1:
                primary_document = document
                primary_output = saved
                primary_report = report

        assert primary_document is not None and primary_output is not None and primary_report is not None
        return {
            "document": primary_document,
            "output_theme_path": str(primary_output),
            "theme_name": _sanitize_theme_name(
                resolved_name if len(variant_dirs) == 1 else f"{_humanize_stem(source)} {_humanize_stem(variant_dirs[0])}"
            ),
            "asset_root": str(primary_output.parent / f"{primary_output.stem}_assets" / date_tag / "ttcr_import"),
            "report": primary_report,
            "generated_themes": generated_themes,
        }

    assets_root = output_theme.parent / f"{output_theme.stem}_assets" / date_tag / "ttcr_import"
    background_dir = assets_root / "background"
    image_dir = assets_root / "images"
    animation_dir = assets_root / "animations"

    source_root, temp_root = _extract_source_tree(source)
    try:
        if source.is_file() and source.suffix.lower() in IMAGE_SUFFIXES | ANIMATION_SUFFIXES | TTCR_CONTAINER_SUFFIXES:
            candidates = [source]
        elif source.is_file() and source.suffix.lower() in LAYOUT_SUFFIXES | TTCR_LAYOUT_SUFFIXES:
            related_assets = []
            for item in source.parent.iterdir():
                if not item.is_file():
                    continue
                if item.suffix.lower() not in IMAGE_SUFFIXES | ANIMATION_SUFFIXES | TTCR_CONTAINER_SUFFIXES:
                    continue
                src_stem = source.stem.lower()
                item_stem = item.stem.lower()
                if src_stem in item_stem or item_stem in src_stem:
                    related_assets.append(item)
            candidates = [source] + related_assets
        else:
            candidates = [p for p in source_root.rglob("*") if p.is_file()]
        image_files = [p for p in candidates if p.suffix.lower() in IMAGE_SUFFIXES]
        animation_files = [p for p in candidates if p.suffix.lower() in ANIMATION_SUFFIXES and p.suffix.lower() not in IMAGE_SUFFIXES]
        layout_files = [p for p in candidates if p.suffix.lower() in LAYOUT_SUFFIXES]
        ttcr_layout_files = [p for p in candidates if p.suffix.lower() in TTCR_LAYOUT_SUFFIXES]
        ttcr_container_files = [p for p in candidates if p.suffix.lower() in TTCR_CONTAINER_SUFFIXES]

        parsed_layouts: list[dict[str, Any]] = []
        for layout_file in layout_files[:8]:
            if layout_file.suffix.lower() == ".json":
                parsed = _parse_layout_json(layout_file)
            else:
                parsed = _parse_layout_xml(layout_file)
            if any(parsed[key] for key in ("texts", "stats", "images", "panels")):
                parsed_layouts.append(parsed)
        for layout_file in ttcr_layout_files[:8]:
            parsed = _parse_ttcr_dc(layout_file)
            if any(parsed[key] for key in ("texts", "stats", "images", "panels")):
                parsed_layouts.append(parsed)

        canvas = None
        imported_texts: list[dict[str, Any]] = []
        imported_stats: list[dict[str, Any]] = []
        imported_unmapped_stats: list[str] = []
        imported_images: list[dict[str, Any]] = []
        imported_panels: list[dict[str, Any]] = []

        if parsed_layouts:
            primary = parsed_layouts[0]
            canvas = primary.get("canvas")
            imported_texts = list(primary.get("texts", []))
            imported_stats = list(primary.get("stats", []))
            imported_unmapped_stats = list(primary.get("unmapped_stats", []))
            imported_images = list(primary.get("images", []))
            imported_panels = list(primary.get("panels", []))

        source_width, source_height = canvas or DEFAULT_CANVAS
        scale_x = DEFAULT_CANVAS[0] / max(1, source_width)
        scale_y = DEFAULT_CANVAS[1] / max(1, source_height)
        scale_font = max(0.75, min(4.0, (scale_x + scale_y) / 2.0))

        asset_map: dict[str, str] = {}
        for img in imported_images:
            raw_path = str(img.get("path", "")).strip()
            if not raw_path:
                continue
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = (source_root / candidate).resolve()
            if candidate.exists():
                copied = _copy_asset(candidate, image_dir, f"{output_theme.stem}_image")
                asset_map[raw_path] = str(copied.relative_to(output_theme.parent))

        preserved_animations: list[str] = []
        extracted_frames: list[str] = []
        for animation in animation_files[:20]:
            copied = _copy_asset(animation, animation_dir, f"{output_theme.stem}_animation")
            preserved_animations.append(str(copied.relative_to(output_theme.parent)))
        for container in ttcr_container_files[:8]:
            copied = _copy_asset(container, animation_dir, f"{output_theme.stem}_ttcr_container")
            preserved_animations.append(str(copied.relative_to(output_theme.parent)))
            frame_dir = animation_dir / f"{_slugify(output_theme.stem)}_{_slugify(container.stem)}_frames"
            for frame in _extract_ttcr_zt_frames(container, frame_dir, f"{output_theme.stem}_{container.stem}_frame"):
                extracted_frames.append(str(frame.relative_to(output_theme.parent)))

        background_candidate = None
        ttcr_base_candidates = [p for p in image_files if p.name.lower() == "00.png"]
        ttcr_preview_candidates = [p for p in image_files if p.name.lower() == "theme.png"]
        ttcr_overlay_candidates = [p for p in image_files if p.name.lower() == "01.png"]
        if extracted_frames:
            if ttcr_base_candidates:
                background_candidate = ttcr_base_candidates[0]
        else:
            if ttcr_base_candidates:
                background_candidate = ttcr_base_candidates[0]
            else:
                for probe in image_files:
                    lowered = probe.name.lower()
                    if any(token in lowered for token in ("background", "wallpaper", "backdrop", "bg")):
                        background_candidate = probe
                        break
                if background_candidate is None and ttcr_preview_candidates:
                    background_candidate = ttcr_preview_candidates[0]
                if background_candidate is None and image_files:
                    non_overlay_images = [p for p in image_files if p not in ttcr_overlay_candidates]
                    background_candidate = max(non_overlay_images or image_files, key=lambda item: item.stat().st_size)

        background_rel = ""
        if background_candidate is not None:
            copied_bg = _copy_asset(background_candidate, background_dir, f"{output_theme.stem}_background")
            background_rel = str(copied_bg.relative_to(output_theme.parent))
        elif extracted_frames:
            background_rel = extracted_frames[0]

        document: dict[str, Any] = {
            "schema_version": 1,
            "meta": {
                "name": resolved_name,
                "description": "Motyw zaimportowany z TTCR (Windows) w trybie best-effort.",
                "author": "TTCR Import",
                "tags": ["ttcr-import", "windows"],
            },
            "canvas": {"width": 1920, "height": 462, "rotation": 180},
            "background": {
                "kind": "image" if background_rel else "generated",
                "base_color": [9, 14, 22],
                "accent_color": [20, 34, 48],
                "texture_alpha": 0.35,
                "panels": [],
            },
            "texts": [],
            "stats": [],
            "images": [],
        "effects": {
            "animation": {
                "enabled": bool(extracted_frames),
                "use_as_background": bool(extracted_frames),
                "fps": 12.0,
                "current_frame": 0,
                "loop": True,
                "frame_paths": extracted_frames,
                "frame_durations_ms": [83] * len(extracted_frames),
            },
            "import_report": {
                "source_path": str(source),
                "source_canvas": [source_width, source_height],
                "imported_layout_files": [str(p.relative_to(source_root)) for p in (layout_files[:8] + ttcr_layout_files[:8])],
                "preserved_animations": preserved_animations,
                "extracted_frames": extracted_frames,
                "detected_stats": _summarize_detected_stats(document.get("stats", [])),
                "stat_entries": _stat_entries_from_items(document.get("stats", [])),
                "unmapped_stats": _summarize_unmapped_stat_labels(imported_unmapped_stats),
                "background_source": (
                    "animation_frame"
                    if extracted_frames and background_candidate is None
                    else (background_candidate.name if background_candidate is not None else "")
                ),
            }
            },
        }
        if background_rel:
            document["background"]["path"] = background_rel
            document["background"]["fit"] = "cover"
            document["background"]["opacity"] = 1.0

        for idx, item in enumerate(imported_panels[:10]):
            rect = _scale_rect(item["rect"], scale_x, scale_y)
            document["background"]["panels"].append(
                {
                    "rect": rect,
                    "radius": 18,
                    "fill": [0, 0, 0],
                    "z_index": 40 + idx,
                    "visible": True,
                    "locked": False,
                }
            )

        for idx, item in enumerate(imported_texts[:20]):
            rect = _scale_rect(item["rect"], scale_x, scale_y)
            text_value = str(item["text"])[:120]
            literal_source = _maybe_map_literal_stat(text_value)
            if literal_source:
                document["stats"].append(
                    {
                        "id": f"stat_auto_{idx}",
                        "label": "",
                        "source": literal_source,
                        "format": "{value}",
                        "x": rect[0],
                        "y": rect[1],
                        "box_width": rect[2],
                        "box_height": rect[3],
                        "font_family": "DejaVu Sans",
                        "font_size": max(12, int(round(24 * scale_font))),
                        "label_color": [255, 255, 255],
                        "value_color": [220, 220, 220],
                        "align": "left",
                        "z_index": 210 + idx,
                        "visible": True,
                        "locked": False,
                    }
                )
                continue
            document["texts"].append(
                {
                    "id": f"text_{idx}",
                    "text": text_value,
                    "x": rect[0],
                    "y": rect[1],
                    "box_width": rect[2],
                    "box_height": rect[3],
                    "font_family": "DejaVu Sans",
                    "font_size": max(12, int(round(24 * scale_font))),
                    "color": [255, 255, 255],
                    "align": "left",
                    "z_index": 210 + idx,
                    "visible": True,
                    "locked": False,
                }
            )

        for idx, item in enumerate(imported_stats[:20]):
            rect = _scale_rect(item["rect"], scale_x, scale_y)
            document["stats"].append(
                {
                    "id": f"stat_{idx}",
                    "label": str(item["label"])[:80],
                    "source": item["source"],
                    "format": "{value}",
                    "x": rect[0],
                    "y": rect[1],
                    "box_width": rect[2],
                    "box_height": rect[3],
                    "font_family": "DejaVu Sans",
                    "font_size": max(12, int(round(24 * scale_font))),
                    "label_color": [255, 255, 255],
                    "value_color": [220, 220, 220],
                    "align": "left",
                    "z_index": 230 + idx,
                    "visible": True,
                    "locked": False,
                }
            )

        for idx, item in enumerate(imported_images[:12]):
            rect = _scale_rect(item["rect"], scale_x, scale_y)
            rel_path = asset_map.get(str(item.get("path", "")).strip())
            if not rel_path:
                continue
            document["images"].append(
                {
                    "id": f"image_{idx}",
                    "path": rel_path,
                    "rect": rect,
                    "fit": "cover",
                    "opacity": 1.0,
                    "rotation": 0,
                    "z_index": 120 + idx,
                    "visible": True,
                    "locked": False,
                }
            )

        normalized = normalize_theme_document(document)
        saved = save_theme_document(output_theme, normalized)
        return {
            "document": normalized,
            "output_theme_path": str(saved),
            "theme_name": resolved_name,
            "asset_root": str(assets_root),
            "report": {
                "background_imported": bool(background_rel),
                "texts": len(normalized.get("texts", [])),
                "stats": len(normalized.get("stats", [])),
                "detected_stats": _summarize_detected_stats(normalized.get("stats", [])),
                "stat_entries": _stat_entries_from_items(normalized.get("stats", [])),
                "unmapped_stats": _summarize_unmapped_stat_labels(imported_unmapped_stats),
                "images": len(normalized.get("images", [])),
                "panels": len(normalized.get("background", {}).get("panels", [])),
                "preserved_animations": preserved_animations,
                "extracted_frames": extracted_frames,
                "layout_files": [str(p) for p in (layout_files[:8] + ttcr_layout_files[:8])],
            },
        }
    finally:
        if temp_root is not None:
            temp_root.cleanup()
