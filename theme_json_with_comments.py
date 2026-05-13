#!/usr/bin/env python3
"""
Optional // and /* */ comments in theme JSON files.

Open Trofeo strips these before json.loads. Use when hand-editing theme files
or when embedding a short field guide at the top of the file.
"""

from __future__ import annotations

import json
from typing import Any


def strip_json_comments(text: str) -> str:
    """Remove // line comments and /* block */ comments; respects double-quoted JSON strings."""
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < n and text[i] not in "\r\n":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i = min(i + 2, n)
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def parse_theme_json_text(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("\ufeff"):
        stripped = stripped[1:]
    return json.loads(strip_json_comments(stripped))


def theme_json_documentation_preamble() -> str:
    """English comment block placed above the JSON object when opening a file for manual editing."""
    lines = [
        "// ============================================================================",
        "// Open Trofeo LCD — theme JSON (optional comments)",
        "// ----------------------------------------------------------------------------",
        "// Lines starting with // and /* ... */ blocks are stripped on load.",
        "// The root must be a JSON object { ... }.",
        "// After editing in an external editor, use “Load theme” / JSON → Designer in the app.",
        "// ============================================================================",
        "//",
        "// schema_version — must be 1 for current format.",
        "//",
        "// meta — theme metadata",
        "//   name (string, required) — display name",
        "//   description, author — optional strings",
        "//   tags — optional string array",
        "//   gauge_style — optional default gauge preset id for stats using presets",
        "//",
        "// canvas — LCD logical size",
        "//   width, height — pixels (typical 1920 x 462)",
        "//   rotation — 0 | 90 | 180 | 270",
        "//",
        "// background",
        "//   kind — \"generated\" | \"image\" | \"color\"",
        "//   base_color, accent_color — [R,G,B] or [R,G,B,A] 0..255",
        "//   texture_alpha — 0..1 (generated texture strength)",
        "//   path, fit (contain|cover|stretch), opacity — when kind=image",
        "//   panels — array of rounded rectangles behind widgets:",
        "//       rect [x,y,w,h], radius, fill color, opacity, z_index, visible, locked",
        "//",
        "// texts[] — static labels (marquee optional)",
        "//   text, x, y, box_width, box_height, font_*, colors, align, z_index, …",
        "//",
        "// stats[] — live values (source keys: cpu_*, mem_*, media_*, volume_*, …)",
        "//   label, source, format (e.g. \"{value}%\")",
        "//   display — \"text\" | \"progress\" | \"gauge\" | \"sparkline\" | \"equalizer\"",
        "//   min_value, max_value — for numeric displays",
        "//   For equalizer: equalizer_bars, equalizer_gap, equalizer_mirror",
        "//   x, y, box_*, colors, z_index, visible, locked, …",
        "//",
        "// images[] — bitmap layers",
        "//   path — file under theme assets / relative to theme file",
        "//   source — optional: \"media_cover\" | \"media_video_frame\" | \"analog_clock\"",
        "//   fit, rect, crop_box, clock_style (for analog_clock), z_index, …",
        "//",
        "// effects — editor / animation / motion",
        "//   show_grid, show_safe_area — designer overlays",
        "//   animation — background frame sequence (also edited in Animation Studio):",
        "//       enabled — turn frame cycling on",
        "//       use_as_background — composite frames as wallpaper",
        "//       fps — fallback rate; per-frame timing in frame_durations_ms",
        "//       frame_paths — list of image paths (same order as durations)",
        "//       frame_durations_ms — display time per frame in milliseconds (> 0)",
        "//       current_frame — index when editing",
        "//       loop — repeat sequence",
        "//   motion_tracks[] — per-widget motion between preview frames:",
        "//       item_id — id of text/stat/image",
        "//       frame_start, frame_end — inclusive range in preview timeline",
        "//       x_to, y_to — target position (pixels)",
        "//       opacity_to — 0..1 target opacity",
        "//   import_report — tooling metadata (safe to leave as {})",
        "//",
        "// See theme_schema.py (KNOWN_STAT_SOURCES, normalization) for allowed sources and defaults.",
        "// ============================================================================",
        "",
    ]
    return "\n".join(lines)
