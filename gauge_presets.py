#!/usr/bin/env python3
"""
Visual presets for stat gauges (display=gauge).

Merged into stat items during theme normalization. Explicit stat fields override preset values.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _c(r: int, g: int, b: int, a: int = 255) -> list[int]:
    return [r, g, b, a]


# Named presets: colors + visual defaults. min/max can still be overridden per stat.
GAUGE_PRESET_ORDER = [
    "usage",
    "thermal",
    "forest",
    "forge",
    "runic_gold",
    "nordic",
    "cyber",
    "plasma_blue",
    "freq",
]

GAUGE_PRESET_LABELS: dict[str, str] = {
    "usage": "Adaptive System",
    "thermal": "Thermal Alert",
    "forest": "Forest Emerald",
    "forge": "Forge Iron",
    "runic_gold": "Runic Gold",
    "nordic": "Nordic Frost",
    "cyber": "Cyber Neon",
    "plasma_blue": "Plasma Blue",
    "freq": "Frequency Arc",
}

GAUGE_PRESETS: dict[str, dict[str, Any]] = {
    "usage": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(52, 211, 153),
        "gauge_color_mid": _c(250, 204, 21),
        "gauge_color_high": _c(249, 115, 22),
        "fill_color": _c(52, 211, 153),
        "track_color": _c(18, 28, 40, 224),
        "label_color": _c(218, 232, 241),
        "value_color": _c(244, 248, 252),
        "stroke_width": 18,
        "gauge_inner_alpha": 0.9,
        "gauge_value_layout": "center",
        "gauge_match_value_color": True,
    },
    "thermal": {
        "min_value": 35.0,
        "max_value": 92.0,
        "gauge_color_low": _c(34, 197, 94),
        "gauge_color_mid": _c(250, 204, 21),
        "gauge_color_high": _c(239, 68, 68),
        "fill_color": _c(250, 204, 21),
        "track_color": _c(28, 16, 18, 228),
        "label_color": _c(255, 223, 178),
        "value_color": _c(255, 248, 237),
        "stroke_width": 20,
        "gauge_inner_alpha": 0.72,
        "gauge_value_layout": "below",
        "gauge_match_value_color": True,
    },
    "forest": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(74, 222, 128),
        "gauge_color_mid": _c(163, 230, 53),
        "gauge_color_high": _c(234, 179, 8),
        "fill_color": _c(74, 222, 128),
        "track_color": _c(8, 28, 22, 228),
        "label_color": _c(219, 234, 208),
        "value_color": _c(250, 251, 235),
        "stroke_width": 18,
        "gauge_inner_alpha": 0.82,
        "gauge_value_layout": "center",
        "gauge_match_value_color": True,
    },
    "ember": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(251, 191, 36),
        "gauge_color_mid": _c(249, 115, 22),
        "gauge_color_high": _c(220, 38, 38),
        "fill_color": _c(249, 115, 22),
        "track_color": _c(34, 16, 14, 232),
        "label_color": _c(255, 220, 188),
        "value_color": _c(255, 248, 243),
        "stroke_width": 20,
        "gauge_inner_alpha": 0.66,
        "gauge_value_layout": "center",
        "gauge_match_value_color": True,
    },
    "cyber": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(34, 211, 238),
        "gauge_color_mid": _c(96, 165, 250),
        "gauge_color_high": _c(244, 114, 182),
        "fill_color": _c(34, 211, 238),
        "track_color": _c(6, 16, 28, 228),
        "label_color": _c(188, 241, 255),
        "value_color": _c(240, 249, 255),
        "stroke_width": 14,
        "gauge_inner_alpha": 0.45,
        "gauge_value_layout": "beside",
        "gauge_match_value_color": False,
    },
    "nordic": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(147, 197, 253),
        "gauge_color_mid": _c(191, 219, 254),
        "gauge_color_high": _c(250, 204, 21),
        "fill_color": _c(191, 219, 254),
        "track_color": _c(22, 31, 46, 226),
        "label_color": _c(225, 234, 246),
        "value_color": _c(248, 250, 252),
        "stroke_width": 16,
        "gauge_inner_alpha": 0.74,
        "gauge_value_layout": "below",
        "gauge_match_value_color": False,
    },
    "forge": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(148, 163, 184),
        "gauge_color_mid": _c(245, 158, 11),
        "gauge_color_high": _c(239, 68, 68),
        "fill_color": _c(245, 158, 11),
        "track_color": _c(30, 24, 20, 230),
        "label_color": _c(235, 223, 199),
        "value_color": _c(255, 248, 236),
        "stroke_width": 22,
        "gauge_inner_alpha": 0.58,
        "gauge_value_layout": "center",
        "gauge_match_value_color": True,
    },
    "runic_gold": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(132, 204, 22),
        "gauge_color_mid": _c(250, 204, 21),
        "gauge_color_high": _c(249, 115, 22),
        "fill_color": _c(250, 204, 21),
        "track_color": _c(28, 22, 15, 228),
        "label_color": _c(231, 211, 166),
        "value_color": _c(255, 248, 232),
        "stroke_width": 19,
        "gauge_inner_alpha": 0.64,
        "gauge_value_layout": "below",
        "gauge_match_value_color": True,
    },
    "plasma_blue": {
        "min_value": 0.0,
        "max_value": 100.0,
        "gauge_color_low": _c(45, 212, 191),
        "gauge_color_mid": _c(96, 165, 250),
        "gauge_color_high": _c(168, 85, 247),
        "fill_color": _c(96, 165, 250),
        "track_color": _c(8, 16, 30, 226),
        "label_color": _c(203, 235, 255),
        "value_color": _c(243, 248, 255),
        "stroke_width": 15,
        "gauge_inner_alpha": 0.48,
        "gauge_value_layout": "beside",
        "gauge_match_value_color": False,
    },
    "freq": {
        "min_value": 0.8,
        "max_value": 5.5,
        "gauge_color_low": _c(96, 165, 250),
        "gauge_color_mid": _c(52, 211, 153),
        "gauge_color_high": _c(251, 191, 36),
        "fill_color": _c(52, 211, 153),
        "track_color": _c(14, 20, 32, 224),
        "label_color": _c(206, 230, 250),
        "value_color": _c(244, 249, 255),
        "stroke_width": 14,
        "gauge_inner_alpha": 0.58,
        "gauge_value_layout": "beside",
        "gauge_match_value_color": False,
    },
}

# meta.gauge_style string -> default preset id when stat has display=gauge but no gauge_preset
THEME_STYLE_PRESET: dict[str, str] = {
    "verdant": "forest",
    "verdant_bloom": "forest",
    "raven": "ember",
    "raven_flame": "ember",
    "ember": "ember",
    "wolfstorm": "forge",
    "wolfstorm_forge": "forge",
    "matrix": "cyber",
    "linux_matrix": "cyber",
    "nordic": "nordic",
    "frost": "nordic",
    "heritage": "runic_gold",
    "slavic": "runic_gold",
    "duality": "runic_gold",
    "runic": "runic_gold",
    "tux": "cyber",
    "cyan": "cyber",
    "plasma": "plasma_blue",
    "blue": "plasma_blue",
    "green": "forest",
    "dashboard": "usage",
    "minimal": "nordic",
}


def _slug_fragment(text: str) -> str:
    t = text.lower().replace(" ", "_").replace("-", "_")
    out = []
    for ch in t:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    return "_".join(x for x in "".join(out).split("_") if x)


def resolve_theme_gauge_preset(meta: dict[str, Any]) -> str:
    """Pick a default preset from meta.gauge_style or theme name/tags."""
    explicit = str(meta.get("gauge_style", "")).strip().lower()
    if explicit:
        if explicit in GAUGE_PRESETS:
            return explicit
        if explicit in THEME_STYLE_PRESET:
            return THEME_STYLE_PRESET[explicit]
    name_slug = _slug_fragment(str(meta.get("name", "")))
    for key in sorted(THEME_STYLE_PRESET.keys(), key=len, reverse=True):
        preset = THEME_STYLE_PRESET[key]
        if key in name_slug:
            return preset
    name_lower = str(meta.get("name", "")).lower()
    for key in sorted(THEME_STYLE_PRESET.keys(), key=len, reverse=True):
        if key in name_lower:
            return THEME_STYLE_PRESET[key]
    tags = [str(t).lower() for t in meta.get("tags", [])]
    for tag in tags:
        for key in sorted(THEME_STYLE_PRESET.keys(), key=len, reverse=True):
            if key in tag:
                return THEME_STYLE_PRESET[key]
    return ""


def merge_gauge_preset(raw_stat: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Apply preset defaults (preset id + theme fallback). Later keys in raw_stat win."""
    data = deepcopy(raw_stat)
    display = str(data.get("display", "text")).strip().lower()
    if display != "gauge":
        return data

    def _unset(key: str) -> bool:
        if key not in data:
            return True
        val = data[key]
        return val is None or val == ""

    preset_id = str(data.get("gauge_preset", "")).strip().lower()
    if not preset_id:
        preset_id = resolve_theme_gauge_preset(meta)
    if preset_id and preset_id in GAUGE_PRESETS:
        base = deepcopy(GAUGE_PRESETS[preset_id])
        for key, value in base.items():
            if _unset(key):
                data[key] = value
    return data
