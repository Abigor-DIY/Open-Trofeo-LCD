#!/usr/bin/env python3
"""
Theme renderer for Open Trofeo LCD.

Stage 3.2: render a validated theme document into a 1920x462 image.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import time
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageChops

from stats_sources import StatsProvider
from theme_schema import ThemeDocument, load_theme_document


DEFAULT_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEFAULT_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_FAMILY_FILES = {
    "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "Liberation Sans": "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "Liberation Serif": "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
    "Liberation Mono": "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    "Noto Sans": "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "Noto Serif": "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
}
_WEATHER_ICON_IMAGE_CACHE: dict[tuple[str, int, int, int, int], Image.Image] = {}


def _rgba(color: list[int]) -> tuple[int, int, int, int]:
    if len(color) == 3:
        return color[0], color[1], color[2], 255
    return color[0], color[1], color[2], color[3]


def _resolve_asset_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    base_candidate = (base_dir / candidate).resolve()
    if base_candidate.exists():
        return base_candidate
    base_name_candidate = (base_dir / candidate.name).resolve()
    if base_name_candidate.exists():
        return base_name_candidate
    cwd_candidate = (Path.cwd() / candidate).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    cwd_name_candidate = (Path.cwd() / candidate.name).resolve()
    if cwd_name_candidate.exists():
        return cwd_name_candidate
    return cwd_candidate


def _animation_frame_path(theme: ThemeDocument, base_dir: Path) -> Path | None:
    effects = theme.data.get("effects", {})
    animation = effects.get("animation", {})
    if not isinstance(animation, dict):
        return None
    if not bool(animation.get("enabled", False)):
        return None
    if not bool(animation.get("use_as_background", True)):
        return None
    frame_paths = animation.get("frame_paths", [])
    if not isinstance(frame_paths, list) or not frame_paths:
        return None
    index = int(animation.get("current_frame", 0))
    if index < 0:
        index = 0
    if index >= len(frame_paths):
        index = len(frame_paths) - 1
    raw_path = str(frame_paths[index]).strip()
    if not raw_path:
        return None
    return _resolve_asset_path(base_dir, raw_path)



def _load_font(
    size: int,
    *,
    bold: bool = False,
    italic: bool = False,
    font_family: str | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    family = (font_family or "").strip()
    italic_files = {
        "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf",
        "Liberation Sans": "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf",
        "Liberation Serif": "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
        "Liberation Mono": "/usr/share/fonts/truetype/liberation2/LiberationMono-Italic.ttf",
    }
    bold_files = {
        "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "Liberation Sans": "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "Liberation Serif": "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "Liberation Mono": "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf",
        "Noto Sans": "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "Noto Serif": "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
    }
    bold_italic_files = {
        "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
        "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-BoldOblique.ttf",
        "Liberation Sans": "/usr/share/fonts/truetype/liberation2/LiberationSans-BoldItalic.ttf",
        "Liberation Serif": "/usr/share/fonts/truetype/liberation2/LiberationSerif-BoldItalic.ttf",
        "Liberation Mono": "/usr/share/fonts/truetype/liberation2/LiberationMono-BoldItalic.ttf",
    }
    if bold and italic:
        font_path = bold_italic_files.get(family, bold_files.get(family, FONT_FAMILY_FILES.get(family, DEFAULT_FONT_BOLD)))
    elif bold:
        font_path = bold_files.get(family, FONT_FAMILY_FILES.get(family, DEFAULT_FONT_BOLD))
    elif italic:
        font_path = italic_files.get(family, FONT_FAMILY_FILES.get(family, DEFAULT_FONT_REGULAR))
    else:
        font_path = FONT_FAMILY_FILES.get(family, DEFAULT_FONT_REGULAR)
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()


def _sorted_by_z(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: int(item.get("z_index", 0)))


def _draw_styled_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    bold: bool = False,
    underline: bool = False,
) -> None:
    x, y = int(position[0]), int(position[1])
    if bold:
        draw.text((x + 1, y), text, fill=fill, font=font)
    draw.text((x, y), text, fill=fill, font=font)
    if underline:
        bbox = draw.textbbox((x, y), text, font=font)
        line_y = bbox[3] + 1
        draw.line((bbox[0], line_y, bbox[2], line_y), fill=fill, width=1)


def _marquee_x(base_x: int, box_width: int, text_width: int, speed_px_s: float, gap_px: int = 48) -> int:
    if text_width <= box_width:
        return base_x
    speed = max(8.0, float(speed_px_s))
    cycle = float(text_width + gap_px + box_width)
    phase = (time.time() * speed) % cycle
    return int(round(base_x + box_width - phase))


def _draw_clipped_text(
    canvas: Image.Image,
    *,
    x: int,
    y: int,
    box_width: int,
    box_height: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    bold: bool,
    underline: bool,
    marquee: bool,
    marquee_speed: float,
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    text_width = draw.textbbox((0, 0), text, font=font)[2]
    draw_x = _marquee_x(x, box_width, text_width, marquee_speed) if marquee else x
    _draw_styled_text(draw, (draw_x, y), text, font=font, fill=fill, bold=bold, underline=underline)
    clip_box = (x, y, x + max(1, box_width), y + max(1, box_height))
    clipped = overlay.crop(clip_box)
    canvas.alpha_composite(clipped, (clip_box[0], clip_box[1]))


def _ellipsize_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> str:
    if max_width <= 0:
        return ""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    ellipsis = "..."
    if draw.textbbox((0, 0), ellipsis, font=font)[2] > max_width:
        return ""
    lo = 0
    hi = len(text)
    best = ellipsis
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text[:mid].rstrip() + ellipsis
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _parse_numeric_stat_value(value: str) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _looks_like_percent_source(source: object, value: object) -> bool:
    source_text = str(source or "").strip().lower()
    value_text = str(value or "").strip()
    return (
        "%" in value_text
        or source_text.endswith("_percent")
        or source_text in {
            "cpu_usage_percent",
            "cpu_core_avg_percent",
            "cpu_core_max_percent",
            "gpu_load",
            "mem_percent",
            "disk_percent",
            "vram_percent",
            "volume_percent",
        }
    )


def _coerce_stat_range(item: dict[str, Any], value: object) -> tuple[float, float]:
    min_value = float(item.get("min_value", 0.0))
    max_value = float(item.get("max_value", 100.0))
    if max_value <= min_value:
        return 0.0, 100.0
    # Percent-like sources must remain 0..100. Older themes or manual edits can
    # leave a 0..1 range, which clamps 2%, 9%, 64% to the top/end of the widget.
    if _looks_like_percent_source(item.get("source", ""), value) and max_value <= 1.0:
        return 0.0, 100.0
    return min_value, max_value


def _stat_ratio(numeric_value: float, min_value: float, max_value: float) -> float:
    span = max_value - min_value
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (float(numeric_value) - min_value) / span))


_GAUGE_ANGLE_SMOOTH: dict[str, float] = {}
_SPARKLINE_HISTORY: dict[str, list[float]] = {}


def _lerp_channel(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _lerp_rgba(
    ca: tuple[int, int, int, int],
    cb: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        _lerp_channel(ca[0], cb[0], t),
        _lerp_channel(ca[1], cb[1], t),
        _lerp_channel(ca[2], cb[2], t),
        _lerp_channel(ca[3], cb[3], t),
    )


def _gauge_arc_fill(item: dict[str, Any], ratio: float) -> tuple[int, int, int, int]:
    low = item.get("gauge_color_low")
    mid = item.get("gauge_color_mid")
    high = item.get("gauge_color_high")
    if not low or not high:
        return _rgba(item.get("fill_color", item["value_color"]))
    lo = _rgba(low)
    hi = _rgba(high)
    r = max(0.0, min(1.0, ratio))
    if mid:
        md = _rgba(mid)
        if r <= 0.5:
            return _lerp_rgba(lo, md, r * 2.0)
        return _lerp_rgba(md, hi, (r - 0.5) * 2.0)
    return _lerp_rgba(lo, hi, r)


def _smooth_gauge_ratio(cache_key: str, target_ratio: float, factor: float) -> float:
    t = max(0.0, min(1.0, target_ratio))
    prev = _GAUGE_ANGLE_SMOOTH.get(cache_key, t)
    delta = abs(t - prev)
    adapt = min(1.0, max(factor, factor + delta * 0.9))
    blended = prev + (t - prev) * adapt
    _GAUGE_ANGLE_SMOOTH[cache_key] = blended
    return max(0.0, min(1.0, blended))


def _update_sparkline_history(cache_key: str, value: float, limit: int) -> list[float]:
    points = max(8, min(240, int(limit)))
    history = _SPARKLINE_HISTORY.setdefault(cache_key, [])
    history.append(float(value))
    if len(history) > points:
        del history[: len(history) - points]
    return history[:]


def _draw_stat_progress(
    canvas: Image.Image,
    item: dict[str, Any],
    *,
    label: str,
    value_text: str,
    numeric_value: float,
    min_value: float,
    max_value: float,
    label_fill: tuple[int, int, int, int],
    value_fill: tuple[int, int, int, int],
    track_fill: tuple[int, int, int, int],
    fill_color: tuple[int, int, int, int],
) -> None:
    draw = ImageDraw.Draw(canvas)
    font = _load_font(
        int(item["font_size"]),
        bold=bool(item.get("font_bold", False)),
        italic=bool(item.get("font_italic", False)),
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )
    x = int(item["x"])
    y = int(item["y"])
    box_width = max(1, int(item.get("box_width", 320)))
    box_height = max(1, int(item.get("box_height", 40)))
    label_height = 0
    if label:
        _draw_styled_text(
            draw,
            (x, y),
            label,
            font=font,
            fill=label_fill,
            bold=bool(item.get("font_bold", False)),
            underline=bool(item.get("font_underline", False)),
        )
        label_bbox = draw.textbbox((0, 0), label, font=font)
        label_height = (label_bbox[3] - label_bbox[1]) + 6
    bar_left = x
    bar_top = y + label_height
    bar_width = box_width
    bar_height = max(10, min(24, box_height - label_height))
    radius = max(5, min(12, bar_height // 2))
    draw.rounded_rectangle((bar_left, bar_top, bar_left + bar_width, bar_top + bar_height), radius=radius, fill=track_fill)
    ratio = _stat_ratio(numeric_value, min_value, max_value)
    fill_width = int(round(bar_width * ratio))
    if fill_width > 0:
        draw.rounded_rectangle(
            (bar_left, bar_top, bar_left + fill_width, bar_top + bar_height),
            radius=radius,
            fill=fill_color,
        )
    if bool(item.get("show_value_text", True)):
        value_bbox = draw.textbbox((0, 0), value_text, font=font)
        value_x = bar_left + max(0, (bar_width - (value_bbox[2] - value_bbox[0])) // 2)
        value_y = bar_top + max(0, (bar_height - (value_bbox[3] - value_bbox[1])) // 2) - 1
        _draw_styled_text(
            draw,
            (value_x, value_y),
            value_text,
            font=font,
            fill=value_fill,
            bold=bool(item.get("font_bold", False)),
            underline=False,
        )


def _normalize_gauge_value_layout(item: dict[str, Any]) -> str:
    raw = str(item.get("gauge_value_layout", "center")).strip().lower()
    aliases = {
        "inside": "center",
        "middle": "center",
        "srodek": "center",
        "below": "below",
        "bottom": "below",
        "dol": "below",
        "pod": "below",
        "spod": "below",
        "beside": "beside",
        "side": "beside",
        "right": "beside",
        "bok": "beside",
    }
    v = aliases.get(raw, raw)
    return v if v in {"center", "below", "beside"} else "center"


def _paint_gauge_disk(
    draw: ImageDraw.ImageDraw,
    item: dict[str, Any],
    gauge_left: int,
    gauge_top: int,
    gauge_size: int,
    *,
    track_fill: tuple[int, int, int, int],
    arc_fill: tuple[int, int, int, int],
    display_ratio: float,
) -> None:
    outer_pad = max(3, int(round(gauge_size * 0.028)))
    _max_pad = max(1, gauge_size // 2 - 2)
    outer_pad = min(outer_pad, _max_pad)
    ring_box = (
        gauge_left + outer_pad,
        gauge_top + outer_pad,
        gauge_left + gauge_size - outer_pad,
        gauge_top + gauge_size - outer_pad,
    )
    sw_cfg = int(item.get("stroke_width", 12))
    if sw_cfg <= 0:
        stroke_width = max(10, min(42, int(round(gauge_size * 0.145))))
    else:
        stroke_width = max(4, min(48, sw_cfg))

    start_angle = 132
    sweep = 276
    outer_ring_color = (
        min(255, track_fill[0] + 12),
        min(255, track_fill[1] + 12),
        min(255, track_fill[2] + 12),
        max(0, min(255, int(track_fill[3] * 0.38))),
    )
    inner_face_color = (
        max(0, track_fill[0] - 18),
        max(0, track_fill[1] - 18),
        max(0, track_fill[2] - 18),
        max(0, min(255, int(track_fill[3] * 0.52))),
    )
    ia = float(item.get("gauge_inner_alpha", 1.0))
    ia = max(0.0, min(1.0, ia))
    inner_face_color = (
        inner_face_color[0],
        inner_face_color[1],
        inner_face_color[2],
        max(0, min(255, int(round(inner_face_color[3] * ia)))),
    )
    draw.ellipse(
        (
            gauge_left + 1,
            gauge_top + 1,
            gauge_left + gauge_size - 1,
            gauge_top + gauge_size - 1,
        ),
        outline=outer_ring_color,
        width=max(1, int(round(stroke_width * 0.35))),
    )
    draw.arc(ring_box, start=start_angle, end=start_angle + sweep, fill=track_fill, width=stroke_width)
    span_check = max(0.0, min(1.0, display_ratio))
    if span_check > 0.0:
        end_angle = start_angle + int(round(sweep * span_check))
        draw.arc(
            ring_box,
            start=start_angle,
            end=end_angle,
            fill=arc_fill,
            width=stroke_width,
        )
        end_radians = math.radians(end_angle - 90)
        ring_radius = (ring_box[2] - ring_box[0]) / 2.0
        cx = (ring_box[0] + ring_box[2]) / 2.0
        cy = (ring_box[1] + ring_box[3]) / 2.0
        end_x = cx + ring_radius * math.cos(end_radians)
        end_y = cy + ring_radius * math.sin(end_radians)
        cap_r = max(4, int(round(stroke_width * 0.42)))
        draw.ellipse((end_x - cap_r, end_y - cap_r, end_x + cap_r, end_y + cap_r), fill=arc_fill)
    inner_margin = int(stroke_width * 1.05) + max(4, int(round(gauge_size * 0.04)))
    _half_cap = max(0, gauge_size // 2 - 3)
    inner_margin = max(0, min(inner_margin, _half_cap))
    inner_box = (
        gauge_left + inner_margin,
        gauge_top + inner_margin,
        gauge_left + gauge_size - inner_margin,
        gauge_top + gauge_size - inner_margin,
    )
    if inner_box[2] > inner_box[0] and inner_box[3] > inner_box[1]:
        draw.ellipse(inner_box, fill=inner_face_color)


def _draw_stat_gauge(
    canvas: Image.Image,
    item: dict[str, Any],
    *,
    label: str,
    value_text: str,
    min_value: float,
    max_value: float,
    label_fill: tuple[int, int, int, int],
    value_fill: tuple[int, int, int, int],
    track_fill: tuple[int, int, int, int],
    display_ratio: float,
    arc_fill: tuple[int, int, int, int],
) -> None:
    draw = ImageDraw.Draw(canvas)
    layout = _normalize_gauge_value_layout(item)
    base_font_size = int(item["font_size"])
    x = int(item["x"])
    y = int(item["y"])
    box_width = max(1, int(item.get("box_width", 320)))
    box_height = max(1, int(item.get("box_height", 40)))
    pad = max(2, int(round(min(box_width, box_height) * 0.025)))
    inner_w = max(1, box_width - 2 * pad)
    inner_h = max(1, box_height - 2 * pad)
    avail = min(inner_w, inner_h)

    ring_opt = item.get("gauge_ring_size")
    if ring_opt is not None:
        gauge_size = max(40, min(int(ring_opt), avail))
    else:
        gauge_size = max(40, avail)

    scale_ref = max(gauge_size, 72) / 120.0
    value_font = _load_font(
        max(15, int(round(base_font_size * (1.38 + 0.12 * min(scale_ref, 1.4))))),
        bold=True,
        italic=False,
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )
    label_font = _load_font(
        max(10, int(round(base_font_size * (0.74 * min(1.1, scale_ref))))),
        bold=False,
        italic=False,
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )

    span = max_value - min_value
    ratio = 0.0 if span <= 0 else max(0.0, min(1.0, display_ratio))

    if layout == "center":
        gauge_left = x + pad + max(0, (inner_w - gauge_size) // 2)
        gauge_top = y + pad + max(0, (inner_h - gauge_size) // 2)
        _paint_gauge_disk(draw, item, gauge_left, gauge_top, gauge_size, track_fill=track_fill, arc_fill=arc_fill, display_ratio=ratio)
        if bool(item.get("show_value_text", True)):
            value_bbox = draw.textbbox((0, 0), value_text, font=value_font)
            value_x = gauge_left + max(0, (gauge_size - (value_bbox[2] - value_bbox[0])) // 2)
            value_y = gauge_top + max(0, int(gauge_size * 0.34) - (value_bbox[3] - value_bbox[1]) // 2)
            _draw_styled_text(
                draw,
                (value_x, value_y),
                value_text,
                font=value_font,
                fill=value_fill,
                bold=True,
                underline=False,
            )
        if label:
            label_bbox = draw.textbbox((0, 0), label, font=label_font)
            label_x = gauge_left + max(0, (gauge_size - (label_bbox[2] - label_bbox[0])) // 2)
            label_y = gauge_top + int(gauge_size * 0.675)
            _draw_styled_text(
                draw,
                (label_x, label_y),
                label,
                font=label_font,
                fill=label_fill,
                bold=False,
                underline=False,
            )
        return

    if layout == "below":
        gap = max(4, int(round(gauge_size * 0.04)))
        label_h = 0
        if label:
            lb = draw.textbbox((0, 0), label, font=label_font)
            label_h = (lb[3] - lb[1]) + gap
        vb = draw.textbbox((0, 0), value_text, font=value_font)
        value_h = (vb[3] - vb[1]) + gap if bool(item.get("show_value_text", True)) else 0
        reserve_bottom = label_h + value_h + gap
        max_ring = inner_h - reserve_bottom
        gauge_size = min(gauge_size, max_ring, inner_w)
        gauge_size = max(40, gauge_size)
        gauge_left = x + pad + max(0, (inner_w - gauge_size) // 2)
        cursor_y = y + pad
        if label:
            lb = draw.textbbox((0, 0), label, font=label_font)
            lx = x + pad + max(0, (inner_w - (lb[2] - lb[0])) // 2)
            _draw_styled_text(draw, (lx, cursor_y), label, font=label_font, fill=label_fill, bold=False, underline=False)
            cursor_y += (lb[3] - lb[1]) + gap
        gauge_top = cursor_y
        _paint_gauge_disk(draw, item, gauge_left, gauge_top, gauge_size, track_fill=track_fill, arc_fill=arc_fill, display_ratio=ratio)
        cursor_y = gauge_top + gauge_size + gap
        if bool(item.get("show_value_text", True)):
            vb = draw.textbbox((0, 0), value_text, font=value_font)
            vx = x + pad + max(0, (inner_w - (vb[2] - vb[0])) // 2)
            _draw_styled_text(draw, (vx, cursor_y), value_text, font=value_font, fill=value_fill, bold=True, underline=False)
        return

    # beside — pierścień po lewej, wartość i ewentualna etykieta w kolumnie po prawej
    gap = max(6, int(round(gauge_size * 0.05)))
    text_col_w = inner_w - gauge_size - gap
    if text_col_w < 72:
        gauge_size = max(40, inner_w - gap - 72)
        text_col_w = inner_w - gauge_size - gap
    gauge_left = x + pad
    gauge_top = y + pad + max(0, (inner_h - gauge_size) // 2)
    _paint_gauge_disk(draw, item, gauge_left, gauge_top, gauge_size, track_fill=track_fill, arc_fill=arc_fill, display_ratio=ratio)
    tx = gauge_left + gauge_size + gap
    ty = y + pad
    stack_h = 0
    if label:
        lb = draw.textbbox((0, 0), label, font=label_font)
        stack_h += lb[3] - lb[1]
    if bool(item.get("show_value_text", True)):
        vb = draw.textbbox((0, 0), value_text, font=value_font)
        stack_h += (vb[3] - vb[1]) + (gap // 2 if label else 0)
    ty = y + pad + max(0, (inner_h - stack_h) // 2)
    if label:
        lb = draw.textbbox((0, 0), label, font=label_font)
        _draw_styled_text(draw, (tx, ty), label, font=label_font, fill=label_fill, bold=False, underline=False)
        ty += (lb[3] - lb[1]) + gap // 2
    if bool(item.get("show_value_text", True)):
        _draw_styled_text(draw, (tx, ty), value_text, font=value_font, fill=value_fill, bold=True, underline=False)


def _draw_stat_sparkline(
    canvas: Image.Image,
    item: dict[str, Any],
    *,
    label: str,
    value_text: str,
    history: list[float],
    min_value: float,
    max_value: float,
    label_fill: tuple[int, int, int, int],
    value_fill: tuple[int, int, int, int],
    track_fill: tuple[int, int, int, int],
    fill_color: tuple[int, int, int, int],
) -> None:
    draw = ImageDraw.Draw(canvas)
    x = int(item["x"])
    y = int(item["y"])
    box_width = max(1, int(item.get("box_width", 320)))
    box_height = max(1, int(item.get("box_height", 72)))
    pad_x = max(6, int(round(box_width * 0.03)))
    pad_y = max(4, int(round(box_height * 0.08)))
    header_gap = max(4, int(round(box_height * 0.05)))
    line_width = max(1, int(item.get("stroke_width", 3) or 3))
    show_value = bool(item.get("show_value_text", True))
    show_points = bool(item.get("sparkline_show_points", True))
    fill_opacity = max(0.0, min(1.0, float(item.get("sparkline_fill_opacity", 0.18))))
    font_size = int(item.get("font_size", 22))
    header_font = _load_font(
        max(10, int(round(font_size * 0.58))),
        bold=False,
        italic=False,
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )
    value_font = _load_font(
        max(12, int(round(font_size * 0.86))),
        bold=True,
        italic=False,
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )

    header_h = 0
    if label or show_value:
        header_h = max(
            (draw.textbbox((0, 0), label, font=header_font)[3] if label else 0),
            (draw.textbbox((0, 0), value_text, font=value_font)[3] if show_value else 0),
        )
    plot_left = x + pad_x
    plot_top = y + pad_y + (header_h + header_gap if header_h else 0)
    plot_right = x + box_width - pad_x
    plot_bottom = y + box_height - pad_y
    if plot_bottom <= plot_top:
        plot_bottom = plot_top + 1
    if plot_right <= plot_left:
        plot_right = plot_left + 1

    if track_fill[3] > 0:
        draw.rounded_rectangle(
            (x, y, x + box_width, y + box_height),
            radius=max(8, int(round(min(box_width, box_height) * 0.1))),
            fill=track_fill,
        )

    if label:
        _draw_styled_text(
            draw,
            (plot_left, y + pad_y),
            label,
            font=header_font,
            fill=label_fill,
            bold=False,
            underline=False,
        )
    if show_value:
        vb = draw.textbbox((0, 0), value_text, font=value_font)
        vx = plot_right - (vb[2] - vb[0])
        _draw_styled_text(
            draw,
            (vx, y + pad_y),
            value_text,
            font=value_font,
            fill=value_fill,
            bold=True,
            underline=False,
        )

    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=(track_fill[0], track_fill[1], track_fill[2], max(60, track_fill[3])), width=1)

    if not history:
        return
    normalized: list[tuple[float, float]] = []
    count = max(1, len(history))
    for idx, raw in enumerate(history):
        ratio = _stat_ratio(raw, min_value, max_value)
        px = plot_left if count == 1 else plot_left + ((plot_right - plot_left) * idx / (count - 1))
        py = plot_bottom - ratio * max(1, plot_bottom - plot_top)
        normalized.append((px, py))

    if len(normalized) >= 2 and fill_opacity > 0.0:
        fill_rgba = (
            fill_color[0],
            fill_color[1],
            fill_color[2],
            max(0, min(255, int(round(fill_color[3] * fill_opacity)))),
        )
        poly = [(normalized[0][0], plot_bottom), *normalized, (normalized[-1][0], plot_bottom)]
        draw.polygon(poly, fill=fill_rgba)

    if len(normalized) == 1:
        px, py = normalized[0]
        draw.line((plot_left, py, plot_right, py), fill=fill_color, width=line_width)
    else:
        draw.line(normalized, fill=fill_color, width=line_width)

    if show_points and normalized:
        end_x, end_y = normalized[-1]
        dot_r = max(2, line_width + 1)
        draw.ellipse((end_x - dot_r, end_y - dot_r, end_x + dot_r, end_y + dot_r), fill=value_fill)


def _resampled_audio_eq_levels(snapshot: dict[str, str], count: int) -> list[float]:
    raw = snapshot.get("audio_eq_bars")
    if not raw:
        return []
    try:
        age_ms = int(float(str(snapshot.get("audio_eq_age_ms", "0") or "0")))
    except (TypeError, ValueError):
        age_ms = 0
    if age_ms > 750:
        return []
    try:
        parsed = json.loads(str(raw))
    except Exception:
        parsed = []
    if not isinstance(parsed, list):
        return []
    levels: list[float] = []
    for value in parsed:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        levels.append(max(0.0, min(1.0, number)))
    if not levels:
        return []
    target = max(1, int(count))
    if len(levels) == target:
        return levels
    if target == 1:
        return [max(levels)]
    if len(levels) == 1:
        return [levels[0]] * target
    out: list[float] = []
    for idx in range(target):
        pos = (idx / float(target - 1)) * (len(levels) - 1)
        left = int(math.floor(pos))
        right = min(len(levels) - 1, left + 1)
        frac = pos - left
        out.append(levels[left] * (1.0 - frac) + levels[right] * frac)
    return out


def _draw_stat_equalizer(
    canvas: Image.Image,
    item: dict[str, Any],
    *,
    label: str,
    value_text: str,
    numeric_value: float,
    min_value: float,
    max_value: float,
    label_fill: tuple[int, int, int, int],
    value_fill: tuple[int, int, int, int],
    track_fill: tuple[int, int, int, int],
    fill_color: tuple[int, int, int, int],
    snapshot: dict[str, str],
) -> None:
    draw = ImageDraw.Draw(canvas)
    x = int(item["x"])
    y = int(item["y"])
    box_width = max(1, int(item.get("box_width", 360)))
    box_height = max(1, int(item.get("box_height", 88)))
    pad_x = max(6, int(round(box_width * 0.03)))
    pad_y = max(5, int(round(box_height * 0.08)))
    bars = max(6, min(64, int(item.get("equalizer_bars", 18) or 18)))
    gap = max(0, min(16, int(item.get("equalizer_gap", 4) or 4)))
    mirror = bool(item.get("equalizer_mirror", False))
    show_value = bool(item.get("show_value_text", True))
    font_size = int(item.get("font_size", 22))
    header_font = _load_font(
        max(10, int(round(font_size * 0.56))),
        bold=False,
        italic=False,
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )
    value_font = _load_font(
        max(12, int(round(font_size * 0.82))),
        bold=True,
        italic=False,
        font_family=str(item.get("font_family", "DejaVu Sans")),
    )
    header_h = 0
    if label or show_value:
        header_h = max(
            (draw.textbbox((0, 0), label, font=header_font)[3] if label else 0),
            (draw.textbbox((0, 0), value_text, font=value_font)[3] if show_value else 0),
        )
    plot_left = x + pad_x
    plot_top = y + pad_y + (header_h + max(3, pad_y // 2) if header_h else 0)
    plot_right = x + box_width - pad_x
    plot_bottom = y + box_height - pad_y
    if track_fill[3] > 0:
        draw.rounded_rectangle(
            (x, y, x + box_width, y + box_height),
            radius=max(8, int(round(min(box_width, box_height) * 0.1))),
            fill=track_fill,
        )
    if label:
        _draw_styled_text(draw, (plot_left, y + pad_y), label, font=header_font, fill=label_fill, bold=False, underline=False)
    if show_value:
        vb = draw.textbbox((0, 0), value_text, font=value_font)
        vx = plot_right - (vb[2] - vb[0])
        _draw_styled_text(draw, (vx, y + pad_y), value_text, font=value_font, fill=value_fill, bold=True, underline=False)
    ratio = _stat_ratio(numeric_value, min_value, max_value)
    media_state = str(snapshot.get("media_state", "")).strip().lower()
    is_playing = media_state == "playing"
    is_paused = media_state == "paused"
    content_w = max(1, plot_right - plot_left)
    plot_h = max(8, plot_bottom - plot_top)
    bar_width = max(3, (content_w - gap * (bars - 1)) // bars)
    total_w = bar_width * bars + gap * (bars - 1)
    start_x = plot_left + max(0, (content_w - total_w) // 2)
    mid_y = plot_top + plot_h / 2.0
    live_levels = _resampled_audio_eq_levels(snapshot, bars)
    seed = (sum(ord(ch) for ch in str(item.get("id", "eq"))) % 31) / 7.0
    phase_t = time.time() * (3.6 if is_playing else 1.2)
    for idx in range(bars):
        px = start_x + idx * (bar_width + gap)
        if live_levels:
            level = live_levels[idx]
            if is_paused:
                level = min(0.34, level * 0.35)
            elif not is_playing:
                level = min(0.16, level * 0.16)
        else:
            phase = phase_t + seed + idx * 0.63
            slow = (math.sin(phase) + 1.0) * 0.5
            fast = (math.sin(phase * 1.93 + 0.7) + 1.0) * 0.5
            pulse = (math.sin(phase * 0.47 + 1.8) + 1.0) * 0.5
            combined = slow * 0.46 + fast * 0.36 + pulse * 0.18
            weight = 0.62 + 0.38 * math.sin(((idx + 1) / float(bars + 1)) * math.pi)
            if is_playing:
                level = min(1.0, 0.10 + combined * ((0.28 + ratio * 0.64) * weight))
            elif is_paused:
                level = min(0.34, 0.05 + combined * 0.16 * weight)
            else:
                level = 0.06 + combined * 0.06 * weight
        bar_fill = _lerp_rgba(fill_color, value_fill, max(0.0, min(1.0, level)) * 0.72)
        if mirror:
            half_h = max(2, int(round((plot_h * 0.48) * level)))
            top = int(round(mid_y - half_h))
            bottom = int(round(mid_y + half_h))
        else:
            bar_h = max(3, int(round((plot_h - 2) * level)))
            top = plot_bottom - bar_h
            bottom = plot_bottom
        draw.rounded_rectangle(
            (px, top, px + bar_width, bottom),
            radius=max(2, min(6, bar_width // 2)),
            fill=bar_fill,
        )


def _motion_progress(track: dict[str, Any], frame_index: int) -> float:
    start = int(track.get("frame_start", 0))
    end = int(track.get("frame_end", start))
    if frame_index <= start:
        return 0.0
    if end <= start:
        return 1.0
    if frame_index >= end:
        return 1.0
    return max(0.0, min(1.0, (frame_index - start) / float(end - start)))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _apply_motion_tracks(theme: ThemeDocument) -> ThemeDocument:
    effects = theme.data.get("effects", {})
    tracks = effects.get("motion_tracks", [])
    if not isinstance(tracks, list) or not tracks:
        return theme
    animation = effects.get("animation", {})
    frame_index = int(animation.get("current_frame", 0)) if isinstance(animation, dict) else 0
    data = deepcopy(theme.data)
    indexed: dict[str, dict[str, Any]] = {}
    for key in ("texts", "stats", "images", "widgets"):
        for item in data.get(key, []):
            if isinstance(item, dict):
                indexed[str(item.get("id", "")).strip()] = item
    background = data.get("background", {})
    if isinstance(background, dict):
        for item in background.get("panels", []):
            if isinstance(item, dict):
                indexed[str(item.get("id", "")).strip()] = item
    for track in tracks:
        if not isinstance(track, dict):
            continue
        item_id = str(track.get("item_id", "")).strip()
        if not item_id:
            continue
        item = indexed.get(item_id)
        if item is None:
            continue
        progress = _motion_progress(track, frame_index)
        if progress <= 0.0 and frame_index < int(track.get("frame_start", 0)):
            continue
        base_x = int(item.get("x", item.get("rect", [0, 0, 1, 1])[0]))
        base_y = int(item.get("y", item.get("rect", [0, 0, 1, 1])[1]))
        base_opacity = float(item.get("opacity", 1.0))
        x_to = int(track.get("x_to", base_x))
        y_to = int(track.get("y_to", base_y))
        opacity_to = float(track.get("opacity_to", base_opacity))
        new_x = int(round(_lerp(base_x, x_to, progress)))
        new_y = int(round(_lerp(base_y, y_to, progress)))
        new_opacity = max(0.0, min(1.0, _lerp(base_opacity, opacity_to, progress)))
        if "rect" in item and isinstance(item.get("rect"), list) and len(item["rect"]) >= 4:
            item["rect"][0] = new_x
            item["rect"][1] = new_y
        else:
            item["x"] = new_x
            item["y"] = new_y
        item["_render_opacity"] = new_opacity
        if "opacity" in item:
            item["opacity"] = new_opacity
    return ThemeDocument(data)


def _fit_image(src: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    if fit == "stretch":
        return src.resize((width, height), Image.LANCZOS)

    src_w, src_h = src.size
    if src_w <= 0 or src_h <= 0:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))

    ratio_x = width / src_w
    ratio_y = height / src_h
    scale = min(ratio_x, ratio_y) if fit == "contain" else max(ratio_x, ratio_y)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    resized = src.resize((new_w, new_h), Image.LANCZOS)

    if fit == "cover":
        left = max(0, (new_w - width) // 2)
        top = max(0, (new_h - height) // 2)
        return resized.crop((left, top, left + width, top + height))

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    paste_x = (width - new_w) // 2
    paste_y = (height - new_h) // 2
    canvas.alpha_composite(resized, (paste_x, paste_y))
    return canvas


def _apply_crop_box(src: Image.Image, crop_box: list[float] | tuple[float, float, float, float] | None) -> Image.Image:
    if not crop_box or len(crop_box) != 4:
        return src
    try:
        left_n, top_n, right_n, bottom_n = [float(v) for v in crop_box]
    except Exception:
        return src
    src_w, src_h = src.size
    left = max(0, min(src_w - 1, int(round(left_n * src_w))))
    top = max(0, min(src_h - 1, int(round(top_n * src_h))))
    right = max(left + 1, min(src_w, int(round(right_n * src_w))))
    bottom = max(top + 1, min(src_h, int(round(bottom_n * src_h))))
    return src.crop((left, top, right, bottom))


def _apply_rounded_alpha(image: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return image
    rounded = image.copy()
    mask = Image.new("L", rounded.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, rounded.width, rounded.height), radius=max(0, int(radius)), fill=255)
    alpha = rounded.getchannel("A")
    rounded.putalpha(ImageChops.multiply(alpha, mask))
    return rounded


def _draw_image_glow(canvas: Image.Image, image: Image.Image, x: int, y: int, radius: int, opacity: float) -> None:
    if radius <= 0 or opacity <= 0.0:
        return
    pad = max(1, int(radius) * 2)
    glow = Image.new("RGBA", (image.width + pad * 2, image.height + pad * 2), (0, 0, 0, 0))
    glow.alpha_composite(image, (pad, pad))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=radius))
    if opacity < 1.0:
        alpha = glow.getchannel("A")
        alpha = alpha.point(lambda v: int(v * opacity))
        glow.putalpha(alpha)
    canvas.alpha_composite(glow, (x - pad, y - pad))


def _draw_image_border(image: Image.Image, radius: int, width: int, color: tuple[int, int, int, int]) -> Image.Image:
    if width <= 0 or color[3] <= 0:
        return image
    bordered = image.copy()
    border = Image.new("RGBA", bordered.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(border)
    inset = max(0, width // 2)
    draw.rounded_rectangle(
        (inset, inset, max(inset, bordered.width - inset - 1), max(inset, bordered.height - inset - 1)),
        radius=max(0, int(radius)),
        outline=color,
        width=width,
    )
    bordered.alpha_composite(border)
    return bordered


def _analog_clock_palette(item: dict[str, Any]) -> dict[str, tuple[int, int, int, int]]:
    style = str(item.get("clock_style", "classic")).strip().lower()
    palettes = {
        "classic": {
            "face": (18, 24, 36, 230),
            "tick": (224, 232, 244, 220),
            "hand": (245, 248, 252, 255),
            "second": (255, 96, 96, 255),
            "center": (250, 250, 252, 255),
        },
        "modern": {
            "face": (8, 16, 28, 210),
            "tick": (86, 214, 255, 235),
            "hand": (235, 245, 255, 255),
            "second": (103, 255, 211, 255),
            "center": (240, 248, 255, 255),
        },
        "nordic": {
            "face": (20, 24, 30, 222),
            "tick": (215, 225, 232, 215),
            "hand": (244, 240, 232, 255),
            "second": (196, 162, 108, 255),
            "center": (252, 248, 242, 255),
        },
    }
    base = palettes.get(style, palettes["classic"])
    return {
        "face": _rgba(item.get("clock_face_color", list(base["face"]))),
        "tick": _rgba(item.get("clock_tick_color", list(base["tick"]))),
        "hand": _rgba(item.get("clock_hand_color", list(base["hand"]))),
        "second": _rgba(item.get("clock_second_color", list(base["second"]))),
        "center": _rgba(item.get("clock_center_color", list(base["center"]))),
    }


def _render_analog_clock(item: dict[str, Any], snapshot: dict[str, str], width: int, height: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    palette = _analog_clock_palette(item)
    size = max(24, min(width, height))
    pad = max(4, int(size * 0.07))
    left = (width - size) // 2
    top = (height - size) // 2
    box = (left + pad, top + pad, left + size - pad, top + size - pad)
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    radius = max(10.0, (box[2] - box[0]) / 2.0)
    draw.ellipse(box, fill=palette["face"])

    style = str(item.get("clock_style", "classic")).strip().lower()
    tick_outer = radius - max(2.0, size * 0.04)
    tick_inner_major = tick_outer - max(8.0, size * 0.12)
    tick_inner_minor = tick_outer - max(4.0, size * 0.06)
    tick_width_major = max(2, int(round(size * 0.016)))
    tick_width_minor = max(1, int(round(size * 0.008)))
    if style == "modern":
        tick_inner_major = tick_outer - max(10.0, size * 0.16)
        tick_inner_minor = tick_outer - max(2.0, size * 0.03)
    elif style == "nordic":
        tick_inner_major = tick_outer - max(7.0, size * 0.10)
        tick_inner_minor = tick_outer - max(3.0, size * 0.05)

    for idx in range(60):
        angle = (idx / 60.0) * 360.0
        radians = ((angle - 90.0) * 3.141592653589793) / 180.0
        outer_x = cx + tick_outer * math.cos(radians)
        outer_y = cy + tick_outer * math.sin(radians)
        if idx % 5 == 0:
            inner = tick_inner_major
            width_px = tick_width_major
        else:
            inner = tick_inner_minor
            width_px = tick_width_minor
        inner_x = cx + inner * math.cos(radians)
        inner_y = cy + inner * math.sin(radians)
        draw.line((inner_x, inner_y, outer_x, outer_y), fill=palette["tick"], width=width_px)

    time_text = str(snapshot.get("time_hms", "")).strip()
    try:
        parts = [int(part) for part in time_text.split(":")[:3]]
        while len(parts) < 3:
            parts.append(0)
        hour, minute, second = parts[0], parts[1], parts[2]
    except Exception:
        local_now = time.localtime()
        hour, minute, second = local_now.tm_hour, local_now.tm_min, local_now.tm_sec

    hour_angle = ((hour % 12) + (minute / 60.0) + (second / 3600.0)) * 30.0
    minute_angle = (minute + (second / 60.0)) * 6.0
    second_angle = second * 6.0

    def _hand(angle_deg: float, length: float, width_px: int, fill: tuple[int, int, int, int]) -> None:
        radians = ((angle_deg - 90.0) * 3.141592653589793) / 180.0
        hand_x = cx + length * math.cos(radians)
        hand_y = cy + length * math.sin(radians)
        draw.line((cx, cy, hand_x, hand_y), fill=fill, width=width_px)

    _hand(hour_angle, radius * 0.5, max(3, int(round(size * 0.026))), palette["hand"])
    _hand(minute_angle, radius * 0.72, max(2, int(round(size * 0.018))), palette["hand"])
    if bool(item.get("clock_show_second_hand", True)):
        _hand(second_angle, radius * 0.78, max(1, int(round(size * 0.010))), palette["second"])
    center_r = max(3, int(round(size * 0.03)))
    draw.ellipse((cx - center_r, cy - center_r, cx + center_r, cy + center_r), fill=palette["center"])
    return image


def render_generated_background(canvas_size: tuple[int, int], background: dict[str, Any]) -> Image.Image:
    width, height = canvas_size
    base = background["base_color"]
    accent = background["accent_color"]
    texture_alpha = float(background["texture_alpha"])

    img = Image.new("RGBA", (width, height), (*base[:3], 255))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / max(1, height - 1)
        r = int(base[0] + (accent[0] - base[0]) * t)
        g = int(base[1] + (accent[1] - base[1]) * t)
        b = int(base[2] + (accent[2] - base[2]) * t)
        draw.line((0, y, width, y), fill=(r, g, b, 255))

    for x in range(0, width, 120):
        draw.rectangle((x, 0, min(width, x + 2), height), fill=(18, 28, 40, 255))
    for y in range(24, height, 48):
        draw.line((24, y, width - 24, y), fill=(20, 34, 48, 255), width=1)

    for panel in _sorted_by_z(background["panels"]):
        if not bool(panel.get("visible", True)):
            continue
        x, y, w, h = panel["rect"]
        fill = list(_rgba(panel["fill"]))
        base_opacity = max(0.0, min(1.0, float(panel.get("opacity", 1.0))))
        render_opacity = max(0.0, min(1.0, float(panel.get("_render_opacity", 1.0))))
        fill[3] = int(fill[3] * base_opacity * render_opacity)
        draw.rounded_rectangle((x, y, x + w, y + h), radius=panel["radius"], fill=tuple(fill))

    texture = Image.effect_noise((width, height), 22).convert("L")
    texture = texture.filter(ImageFilter.GaussianBlur(radius=1.2))
    texture_rgb = Image.new("RGBA", (width, height))
    src = texture.load()
    dst = texture_rgb.load()
    for y in range(height):
        for x in range(width):
            v = src[x, y]
            dst[x, y] = (10 + v // 10, 16 + v // 9, 24 + v // 8, 255)

    return Image.blend(img, texture_rgb, max(0.0, min(1.0, texture_alpha)))


def render_background(theme: ThemeDocument, base_dir: Path) -> Image.Image:
    canvas = theme.data["canvas"]
    background = theme.data["background"]
    size = (canvas["width"], canvas["height"])
    animation_frame = _animation_frame_path(theme, base_dir)
    if animation_frame is not None and animation_frame.exists():
        src = Image.open(animation_frame).convert("RGBA")
        return _fit_image(src, size[0], size[1], background.get("fit", "cover"))

    if background["kind"] == "generated":
        return render_generated_background(size, background)

    if background["kind"] == "color":
        color = _rgba(background["base_color"])
        return Image.new("RGBA", size, color)

    if background["kind"] == "image":
        src = Image.open(_resolve_asset_path(base_dir, background["path"])).convert("RGBA")
        fitted = _fit_image(src, size[0], size[1], background["fit"])
        opacity = float(background.get("opacity", 1.0))
        if opacity < 1.0:
            alpha = fitted.getchannel("A")
            alpha = alpha.point(lambda v: int(v * opacity))
            fitted.putalpha(alpha)
        return fitted

    return Image.new("RGBA", size, (0, 0, 0, 255))


def render_images(canvas: Image.Image, theme: ThemeDocument, base_dir: Path, snapshot: dict[str, str] | None = None) -> None:
    snapshot = {} if snapshot is None else snapshot
    for item in _sorted_by_z(theme.data["images"]):
        if not bool(item.get("visible", True)):
            continue
        source = str(item.get("source", "")).strip()
        x, y, w, h = item["rect"]
        if source == "analog_clock":
            fitted = _render_analog_clock(item, snapshot, w, h)
        elif source == "weather_icon" or (source.startswith("weather_day_") and source.endswith("_icon")):
            icon_path_key = "weather_icon_path" if source == "weather_icon" else f"{source}_path"
            icon_path = str(snapshot.get(icon_path_key, "")).strip()
            if not icon_path:
                continue
            src_path = _resolve_asset_path(base_dir, icon_path)
            if not src_path.exists():
                continue
            src = Image.open(src_path).convert("RGBA")
            src = _apply_crop_box(src, item.get("crop_box"))
            fitted = _fit_image(src, w, h, item["fit"])
        elif source in {"media_cover", "media_video_frame"}:
            cover_path = ""
            if source == "media_video_frame":
                cover_path = str(snapshot.get("media_video_frame_path", "")).strip() or str(snapshot.get("media_cover_path", "")).strip()
            else:
                cover_path = str(snapshot.get("media_cover_path", "")).strip()
            if not cover_path:
                continue
            src_path = _resolve_asset_path(base_dir, cover_path)
            if not src_path.exists():
                continue
            src = Image.open(src_path).convert("RGBA")
            src = _apply_crop_box(src, item.get("crop_box"))
            fitted = _fit_image(src, w, h, item["fit"])
        else:
            src_path = _resolve_asset_path(base_dir, item["path"])
            if not src_path.exists():
                continue
            src = Image.open(src_path).convert("RGBA")
            src = _apply_crop_box(src, item.get("crop_box"))
            fitted = _fit_image(src, w, h, item["fit"])
        rotation = int(item.get("rotation", 0)) % 360
        if rotation:
            fitted = fitted.rotate(rotation, expand=True, resample=Image.BICUBIC)
        radius = max(0, int(item.get("radius", 0)))
        if radius:
            fitted = _apply_rounded_alpha(fitted, radius)
        opacity = float(item.get("opacity", 1.0))
        if opacity < 1.0:
            alpha = fitted.getchannel("A")
            alpha = alpha.point(lambda v: int(v * opacity))
            fitted.putalpha(alpha)
        glow_radius = max(0, int(item.get("glow_radius", 0)))
        glow_opacity = max(0.0, min(1.0, float(item.get("glow_opacity", 0.0))))
        if glow_radius > 0 and glow_opacity > 0.0:
            _draw_image_glow(canvas, fitted, x, y, glow_radius, glow_opacity)
        border_width = max(0, int(item.get("border_width", 0)))
        if border_width > 0:
            fitted = _draw_image_border(fitted, radius, border_width, _rgba(item.get("border_color", [255, 255, 255, 0])))
        canvas.alpha_composite(fitted, (x, y))


def render_texts(canvas: Image.Image, theme: ThemeDocument) -> None:
    draw = ImageDraw.Draw(canvas)
    for item in _sorted_by_z(theme.data["texts"]):
        if not bool(item.get("visible", True)):
            continue
        font = _load_font(
            int(item["font_size"]),
            bold=bool(item.get("font_bold", int(item["font_size"]) >= 28)),
            italic=bool(item.get("font_italic", False)),
            font_family=str(item.get("font_family", "DejaVu Sans")),
        )
        fill = _rgba(item["color"])
        render_opacity = max(0.0, min(1.0, float(item.get("_render_opacity", 1.0))))
        fill = (fill[0], fill[1], fill[2], int(fill[3] * render_opacity))
        x = int(item["x"])
        y = int(item["y"])
        box_width = max(1, int(item.get("box_width", 320)))
        box_height = max(1, int(item.get("box_height", 48)))
        text = item["text"]
        marquee = bool(item.get("marquee", False))
        if not marquee and item["align"] == "left":
            text = _ellipsize_text(draw, text, font, box_width)
        if item["align"] == "center":
            bbox = draw.textbbox((0, 0), text, font=font)
            width = bbox[2] - bbox[0]
            x += max(0, (box_width - width) // 2)
        elif item["align"] == "right":
            bbox = draw.textbbox((0, 0), text, font=font)
            width = bbox[2] - bbox[0]
            x += max(0, box_width - width)
        if marquee and item["align"] == "left":
            _draw_clipped_text(
                canvas,
                x=x,
                y=y,
                box_width=box_width,
                box_height=box_height,
                text=text,
                font=font,
                fill=fill,
                bold=bool(item.get("font_bold", int(item["font_size"]) >= 28)),
                underline=bool(item.get("font_underline", False)),
                marquee=True,
                marquee_speed=float(item.get("marquee_speed", 55.0)),
            )
        else:
            _draw_styled_text(
                draw,
                (x, y),
                text,
                font=font,
                fill=fill,
                bold=bool(item.get("font_bold", int(item["font_size"]) >= 28)),
                underline=bool(item.get("font_underline", False)),
            )


def render_stats(canvas: Image.Image, theme: ThemeDocument, snapshot: dict[str, str]) -> None:
    draw = ImageDraw.Draw(canvas)
    for item in _sorted_by_z(theme.data["stats"]):
        if not bool(item.get("visible", True)):
            continue
        font = _load_font(
            int(item["font_size"]),
            bold=bool(item.get("font_bold", False)),
            italic=bool(item.get("font_italic", False)),
            font_family=str(item.get("font_family", "DejaVu Sans")),
        )
        render_opacity = max(0.0, min(1.0, float(item.get("_render_opacity", 1.0))))
        label_fill_rgba = _rgba(item["label_color"])
        value_fill_rgba = _rgba(item["value_color"])
        track_fill_rgba = _rgba(item.get("track_color", [34, 44, 58, 210]))
        fill_color_rgba = _rgba(item.get("fill_color", item["value_color"]))
        label_fill = (label_fill_rgba[0], label_fill_rgba[1], label_fill_rgba[2], int(label_fill_rgba[3] * render_opacity))
        value_fill = (value_fill_rgba[0], value_fill_rgba[1], value_fill_rgba[2], int(value_fill_rgba[3] * render_opacity))
        track_fill = (track_fill_rgba[0], track_fill_rgba[1], track_fill_rgba[2], int(track_fill_rgba[3] * render_opacity))
        fill_color = (fill_color_rgba[0], fill_color_rgba[1], fill_color_rgba[2], int(fill_color_rgba[3] * render_opacity))
        x = int(item["x"])
        y = int(item["y"])
        box_width = max(1, int(item.get("box_width", 320)))
        box_height = max(1, int(item.get("box_height", 40)))
        label = item["label"]
        value = snapshot.get(item["source"], "N/A")
        value_text = item["format"].format(value=value)
        display = str(item.get("display", "text")).strip().lower()
        marquee = bool(item.get("marquee", False))
        numeric_value = _parse_numeric_stat_value(value)
        if display in {"progress", "gauge", "sparkline", "equalizer"} and numeric_value is not None:
            min_value, max_value = _coerce_stat_range(item, value)
            if display == "progress":
                _draw_stat_progress(
                    canvas,
                    item,
                    label=label,
                    value_text=value_text,
                    numeric_value=numeric_value,
                    min_value=min_value,
                    max_value=max_value,
                    label_fill=label_fill,
                    value_fill=value_fill,
                    track_fill=track_fill,
                    fill_color=fill_color,
                )
            elif display == "gauge":
                target_ratio = _stat_ratio(numeric_value, min_value, max_value)
                cache_key = f"{item.get('id', 'stat')}::{item.get('source', '')}"
                smooth_f = float(item.get("gauge_smooth", 0.32))
                display_ratio = _smooth_gauge_ratio(cache_key, target_ratio, smooth_f)
                arc_fill_rgba = _gauge_arc_fill(item, display_ratio)
                arc_fill = (
                    arc_fill_rgba[0],
                    arc_fill_rgba[1],
                    arc_fill_rgba[2],
                    int(arc_fill_rgba[3] * render_opacity),
                )
                value_fill_gauge = (
                    arc_fill[0],
                    arc_fill[1],
                    arc_fill[2],
                    arc_fill[3],
                ) if bool(item.get("gauge_match_value_color", True)) else value_fill
                _draw_stat_gauge(
                    canvas,
                    item,
                    label=label,
                    value_text=value_text,
                    min_value=min_value,
                    max_value=max_value,
                    label_fill=label_fill,
                    value_fill=value_fill_gauge,
                    track_fill=track_fill,
                    display_ratio=display_ratio,
                    arc_fill=arc_fill,
                )
            elif display == "sparkline":
                cache_key = f"{item.get('id', 'stat')}::{item.get('source', '')}"
                history = _update_sparkline_history(cache_key, numeric_value, int(item.get("sparkline_points", 42)))
                _draw_stat_sparkline(
                    canvas,
                    item,
                    label=label,
                    value_text=value_text,
                    history=history,
                    min_value=min_value,
                    max_value=max_value,
                    label_fill=label_fill,
                    value_fill=value_fill,
                    track_fill=track_fill,
                    fill_color=fill_color,
                )
            else:
                _draw_stat_equalizer(
                    canvas,
                    item,
                    label=label,
                    value_text=value_text,
                    numeric_value=numeric_value,
                    min_value=min_value,
                    max_value=max_value,
                    label_fill=label_fill,
                    value_fill=value_fill,
                    track_fill=track_fill,
                    fill_color=fill_color,
                    snapshot=snapshot,
                )
            continue
        if not marquee and not label and item["align"] == "left":
            value_text = _ellipsize_text(draw, value_text, font, box_width)

        if label:
            label_text = f"{label}: "
            label_bbox = draw.textbbox((0, 0), label_text, font=font)
            label_width = label_bbox[2] - label_bbox[0]
            value_bbox = draw.textbbox((0, 0), value_text, font=font)
            total_width = label_width + (value_bbox[2] - value_bbox[0])
            if item["align"] == "center":
                x += max(0, (box_width - total_width) // 2)
            elif item["align"] == "right":
                x += max(0, box_width - total_width)
            _draw_styled_text(
                draw,
                (x, y),
                label_text,
                font=font,
                fill=label_fill,
                bold=bool(item.get("font_bold", False)),
                underline=bool(item.get("font_underline", False)),
            )
            _draw_styled_text(
                draw,
                (x + label_width, y),
                value_text,
                font=font,
                fill=value_fill,
                bold=bool(item.get("font_bold", False)),
                underline=bool(item.get("font_underline", False)),
            )
        else:
            if item["align"] != "left":
                bbox = draw.textbbox((0, 0), value_text, font=font)
                width = bbox[2] - bbox[0]
                if item["align"] == "center":
                    x += max(0, (box_width - width) // 2)
                elif item["align"] == "right":
                    x += max(0, box_width - width)
            if marquee and item["align"] == "left":
                _draw_clipped_text(
                    canvas,
                    x=x,
                    y=y,
                    box_width=box_width,
                    box_height=box_height,
                    text=value_text,
                    font=font,
                    fill=value_fill,
                    bold=bool(item.get("font_bold", False)),
                    underline=bool(item.get("font_underline", False)),
                    marquee=True,
                    marquee_speed=float(item.get("marquee_speed", 55.0)),
                )
            else:
                _draw_styled_text(
                    draw,
                    (x, y),
                    value_text,
                    font=font,
                    fill=value_fill,
                    bold=bool(item.get("font_bold", False)),
                    underline=bool(item.get("font_underline", False)),
                )


def _scaled_font(size: int, scale: float, *, bold: bool = False, font_family: str = "DejaVu Sans") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font(max(8, int(round(size * scale))), bold=bold, font_family=font_family)


def _draw_widget_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    max_width: int,
) -> None:
    draw.text(xy, _ellipsize_text(draw, str(text or "N/A"), font, max(1, max_width)), font=font, fill=fill)


def _weather_icon_image(source: str, snapshot: dict[str, str], base_dir: Path, size: tuple[int, int]) -> Image.Image | None:
    icon_path_key = "weather_icon_path" if source == "weather_icon" else f"{source}_path"
    icon_path = str(snapshot.get(icon_path_key, "")).strip()
    if not icon_path:
        return None
    src_path = _resolve_asset_path(base_dir, icon_path)
    if not src_path.exists():
        return None
    try:
        stat = src_path.stat()
        cache_key = (str(src_path), int(stat.st_mtime_ns), int(stat.st_size), int(size[0]), int(size[1]))
    except OSError:
        return None
    cached = _WEATHER_ICON_IMAGE_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()
    try:
        with Image.open(src_path) as src:
            fitted = _fit_image(src.convert("RGBA"), size[0], size[1], "contain")
        if len(_WEATHER_ICON_IMAGE_CACHE) > 96:
            _WEATHER_ICON_IMAGE_CACHE.clear()
        _WEATHER_ICON_IMAGE_CACHE[cache_key] = fitted
        return fitted.copy()
    except Exception:
        return None


def _animate_weather_icon(icon: Image.Image, source: str, snapshot: dict[str, str], settings: dict[str, Any]) -> Image.Image:
    if not bool(settings.get("animate_icons", True)):
        return icon
    phase = time.time() * float(settings.get("icon_animation_speed", 1.0) or 1.0)
    text = " ".join(
        str(snapshot.get(key, ""))
        for key in (
            source,
            "weather_condition",
            "weather_icon",
        )
    ).lower()
    w, h = icon.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if any(token in text for token in ("rain", "drizzle", "sleet", "snow", "hail")):
        offset = int((phase * 10) % max(1, h // 5))
        out.alpha_composite(icon, (0, offset - max(1, h // 10)))
        faded = icon.copy()
        faded.putalpha(faded.getchannel("A").point(lambda a: int(a * 0.38)))
        out.alpha_composite(faded, (0, offset + max(1, h // 12)))
        return out
    if any(token in text for token in ("cloud", "fog", "overcast")):
        offset = int(round(math.sin(phase * 1.8) * max(1, w * 0.035)))
        out.alpha_composite(icon, (offset, 0))
        return out
    angle = math.sin(phase * 1.5) * 3.0
    scale = 1.0 + 0.035 * math.sin(phase * 2.0)
    resized = icon.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    rotated = resized.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    out.alpha_composite(rotated, ((w - rotated.width) // 2, (h - rotated.height) // 2))
    return out


def _render_weather_current_widget(canvas: Image.Image, item: dict[str, Any], base_dir: Path, snapshot: dict[str, str]) -> None:
    x, y, w, h = [int(v) for v in item["rect"]]
    settings = item.get("settings", {}) if isinstance(item.get("settings", {}), dict) else {}
    opacity = max(0.0, min(1.0, float(item.get("opacity", 1.0))))
    scale = max(0.55, min(2.4, min(w / 500.0, h / 152.0)))
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    fill = _rgba(settings.get("panel_fill", [8, 14, 24, 205]))
    if bool(settings.get("panel_enabled", True)) and fill[3] > 0:
        pdraw.rounded_rectangle((0, 0, w - 1, h - 1), radius=max(4, int(22 * scale)), fill=(fill[0], fill[1], fill[2], int(fill[3] * opacity)))
    icon_size = max(42, min(int(h * 0.62), int(w * 0.22)))
    icon_x = int(24 * scale)
    icon_y = max(8, (h - icon_size) // 2)
    icon = _weather_icon_image("weather_icon", snapshot, base_dir, (icon_size, icon_size))
    if icon is not None:
        icon = _animate_weather_icon(icon, "weather_icon", snapshot, settings)
        panel.alpha_composite(icon, (icon_x, icon_y))
    text_x = icon_x + icon_size + int(18 * scale)
    right_x = max(text_x + int(180 * scale), int(w * 0.63))
    font_family = str(settings.get("font_family", "DejaVu Sans"))
    _draw_widget_text(pdraw, (text_x, int(18 * scale)), snapshot.get("weather_location", "N/A"), font=_scaled_font(int(settings.get("location_font_size", 18)), scale, bold=True, font_family=font_family), fill=_rgba(settings.get("location_color", [235, 246, 255])), max_width=right_x - text_x - 8)
    _draw_widget_text(pdraw, (text_x, int(44 * scale)), snapshot.get("weather_temp_c", "N/A"), font=_scaled_font(int(settings.get("temp_font_size", 38)), scale, bold=True, font_family=font_family), fill=_rgba(settings.get("temp_color", [246, 231, 152])), max_width=right_x - text_x - 8)
    _draw_widget_text(pdraw, (text_x, int(98 * scale)), snapshot.get("weather_condition", "N/A"), font=_scaled_font(int(settings.get("condition_font_size", 20)), scale, font_family=font_family), fill=_rgba(settings.get("condition_color", [210, 224, 240])), max_width=right_x - text_x - 8)
    detail_font = _scaled_font(int(settings.get("detail_font_size", 18)), scale, font_family=font_family)
    detail_color = _rgba(settings.get("detail_color", [210, 224, 240]))
    _draw_widget_text(pdraw, (right_x, int(48 * scale)), f"Wind {snapshot.get('weather_wind_kph', 'N/A')}", font=detail_font, fill=detail_color, max_width=w - right_x - 16)
    _draw_widget_text(pdraw, (right_x, int(80 * scale)), f"Humidity {snapshot.get('weather_humidity_percent', 'N/A')}", font=detail_font, fill=detail_color, max_width=w - right_x - 16)
    canvas.alpha_composite(panel, (x, y))


def _render_weather_forecast_widget(canvas: Image.Image, item: dict[str, Any], base_dir: Path, snapshot: dict[str, str]) -> None:
    x, y, w, h = [int(v) for v in item["rect"]]
    settings = item.get("settings", {}) if isinstance(item.get("settings", {}), dict) else {}
    opacity = max(0.0, min(1.0, float(item.get("opacity", 1.0))))
    scale = max(0.45, min(2.0, min(w / 1088.0, h / 112.0)))
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    fill = _rgba(settings.get("panel_fill", [8, 14, 24, 190]))
    if bool(settings.get("panel_enabled", True)) and fill[3] > 0:
        pdraw.rounded_rectangle((0, 0, w - 1, h - 1), radius=max(4, int(18 * scale)), fill=(fill[0], fill[1], fill[2], int(fill[3] * opacity)))
    font_family = str(settings.get("font_family", "DejaVu Sans"))
    _draw_widget_text(pdraw, (int(26 * scale), int(10 * scale)), snapshot.get("weather_location", "N/A"), font=_scaled_font(int(settings.get("location_font_size", 18)), scale, bold=True, font_family=font_family), fill=_rgba(settings.get("location_color", [235, 246, 255])), max_width=w - int(52 * scale))
    label_font = _scaled_font(int(settings.get("day_font_size", 17)), scale, bold=True, font_family=font_family)
    hi_font = _scaled_font(int(settings.get("temp_max_font_size", 21)), scale, bold=True, font_family=font_family)
    lo_font = _scaled_font(int(settings.get("temp_min_font_size", 16)), scale, font_family=font_family)
    cond_font = _scaled_font(int(settings.get("condition_font_size", 13)), scale, font_family=font_family)
    day_w = max(1, int((w - int(56 * scale)) / 7))
    top = int(36 * scale)
    icon_size = max(18, min(int(30 * scale), max(18, h - top - int(52 * scale))))
    for idx in range(7):
        dx = int(28 * scale) + idx * day_w
        _draw_widget_text(pdraw, (dx, top), snapshot.get(f"weather_day_{idx}_label", "N/A"), font=label_font, fill=_rgba(settings.get("day_color", [160, 196, 232])), max_width=day_w - 4)
        icon = _weather_icon_image(f"weather_day_{idx}_icon", snapshot, base_dir, (icon_size, icon_size))
        if icon is not None:
            icon = _animate_weather_icon(icon, f"weather_day_{idx}_icon", snapshot, settings)
            panel.alpha_composite(icon, (dx, top + int(24 * scale)))
        _draw_widget_text(pdraw, (dx + icon_size + int(6 * scale), top + int(23 * scale)), snapshot.get(f"weather_day_{idx}_temp_max_c", "N/A"), font=hi_font, fill=_rgba(settings.get("temp_max_color", [246, 231, 152])), max_width=day_w - icon_size - 6)
        _draw_widget_text(pdraw, (dx + icon_size + int(48 * scale), top + int(29 * scale)), snapshot.get(f"weather_day_{idx}_temp_min_c", "N/A"), font=lo_font, fill=_rgba(settings.get("temp_min_color", [180, 206, 232])), max_width=day_w - icon_size - 48)
        _draw_widget_text(pdraw, (dx, top + int(58 * scale)), snapshot.get(f"weather_day_{idx}_condition", "N/A"), font=cond_font, fill=_rgba(settings.get("condition_color", [210, 224, 240])), max_width=day_w - 6)
    canvas.alpha_composite(panel, (x, y))


def _media_cover_image(snapshot: dict[str, str], base_dir: Path, size: tuple[int, int], *, video_frame: bool = False) -> Image.Image | None:
    cover_path = ""
    if video_frame:
        cover_path = str(snapshot.get("media_video_frame_path", "")).strip() or str(snapshot.get("media_cover_path", "")).strip()
    else:
        cover_path = str(snapshot.get("media_cover_path", "")).strip()
    if not cover_path:
        return None
    src_path = _resolve_asset_path(base_dir, cover_path)
    if not src_path.exists():
        return None
    try:
        return _fit_image(Image.open(src_path).convert("RGBA"), size[0], size[1], "cover")
    except Exception:
        return None


def _media_cover_placeholder(
    size: tuple[int, int],
    *,
    title: str,
    artist: str,
    fill: tuple[int, int, int, int],
    accent: tuple[int, int, int, int],
) -> Image.Image:
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    base = (max(0, fill[0] + 10), max(0, fill[1] + 14), max(0, fill[2] + 22), min(230, max(150, fill[3])))
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=max(8, min(w, h) // 8), fill=base)
    ring = (accent[0], accent[1], accent[2], min(180, max(80, accent[3])))
    pad = max(8, min(w, h) // 8)
    draw.ellipse((pad, pad, w - pad, h - pad), outline=ring, width=max(2, min(w, h) // 24))
    draw.ellipse((w * 0.43, h * 0.43, w * 0.57, h * 0.57), fill=ring)
    initial = ""
    for value in (title, artist):
        clean = str(value or "").strip()
        if clean and clean != "N/A":
            initial = clean[0].upper()
            break
    if initial:
        font = _load_font(max(16, min(w, h) // 3), bold=True)
        bbox = draw.textbbox((0, 0), initial, font=font)
        draw.text(((w - (bbox[2] - bbox[0])) // 2, (h - (bbox[3] - bbox[1])) // 2 - bbox[1]), initial, font=font, fill=accent)
    return img


def _draw_media_widget_text(
    panel: Image.Image,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    bold: bool = False,
    marquee: bool = False,
    marquee_speed: float = 55.0,
) -> None:
    _draw_clipped_text(
        panel,
        x=max(0, int(x)),
        y=max(0, int(y)),
        box_width=max(1, int(width)),
        box_height=max(1, int(height)),
        text=str(text),
        font=font,
        fill=fill,
        bold=bold,
        underline=False,
        marquee=marquee,
        marquee_speed=marquee_speed,
    )


def _draw_media_widget_equalizer(
    panel: Image.Image,
    *,
    rect: tuple[int, int, int, int],
    snapshot: dict[str, str],
    fill_color: tuple[int, int, int, int],
    accent_color: tuple[int, int, int, int],
    bars: int,
    gap: int,
    mirror: bool,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    fake_item = {
        "id": "widget_media_equalizer",
        "x": x,
        "y": y,
        "box_width": w,
        "box_height": h,
        "font_size": 12,
        "font_family": "DejaVu Sans",
        "equalizer_bars": bars,
        "equalizer_gap": gap,
        "equalizer_mirror": mirror,
        "show_value_text": False,
    }
    value = str(snapshot.get("volume_percent", "65"))
    numeric = _parse_numeric_stat_value(value)
    if numeric is None:
        numeric = 65.0 if str(snapshot.get("media_state", "")).strip().lower() == "playing" else 18.0
    _draw_stat_equalizer(
        panel,
        fake_item,
        label="",
        value_text="",
        numeric_value=numeric,
        min_value=0.0,
        max_value=100.0,
        label_fill=accent_color,
        value_fill=accent_color,
        track_fill=(0, 0, 0, 0),
        fill_color=fill_color,
        snapshot=snapshot,
    )


def _render_media_now_playing_widget(canvas: Image.Image, item: dict[str, Any], base_dir: Path, snapshot: dict[str, str]) -> None:
    x, y, w, h = [int(v) for v in item["rect"]]
    settings = item.get("settings", {}) if isinstance(item.get("settings", {}), dict) else {}
    style = str(item.get("style", "standard")).strip().lower()
    opacity = max(0.0, min(1.0, float(item.get("opacity", 1.0))))
    scale = max(0.45, min(2.4, min(w / (932.0 if style == "hero" else 760.0), h / (176.0 if style == "hero" else 128.0))))
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    panel_enabled = bool(settings.get("panel_enabled", True))
    backdrop_enabled = bool(settings.get("backdrop_enabled", True))
    cover_enabled = bool(settings.get("cover_enabled", True))
    cover_placeholder_enabled = bool(settings.get("cover_placeholder_enabled", True))
    equalizer_enabled = bool(settings.get("equalizer_enabled", True))
    title_marquee = bool(settings.get("title_marquee", True))
    marquee_speed = float(settings.get("title_marquee_speed", settings.get("marquee_speed", 55.0)))
    if backdrop_enabled:
        backdrop = _media_cover_image(snapshot, base_dir, (w, h), video_frame=True)
        if backdrop is not None:
            alpha = backdrop.getchannel("A")
            alpha = alpha.point(lambda v: int(v * max(0.0, min(1.0, float(settings.get("backdrop_opacity", 0.30))))))
            backdrop.putalpha(alpha)
            panel.alpha_composite(backdrop, (0, 0))
    fill = _rgba(settings.get("panel_fill", [8, 14, 24, 210]))
    radius = max(4, int((26 if style == "hero" else 16) * scale))
    if panel_enabled and fill[3] > 0:
        pdraw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=(fill[0], fill[1], fill[2], int(fill[3] * opacity)))
    font_family = str(settings.get("font_family", "DejaVu Sans"))
    title_font = _scaled_font(int(settings.get("title_font_size", 32 if style == "hero" else 28 if style != "mini" else 20)), scale, bold=True, font_family=font_family)
    artist_font = _scaled_font(int(settings.get("artist_font_size", 24 if style == "hero" else 22 if style != "mini" else 16)), scale, font_family=font_family)
    detail_font = _scaled_font(int(settings.get("detail_font_size", 18)), scale, font_family=font_family)
    title_color = _rgba(settings.get("title_color", [244, 248, 255]))
    artist_color = _rgba(settings.get("artist_color", [210, 224, 240]))
    detail_color = _rgba(settings.get("detail_color", [160, 196, 232]))
    eq_color = _rgba(settings.get("equalizer_color", settings.get("detail_color", [94, 205, 255, 210])))
    eq_accent = _rgba(settings.get("equalizer_accent_color", settings.get("title_color", [244, 248, 255, 230])))
    media_title = str(snapshot.get("media_title", "N/A") or "N/A")
    media_artist = str(snapshot.get("media_artist", "N/A") or "N/A")
    media_app = str(snapshot.get("media_app", "N/A") or "N/A")
    media_state = str(snapshot.get("media_state", "N/A") or "N/A")
    if style == "mini":
        pad = max(6, int(12 * scale))
        gap = max(3, int(5 * scale))
        cover_size = 0
        cover_x = pad
        cover_y = 0
        if cover_enabled and w >= 220 and h >= 58:
            cover_size = max(42, min(int(h * 0.70), int(w * 0.22)))
            cover_y = max(4, (h - cover_size) // 2)
            cover = _media_cover_image(snapshot, base_dir, (cover_size, cover_size))
            if cover is None and cover_placeholder_enabled:
                cover = _media_cover_placeholder((cover_size, cover_size), title=media_title, artist=media_artist, fill=fill, accent=title_color)
            if cover is not None:
                panel.alpha_composite(_apply_rounded_alpha(cover, max(5, int(10 * scale))), (cover_x, cover_y))
        text_x = pad + cover_size + (gap * 2 if cover_size else 0)
        text_w = max(1, w - text_x - pad)
        top = max(4, int(9 * scale))
        bottom = max(4, int(7 * scale))
        title_h = max(14, min(int(28 * scale), max(14, h // 3)))
        artist_h = max(0, min(int(20 * scale), max(0, h // 4)))
        eq_h = max(0, h - top - title_h - artist_h - gap * 2 - bottom)
        if equalizer_enabled and eq_h < 14:
            artist_h = max(0, min(artist_h, h - top - title_h - gap - bottom - 14))
            eq_h = max(0, h - top - title_h - artist_h - gap * 2 - bottom)
        title_y = top
        artist_y = title_y + title_h + gap
        _draw_media_widget_text(panel, x=text_x, y=title_y, width=text_w, height=title_h, text=f"♫ {media_title}", font=title_font, fill=title_color, bold=True, marquee=title_marquee, marquee_speed=marquee_speed)
        show_artist = artist_h >= 8
        if show_artist:
            _draw_media_widget_text(panel, x=text_x, y=artist_y, width=text_w, height=artist_h, text=media_artist, font=artist_font, fill=artist_color)
        if equalizer_enabled and eq_h >= 14:
            eq_top = (artist_y + artist_h + gap) if show_artist else (title_y + title_h + gap)
            _draw_media_widget_equalizer(panel, rect=(text_x, eq_top, text_w, eq_h), snapshot=snapshot, fill_color=eq_color, accent_color=eq_accent, bars=int(settings.get("equalizer_bars", 20)), gap=int(settings.get("equalizer_gap", 3)), mirror=bool(settings.get("equalizer_mirror", False)))
    else:
        cover_size = max(58, min(int(h * 0.78), int(w * 0.18)))
        cover_x = int(20 * scale)
        cover_y = max(8, (h - cover_size) // 2)
        cover = _media_cover_image(snapshot, base_dir, (cover_size, cover_size)) if cover_enabled else None
        if cover is None and cover_enabled and cover_placeholder_enabled:
            cover = _media_cover_placeholder((cover_size, cover_size), title=media_title, artist=media_artist, fill=fill, accent=title_color)
        if cover is not None:
            radius = max(6, int(18 * scale))
            cover = _apply_rounded_alpha(cover, radius)
            panel.alpha_composite(cover, (cover_x, cover_y))
        text_x = cover_x + cover_size + int(22 * scale) if cover_enabled else int(22 * scale)
        max_text_w = max(1, w - text_x - int(28 * scale))
        title_y = max(6, int(14 * scale))
        bottom_pad = max(6, int(8 * scale))
        gap = max(3, int(5 * scale))
        title_h = max(18, min(int(38 * scale), max(18, h // 3)))
        artist_h = max(14, min(int(30 * scale), max(14, h // 4)))
        detail_h = max(0, min(int(24 * scale), max(0, h // 5)))
        min_eq_h = 16 if h >= 92 else 0
        eq_h = max(0, h - title_y - title_h - artist_h - detail_h - gap * 3 - bottom_pad)
        if equalizer_enabled and eq_h < min_eq_h:
            detail_h = 0
            eq_h = max(0, h - title_y - title_h - artist_h - gap * 2 - bottom_pad)
        if equalizer_enabled and eq_h < min_eq_h:
            available_artist_h = h - title_y - title_h - gap * 2 - bottom_pad - min_eq_h
            artist_h = max(0, min(artist_h, available_artist_h))
            eq_h = max(0, h - title_y - title_h - artist_h - gap * 2 - bottom_pad)
        artist_y = title_y + title_h + gap
        detail_y = artist_y + artist_h + gap
        eq_top = (detail_y + detail_h + gap) if detail_h > 0 else (artist_y + artist_h + gap)
        title_prefix = "" if bool(settings.get("hide_title_prefix", True)) else "Now Playing: "
        _draw_media_widget_text(panel, x=text_x, y=title_y, width=max_text_w, height=title_h, text=f"{title_prefix}{media_title}", font=title_font, fill=title_color, bold=True, marquee=title_marquee, marquee_speed=marquee_speed)
        if artist_h > 0:
            _draw_media_widget_text(panel, x=text_x, y=artist_y, width=max_text_w, height=artist_h, text=media_artist, font=artist_font, fill=artist_color)
        if detail_h > 0:
            _draw_media_widget_text(panel, x=text_x, y=detail_y, width=max_text_w, height=detail_h, text=f"{media_app} - {media_state}", font=detail_font, fill=detail_color)
        if equalizer_enabled and eq_h >= 18:
            _draw_media_widget_equalizer(panel, rect=(text_x, eq_top, max_text_w, eq_h), snapshot=snapshot, fill_color=eq_color, accent_color=eq_accent, bars=int(settings.get("equalizer_bars", 24 if style == "hero" else 18)), gap=int(settings.get("equalizer_gap", 4)), mirror=bool(settings.get("equalizer_mirror", False)))
    canvas.alpha_composite(panel, (x, y))


def render_widgets(canvas: Image.Image, theme: ThemeDocument, base_dir: Path, snapshot: dict[str, str]) -> None:
    for item in _sorted_by_z(theme.data.get("widgets", [])):
        if not bool(item.get("visible", True)):
            continue
        kind = str(item.get("kind", "")).strip().lower()
        if kind == "weather_current":
            _render_weather_current_widget(canvas, item, base_dir, snapshot)
        elif kind == "weather_forecast_7d":
            _render_weather_forecast_widget(canvas, item, base_dir, snapshot)
        elif kind == "media_now_playing":
            _render_media_now_playing_widget(canvas, item, base_dir, snapshot)


def render_effects(canvas: Image.Image, theme: ThemeDocument) -> None:
    effects = theme.data["effects"]
    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size

    if effects.get("show_grid", False):
        for x in range(0, width, 120):
            draw.line((x, 0, x, height), fill=(60, 60, 60, 120), width=1)
        for y in range(0, height, 60):
            draw.line((0, y, width, y), fill=(60, 60, 60, 120), width=1)

    if effects.get("show_safe_area", False):
        draw.rectangle((20, 20, width - 20, height - 20), outline=(255, 80, 80, 180), width=2)


def render_theme_document(
    theme: ThemeDocument,
    *,
    base_dir: Path | None = None,
    stats_provider: StatsProvider | None = None,
    stats_override: dict[str, str] | None = None,
    transparent_background: bool = False,
    include_images: bool = True,
    include_effects: bool = True,
    output_mode: str = "RGB",
) -> Image.Image:
    base_dir = Path(".") if base_dir is None else base_dir
    stats_provider = StatsProvider() if stats_provider is None else stats_provider

    themed = _apply_motion_tracks(theme)
    snapshot = dict(stats_override) if isinstance(stats_override, dict) else stats_provider.snapshot().values
    if transparent_background:
        size = (
            int(themed.data["canvas"]["width"]),
            int(themed.data["canvas"]["height"]),
        )
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    else:
        canvas = render_background(themed, base_dir)
    if include_images:
        render_images(canvas, themed, base_dir, snapshot)
    render_texts(canvas, themed)
    render_stats(canvas, themed, snapshot)
    render_widgets(canvas, themed, base_dir, snapshot)
    if include_effects:
        render_effects(canvas, themed)

    rotation = int(themed.data["canvas"]["rotation"]) % 360
    if rotation:
        canvas = canvas.transpose(
            {
                90: Image.ROTATE_90,
                180: Image.ROTATE_180,
                270: Image.ROTATE_270,
            }[rotation]
        )
    if output_mode.upper() == "RGBA":
        return canvas.convert("RGBA")
    return canvas.convert("RGB")


def render_theme_file(theme_path: str | Path, *, stats_provider: StatsProvider | None = None) -> Image.Image:
    path = Path(theme_path)
    theme = load_theme_document(path)
    return render_theme_document(theme, base_dir=path.parent, stats_provider=stats_provider)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Open Trofeo LCD theme JSON to PNG")
    parser.add_argument("theme", help="Theme JSON path")
    parser.add_argument("--output", "-o", help="Output PNG path")
    args = parser.parse_args()

    theme_path = Path(args.theme)
    out_path = Path(args.output) if args.output else theme_path.with_suffix(".preview.png")
    image = render_theme_file(theme_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    print(f"OK {theme_path} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
