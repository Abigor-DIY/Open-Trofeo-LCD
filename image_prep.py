#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageFilter


CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 462


def _fit_image(src: Image.Image, width: int, height: int, fit: str) -> Image.Image:
    if fit == "stretch":
        return src.resize((width, height), Image.LANCZOS)

    src_w, src_h = src.size
    if src_w <= 0 or src_h <= 0:
        return Image.new("RGB", (width, height), (0, 0, 0))

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

    canvas = Image.new("RGB", (width, height), (10, 14, 22))
    paste_x = (width - new_w) // 2
    paste_y = (height - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))
    return canvas


def render_prepared_image(
    input_path: str | Path,
    *,
    width: int = CANVAS_WIDTH,
    height: int = CANVAS_HEIGHT,
    fit: str = "cover",
    rotate: int = 0,
    blur_background: bool = False,
    crop_box: tuple[float, float, float, float] | None = None,
) -> Image.Image:
    src_path = Path(input_path).expanduser().resolve()
    image = Image.open(src_path).convert("RGB")
    if crop_box is not None:
        left_n, top_n, right_n, bottom_n = crop_box
        src_w, src_h = image.size
        left = max(0, min(src_w - 1, int(round(left_n * src_w))))
        top = max(0, min(src_h - 1, int(round(top_n * src_h))))
        right = max(left + 1, min(src_w, int(round(right_n * src_w))))
        bottom = max(top + 1, min(src_h, int(round(bottom_n * src_h))))
        image = image.crop((left, top, right, bottom))
    if rotate:
        image = image.rotate(int(rotate) % 360, expand=True, resample=Image.BICUBIC)

    fitted = _fit_image(image, width, height, fit)
    if blur_background and fit == "contain":
        background = _fit_image(image, width, height, "cover").filter(ImageFilter.GaussianBlur(radius=14))
        background.paste(fitted, mask=None)
        fitted = background
    return fitted


def prepare_image_for_canvas(
    input_path: str | Path,
    output_path: str | Path,
    *,
    width: int = CANVAS_WIDTH,
    height: int = CANVAS_HEIGHT,
    fit: str = "cover",
    rotate: int = 0,
    blur_background: bool = False,
    quality: int = 95,
    crop_box: tuple[float, float, float, float] | None = None,
) -> Path:
    src_path = Path(input_path).expanduser().resolve()
    dst_path = Path(output_path).expanduser().resolve()
    fitted = render_prepared_image(
        src_path,
        width=width,
        height=height,
        fit=fit,
        rotate=rotate,
        blur_background=blur_background,
        crop_box=crop_box,
    )

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = dst_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        fitted.save(dst_path, quality=max(50, min(100, int(quality))), optimize=True)
    else:
        fitted.save(dst_path)
    return dst_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare image for Trofeo LCD canvas")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--width", type=int, default=CANVAS_WIDTH)
    parser.add_argument("--height", type=int, default=CANVAS_HEIGHT)
    parser.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    parser.add_argument("--rotate", type=int, default=0)
    parser.add_argument("--blur-background", action="store_true")
    parser.add_argument("--quality", type=int, default=95)
    args = parser.parse_args()

    out = prepare_image_for_canvas(
        args.input,
        args.output,
        width=args.width,
        height=args.height,
        fit=args.fit,
        rotate=args.rotate,
        blur_background=args.blur_background,
        quality=args.quality,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
