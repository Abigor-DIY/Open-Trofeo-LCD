#!/usr/bin/env python3
"""
Theme renderer for Open Trofeo LCD.

Stage 3.2: render a validated theme document into a 1920x462 image.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
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
    for key in ("texts", "stats", "images"):
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
        render_opacity = max(0.0, min(1.0, float(panel.get("_render_opacity", 1.0))))
        fill[3] = int(fill[3] * render_opacity)
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
        if source in {"media_cover", "media_video_frame"}:
            cover_path = ""
            if source == "media_video_frame":
                cover_path = str(snapshot.get("media_video_frame_path", "")).strip() or str(snapshot.get("media_cover_path", "")).strip()
            else:
                cover_path = str(snapshot.get("media_cover_path", "")).strip()
            if not cover_path:
                continue
            src_path = _resolve_asset_path(base_dir, cover_path)
        else:
            src_path = _resolve_asset_path(base_dir, item["path"])
        if not src_path.exists():
            continue
        src = Image.open(src_path).convert("RGBA")
        x, y, w, h = item["rect"]
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
        label_fill = (label_fill_rgba[0], label_fill_rgba[1], label_fill_rgba[2], int(label_fill_rgba[3] * render_opacity))
        value_fill = (value_fill_rgba[0], value_fill_rgba[1], value_fill_rgba[2], int(value_fill_rgba[3] * render_opacity))
        x = int(item["x"])
        y = int(item["y"])
        box_width = max(1, int(item.get("box_width", 320)))
        box_height = max(1, int(item.get("box_height", 40)))
        label = item["label"]
        value = snapshot.get(item["source"], "N/A")
        value_text = item["format"].format(value=value)
        marquee = bool(item.get("marquee", False))

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
