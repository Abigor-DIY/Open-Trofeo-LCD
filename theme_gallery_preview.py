"""Preview pixmap rendering helpers for Theme Gallery."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform

from theme_json_with_comments import parse_theme_json_text

try:
    from theme_renderer import render_theme_file
except Exception:  # pragma: no cover - optional renderer in stripped environments.
    render_theme_file = None


ResolvePathFn = Callable[[str], Path]


class ThemeGalleryPreviewRenderer:
    def __init__(
        self,
        *,
        stats_provider: Any,
        resolve_path: ResolvePathFn,
    ) -> None:
        self.stats_provider = stats_provider
        self.resolve_path = resolve_path

    @property
    def has_local_theme_renderer(self) -> bool:
        return render_theme_file is not None

    def render_template_thumbnail(self, template_path: str) -> QPixmap | None:
        if render_theme_file is None:
            return None
        try:
            image = render_theme_file(template_path, stats_provider=self.stats_provider)
            try:
                raw = json.loads(Path(template_path).read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    rotation = int(raw.get("canvas", {}).get("rotation", 0)) % 360
                    if rotation:
                        image = image.rotate((-rotation) % 360, expand=True)
            except Exception:
                pass
            image.thumbnail((240, 88))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            pixmap = QPixmap()
            if pixmap.loadFromData(buffer.getvalue(), "PNG"):
                return pixmap
        except Exception:
            return None
        return None

    def upright_template_pixmap(self, pixmap: QPixmap, template_path: str) -> QPixmap:
        try:
            raw = json.loads(Path(template_path).read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                rotation = int(raw.get("canvas", {}).get("rotation", 0)) % 360
                if rotation:
                    return pixmap.transformed(QTransform().rotate((-rotation) % 360), Qt.SmoothTransformation)
        except Exception:
            pass
        return pixmap

    @staticmethod
    def render_template_placeholder(title: str, accent: str, size: QSize) -> QPixmap:
        width = max(220, int(size.width()))
        height = max(88, int(size.height()))
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#111723"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(0, 0, width, height, QColor("#111723"))
        painter.fillRect(0, 0, width, 16, QColor(accent))
        painter.fillRect(0, height - 22, width, 22, QColor("#182230"))
        painter.setPen(QColor("#2f3f58"))
        for x in range(12, width, 28):
            painter.drawLine(x, 18, x, height - 8)
        painter.setPen(QColor("#e8f1ff"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QRect(14, 24, width - 28, 24), Qt.AlignLeft | Qt.AlignVCenter, title)
        painter.setPen(QColor(accent))
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QRect(14, 50, width - 28, 18), Qt.AlignLeft | Qt.AlignVCenter, "Template")
        painter.setPen(QColor("#9fb2ca"))
        painter.drawRoundedRect(QRect(width - 84, height - 18, 68, 10), 5, 5)
        painter.end()
        return pixmap

    def runtime_theme_card_pixmap(self, item: dict[str, Any], size: QSize) -> QPixmap:
        path = str(item.get("path", "")).strip()
        theme_type = str(item.get("type", "image")).strip()
        if theme_type == "theme-doc" and render_theme_file is not None and path:
            try:
                image = render_theme_file(path, stats_provider=self.stats_provider)
                try:
                    raw = parse_theme_json_text(Path(path).read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        rotation = int(raw.get("canvas", {}).get("rotation", 0)) % 360
                        if rotation:
                            image = image.rotate((-rotation) % 360, expand=True)
                except Exception:
                    pass
                image.thumbnail((max(240, size.width()), max(92, size.height())))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                pixmap = QPixmap()
                if pixmap.loadFromData(buffer.getvalue(), "PNG"):
                    return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except Exception:
                pass
            asset_path = self.theme_card_fast_preview_asset(path)
            if asset_path:
                pixmap = QPixmap(str(asset_path))
                if not pixmap.isNull():
                    return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if path:
            resolved = self.resolve_path(path)
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self.render_template_placeholder(str(item.get("name", "Theme")), "#5ec8ff", size)

    def theme_card_fast_preview_asset(self, raw_path: str) -> Path | None:
        def _resolve_from_theme(theme_dir: Path, asset: str) -> Path:
            candidate = Path(asset).expanduser()
            if candidate.is_absolute():
                return candidate.resolve()
            theme_candidate = (theme_dir / candidate).resolve()
            if theme_candidate.exists():
                return theme_candidate
            return (Path.cwd() / candidate).resolve()

        try:
            path = self.resolve_path(str(raw_path))
            if not path.exists():
                return None
            raw = parse_theme_json_text(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            background = raw.get("background", {})
            if isinstance(background, dict):
                bg_path = str(background.get("path", "")).strip()
                if bg_path:
                    candidate = _resolve_from_theme(path.parent, bg_path)
                    if candidate.exists():
                        return candidate
            effects = raw.get("effects", {})
            animation = effects.get("animation", {}) if isinstance(effects, dict) else {}
            frames = animation.get("frame_paths", []) if isinstance(animation, dict) else []
            if isinstance(frames, list):
                for frame in frames[:8]:
                    candidate = _resolve_from_theme(path.parent, str(frame))
                    if candidate.exists():
                        return candidate
        except Exception:
            return None
        return None

    def render_theme_preview_pixmap(self, item: dict[str, Any], size: QSize) -> QPixmap:
        path = str(item.get("path", "")).strip()
        theme_name = str(item.get("name", "Theme")).strip() or "Theme"
        theme_type = str(item.get("type", "image")).strip()
        if theme_type == "theme-doc" and render_theme_file is not None and path:
            try:
                image = render_theme_file(path, stats_provider=self.stats_provider)
                try:
                    raw = parse_theme_json_text(Path(path).read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        rotation = int(raw.get("canvas", {}).get("rotation", 0)) % 360
                        if rotation:
                            image = image.rotate((-rotation) % 360, expand=True)
                except Exception:
                    pass
                image.thumbnail((max(920, size.width()), max(280, size.height())))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                pixmap = QPixmap()
                if pixmap.loadFromData(buffer.getvalue(), "PNG"):
                    return pixmap
            except Exception:
                pass
        if path:
            resolved = self.resolve_path(path)
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self.render_template_placeholder(theme_name, "#5ec8ff", size)
