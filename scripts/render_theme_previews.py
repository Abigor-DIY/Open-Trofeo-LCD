#!/usr/bin/env python3
"""Render bundled theme previews for docs and release metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_renderer import render_theme_document
from theme_schema import load_theme_document
from preview_stats import PreviewStatsProvider


PREVIEW_NAMES = {
    "PerunStatic.json": "theme-verdant-bloom.png",
    "heritage_duality.json": "theme-heritage-duality.png",
    "linux_matrix_blue.json": "theme-linux-matrix-blue.png",
    "linux_matrix_green.json": "theme-linux-matrix-green.png",
    "new_theme_minimal.json": "theme-new-theme.png",
    "theme_ttcr_import_4.json": "theme-ttcr-import.png",
}


def render_preview(theme_path: Path, out_path: Path, *, width: int | None) -> None:
    document = load_theme_document(theme_path)
    image = render_theme_document(document, base_dir=theme_path.parent, stats_provider=PreviewStatsProvider())
    if width is not None and width > 0 and image.width != width:
        height = max(1, int(round(image.height * (width / float(image.width)))))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render bundled Open Trofeo LCD theme previews.")
    parser.add_argument("--themes-dir", type=Path, default=Path("themes"))
    parser.add_argument("--out-dir", type=Path, default=Path("docs/screenshots"))
    parser.add_argument("--width", type=int, default=1920, help="Output width, preserving Trofeo aspect ratio. Use 0 for native.")
    args = parser.parse_args()

    width = None if args.width <= 0 else int(args.width)
    rendered = 0
    for theme_path in sorted(args.themes_dir.glob("*.json")):
        out_name = PREVIEW_NAMES.get(theme_path.name)
        if not out_name:
            continue
        out_path = args.out_dir / out_name
        render_preview(theme_path, out_path, width=width)
        print(f"{theme_path} -> {out_path}")
        rendered += 1
    print(f"Rendered {rendered} theme preview(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
