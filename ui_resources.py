"""Shared UI constants and lightweight resource helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImageReader, QPixmap

FONT_FAMILY_FILES = {
    "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu Serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "Liberation Sans": "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "Liberation Serif": "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
    "Liberation Mono": "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    "Noto Sans": "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "Noto Serif": "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
    "Ubuntu": "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "JetBrains Mono": "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
}

UI_THEMES = {
    "Plasma Blue": {"primary": "#1f6feb", "primary_border": "#3c86f7", "accent": "#5ec8ff"},
    "Graphite": {"primary": "#596273", "primary_border": "#7d889a", "accent": "#c7d2e2"},
    "Emerald": {"primary": "#1f8f6b", "primary_border": "#34b087", "accent": "#7bf0c9"},
}

UI_LANGUAGES = {
    "English": "en",
    "Polski": "pl",
}


def detect_app_version() -> str:
    candidates = [
        Path.cwd() / ".system-package-version",
        Path.cwd() / ".package-source-version",
        Path("/usr/share/open-trofeo-lcd/.package-source-version"),
    ]
    for path in candidates:
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if not raw:
            continue
        if raw.startswith("version="):
            raw = raw.split("=", 1)[1].strip()
        if raw.startswith("deb-"):
            raw = raw[4:]
        return raw if raw.startswith("v") else f"v{raw}"
    return "dev"


def available_font_families() -> list[str]:
    out = [name for name, path in FONT_FAMILY_FILES.items() if Path(path).exists()]
    return out or ["DejaVu Sans"]


def load_uncached_pixmap(path: str) -> QPixmap:
    """Load a pixmap from disk without relying on Qt's path-keyed pixmap cache."""
    clean_path = str(path).strip()
    if not clean_path:
        return QPixmap()
    reader = QImageReader(clean_path)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        return QPixmap()
    return QPixmap.fromImage(image)
