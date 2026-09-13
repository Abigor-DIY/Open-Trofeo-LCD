#!/usr/bin/env python3
"""Generate lightweight PNG frame caches from bundled Meteocons PNG assets.

The bundled Meteocons SVG files contain SMIL animation, but QtSvg renders some
SVG masks incorrectly on Linux. This tool starts from the known-good static PNG
icons and adds small, deterministic motion layers, keeping runtime rendering
cheap and dependency-free.
"""

from __future__ import annotations

import argparse
import math
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "assets/weather/icons/meteocons/png"
DEFAULT_OUTPUT_DIR = ROOT / "assets/weather/icons/meteocons/frames"
DEFAULT_ICONS = (
    "clear-day",
    "clear-night",
    "mostly-clear-day",
    "mostly-clear-night",
    "partly-cloudy-day",
    "partly-cloudy-night",
    "overcast-day",
    "overcast-night",
    "cloudy",
    "fog",
    "fog-day",
    "fog-night",
    "drizzle",
    "rain",
    "extreme-rain",
    "snow",
    "extreme-snow",
    "sleet",
    "thunderstorms",
    "thunderstorms-day",
    "thunderstorms-night",
    "hail",
    "wind",
)


def _fit_icon(path: Path, size: int) -> Image.Image:
    with Image.open(path) as src:
        img = src.convert("RGBA")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    return out


def _with_alpha(image: Image.Image, scale: float) -> Image.Image:
    out = image.copy()
    scale = max(0.0, min(1.0, scale))
    out.putalpha(out.getchannel("A").point(lambda value: int(value * scale)))
    return out


def _centered_scaled(image: Image.Image, scale: float, size: int) -> Image.Image:
    scaled_size = max(1, int(round(size * scale)))
    resized = image.resize((scaled_size, scaled_size), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return out


def _draw_mist(out: Image.Image, phase: float) -> None:
    size = out.width
    mist = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(mist)
    colors = (
        (230, 242, 250, 74),
        (192, 215, 230, 66),
        (255, 255, 255, 58),
    )
    for idx in range(7):
        band_h = max(5, int(size * (0.050 + 0.010 * (idx % 2))))
        band_w = int(size * (0.52 + 0.06 * (idx % 3)))
        gap = int(size * 0.16)
        base_y = size * (0.28 + idx * 0.072)
        y = int(round(base_y + math.sin(phase * math.tau + idx * 0.7) * size * 0.014))
        x0 = int(round(((phase * (size * (0.42 + idx * 0.06))) + idx * size * 0.17) % (band_w + gap) - band_w))
        for x in range(x0, size + band_w, band_w + gap):
            draw.rounded_rectangle((x, y, x + band_w, y + band_h), radius=band_h // 2, fill=colors[idx % len(colors)])
    out.alpha_composite(mist.filter(ImageFilter.GaussianBlur(max(1.2, size * 0.016))))


def _draw_rain(out: Image.Image, phase: float, heavy: bool = False) -> None:
    size = out.width
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    count = 9 if heavy else 6
    for idx in range(count):
        x = int((idx * size * 0.15 + phase * size * (0.48 if heavy else 0.36)) % size)
        y = int((idx * size * 0.17 + phase * size * 0.58) % int(size * 0.44)) + int(size * 0.47)
        draw.line(
            (x, y, x - int(size * 0.045), y + int(size * 0.18)),
            fill=(85, 198, 255, 150 if heavy else 118),
            width=max(1, size // 36),
        )
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.15)))


def _draw_snow(out: Image.Image, phase: float, heavy: bool = False) -> None:
    size = out.width
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    count = 13 if heavy else 8
    radius = max(1, size // 48)
    for idx in range(count):
        x = int((idx * size * 0.19 + math.sin(phase * math.tau + idx) * size * 0.04) % size)
        y = int((idx * size * 0.13 + phase * size * (0.36 if heavy else 0.26)) % int(size * 0.50)) + int(size * 0.43)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(238, 248, 255, 148))
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.2)))


def _draw_lightning(out: Image.Image, phase: float) -> None:
    if phase < 0.08 or 0.52 < phase < 0.58:
        glow = Image.new("RGBA", out.size, (255, 238, 118, 34))
        out.alpha_composite(glow)


def _weather_frame(icon: str, base: Image.Image, idx: int, frame_count: int) -> Image.Image:
    phase = idx / float(frame_count)
    name = icon.lower()
    size = base.width
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    if any(token in name for token in ("clear", "mostly-clear")):
        pulse = 1.0 + 0.018 * math.sin(phase * math.tau)
        out.alpha_composite(_centered_scaled(base, pulse, size))
        if "day" in name:
            glow = _with_alpha(base.filter(ImageFilter.GaussianBlur(max(1.0, size * 0.025))), 0.18)
            out.alpha_composite(glow)
        return out
    if "fog" in name:
        out.alpha_composite(_with_alpha(base, 0.88))
        _draw_mist(out, phase)
        return out
    if any(token in name for token in ("rain", "drizzle", "sleet")):
        out.alpha_composite(_with_alpha(base, 0.90))
        _draw_rain(out, phase, heavy="extreme" in name)
        if "sleet" in name:
            _draw_snow(out, (phase + 0.35) % 1.0, heavy=False)
        return out
    if any(token in name for token in ("snow", "hail")):
        out.alpha_composite(_with_alpha(base, 0.90))
        _draw_snow(out, phase, heavy="extreme" in name)
        return out
    if "thunder" in name:
        out.alpha_composite(base)
        _draw_rain(out, phase, heavy=False)
        _draw_lightning(out, phase)
        return out
    if "wind" in name:
        dx = int(round(math.sin(phase * math.tau) * size * 0.025))
        out.alpha_composite(base, (dx, 0))
        return out
    if any(token in name for token in ("cloud", "overcast")):
        dx = int(round(math.sin(phase * math.tau) * size * 0.018))
        out.alpha_composite(_with_alpha(base.filter(ImageFilter.GaussianBlur(max(0.5, size * 0.008))), 0.20), (-dx, 0))
        out.alpha_composite(base, (dx, 0))
        return out
    out.alpha_composite(base)
    return out


def render_icon_frames(*, source_dir: Path, output_dir: Path, icon: str, size: int, frames: int, clean: bool) -> int:
    source_path = source_dir / f"{icon}.png"
    if not source_path.exists():
        print(f"skip {icon}: missing {source_path.relative_to(ROOT)}", file=sys.stderr)
        return 0
    target_dir = output_dir / icon
    if clean and target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    base = _fit_icon(source_path, size)
    for idx in range(frames):
        _weather_frame(icon, base, idx, frames).save(target_dir / f"frame_{idx:03d}.png")
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PNG frame caches from bundled Meteocons PNG files.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("icons", nargs="*", default=list(DEFAULT_ICONS))
    args = parser.parse_args()

    size = max(32, min(512, int(args.size)))
    frames = max(4, min(120, int(args.frames)))
    total = 0
    for icon in args.icons:
        total += render_icon_frames(
            source_dir=args.source_dir.resolve(),
            output_dir=args.output_dir.resolve(),
            icon=str(icon).strip(),
            size=size,
            frames=frames,
            clean=bool(args.clean),
        )
    print(f"Generated {total} weather icon frame(s) in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
