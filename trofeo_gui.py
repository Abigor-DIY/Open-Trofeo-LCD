#!/usr/bin/env python3
"""
Open Trofeo LCD - Qt GUI Client (Etap 2.3)

Minimal GUI over local backend API (trofeo_backend.py).
"""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime
import io
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urlparse

from animation_limits import (
    ANIMATION_FRAMES_EXTREME_WARN,
    ANIMATION_FRAMES_SOFT_WARN,
    ANIMATION_FRAMES_STRONG_WARN,
    ANIMATION_LIST_THUMB_MAX_FRAMES,
    ANIMATION_TIMELINE_THUMB_MAX_FRAMES,
    VIDEO_IMPORT_MAX_FRAMES,
)
from animation_studio import AnimationSequenceController, AnimationTimelineWidget

try:
    from PySide6.QtCore import QEasingCurve, QPoint, QRect, QSize, Qt, QTimer, Signal, QPropertyAnimation, QUrl, QEvent, QObject
    from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut, QTransform
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QCompleter,
        QColorDialog,
        QDialog,
        QFileDialog,
        QFontComboBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QInputDialog,
        QPushButton,
        QAbstractItemView,
        QScrollArea,
        QSplitter,
        QSpinBox,
        QSlider,
        QSizePolicy,
        QTabWidget,
        QGraphicsOpacityEffect,
        QGraphicsDropShadowEffect,
        QDoubleSpinBox,
        QTextEdit,
        QStyle,
        QVBoxLayout,
        QWidget,
        QMenu,
        QPlainTextEdit,
        QSystemTrayIcon,
        QToolButton,
    )
except ImportError:
    print("BŁĄD: Brak PySide6.")
    print("Użyj venv (PEP 668): scripts/setup_gui_venv.sh")
    print("albo: ~/trofeo-venv/bin/pip install PySide6")
    raise SystemExit(1)

from gauge_presets import GAUGE_PRESETS, GAUGE_PRESET_LABELS, GAUGE_PRESET_ORDER, THEME_STYLE_PRESET
from preview_stats import PreviewStatsProvider
from theme_json_with_comments import parse_theme_json_text, theme_json_documentation_preamble
from theme_schema import KNOWN_STAT_DISPLAY, KNOWN_STAT_SOURCES, ThemeDocument, normalize_theme_document, save_theme_document
from stats_sources import StatsProvider

try:
    from theme_renderer import render_theme_document, render_theme_file
except Exception:
    render_theme_document = None
    render_theme_file = None

try:
    from image_prep import prepare_image_for_canvas, render_prepared_image
except Exception:
    prepare_image_for_canvas = None
    render_prepared_image = None

try:
    from ttcr_import import import_ttcr_theme, extract_ttcr_zt_frames
except Exception:
    import_ttcr_theme = None
    extract_ttcr_zt_frames = None


LAYOUT_PRESETS_PATH = Path(".trofeo-layout-presets.json")
IMAGE_PRESETS_PATH = Path(".trofeo-image-presets.json")
THEME_AUTOSAVE_PATH = Path(".trofeo-theme-autosave.json")
UI_STATE_PATH = Path(".trofeo-ui-state.json")
TTCR_STAT_RULES_PATH = Path(".trofeo-ttcr-stat-rules.json")

# Stats whose data-source fields are shown on the inspector "Music" tab (audio / MPRIS / volume).
MUSIC_AUDIO_STAT_SOURCES: frozenset[str] = frozenset(
    {
        "volume_percent",
        "volume_state",
        "audio_eq_status",
        "audio_eq_source",
        "audio_eq_age_ms",
        "media_title",
        "media_artist",
        "media_app",
        "media_state",
    }
)
MUSIC_RELATED_IMAGE_SOURCES: frozenset[str] = frozenset({"media_cover", "media_video_frame"})
WEATHER_STAT_SOURCES: frozenset[str] = frozenset(source for source in KNOWN_STAT_SOURCES if source.startswith("weather_"))
WEATHER_RELATED_IMAGE_SOURCES: frozenset[str] = frozenset({"weather_icon"})
WEATHER_RELATED_PANEL_ID_PREFIXES: tuple[str, ...] = ("panel_weather",)
VIDEO_BACKGROUND_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"})
MUSIC_RELATED_PANEL_ID_PREFIXES: tuple[str, ...] = ("panel_media", "panel_volume", "panel_music_eq")
MUSIC_VISUAL_STAT_DISPLAYS: frozenset[str] = frozenset({"equalizer"})
DESIGNER_DOMAIN_MODES: tuple[tuple[str, str], ...] = (
    ("all", "All"),
    ("system", "System"),
    ("music", "Music"),
    ("weather", "Weather"),
)

THEME_COLOR_PRESETS = {
    "Ocean": {
        "base": [8, 18, 30],
        "accent": [42, 120, 170],
        "text": [82, 206, 255],
        "label": [225, 236, 245],
        "value": [114, 231, 255],
        "panel": [0, 0, 0],
    },
    "Amber": {
        "base": [24, 16, 8],
        "accent": [138, 78, 24],
        "text": [255, 196, 92],
        "label": [246, 236, 214],
        "value": [255, 214, 128],
        "panel": [8, 4, 0],
    },
    "Mono": {
        "base": [10, 12, 15],
        "accent": [54, 64, 76],
        "text": [226, 232, 238],
        "label": [198, 206, 216],
        "value": [244, 248, 252],
        "panel": [0, 0, 0],
    },
    "Neon": {
        "base": [8, 10, 20],
        "accent": [58, 18, 92],
        "text": [103, 255, 211],
        "label": [241, 214, 255],
        "value": [103, 255, 211],
        "panel": [0, 0, 0],
    },
}
THEME_TEMPLATE_CATALOG = [
    {
        "title": "Heritage Duality",
        "description": "Animowany motyw panoramiczny z gotowym ukladem dashboardu i widgetami.",
        "path": "themes/heritage_duality.json",
        "accent": "#59b7ff",
    },
    {
        "title": "Linux Matrix Blue",
        "description": "Statyczny motyw techniczny z czytelnymi statystykami systemu.",
        "path": "themes/linux_matrix_blue.json",
        "accent": "#8fd878",
    },
    {
        "title": "New Theme",
        "description": "Animowany motyw startowy do dalszego dopracowania w projektancie.",
        "path": "themes/new_theme_minimal.json",
        "accent": "#f1b15b",
    },
]

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
PROJECT_REPOSITORY_URL = "https://github.com/Abigor-DIY/Open-Trofeo-LCD"
PROJECT_SPONSOR_URL = "https://github.com/sponsors/Abigor-DIY"


def available_font_families() -> list[str]:
    out = [name for name, path in FONT_FAMILY_FILES.items() if Path(path).exists()]
    return out or ["DejaVu Sans"]


class PreviewLabel(QLabel):
    image_clicked = Signal(int, int)
    element_selected = Signal(str, int)
    element_moved = Signal(str, int, int, int)
    element_resized = Signal(str, int, int, int, int, int)
    elements_box_selected = Signal(object)
    crop_rect_selected = Signal(object)
    cursor_changed = Signal(object)
    drag_started = Signal()
    drag_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(680, 190)
        self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.setStyleSheet("border: 1px solid #555; background: #111;")
        self._source_pixmap: QPixmap | None = None
        self._draw_offset_x = 0
        self._draw_offset_y = 0
        self._draw_width = 0
        self._draw_height = 0
        self._canvas_size = QSize(1920, 462)
        self._display_rotation = 0
        self._elements: list[dict[str, Any]] = []
        self._selected: tuple[str, int] | None = None
        self._selected_many: set[tuple[str, int]] = set()
        self._drag_mode: str | None = None
        self._drag_origin = QPoint()
        self._drag_start_rect: tuple[int, int, int, int] | None = None
        self._had_drag_motion = False
        self._selection_origin_widget: QPoint | None = None
        self._selection_current_widget: QPoint | None = None
        self._zoom_mode = "fit"
        self._zoom_percent = 100
        self._guide_lines: list[dict[str, Any]] = []
        self._movement_badge: str = ""
        self._tool_mode = "auto"
        self._snap_threshold = 8

    def set_preview_pixmap(self, pixmap: QPixmap | None, *, display_rotation: int = 0) -> None:
        self._display_rotation = int(display_rotation) % 360
        if pixmap is not None and not pixmap.isNull() and self._display_rotation:
            transform = QTransform().rotate(self._display_rotation)
            pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self._source_pixmap = pixmap
        self._refresh_scaled_pixmap()

    def set_canvas_metadata(
        self,
        *,
        canvas_width: int,
        canvas_height: int,
        elements: list[dict[str, Any]],
        selected: list[tuple[str, int]] | tuple[str, int] | None,
    ) -> None:
        self._canvas_size = QSize(max(1, canvas_width), max(1, canvas_height))
        self._elements = elements
        normalized: list[tuple[str, int]] = []
        if isinstance(selected, tuple) and len(selected) == 2:
            normalized = [(str(selected[0]), int(selected[1]))]
        elif isinstance(selected, list):
            for entry in selected:
                if (
                    isinstance(entry, tuple)
                    and len(entry) == 2
                    and isinstance(entry[0], str)
                    and isinstance(entry[1], int)
                ):
                    normalized.append((str(entry[0]), int(entry[1])))
        self._selected = normalized[0] if normalized else None
        self._selected_many = set(normalized)
        self._guide_lines = []
        self.update()

    def set_temporary_guides(self, guides: list[object], badge: str = "") -> None:
        normalized_guides: list[dict[str, Any]] = []
        for guide in guides:
            entry = self._normalize_guide_entry(guide)
            if entry is not None:
                normalized_guides.append(entry)
        self._guide_lines = normalized_guides
        self._movement_badge = self._compose_guide_badge(badge, self._guide_lines)
        self.update()

    def clear_temporary_guides(self) -> None:
        self._guide_lines = []
        self._movement_badge = ""
        self.update()

    def set_zoom_mode(self, mode: str) -> None:
        self._zoom_mode = mode
        self._refresh_scaled_pixmap()

    def set_zoom_percent(self, percent: int) -> None:
        self._zoom_mode = "manual"
        self._zoom_percent = max(25, min(300, int(percent)))
        self._refresh_scaled_pixmap()

    def set_snap_threshold(self, value: int) -> None:
        self._snap_threshold = max(4, min(32, int(value)))

    def set_tool_mode(self, mode: str) -> None:
        normalized = str(mode).strip().lower() or "auto"
        if normalized not in {"auto", "select", "move", "scale", "crop"}:
            normalized = "auto"
        self._tool_mode = normalized
        self.setCursor(self._cursor_for_tool_or_hit(None))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._source_pixmap is None or self._draw_width <= 0 or self._draw_height <= 0:
            return
        pos = event.position().toPoint()
        local_x = pos.x() - self._draw_offset_x
        local_y = pos.y() - self._draw_offset_y
        if local_x < 0 or local_y < 0 or local_x >= self._draw_width or local_y >= self._draw_height:
            return
        src_w = max(1, self._source_pixmap.width())
        src_h = max(1, self._source_pixmap.height())
        img_x = int(round(local_x * src_w / self._draw_width))
        img_y = int(round(local_y * src_h / self._draw_height))
        img_x = max(0, min(src_w - 1, img_x))
        img_y = max(0, min(src_h - 1, img_y))
        if self._tool_mode == "crop":
            self._selection_origin_widget = pos
            self._selection_current_widget = pos
            self._drag_mode = None
            self.update()
            return
        hit = self._hit_test(event.position().toPoint())
        if self._tool_mode == "select":
            if hit is not None:
                collection, index, _mode = hit
                target = (collection, index)
                preserve_multi = target in self._selected_many and len(self._selected_many) > 1
                self._selected = target
                if not preserve_multi:
                    self._selected_many = {target}
                    self.element_selected.emit(collection, index)
                self.update()
                return
            self._selection_origin_widget = pos
            self._selection_current_widget = pos
            return
        if hit is not None:
            collection, index, mode = hit
            target = (collection, index)
            preserve_multi = target in self._selected_many and len(self._selected_many) > 1
            self._selected = target
            if not preserve_multi:
                self._selected_many = {target}
                self.element_selected.emit(collection, index)
            rect = self._element_rect_for_canvas(collection, index)
            if rect is not None:
                forced_mode = mode
                if self._tool_mode == "move":
                    forced_mode = "move"
                elif self._tool_mode == "scale":
                    if forced_mode.startswith("resize-"):
                        pass
                    else:
                        forced_mode = self._preferred_resize_mode(self._canvas_rect_to_widget_rect(rect), pos)
                self._drag_mode = forced_mode
                self._drag_origin = QPoint(img_x, img_y)
                self._drag_start_rect = rect
                self._had_drag_motion = False
                self.drag_started.emit()
            self.update()
            return
        self._selection_origin_widget = pos
        self._selection_current_widget = pos

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_mode is None or self._selected is None or self._drag_start_rect is None:
            pos = event.position().toPoint()
            if self._selection_origin_widget is not None:
                self._selection_current_widget = pos
                self.update()
            hit_mode: str | None = None
            if self._tool_mode in {"auto", "move", "scale"}:
                hit = self._hit_test(pos)
                if hit is not None:
                    hit_mode = str(hit[2])
                    if self._tool_mode == "move" and hit_mode.startswith("resize-"):
                        hit_mode = "move"
                    elif self._tool_mode == "scale" and hit_mode == "move":
                        rect = self._element_rect_for_canvas(str(hit[0]), int(hit[1]))
                        hit_mode = self._preferred_resize_mode(self._canvas_rect_to_widget_rect(rect), pos) if rect is not None else "resize-br"
            self.setCursor(self._cursor_for_tool_or_hit(hit_mode))
            self.cursor_changed.emit(img_pos if (img_pos := self._widget_to_image_point(pos)) is not None else None)
            return
        pos = event.position().toPoint()
        img_pos = self._widget_to_image_point(pos)
        if img_pos is None:
            return
        start_x, start_y, start_w, start_h = self._drag_start_rect
        dx = img_pos.x() - self._drag_origin.x()
        dy = img_pos.y() - self._drag_origin.y()
        self._had_drag_motion = self._had_drag_motion or bool(dx or dy)
        collection, index = self._selected
        self.cursor_changed.emit(img_pos)
        if self._drag_mode == "move":
            self._guide_lines = self._compute_snap_guides(start_x + dx, start_y + dy, start_w, start_h, collection, index)
            self.element_moved.emit(collection, index, start_x + dx, start_y + dy)
        elif self._drag_mode.startswith("resize"):
            next_x, next_y, next_w, next_h = self._resize_rect_from_drag(
                self._drag_mode,
                start_x,
                start_y,
                start_w,
                start_h,
                dx,
                dy,
            )
            self._guide_lines = self._compute_snap_guides(next_x, next_y, next_w, next_h, collection, index)
            self.element_resized.emit(
                collection,
                index,
                next_x,
                next_y,
                next_w,
                next_h,
            )

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.cursor_changed.emit(None)
        self.setCursor(self._cursor_for_tool_or_hit(None))
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        had_drag = self._drag_mode is not None and self._had_drag_motion
        self._drag_mode = None
        self._drag_start_rect = None
        self._had_drag_motion = False
        self._guide_lines = []
        if had_drag:
            self.drag_finished.emit()
        elif self._selection_origin_widget is not None and self._selection_current_widget is not None:
            selection_rect = QRect(self._selection_origin_widget, self._selection_current_widget).normalized()
            if selection_rect.width() >= 8 or selection_rect.height() >= 8:
                if self._tool_mode == "crop":
                    start_img = self._widget_to_image_point(self._selection_origin_widget)
                    end_img = self._widget_to_image_point(self._selection_current_widget)
                    if start_img is not None and end_img is not None:
                        left = min(start_img.x(), end_img.x())
                        top = min(start_img.y(), end_img.y())
                        right = max(start_img.x(), end_img.x())
                        bottom = max(start_img.y(), end_img.y())
                        if right - left >= 4 and bottom - top >= 4:
                            self.crop_rect_selected.emit((left, top, right, bottom))
                else:
                    selected = self._elements_in_widget_rect(selection_rect)
                    if selected:
                        self.elements_box_selected.emit(selected)
            else:
                img_pos = self._widget_to_image_point(event.position().toPoint())
                if img_pos is not None:
                    self.image_clicked.emit(img_pos.x(), img_pos.y())
        self._selection_origin_widget = None
        self._selection_current_widget = None
        self.cursor_changed.emit(None)
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self._draw_width <= 0 or self._draw_height <= 0 or not self._elements:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            for item in self._elements:
                if not bool(item.get("visible", True)):
                    continue
                rect = self._canvas_rect_to_widget_rect(item["rect"])
                if rect.width() <= 0 or rect.height() <= 0:
                    continue
                key = (str(item["collection"]), int(item["index"]))
                is_selected = key in self._selected_many or self._selected == key
                color = "#888888" if bool(item.get("locked", False)) else ("#5ec8ff" if is_selected else "#ffb347")
                pen = QPen(QColor(color))
                pen.setWidth(2 if is_selected else 1)
                painter.setPen(pen)
                painter.drawRect(rect)
                painter.drawText(rect.topLeft() + QPoint(4, 14), str(item["label"]))
                if is_selected:
                    self._paint_selection_handles(painter, rect, key == self._selected)
            if len(self._selected_many) > 1:
                group_rect = self._group_bounds_rect()
                if group_rect is not None:
                    painter.setPen(QPen(QColor("#5ec8ff"), 1, Qt.DashLine))
                    painter.drawRoundedRect(group_rect.adjusted(-8, -8, 8, 8), 10, 10)
                    painter.drawText(group_rect.topLeft() + QPoint(6, -6), "Group")
            if self._selection_origin_widget is not None and self._selection_current_widget is not None:
                select_rect = QRect(self._selection_origin_widget, self._selection_current_widget).normalized()
                painter.setPen(QPen(QColor("#89ddff"), 1, Qt.DashLine))
                painter.fillRect(select_rect, QColor(94, 200, 255, 36))
                painter.drawRect(select_rect)
            if self._guide_lines:
                guide_pen = QPen(QColor("#45d0ff"), 1, Qt.DashLine)
                painter.setPen(guide_pen)
                for guide in self._guide_lines:
                    axis = str(guide.get("axis", ""))
                    value = int(guide.get("value", 0))
                    if axis == "x":
                        x = self._draw_offset_x + int(round(value * self._draw_width / max(1, self._canvas_size.width())))
                        painter.drawLine(x, self._draw_offset_y, x, self._draw_offset_y + self._draw_height)
                        self._paint_guide_label(painter, QPoint(x + 6, self._draw_offset_y + 24), str(guide.get("label", value)))
                    else:
                        y = self._draw_offset_y + int(round(value * self._draw_height / max(1, self._canvas_size.height())))
                        painter.drawLine(self._draw_offset_x, y, self._draw_offset_x + self._draw_width, y)
                        self._paint_guide_label(painter, QPoint(self._draw_offset_x + 30, y - 6), str(guide.get("label", value)))
            if self._movement_badge:
                badge_rect = QRect(self._draw_offset_x + 18, self._draw_offset_y + 22, 180, 34)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(12, 18, 28, 220))
                painter.drawRoundedRect(badge_rect, 8, 8)
                painter.setPen(QColor("#7dd3fc"))
                painter.drawText(badge_rect.adjusted(12, 0, -12, 0), Qt.AlignVCenter | Qt.AlignLeft, self._movement_badge)
            self._paint_rulers(painter)
        finally:
            painter.end()

    def _widget_to_image_point(self, pos: QPoint) -> QPoint | None:
        local_x = pos.x() - self._draw_offset_x
        local_y = pos.y() - self._draw_offset_y
        if local_x < 0 or local_y < 0 or local_x >= self._draw_width or local_y >= self._draw_height:
            return None
        src_w = max(1, self._canvas_size.width())
        src_h = max(1, self._canvas_size.height())
        img_x = int(round(local_x * src_w / self._draw_width))
        img_y = int(round(local_y * src_h / self._draw_height))
        return QPoint(max(0, min(src_w - 1, img_x)), max(0, min(src_h - 1, img_y)))

    def _canvas_rect_to_widget_rect(self, rect: tuple[int, int, int, int]) -> QRect:
        src_w = max(1, self._canvas_size.width())
        src_h = max(1, self._canvas_size.height())
        x, y, w, h = rect
        wx = self._draw_offset_x + int(round(x * self._draw_width / src_w))
        wy = self._draw_offset_y + int(round(y * self._draw_height / src_h))
        ww = max(1, int(round(w * self._draw_width / src_w)))
        wh = max(1, int(round(h * self._draw_height / src_h)))
        return QRect(wx, wy, ww, wh)

    def _resize_handle_rects(self, rect: QRect) -> dict[str, QRect]:
        size = 12
        center_x = rect.center().x()
        center_y = rect.center().y()
        return {
            "resize-tl": QRect(rect.left() - size // 2, rect.top() - size // 2, size, size),
            "resize-t": QRect(center_x - size // 2, rect.top() - size // 2, size, size),
            "resize-tr": QRect(rect.right() - size // 2, rect.top() - size // 2, size, size),
            "resize-l": QRect(rect.left() - size // 2, center_y - size // 2, size, size),
            "resize-r": QRect(rect.right() - size // 2, center_y - size // 2, size, size),
            "resize-bl": QRect(rect.left() - size // 2, rect.bottom() - size // 2, size, size),
            "resize-b": QRect(center_x - size // 2, rect.bottom() - size // 2, size, size),
            "resize-br": QRect(rect.right() - size // 2, rect.bottom() - size // 2, size, size),
        }

    def _paint_selection_handles(self, painter: QPainter, rect: QRect, active: bool) -> None:
        fill = QColor("#5ec8ff" if active else "#cfeeff")
        outline = QColor("#0f172a")
        painter.setPen(QPen(outline, 1))
        painter.setBrush(fill)
        for handle in self._resize_handle_rects(rect).values():
            painter.drawRect(handle)

    def _preferred_resize_mode(self, rect: QRect, pos: QPoint) -> str:
        edge_band = max(10, min(rect.width(), rect.height()) // 4)
        near_left = abs(pos.x() - rect.left()) <= edge_band
        near_right = abs(pos.x() - rect.right()) <= edge_band
        near_top = abs(pos.y() - rect.top()) <= edge_band
        near_bottom = abs(pos.y() - rect.bottom()) <= edge_band
        if near_top and not (near_left or near_right):
            return "resize-t"
        if near_bottom and not (near_left or near_right):
            return "resize-b"
        if near_left and not (near_top or near_bottom):
            return "resize-l"
        if near_right and not (near_top or near_bottom):
            return "resize-r"
        horizontal = "l" if pos.x() <= rect.center().x() else "r"
        vertical = "t" if pos.y() <= rect.center().y() else "b"
        return f"resize-{vertical}{horizontal}"

    def _resize_rect_from_drag(
        self,
        mode: str,
        x: int,
        y: int,
        width: int,
        height: int,
        dx: int,
        dy: int,
    ) -> tuple[int, int, int, int]:
        left = x
        top = y
        right = x + width
        bottom = y + height
        if "l" in mode:
            left += dx
        if "r" in mode:
            right += dx
        if "t" in mode:
            top += dy
        if "b" in mode:
            bottom += dy
        min_size = 1
        if right - left < min_size:
            if "l" in mode:
                left = right - min_size
            else:
                right = left + min_size
        if bottom - top < min_size:
            if "t" in mode:
                top = bottom - min_size
            else:
                bottom = top + min_size
        return int(left), int(top), int(right - left), int(bottom - top)

    def _cursor_for_tool_or_hit(self, hit_mode: str | None) -> Qt.CursorShape:
        if hit_mode:
            if hit_mode in {"resize-tl", "resize-br"}:
                return Qt.SizeFDiagCursor
            if hit_mode in {"resize-tr", "resize-bl"}:
                return Qt.SizeBDiagCursor
            if hit_mode in {"resize-l", "resize-r"}:
                return Qt.SizeHorCursor
            if hit_mode in {"resize-t", "resize-b"}:
                return Qt.SizeVerCursor
            if hit_mode == "move":
                return Qt.SizeAllCursor
        if self._tool_mode == "move":
            return Qt.SizeAllCursor
        if self._tool_mode == "scale":
            return Qt.SizeFDiagCursor
        if self._tool_mode == "crop":
            return Qt.CrossCursor
        return Qt.ArrowCursor

    def _group_bounds_rect(self) -> QRect | None:
        selected_rects: list[QRect] = []
        for item in self._elements:
            key = (str(item["collection"]), int(item["index"]))
            if key not in self._selected_many:
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            if rect.width() > 0 and rect.height() > 0:
                selected_rects.append(rect)
        if not selected_rects:
            return None
        group_rect = QRect(selected_rects[0])
        for rect in selected_rects[1:]:
            group_rect = group_rect.united(rect)
        return group_rect

    def _normalize_guide_entry(self, guide: object) -> dict[str, Any] | None:
        if isinstance(guide, dict):
            axis = str(guide.get("axis", "")).strip().lower()
            if axis not in {"x", "y"}:
                return None
            try:
                value = int(guide.get("value", 0))
            except Exception:
                return None
            label = str(guide.get("label", value)).strip() or str(value)
            return {"axis": axis, "value": value, "label": label}
        if isinstance(guide, tuple) and len(guide) >= 2:
            axis = str(guide[0]).strip().lower()
            if axis not in {"x", "y"}:
                return None
            try:
                value = int(guide[1])
            except Exception:
                return None
            label = str(guide[2]).strip() if len(guide) >= 3 else str(value)
            return {"axis": axis, "value": value, "label": label or str(value)}
        return None

    def _compose_guide_badge(self, badge: str, guides: list[dict[str, Any]]) -> str:
        labels: list[str] = []
        seen: set[str] = set()
        for guide in guides:
            label = str(guide.get("label", "")).strip()
            if not label or label in seen:
                continue
            labels.append(label)
            seen.add(label)
            if len(labels) >= 2:
                break
        if not labels:
            return badge
        suffix = " • ".join(labels)
        return f"{badge} • {suffix}" if badge else suffix

    def _paint_guide_label(self, painter: QPainter, anchor: QPoint, text: str) -> None:
        if not text:
            return
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text) + 12
        text_height = metrics.height() + 4
        rect = QRect(anchor.x(), anchor.y(), text_width, text_height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(12, 18, 28, 220))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor("#7dd3fc"))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _hit_test(self, pos: QPoint) -> tuple[str, int, str] | None:
        for item in reversed(self._elements):
            if not bool(item.get("visible", True)):
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            for handle_name, handle_rect in self._resize_handle_rects(rect).items():
                if handle_rect.contains(pos):
                    return item["collection"], item["index"], handle_name
            hit_rect = rect.adjusted(-8, -8, 8, 8)
            if hit_rect.contains(pos):
                return item["collection"], item["index"], "move"
        return None

    def _element_rect_for_canvas(self, collection: str, index: int) -> tuple[int, int, int, int] | None:
        for item in self._elements:
            if item["collection"] == collection and item["index"] == index:
                return item["rect"]
        return None

    def _elements_in_widget_rect(self, selection_rect: QRect) -> list[tuple[str, int]]:
        selected: list[tuple[str, int]] = []
        for item in self._elements:
            if not bool(item.get("visible", True)):
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            if selection_rect.intersects(rect):
                selected.append((str(item["collection"]), int(item["index"])))
        return selected

    def _compute_snap_guides(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        collection: str,
        index: int,
    ) -> list[dict[str, Any]]:
        guides: list[dict[str, Any]] = []
        current_x = [("left", x), ("center", x + w // 2), ("right", x + w)]
        current_y = [("top", y), ("center", y + h // 2), ("bottom", y + h)]
        safe_left = 24
        safe_right = max(0, self._canvas_size.width() - 24)
        safe_top = 18
        safe_bottom = max(0, self._canvas_size.height() - 18)
        canvas_guides_x = [
            (self._canvas_size.width() // 2, "canvas center"),
            (safe_left, "safe left"),
            (safe_right, "safe right"),
        ]
        canvas_guides_y = [
            (self._canvas_size.height() // 2, "canvas middle"),
            (safe_top, "safe top"),
            (safe_bottom, "safe bottom"),
        ]
        threshold = max(4, int(getattr(self, "_snap_threshold", 8)))
        for _edge, cx in current_x:
            for ox, label in canvas_guides_x:
                if abs(cx - ox) <= threshold:
                    guides.append({"axis": "x", "value": ox, "label": label})
        for _edge, cy in current_y:
            for oy, label in canvas_guides_y:
                if abs(cy - oy) <= threshold:
                    guides.append({"axis": "y", "value": oy, "label": label})
        for item in self._elements:
            if item["collection"] == collection and int(item["index"]) == index:
                continue
            if not bool(item.get("visible", True)):
                continue
            rx, ry, rw, rh = item["rect"]
            other_label = str(item.get("label", item.get("collection", "element"))).strip()[:18]
            other_x = [
                (rx, f"{other_label} left"),
                (rx + rw // 2, f"{other_label} center"),
                (rx + rw, f"{other_label} right"),
            ]
            other_y = [
                (ry, f"{other_label} top"),
                (ry + rh // 2, f"{other_label} middle"),
                (ry + rh, f"{other_label} bottom"),
            ]
            for _edge, cx in current_x:
                for ox, label in other_x:
                    if abs(cx - ox) <= threshold:
                        guides.append({"axis": "x", "value": ox, "label": label})
                        break
            for _edge, cy in current_y:
                for oy, label in other_y:
                    if abs(cy - oy) <= threshold:
                        guides.append({"axis": "y", "value": oy, "label": label})
                        break
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for item in guides:
            key = (str(item.get("axis", "")), int(item.get("value", 0)))
            if key not in seen:
                unique.append(item)
                seen.add(key)
        return unique

    def _paint_rulers(self, painter: QPainter) -> None:
        if self._draw_width <= 0 or self._draw_height <= 0:
            return
        painter.setPen(QPen(QColor("#344255"), 1))
        painter.fillRect(QRect(self._draw_offset_x, self._draw_offset_y, self._draw_width, 18), QColor(15, 20, 28, 190))
        painter.fillRect(QRect(self._draw_offset_x, self._draw_offset_y, 26, self._draw_height), QColor(15, 20, 28, 190))
        step_x = max(60, self._canvas_size.width() // 8)
        step_y = max(40, self._canvas_size.height() // 6)
        for x in range(0, self._canvas_size.width() + 1, step_x):
            wx = self._draw_offset_x + int(round(x * self._draw_width / max(1, self._canvas_size.width())))
            painter.drawLine(wx, self._draw_offset_y, wx, self._draw_offset_y + 10)
            painter.drawText(wx + 2, self._draw_offset_y + 14, str(x))
        for y in range(0, self._canvas_size.height() + 1, step_y):
            wy = self._draw_offset_y + int(round(y * self._draw_height / max(1, self._canvas_size.height())))
            painter.drawLine(self._draw_offset_x, wy, self._draw_offset_x + 10, wy)
            painter.drawText(self._draw_offset_x + 12, wy - 2, str(y))

    def _refresh_scaled_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            self.clear()
            self._draw_offset_x = 0
            self._draw_offset_y = 0
            self._draw_width = 0
            self._draw_height = 0
            return
        if self._zoom_mode == "fit":
            scaled = self._source_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            width = max(1, int(self._source_pixmap.width() * self._zoom_percent / 100))
            height = max(1, int(self._source_pixmap.height() * self._zoom_percent / 100))
            scaled = self._source_pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self._draw_width = scaled.width()
        self._draw_height = scaled.height()
        self._draw_offset_x = max(0, (self.width() - self._draw_width) // 2)
        self._draw_offset_y = 0 if self._zoom_mode == "fit" else max(0, (self.height() - self._draw_height) // 2)
        self.update()


class LcdPreviewScrollArea(QScrollArea):
    """Scroll area that keeps the LCD preview at the physical 1920x462 aspect."""

    LCD_WIDTH = 1920
    LCD_HEIGHT = 462

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(160)
        self.setMaximumHeight(330)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_aspect_height()

    def _sync_aspect_height(self) -> None:
        width = max(1, self.viewport().width() or self.width())
        target = int(round(width * self.LCD_HEIGHT / self.LCD_WIDTH)) + 2
        target = max(160, min(330, target))
        if self.minimumHeight() != target or self.maximumHeight() != target:
            self.setMinimumHeight(target)
            self.setMaximumHeight(target)


class LayerListWidget(QListWidget):
    rows_reordered = Signal()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        super().dropEvent(event)
        self.rows_reordered.emit()


class LayerRowWidget(QWidget):
    visibility_toggled = Signal()
    lock_toggled = Signal()
    activated = Signal(object)

    def __init__(
        self,
        *,
        title: str,
        subtitle: str = "",
        icon: QIcon,
        visible: bool,
        locked: bool,
        accent: str = "#cfd7e6",
        thumbnail: QPixmap | None = None,
    ) -> None:
        super().__init__()
        self._selected = False
        self._raw_title = title
        self._raw_subtitle = subtitle
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(6)
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(16, 16))
        layout.addWidget(icon_label)
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(42, 28)
        self.thumb_label.setStyleSheet("background: #0f1319; border: 1px solid #314055; border-radius: 8px;")
        if thumbnail is not None and not thumbnail.isNull():
            self.thumb_label.setPixmap(thumbnail.scaled(42, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.thumb_label)
        self.badge_label = QLabel()
        self.badge_label.setObjectName("layerBadgeLabel")
        layout.addWidget(self.badge_label)
        text_stack = QVBoxLayout()
        text_stack.setContentsMargins(0, 0, 0, 0)
        text_stack.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("layerTitleLabel")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("layerSubtitleLabel")
        self.title_label.setWordWrap(False)
        self.subtitle_label.setWordWrap(False)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.subtitle_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_stack.addWidget(self.title_label)
        text_stack.addWidget(self.subtitle_label)
        self._accent = accent
        self._collection = ""
        layout.addLayout(text_stack, 1)
        self.eye_btn = QToolButton()
        self.eye_btn.setCheckable(True)
        self.eye_btn.setChecked(bool(visible))
        self._visible_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)
        self._hidden_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        self.eye_btn.setIcon(self._visible_icon if visible else self._hidden_icon)
        self.eye_btn.setText("")
        self.eye_btn.setToolTip("Pokaż / Ukryj")
        self.eye_btn.setFixedWidth(22)
        self.lock_btn = QToolButton()
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(bool(locked))
        self.lock_btn.setText("L" if locked else "E")
        self.lock_btn.setToolTip("Blokuj / Odblokuj")
        self.lock_btn.setFixedWidth(22)
        layout.addWidget(self.eye_btn)
        layout.addWidget(self.lock_btn)
        self.eye_btn.clicked.connect(self._emit_visibility)
        self.lock_btn.clicked.connect(self._emit_lock)
        self.setMinimumHeight(50)
        self.set_title(title)
        self.set_subtitle(subtitle)
        self.set_thumbnail(thumbnail)
        self.set_locked(bool(locked))
        self.set_selected(False)

    def set_title(self, title: str) -> None:
        self._raw_title = title
        badge = ""
        rest = title
        if title.startswith("[") and "]" in title:
            badge, rest = title.split("]", 1)
            badge = badge.lstrip("[")
            rest = rest.strip()
        self.badge_label.setText(badge)
        self.badge_label.setVisible(bool(badge))
        self._collection = badge
        self._update_elided_labels()

    def set_visible_state(self, visible: bool) -> None:
        self.eye_btn.setChecked(bool(visible))
        self.eye_btn.setIcon(self._visible_icon if visible else self._hidden_icon)
        self.eye_btn.setText("")

    def set_subtitle(self, subtitle: str) -> None:
        self._raw_subtitle = subtitle
        self._update_elided_labels()

    def _update_elided_labels(self) -> None:
        title_text = ""
        if self._raw_title.startswith("[") and "]" in self._raw_title:
            _badge, title_text = self._raw_title.split("]", 1)
            title_text = title_text.strip()
        else:
            title_text = self._raw_title
        chrome = 112 if self.thumb_label.isVisible() else 74
        if self.badge_label.isVisible():
            chrome += max(26, self.badge_label.sizeHint().width())
        available = max(110, self.width() - chrome)
        self.title_label.setText(self.title_label.fontMetrics().elidedText(title_text or self._raw_title, Qt.ElideRight, available))
        text = self._raw_subtitle.strip()
        self.subtitle_label.setVisible(bool(text))
        self.subtitle_label.setText(self.subtitle_label.fontMetrics().elidedText(text, Qt.ElideRight, available))

    def set_locked(self, locked: bool) -> None:
        self.lock_btn.setChecked(bool(locked))
        self.lock_btn.setText("🔒" if locked else "🔓")
        self.title_label.setStyleSheet(f"color: {'#8a94a6' if locked else self._accent};")
        self.subtitle_label.setStyleSheet(f"color: {'#657287' if locked else '#8da0b8'};")

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.setStyleSheet(
            "background: #273347; border: 1px solid #4b84f6; border-radius: 12px;"
            if self._selected
            else "background: rgba(18, 24, 32, 0.45); border: 1px solid rgba(68, 86, 112, 0.45); border-radius: 12px;"
        )

    def set_thumbnail(self, thumbnail: QPixmap | None) -> None:
        if thumbnail is not None and not thumbnail.isNull():
            self.thumb_label.setPixmap(thumbnail.scaled(42, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.thumb_label.setStyleSheet("background: #0f1319; border: 1px solid #314055; border-radius: 6px;")
            self.thumb_label.setAlignment(Qt.AlignCenter)
            self.thumb_label.setText("")
            self.thumb_label.show()
        elif self._collection in {"TXT", "STA", "PNL"}:
            label_map = {"TXT": ("T", "#3a2648"), "STA": ("S", "#20394e"), "PNL": ("P", "#233129")}
            self.thumb_label.setPixmap(QPixmap())
            letter, bg = label_map.get(self._collection, ("", "#1b2430"))
            self.thumb_label.setText(letter)
            self.thumb_label.setAlignment(Qt.AlignCenter)
            self.thumb_label.setStyleSheet(f"background: {bg}; border: 1px solid #314055; border-radius: 6px; color: #f4f8ff; font-weight: 700;")
            self.thumb_label.show()
        else:
            self.thumb_label.setPixmap(QPixmap())
            self.thumb_label.setText("")
            self.thumb_label.hide()
        self._update_elided_labels()

    def _emit_visibility(self) -> None:
        self.set_visible_state(self.eye_btn.isChecked())
        self.visibility_toggled.emit()

    def _emit_lock(self) -> None:
        self.set_locked(self.lock_btn.isChecked())
        self.lock_toggled.emit()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.activated.emit(event.modifiers())
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_elided_labels()


class AnimatedCardFrame(QFrame):
    def __init__(self, object_name: str = "animatedCard") -> None:
        super().__init__()
        self.setObjectName(object_name)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(20)
        self._shadow.setColor(QColor(0, 0, 0, 0))
        self._shadow.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._shadow.setColor(QColor(0, 0, 0, 80))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._shadow.setColor(QColor(0, 0, 0, 0))
        super().leaveEvent(event)


class AnimatedToolbarButton(QPushButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._hovered = False
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0.0)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(94, 200, 255, 0))
        self.setGraphicsEffect(self._shadow)
        self._blur_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._blur_anim.setDuration(160)
        self._blur_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._offset_anim = QPropertyAnimation(self._shadow, b"offset", self)
        self._offset_anim.setDuration(160)
        self._offset_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setCursor(Qt.PointingHandCursor)
        self.pressed.connect(self._animate_pressed)

    def setCheckable(self, checkable: bool) -> None:  # type: ignore[override]
        already = self.isCheckable()
        super().setCheckable(checkable)
        if checkable and not already:
            self.toggled.connect(lambda _checked: self._sync_shadow_state())

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = True
        self._sync_shadow_state()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = False
        self._sync_shadow_state()
        super().leaveEvent(event)

    def _animate_pressed(self) -> None:
        self._shadow.setColor(QColor(94, 200, 255, 150))
        self._blur_anim.stop()
        self._blur_anim.setStartValue(float(self._shadow.blurRadius()))
        self._blur_anim.setEndValue(22.0)
        self._blur_anim.start()
        self._offset_anim.stop()
        self._offset_anim.setStartValue(self._shadow.offset())
        self._offset_anim.setEndValue(QPoint(0, 1))
        self._offset_anim.start()

    def _sync_shadow_state(self) -> None:
        active = self._hovered or self.isDown() or self.isChecked()
        checked = self.isCheckable() and self.isChecked()
        color = QColor(31, 111, 235, 170 if checked else 120) if active else QColor(94, 200, 255, 0)
        target_blur = 18.0 if checked else (14.0 if active else 0.0)
        target_offset = QPoint(0, 2) if checked else (QPoint(0, 1) if active else QPoint(0, 0))
        self._shadow.setColor(color)
        self._blur_anim.stop()
        self._blur_anim.setStartValue(float(self._shadow.blurRadius()))
        self._blur_anim.setEndValue(target_blur)
        self._blur_anim.start()
        self._offset_anim.stop()
        self._offset_anim.setStartValue(self._shadow.offset())
        self._offset_anim.setEndValue(target_offset)
        self._offset_anim.start()


class TTCRImportReviewDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        theme_name: str,
        stat_sources: list[str],
        stat_entries: list[dict[str, Any]],
        unmapped_stats: list[Any],
        reference_image_path: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sprawdź statystyki po imporcie TTCR")
        self.resize(860, 620)
        self._rows: list[tuple[int, QComboBox, str]] = []
        self._remember_rules_chk = QCheckBox("Zapamiętaj te mapowania dla kolejnych importów TTCR")
        self._remember_rules_chk.setChecked(True)
        self._reference_pixmap = QPixmap(reference_image_path) if reference_image_path else QPixmap()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro = QLabel(
            f"Zaimportowano motyw: <b>{theme_name}</b>.<br>"
            "Sprawdź mapowanie statystyk TTCR na źródła Linux i popraw je w razie potrzeby."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_host = QWidget()
        rows_layout = QVBoxLayout(scroll_host)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(8)

        if stat_entries:
            grouped: dict[str, list[tuple[int, dict[str, str]]]] = {}
            for idx, entry in enumerate(stat_entries):
                current_source = str(entry.get("source", "")).strip()
                category = self._group_name_for_source(current_source)
                grouped.setdefault(category, []).append((idx, entry))
            for category, entries in grouped.items():
                category_box = QGroupBox(category)
                category_layout = QVBoxLayout(category_box)
                category_layout.setContentsMargins(10, 10, 10, 10)
                category_layout.setSpacing(8)
                for idx, entry in entries:
                    row_box = QGroupBox(f"Statystyka {idx + 1}")
                    row_layout = QHBoxLayout(row_box)
                    row_layout.setContentsMargins(12, 12, 12, 12)
                    row_layout.setSpacing(12)
                    preview = QLabel()
                    preview.setFixedSize(180, 72)
                    preview.setObjectName("templateCardThumb")
                    preview.setAlignment(Qt.AlignCenter)
                    self._fill_preview_crop(preview, entry)
                    row_layout.addWidget(preview, 0)
                    fields_box = QWidget()
                    fields_layout = QFormLayout(fields_box)
                    fields_layout.setContentsMargins(0, 0, 0, 0)
                    fields_layout.setSpacing(8)
                    fields_layout.addRow("Etykieta TTCR", QLabel(str(entry.get("label", "")).strip() or "-"))
                    pos_text = (
                        f"x={int(entry.get('x', 0) or 0)}, y={int(entry.get('y', 0) or 0)}"
                        f" • {int(entry.get('box_width', 0) or 0)}×{int(entry.get('box_height', 0) or 0)}"
                    )
                    pos_label = QLabel(pos_text)
                    pos_label.setWordWrap(True)
                    fields_layout.addRow("Pozycja / rozmiar", pos_label)
                    combo = QComboBox()
                    combo.addItems(stat_sources)
                    current_source = str(entry.get("source", "")).strip()
                    if current_source in stat_sources:
                        combo.setCurrentText(current_source)
                    fields_layout.addRow("Źródło Linux", combo)
                    row_layout.addWidget(fields_box, 1)
                    category_layout.addWidget(row_box)
                    self._rows.append((idx, combo, str(entry.get("label", "")).strip()))
                rows_layout.addWidget(category_box)
        else:
            empty = QLabel("Importer nie znalazł jednoznacznych statystyk do edycji.")
            empty.setWordWrap(True)
            rows_layout.addWidget(empty)

        if unmapped_stats:
            unmapped_box = QGroupBox("Do ręcznej korekty")
            unmapped_layout = QVBoxLayout(unmapped_box)
            hint = QLabel(
                "Poniższe etykiety wyglądały jak statystyki TTCR. Możesz od razu przypisać im źródło Linux albo zostawić do późniejszej ręcznej edycji:"
            )
            hint.setWordWrap(True)
            unmapped_layout.addWidget(hint)
            for offset, entry in enumerate(unmapped_stats[:12], start=len(self._rows)):
                raw_entry = entry if isinstance(entry, dict) else {"label": str(entry)}
                row_box = QGroupBox(f"Niezmapowana statystyka {offset + 1}")
                row_layout = QHBoxLayout(row_box)
                row_layout.setContentsMargins(12, 12, 12, 12)
                row_layout.setSpacing(12)
                preview = QLabel()
                preview.setFixedSize(180, 72)
                preview.setObjectName("templateCardThumb")
                preview.setAlignment(Qt.AlignCenter)
                self._fill_preview_crop(preview, raw_entry)
                row_layout.addWidget(preview, 0)
                fields_box = QWidget()
                fields_layout = QFormLayout(fields_box)
                fields_layout.setContentsMargins(0, 0, 0, 0)
                fields_layout.setSpacing(8)
                label_text = str(raw_entry.get("label", "")).strip() or "-"
                fields_layout.addRow("Etykieta TTCR", QLabel(label_text))
                pos_text = (
                    f"x={int(raw_entry.get('x', 0) or 0)}, y={int(raw_entry.get('y', 0) or 0)}"
                    f" • {int(raw_entry.get('box_width', 0) or 0)}×{int(raw_entry.get('box_height', 0) or 0)}"
                )
                pos_label = QLabel(pos_text)
                pos_label.setWordWrap(True)
                fields_layout.addRow("Pozycja / rozmiar", pos_label)
                combo = QComboBox()
                combo.addItem("Pomiń", "")
                combo.addItems(stat_sources)
                fields_layout.addRow("Źródło Linux", combo)
                row_layout.addWidget(fields_box, 1)
                unmapped_layout.addWidget(row_box)
                self._rows.append((offset, combo, label_text))
            if len(unmapped_stats) > 12:
                more = QLabel(f"... i jeszcze {len(unmapped_stats) - 12}.")
                unmapped_layout.addWidget(more)
            rows_layout.addWidget(unmapped_box)

        rows_layout.addStretch(1)
        scroll.setWidget(scroll_host)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._remember_rules_chk)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Pomiń")
        accept_btn = QPushButton("Zastosuj mapowanie")
        accept_btn.setObjectName("primaryButton")
        cancel_btn.clicked.connect(self.reject)
        accept_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(accept_btn)
        layout.addLayout(buttons)

    def selected_sources(self) -> list[tuple[int, str, str]]:
        out: list[tuple[int, str, str]] = []
        for idx, combo, label in self._rows:
            source = combo.currentText().strip()
            source_data = str(combo.currentData() if combo.currentData() is not None else source).strip()
            if source_data:
                out.append((idx, source_data, label))
        return out

    def remember_rules(self) -> bool:
        return self._remember_rules_chk.isChecked()

    def _group_name_for_source(self, source: str) -> str:
        lowered = source.lower()
        if lowered.startswith("cpu_") or lowered == "load_average":
            return "CPU"
        if lowered.startswith("gpu_") or lowered.startswith("vram_"):
            return "GPU"
        if lowered.startswith("mem_"):
            return "Pamięć"
        if lowered.startswith("disk_"):
            return "Dysk"
        if lowered.startswith("net_") or lowered == "ip_local":
            return "Sieć"
        if lowered.startswith("time_") or lowered.startswith("date_") or lowered.startswith("uptime_"):
            return "Czas"
        if lowered.startswith("host"):
            return "System"
        return "Inne"

    def _fill_preview_crop(self, label: QLabel, entry: dict[str, Any]) -> None:
        if self._reference_pixmap.isNull():
            label.setText("Brak podglądu")
            return
        x = max(0, int(entry.get("x", 0) or 0))
        y = max(0, int(entry.get("y", 0) or 0))
        w = max(80, int(entry.get("box_width", 0) or 160))
        h = max(40, int(entry.get("box_height", 0) or 56))
        pad_x = max(40, w // 3)
        pad_y = max(24, h // 2)
        crop = self._reference_pixmap.copy(
            max(0, x - pad_x),
            max(0, y - pad_y),
            min(self._reference_pixmap.width() - max(0, x - pad_x), w + pad_x * 2),
            min(self._reference_pixmap.height() - max(0, y - pad_y), h + pad_y * 2),
        )
        if crop.isNull():
            label.setText("Brak podglądu")
            return
        label.setPixmap(crop.scaled(label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))


class ImageCropLabel(QLabel):
    crop_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(860, 220)
        self.setStyleSheet("border: 1px solid #3a4250; background: #0f1319;")
        self._source_pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self._draw_offset_x = 0
        self._draw_offset_y = 0
        self._draw_width = 0
        self._draw_height = 0
        self._selection_start: QPoint | None = None
        self._selection_end: QPoint | None = None
        self._crop_rect = QRect()
        self._aspect_ratio: float | None = None
        self._drag_mode: str | None = None
        self._pan_offset = QPoint(0, 0)
        self._panning = False

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap
        self._update_scaled()

    def crop_box(self) -> tuple[float, float, float, float] | None:
        if self._source_pixmap is None or self._crop_rect.isNull() or self._draw_width <= 0 or self._draw_height <= 0:
            return None
        rect = self._crop_rect.normalized()
        left = max(0.0, min(1.0, (rect.left() - self._draw_offset_x) / self._draw_width))
        top = max(0.0, min(1.0, (rect.top() - self._draw_offset_y) / self._draw_height))
        right = max(0.0, min(1.0, (rect.right() - self._draw_offset_x) / self._draw_width))
        bottom = max(0.0, min(1.0, (rect.bottom() - self._draw_offset_y) / self._draw_height))
        if right - left < 0.01 or bottom - top < 0.01:
            return None
        return (left, top, right, bottom)

    def clear_crop(self) -> None:
        self._selection_start = None
        self._selection_end = None
        self._crop_rect = QRect()
        self.crop_changed.emit(None)
        self.update()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self._source_pixmap is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.1 if delta > 0 else 0.9
        if self._scaled_pixmap is not None:
            new_w = max(120, int(self._scaled_pixmap.width() * factor))
            new_h = max(80, int(self._scaled_pixmap.height() * factor))
            self._scaled_pixmap = self._source_pixmap.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(self._scaled_pixmap)
            self._draw_width = self._scaled_pixmap.width()
            self._draw_height = self._scaled_pixmap.height()
            self.update()

    def set_locked_aspect_ratio(self, width: int | None, height: int | None) -> None:
        if width and height and width > 0 and height > 0:
            self._aspect_ratio = float(width) / float(height)
        else:
            self._aspect_ratio = None

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_scaled()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._source_pixmap is None:
            return
        pos = event.position().toPoint()
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._selection_start = pos
            return
        handle = self._hit_handle(pos)
        if handle is not None:
            self._drag_mode = handle
            self._selection_start = pos
            self._selection_end = pos
            return
        self._drag_mode = "new"
        self._selection_start = pos
        self._selection_end = self._selection_start
        self._crop_rect = QRect(self._selection_start, self._selection_end).normalized()
        self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._selection_start is None:
            return
        pos = event.position().toPoint()
        if self._panning:
            delta = pos - self._selection_start
            self._pan_offset += delta
            self._selection_start = pos
            self.update()
            return
        if self._drag_mode == "new":
            self._selection_end = pos
            self._crop_rect = self._build_crop_rect(self._selection_start, self._selection_end)
        else:
            self._crop_rect = self._adjust_existing_crop(pos)
        self.crop_changed.emit(self.crop_box())
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._selection_start is None:
            return
        pos = event.position().toPoint()
        if self._panning:
            self._panning = False
            self._selection_start = None
            return
        if self._drag_mode == "new":
            self._selection_end = pos
            self._crop_rect = self._build_crop_rect(self._selection_start, self._selection_end)
        else:
            self._crop_rect = self._adjust_existing_crop(pos)
        self._drag_mode = None
        self._selection_start = None
        self._selection_end = None
        self.crop_changed.emit(self.crop_box())
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self._crop_rect.isNull():
            return
        painter = QPainter(self)
        try:
            painter.setPen(QPen(QColor("#89ddff"), 2, Qt.DashLine))
            painter.fillRect(self._crop_rect, QColor(94, 200, 255, 36))
            painter.drawRect(self._crop_rect)
            for handle in self._handle_rects().values():
                painter.fillRect(handle, QColor("#89ddff"))
        finally:
            painter.end()

    def _update_scaled(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            self.clear()
            self._scaled_pixmap = None
            return
        scaled = self._source_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._scaled_pixmap = scaled
        self.setPixmap(scaled)
        self._draw_width = scaled.width()
        self._draw_height = scaled.height()
        self._draw_offset_x = max(0, (self.width() - self._draw_width) // 2)
        self._draw_offset_y = max(0, (self.height() - self._draw_height) // 2)
        self._draw_offset_x += self._pan_offset.x()
        self._draw_offset_y += self._pan_offset.y()
        self.update()

    def _build_crop_rect(self, start: QPoint, end: QPoint) -> QRect:
        if self._aspect_ratio is None:
            return QRect(start, end).normalized()
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if dx == 0 and dy == 0:
            return QRect(start, end).normalized()
        sign_x = 1 if dx >= 0 else -1
        sign_y = 1 if dy >= 0 else -1
        abs_dx = abs(dx)
        abs_dy = abs(dy)
        target_h = int(round(abs_dx / self._aspect_ratio)) if self._aspect_ratio else abs_dy
        target_w = int(round(abs_dy * self._aspect_ratio)) if self._aspect_ratio else abs_dx
        if target_h <= abs_dy:
            width = abs_dx
            height = target_h
        else:
            width = target_w
            height = abs_dy
        adjusted = QPoint(start.x() + sign_x * width, start.y() + sign_y * height)
        return QRect(start, adjusted).normalized()

    def _handle_rects(self) -> dict[str, QRect]:
        rect = self._crop_rect.normalized()
        if rect.isNull():
            return {}
        size = 10
        return {
            "tl": QRect(rect.left() - size // 2, rect.top() - size // 2, size, size),
            "tr": QRect(rect.right() - size // 2, rect.top() - size // 2, size, size),
            "bl": QRect(rect.left() - size // 2, rect.bottom() - size // 2, size, size),
            "br": QRect(rect.right() - size // 2, rect.bottom() - size // 2, size, size),
        }

    def _hit_handle(self, pos: QPoint) -> str | None:
        for name, rect in self._handle_rects().items():
            if rect.contains(pos):
                return name
        return None

    def _adjust_existing_crop(self, pos: QPoint) -> QRect:
        rect = self._crop_rect.normalized()
        if rect.isNull() or self._drag_mode is None:
            return rect
        if self._drag_mode == "tl":
            start = rect.bottomRight()
        elif self._drag_mode == "tr":
            start = rect.bottomLeft()
        elif self._drag_mode == "bl":
            start = rect.topRight()
        else:
            start = rect.topLeft()
        return self._build_crop_rect(start, pos)


class ImagePrepDialog(QDialog):
    PRESETS = {
        "Wallpaper": {"fit": "cover", "rotate": 0, "blur": False},
        "Banner": {"fit": "stretch", "rotate": 0, "blur": False},
        "Photo Left": {"fit": "contain", "rotate": 0, "blur": True},
        "Full Background": {"fit": "cover", "rotate": 0, "blur": False},
    }

    def __init__(
        self,
        parent: QWidget | None,
        source_path: Path,
        *,
        suggested_output_path: Path | None = None,
        accept_button_text: str = "Zapisz jako...",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import obrazu do motywu")
        self.resize(1040, 720)
        self.setMinimumSize(920, 640)
        self.source_path = source_path
        self.output_path: Path | None = None
        self.suggested_output_path = suggested_output_path
        self._user_presets = self._load_user_presets()
        self._crop_box: tuple[float, float, float, float] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        info = QLabel(
            f"Źródło: {source_path}\n"
            "Przygotuj obraz pod LCD 1920x462 i sprawdź wynik przed zapisaniem."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        controls = QHBoxLayout()
        self.preset_combo = QComboBox()
        self._rebuild_preset_combo()
        self.save_preset_btn = QPushButton("Zapisz preset")
        self.delete_preset_btn = QPushButton("Usuń preset")
        self.fit_combo = QComboBox()
        self.fit_combo.addItems(["cover", "contain", "stretch"])
        self.rotate_spin = QSpinBox()
        self.rotate_spin.setRange(0, 359)
        self.rotate_spin.setSingleStep(90)
        self.blur_chk = QCheckBox("Blur background dla contain")
        self.lock_ratio_chk = QCheckBox("Zachowaj proporcję 1920:462")
        self.lock_ratio_chk.setChecked(True)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(50, 100)
        self.quality_spin.setValue(95)
        controls.addWidget(QLabel("Preset:"))
        controls.addWidget(self.preset_combo)
        controls.addWidget(self.save_preset_btn)
        controls.addWidget(self.delete_preset_btn)
        controls.addWidget(QLabel("Fit:"))
        controls.addWidget(self.fit_combo)
        controls.addWidget(QLabel("Rotate:"))
        controls.addWidget(self.rotate_spin)
        controls.addWidget(self.blur_chk)
        controls.addWidget(self.lock_ratio_chk)
        controls.addWidget(QLabel("JPEG quality:"))
        controls.addWidget(self.quality_spin)
        controls.addStretch(1)
        root.addLayout(controls)

        root.addWidget(QLabel("Kadr źródłowy"))
        self.crop_label = ImageCropLabel()
        self.crop_label.crop_changed.connect(self.on_crop_changed)
        root.addWidget(self.crop_label, 1)

        root.addWidget(QLabel("Podgląd wynikowy"))
        self.preview_label = QLabel("Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(860, 220)
        self.preview_label.setStyleSheet("border: 1px solid #3a4250; background: #0f1319;")
        root.addWidget(self.preview_label, 1)

        actions = QHBoxLayout()
        self.clear_crop_btn = QPushButton("Wyczyść kadr")
        self.save_as_btn = QPushButton(accept_button_text)
        self.cancel_btn = QPushButton("Anuluj")
        actions.addStretch(1)
        actions.addWidget(self.clear_crop_btn)
        actions.addWidget(self.save_as_btn)
        actions.addWidget(self.cancel_btn)
        root.addLayout(actions)

        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        self.save_preset_btn.clicked.connect(self.save_user_preset)
        self.delete_preset_btn.clicked.connect(self.delete_user_preset)
        self.fit_combo.currentTextChanged.connect(self.refresh_preview)
        self.rotate_spin.valueChanged.connect(self.refresh_preview)
        self.blur_chk.toggled.connect(self.refresh_preview)
        self.lock_ratio_chk.toggled.connect(self.on_lock_ratio_toggled)
        self.clear_crop_btn.clicked.connect(self.clear_crop)
        self.save_as_btn.clicked.connect(self.save_as)
        self.cancel_btn.clicked.connect(self.reject)

        self.apply_preset(self.preset_combo.currentText())
        self._load_source_preview()
        self.on_lock_ratio_toggled(self.lock_ratio_chk.isChecked())

    def _rebuild_preset_combo(self) -> None:
        current = getattr(self, "preset_combo", None)
        current_text = current.currentText() if current is not None else ""
        if current is None:
            return
        current.blockSignals(True)
        current.clear()
        for name in self.PRESETS:
            current.addItem(name)
        for name in sorted(self._user_presets):
            current.addItem(f"User: {name}")
        if current_text:
            current.setCurrentText(current_text)
        current.blockSignals(False)

    def _load_user_presets(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(IMAGE_PRESETS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            pass
        return {}

    def _save_user_presets(self) -> None:
        IMAGE_PRESETS_PATH.write_text(
            json.dumps(self._user_presets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def apply_preset(self, preset_name: str) -> None:
        preset = self.PRESETS.get(preset_name)
        if preset is None and preset_name.startswith("User: "):
            preset = self._user_presets.get(preset_name.replace("User: ", "", 1))
        if not preset:
            return
        self.fit_combo.setCurrentText(str(preset["fit"]))
        self.rotate_spin.setValue(int(preset["rotate"]))
        self.blur_chk.setChecked(bool(preset["blur"]))
        if "quality" in preset:
            self.quality_spin.setValue(int(preset["quality"]))
        self.refresh_preview()

    def save_user_preset(self) -> None:
        preset_name, ok = QInputDialog.getText(
            self,
            "Nazwa presetu",
            "Podaj nazwę własnego presetu importu:",
        )
        if not ok:
            return
        preset_name = preset_name.strip()
        if not preset_name:
            return
        self._user_presets[preset_name] = {
            "fit": self.fit_combo.currentText(),
            "rotate": int(self.rotate_spin.value()),
            "blur": bool(self.blur_chk.isChecked()),
            "quality": int(self.quality_spin.value()),
        }
        self._save_user_presets()
        self._rebuild_preset_combo()
        self.preset_combo.setCurrentText(f"User: {preset_name}")

    def delete_user_preset(self) -> None:
        current = self.preset_combo.currentText()
        if not current.startswith("User: "):
            QMessageBox.information(self, "Preset", "Możesz usunąć tylko własny preset.")
            return
        name = current.replace("User: ", "", 1)
        self._user_presets.pop(name, None)
        self._save_user_presets()
        self._rebuild_preset_combo()
        self.preset_combo.setCurrentText(next(iter(self.PRESETS.keys())))

    def _render_preview_pixmap(self) -> QPixmap | None:
        if render_prepared_image is None:
            return None
        try:
            image = render_prepared_image(
                self.source_path,
                width=1920,
                height=462,
                fit=self.fit_combo.currentText(),
                rotate=int(self.rotate_spin.value()),
                blur_background=bool(self.blur_chk.isChecked()),
                crop_box=self._crop_box,
            )
            preview = image.copy()
            preview.thumbnail((920, 240))
            buffer = io.BytesIO()
            preview.save(buffer, format="PNG")
            pixmap = QPixmap()
            if pixmap.loadFromData(buffer.getvalue(), "PNG"):
                return pixmap
        except Exception:
            return None
        return None

    def _load_source_preview(self) -> None:
        pixmap = QPixmap(str(self.source_path))
        if pixmap.isNull():
            self.crop_label.setText("Nie udało się wczytać obrazu źródłowego.")
            return
        self.crop_label.set_source_pixmap(pixmap)

    def on_crop_changed(self, crop_box: object) -> None:
        self._crop_box = crop_box if isinstance(crop_box, tuple) else None
        self.refresh_preview()

    def on_lock_ratio_toggled(self, checked: bool) -> None:
        self.crop_label.set_locked_aspect_ratio(1920, 462) if checked else self.crop_label.set_locked_aspect_ratio(None, None)

    def clear_crop(self) -> None:
        self._crop_box = None
        self.crop_label.clear_crop()
        self.refresh_preview()

    def refresh_preview(self) -> None:
        pixmap = self._render_preview_pixmap()
        if pixmap is None or pixmap.isNull():
            self.preview_label.setText("Nie udało się wygenerować preview.")
            self.preview_label.setPixmap(QPixmap())
            return
        self.preview_label.setText("")
        self.preview_label.setPixmap(pixmap)

    def save_as(self) -> None:
        if self.suggested_output_path is not None:
            out_path = str(self.suggested_output_path)
        else:
            suggested = self.source_path.with_name(f"{self.source_path.stem}_trofeo.jpg")
            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Zapisz przygotowany obraz",
                str(suggested),
                "JPEG (*.jpg *.jpeg);;PNG (*.png)",
            )
            if not out_path:
                return
        try:
            out = prepare_image_for_canvas(
                self.source_path,
                out_path,
                width=1920,
                height=462,
                fit=self.fit_combo.currentText(),
                rotate=int(self.rotate_spin.value()),
                blur_background=bool(self.blur_chk.isChecked()),
                quality=int(self.quality_spin.value()),
                crop_box=self._crop_box,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Błąd obrazu", str(exc))
            return
        self.output_path = out
        self.accept()


class ThemePreviewDialog(QDialog):
    def __init__(self, theme_name: str, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Podgląd motywu - {theme_name}")
        self.resize(1320, 620)
        self.setMinimumSize(980, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        title = QLabel(theme_name)
        title.setObjectName("libraryCardTitle")
        root.addWidget(title)

        hint = QLabel("Powiększony podgląd motywu. Jeśli obraz jest szerszy, możesz przewinąć obszar.")
        hint.setObjectName("libraryCardMeta")
        hint.setWordWrap(True)
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumHeight(360)
        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(max(920, pixmap.width()), max(260, pixmap.height()))
        preview.setPixmap(pixmap)
        scroll.setWidget(preview)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        root.addLayout(actions)


class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        data = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(self._url(path), data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            err_text = body
            try:
                decoded = json.loads(body) if body else {}
                if isinstance(decoded, dict) and "error" in decoded:
                    err_text = str(decoded["error"])
            except Exception:
                pass
            raise RuntimeError(f"HTTP {exc.code}: {err_text}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Połączenie nieudane: {exc}") from exc
        except socket.timeout as exc:
            raise RuntimeError("Request timeout") from exc


class TrofeoGui(QMainWindow):
    api_result = Signal(str, bool, object)
    weather_city_search_finished = Signal(list, str)

    def __init__(self, base_url: str):
        super().__init__()
        self._ui_language = "en"
        self.setWindowTitle("Open Trofeo LCD[*]")
        self.resize(1680, 1040)
        self.setMinimumSize(1480, 920)
        self._status_in_flight = False
        self.theme_items: dict[str, dict[str, Any]] = {}
        self.theme_doc_model: dict[str, Any] | None = None
        self._theme_doc_dirty = False
        self._theme_doc_editor_syncing = False
        self.theme_stat_sources = sorted(KNOWN_STAT_SOURCES)
        self._designer_updating = False
        self.layout_presets: dict[str, Any] = {}
        self.designer_clipboard: list[tuple[str, dict[str, Any]]] = []
        self.designer_cross_selection: list[tuple[str, int]] = []
        self._designer_selection_group_label = ""
        self._tray_icon: QSystemTrayIcon | None = None
        self._close_to_tray_enabled = True
        self._tray_message_shown = False
        self._template_cards: list[dict[str, Any]] = []
        self._template_thumb_map: dict[str, QLabel] = {}
        self._log_entries: list[str] = []
        self._max_log_entries = 1500
        self._log_refresh_pending = False
        self._startup_theme_name = ""
        self._startup_theme_applied = False
        self._history_undo: list[dict[str, Any]] = []
        self._history_redo: list[dict[str, Any]] = []
        self._history_suspended = False
        self._designer_drag_active = False
        self._animation_syncing_from_timeline = False
        self._animation_studio_built = False
        self._animation_studio_shortcuts: list[QShortcut] = []
        self._preview_stats_provider = PreviewStatsProvider()
        self._animation_export_in_flight = False
        self._animation_import_in_flight = False
        self._animation_duplicate_in_flight = False
        self._animation_stabilize_in_flight = False
        self._animation_export_cancel_event: threading.Event | None = None
        self._animation_import_cancel_event: threading.Event | None = None
        self._animation_worker_states: dict[str, str] = {}
        self._animation_thumbnail_generation = 0
        self._animation_thumbnail_in_flight = False
        self._animation_thumbnail_pending_jobs: dict[tuple[str, int], dict[str, Any]] = {}
        self._image_thumbnail_cache: dict[tuple[str, int], QPixmap] = {}
        self._preview_request_in_flight = False
        self._preview_request_queued = False
        self._preview_request_seq = 0
        self._preview_request_active_seq = 0
        self._runtime_theme_cards_dirty = True
        self._library_theme_browser_dirty = True
        self._asset_gallery_dirty = True
        self._initial_theme_data_loaded = False
        self.preview_debounce = QTimer(self)
        self.preview_debounce.setSingleShot(True)
        self.preview_debounce.timeout.connect(self.preview_theme_doc)
        self.autosave_debounce = QTimer(self)
        self.autosave_debounce.setSingleShot(True)
        self.autosave_debounce.timeout.connect(self._write_theme_autosave)
        self.animation_preview_timer = QTimer(self)
        self.animation_preview_timer.timeout.connect(self._advance_animation_preview)
        self._animation_preview_active = False
        self._weather_search_target = "config"
        self._weather_config_restored_to_backend = False

        self.client = BackendClient(base_url=base_url)
        self._build_ui(base_url)
        self._update_theme_doc_save_state()
        self._restore_ui_state()
        self._setup_shortcuts()
        self._setup_tray()
        self.apply_ui_chrome()
        self.api_result.connect(self._on_api_result)
        self.weather_city_search_finished.connect(self._finish_weather_city_search)
        QTimer.singleShot(750, self._apply_restored_weather_config_to_backend)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(1500)

        self.refresh_status()
        QTimer.singleShot(150, self.refresh_themes)
        QTimer.singleShot(300, self.refresh_playlist)
        QTimer.singleShot(450, self.refresh_theme_schema)
        self._load_layout_presets()
        QTimer.singleShot(650, self._refresh_template_cards)
        self.suggest_new_theme_path_from_template()
        restored_autosave = self._restore_theme_autosave()
        if not restored_autosave and Path(self.theme_doc_path_edit.text().strip()).exists():
            QTimer.singleShot(850, self.load_theme_doc)
        # Always start on dashboard/system view.
        self._go_system()
        self._show_onboarding_once()

    def _create_stat_pill(self, label: str, initial_value: str = "-") -> tuple[QWidget, QLabel]:
        frame = QFrame()
        frame.setObjectName("statPillFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        lbl = QLabel(label)
        lbl.setObjectName("statPillLabel")
        val = QLabel(initial_value)
        val.setObjectName("statPillValue")
        val.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(lbl)
        layout.addWidget(val)
        return frame, val

    def _show_stat_picker_menu(self, target_edit: QLineEdit) -> None:
        menu = QMenu(self)
        for group_name, stats in self._designer_source_groups(self._designer_domain_mode()):
            submenu = menu.addMenu(group_name)
            for s in stats:
                if s in self.theme_stat_sources:
                    action = submenu.addAction(self._humanize_stat_source(s))
                    action.triggered.connect(lambda _, st=s: target_edit.insert(f"{{{st}}}"))

        menu.exec(QCursor.pos())

    def _humanize_stat_source(self, source: str) -> str:
        custom = {
            "hostname": "Computer Name",
            "ip_local": "Local IP Address",
            "time_hms": "Current Time (HH:MM:SS)",
            "date_ymd": "Current Date (YYYY-MM-DD)",
            "uptime_human": "System Uptime",
            "cpu_usage_percent": "CPU Usage (%)",
            "cpu_core_avg_percent": "CPU Core Average (%)",
            "cpu_core_max_percent": "CPU Core Peak (%)",
            "cpu_core_count": "CPU Core Count",
            "cpu_freq_ghz": "CPU Frequency (GHz)",
            "cpu_temp_c": "CPU Temperature (C)",
            "load_average": "System Load Average",
            "gpu_name": "GPU Name",
            "gpu_temp": "GPU Temperature (C)",
            "gpu_load": "GPU Usage (%)",
            "vram_percent": "VRAM Usage (%)",
            "vram_used_mb": "VRAM Used (MB)",
            "vram_total_mb": "VRAM Total (MB)",
            "mem_percent": "RAM Usage (%)",
            "mem_used_mb": "RAM Used (MB)",
            "mem_total_mb": "RAM Total (MB)",
            "disk_percent": "Disk Usage (%)",
            "disk_used_gb": "Disk Used (GB)",
            "disk_total_gb": "Disk Total (GB)",
            "net_dl_kbps": "Network Download (kbps)",
            "net_ul_kbps": "Network Upload (kbps)",
            "volume_percent": "Audio Volume (%)",
            "volume_state": "Audio Volume State",
            "audio_eq_bars": "Audio EQ Bars",
            "audio_eq_raw_bars": "Audio EQ Raw Bars",
            "audio_eq_source": "Audio EQ Source",
            "audio_eq_status": "Audio EQ Status",
            "audio_eq_age_ms": "Audio EQ Age (ms)",
            "media_title": "Now Playing: Title",
            "media_artist": "Now Playing: Artist",
            "media_app": "Now Playing: App",
            "media_state": "Now Playing: State",
            "weather_location": "Weather: Location",
            "weather_temp_c": "Weather: Temperature (C)",
            "weather_feels_like_c": "Weather: Feels Like (C)",
            "weather_humidity_percent": "Weather: Humidity (%)",
            "weather_wind_kph": "Weather: Wind (km/h)",
            "weather_precip_mm": "Weather: Precipitation (mm)",
            "weather_cloud_percent": "Weather: Cloud Cover (%)",
            "weather_condition": "Weather: Condition",
            "weather_icon": "Weather: Icon Name",
            "weather_is_day": "Weather: Day/Night",
        }
        if source in custom:
            return custom[source]
        return source.replace("_", " ").title()

    def _is_music_stat_source(self, source: str) -> bool:
        return str(source).strip().lower() in MUSIC_AUDIO_STAT_SOURCES

    def _is_weather_stat_source(self, source: str) -> bool:
        return str(source).strip().lower().startswith("weather_")

    def _designer_domain_mode(self) -> str:
        combo = getattr(self, "designer_domain_combo", None)
        if combo is None:
            return "all"
        return str(combo.currentData() or "all").strip().lower() or "all"

    def _designer_source_groups(self, domain: str = "all") -> list[tuple[str, list[str]]]:
        domain_key = str(domain).strip().lower() or "all"
        music_groups = [
            ("Music / Now Playing", ["media_title", "media_artist", "media_app", "media_state"]),
            ("Audio / Volume", ["volume_percent", "volume_state"]),
            ("Audio / EQ", ["audio_eq_status", "audio_eq_source", "audio_eq_age_ms"]),
        ]
        system_groups = [
            ("System", ["hostname", "ip_local", "time_hms", "date_ymd", "uptime_human"]),
            ("CPU", ["cpu_usage_percent", "cpu_core_avg_percent", "cpu_core_max_percent", "cpu_freq_ghz", "cpu_temp_c", "load_average"]),
            ("GPU", ["gpu_name", "gpu_temp", "gpu_load", "vram_percent", "vram_used_mb", "vram_total_mb"]),
            ("Memory", ["mem_percent", "mem_used_mb", "mem_total_mb"]),
            ("Disk", ["disk_percent", "disk_used_gb", "disk_total_gb"]),
            ("Network", ["net_dl_kbps", "net_ul_kbps"]),
        ]
        weather_groups = [
            (
                "Weather",
                [
                    "weather_location", "weather_temp_c", "weather_feels_like_c",
                    "weather_humidity_percent", "weather_wind_kph", "weather_precip_mm",
                    "weather_cloud_percent", "weather_condition", "weather_icon",
                ],
            ),
            (
                "Weather / 7-day forecast",
                [
                    "weather_day_0_label", "weather_day_0_temp_max_c", "weather_day_0_temp_min_c", "weather_day_0_condition",
                    "weather_day_1_label", "weather_day_1_temp_max_c", "weather_day_1_temp_min_c", "weather_day_1_condition",
                    "weather_day_2_label", "weather_day_2_temp_max_c", "weather_day_2_temp_min_c", "weather_day_2_condition",
                    "weather_day_3_label", "weather_day_3_temp_max_c", "weather_day_3_temp_min_c", "weather_day_3_condition",
                    "weather_day_4_label", "weather_day_4_temp_max_c", "weather_day_4_temp_min_c", "weather_day_4_condition",
                    "weather_day_5_label", "weather_day_5_temp_max_c", "weather_day_5_temp_min_c", "weather_day_5_condition",
                    "weather_day_6_label", "weather_day_6_temp_max_c", "weather_day_6_temp_min_c", "weather_day_6_condition",
                ],
            ),
        ]
        if domain_key == "music":
            return music_groups
        if domain_key == "system":
            return system_groups
        if domain_key == "weather":
            return weather_groups
        return music_groups + system_groups + weather_groups

    def _populate_designer_source_combo(self, selected_source: str = "") -> None:
        if not hasattr(self, "designer_source_combo"):
            return
        self.designer_source_combo.blockSignals(True)
        self.designer_source_combo.clear()
        model = self.designer_source_combo.model()
        groups = self._designer_source_groups(self._designer_domain_mode())
        first_group = True
        for group_name, stats in groups:
            available = [source for source in stats if source in self.theme_stat_sources]
            if not available:
                continue
            if not first_group:
                self.designer_source_combo.insertSeparator(self.designer_source_combo.count())
            first_group = False
            header_index = self.designer_source_combo.count()
            self.designer_source_combo.addItem(f"── {group_name} ──", f"__header__:{group_name}")
            try:
                header_item = model.item(header_index)
                if header_item is not None:
                    header_item.setEnabled(False)
            except Exception:
                pass
            for source in available:
                self.designer_source_combo.addItem(self._humanize_stat_source(source), source)
        if selected_source:
            idx = self.designer_source_combo.findData(selected_source)
            if idx >= 0:
                self.designer_source_combo.setCurrentIndex(idx)
        elif self.designer_source_combo.count() > 0:
            for idx in range(self.designer_source_combo.count()):
                data = str(self.designer_source_combo.itemData(idx) or "")
                if not data.startswith("__header__:"):
                    self.designer_source_combo.setCurrentIndex(idx)
                    break
        self.designer_source_combo.blockSignals(False)

    def _populate_weather_source_combo(self, selected_source: str = "") -> None:
        combo = getattr(self, "weather_source_combo", None)
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        for group_name, sources in self._designer_source_groups("weather"):
            combo.addItem(f"── {group_name} ──", f"__header__:{group_name}")
            header_idx = combo.count() - 1
            try:
                combo.model().item(header_idx).setEnabled(False)
            except Exception:
                pass
            for source in sources:
                combo.addItem(self._humanize_stat_source(source), source)
        idx = combo.findData(selected_source)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _on_weather_source_changed(self, _idx: int) -> None:
        if self._designer_updating:
            return
        source = str(self.weather_source_combo.currentData() or "").strip()
        if not source or source.startswith("__header__:"):
            return
        idx = self.designer_source_combo.findData(source)
        if idx >= 0:
            self.designer_source_combo.setCurrentIndex(idx)
        self.apply_designer_changes()

    def _on_weather_format_changed(self, _idx: int) -> None:
        if self._designer_updating:
            return
        fmt = str(self.weather_format_combo.currentData() or "{value}").strip() or "{value}"
        self.designer_format_edit.setText(fmt)
        self.apply_designer_changes()

    def _build_designer_content_row(self, label: str, edit: QLineEdit, has_picker: bool = True) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(edit, 1)
        if has_picker:
            btn = QPushButton("📊")
            btn.setFixedWidth(36)
            btn.setToolTip("Wstaw statystykę")
            btn.clicked.connect(lambda: self._show_stat_picker_menu(edit))
            layout.addWidget(btn)
        return row

    def _create_dashboard_status_row(self, label: str, value: str = "-") -> tuple[QWidget, QLabel, QLabel]:
        frame = QFrame()
        frame.setObjectName("statPillFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        title = QLabel(label)
        title.setObjectName("statPillLabel")
        current = QLabel(value)
        current.setObjectName("statPillValue")
        current.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, 1)
        layout.addWidget(current)
        return frame, title, current

    def _set_dashboard_badge(self, label: QLabel, text: str, tone: str = "neutral") -> None:
        palette = {
            "ok": ("#0f2f1d", "#4ade80", "#1b5e34"),
            "warn": ("#37270d", "#facc15", "#6b4f16"),
            "error": ("#35161a", "#f87171", "#6b1f27"),
            "info": ("#13293d", "#7dd3fc", "#164e63"),
            "neutral": ("#111827", "#e2e8f0", "#334155"),
        }
        bg, fg, border = palette.get(tone, palette["neutral"])
        label.setText(text)
        label.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 6px 12px; font-weight: 800;"
        )

    def _create_system_metric_card(self, title: str, value: str = "-", detail: str = "-") -> tuple[QFrame, QLabel, QLabel, QLabel]:
        card = AnimatedCardFrame("assetCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("templateCardTitle")
        title_lbl.setAlignment(Qt.AlignCenter)
        value_lbl = QLabel(value)
        value_lbl.setObjectName("statPillValue")
        value_lbl.setAlignment(Qt.AlignCenter)
        detail_lbl = QLabel(detail)
        detail_lbl.setObjectName("templateCardMeta")
        detail_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)
        layout.addStretch(1)
        layout.addWidget(value_lbl)
        layout.addWidget(detail_lbl)
        layout.addStretch(1)
        return card, title_lbl, value_lbl, detail_lbl

    def _format_duration_human(self, seconds: float | int | None) -> str:
        if seconds is None:
            return "-"
        total = int(max(0, float(seconds)))
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days:
            return f"{days}d {hours}h {minutes}m"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def _read_system_uptime(self) -> str:
        try:
            raw = Path("/proc/uptime").read_text(encoding="utf-8").split()[0]
            return self._format_duration_human(float(raw))
        except Exception:
            return "-"

    def _read_memory_snapshot(self) -> tuple[str, str]:
        try:
            meminfo: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0])
            total = meminfo.get("MemTotal", 0) / 1024
            avail = meminfo.get("MemAvailable", 0) / 1024
            used = max(0.0, total - avail)
            percent = int(round((used / total) * 100)) if total else 0
            return f"{percent}%", f"{used/1024:.1f} / {total/1024:.1f} GB"
        except Exception:
            return "N/A", "-"

    def _read_disk_snapshot(self) -> tuple[str, str]:
        try:
            usage = shutil.disk_usage(Path.cwd())
            total = usage.total / (1024 ** 3)
            used = usage.used / (1024 ** 3)
            percent = int(round((usage.used / usage.total) * 100)) if usage.total else 0
            return f"{percent}%", f"{used:.1f} / {total:.1f} GB"
        except Exception:
            return "N/A", "-"

    def _read_cpu_snapshot(self) -> tuple[str, str]:
        try:
            load1 = os.getloadavg()[0]
            cpus = os.cpu_count() or 1
            percent = int(max(0, min(100, round((load1 / cpus) * 100))))
            return f"{percent}%", f"{load1:.2f} load / {cpus} rdzeni"
        except Exception:
            return "N/A", "-"

    def _read_temperature_snapshot(self) -> tuple[str, str]:
        thermal_roots = [
            Path("/sys/class/thermal/thermal_zone0/temp"),
            Path("/sys/class/hwmon/hwmon0/temp1_input"),
        ]
        for path in thermal_roots:
            try:
                raw = path.read_text(encoding="utf-8").strip()
                value = float(raw) / 1000.0
                return f"{value:.0f}°C", path.parent.name
            except Exception:
                continue
        return "N/A", "-"

    def _sync_config_ui_controls_from_header(self) -> None:
        if not hasattr(self, "cfg_ui_theme_combo"):
            return
        if getattr(self, "cfg_ui_theme_combo", None) is getattr(self, "ui_theme_combo", None):
            return
        pairs = [
            (self.cfg_ui_theme_combo, getattr(self, "ui_theme_combo", None), "currentText"),
            (self.cfg_ui_mode_combo, getattr(self, "ui_mode_combo", None), "currentText"),
        ]
        for target, source, accessor in pairs:
            if source is None:
                continue
            target.blockSignals(True)
            target.setCurrentText(getattr(source, accessor)())
            target.blockSignals(False)
        if hasattr(self, "cfg_ui_scale_combo") and hasattr(self, "ui_scale_combo"):
            self.cfg_ui_scale_combo.blockSignals(True)
            self.cfg_ui_scale_combo.setCurrentIndex(self.ui_scale_combo.currentIndex())
            self.cfg_ui_scale_combo.blockSignals(False)

    def _apply_configuration_preferences(self) -> None:
        if hasattr(self, "cfg_ui_theme_combo"):
            self.ui_theme_combo.setCurrentText(self.cfg_ui_theme_combo.currentText())
        if hasattr(self, "cfg_ui_mode_combo"):
            self.ui_mode_combo.setCurrentText(self.cfg_ui_mode_combo.currentText())
        if hasattr(self, "cfg_ui_scale_combo"):
            self.ui_scale_combo.setCurrentIndex(self.cfg_ui_scale_combo.currentIndex())
        self.apply_ui_chrome()
        if hasattr(self, "cfg_weather_lat_edit"):
            self.apply_weather_config()
        if hasattr(self, "cfg_audio_eq_input_combo"):
            self.apply_audio_eq_config()
        self._save_ui_state()
        self.append_log("[config] Zastosowano ustawienia interfejsu.")

    def _weather_config_payload(self) -> dict[str, object]:
        return {
            "weather_lat": self.cfg_weather_lat_edit.text().strip() if hasattr(self, "cfg_weather_lat_edit") else "",
            "weather_lon": self.cfg_weather_lon_edit.text().strip() if hasattr(self, "cfg_weather_lon_edit") else "",
            "weather_location": self.cfg_weather_location_edit.text().strip() if hasattr(self, "cfg_weather_location_edit") else "",
            "weather_refresh_s": int(self.cfg_weather_refresh_spin.value()) if hasattr(self, "cfg_weather_refresh_spin") else 900,
        }

    def apply_weather_config(self) -> None:
        if not hasattr(self, "cfg_weather_lat_edit"):
            return
        payload = self._weather_config_payload()
        self.api_call("config", "POST", "/v1/config", payload)
        self._weather_config_restored_to_backend = True
        self._save_ui_state()
        self.append_log("[weather] Applied weather configuration.")

    def _apply_restored_weather_config_to_backend(self) -> None:
        if self._weather_config_restored_to_backend or not hasattr(self, "cfg_weather_lat_edit"):
            return
        payload = self._weather_config_payload()
        if not str(payload.get("weather_lat", "")).strip() or not str(payload.get("weather_lon", "")).strip():
            return
        self._weather_config_restored_to_backend = True
        self.api_call("config", "POST", "/v1/config", payload)
        self.append_log("[weather] Restored saved weather configuration.")

    def refresh_weather_now(self) -> None:
        if not hasattr(self, "cfg_weather_lat_edit"):
            return
        payload = self._weather_config_payload()
        payload["weather_refresh_now"] = True
        self.api_call("config", "POST", "/v1/config", payload)
        self.append_log("[weather] Forced weather refresh.")

    def _audio_eq_config_payload(self) -> dict[str, object]:
        input_combo = getattr(self, "cfg_audio_eq_input_combo", None)
        profile_combo = getattr(self, "cfg_audio_eq_profile_combo", None)
        sensitivity_spin = getattr(self, "cfg_audio_eq_sensitivity_spin", None)
        method = str(input_combo.currentData() if input_combo is not None else "auto").strip() or "auto"
        profile = str(profile_combo.currentData() if profile_combo is not None else "responsive").strip() or "responsive"
        sensitivity = float(sensitivity_spin.value()) / 100.0 if sensitivity_spin is not None else 1.0
        return {"audio_eq_input": method, "audio_eq_profile": profile, "audio_eq_sensitivity": sensitivity}

    def apply_audio_eq_config(self) -> None:
        if not hasattr(self, "cfg_audio_eq_input_combo"):
            return
        self.api_call("config", "POST", "/v1/config", self._audio_eq_config_payload())
        self._audio_eq_config_dirty = False
        self._save_ui_state()
        self.append_log("[audio-eq] Applied CAVA input configuration.")

    def _start_weather_city_search(self, query: str, target: str) -> None:
        self._weather_search_target = target
        search_btn = self.weather_designer_search_btn if target == "designer" and hasattr(self, "weather_designer_search_btn") else getattr(self, "cfg_weather_search_btn", None)
        if search_btn is not None:
            search_btn.setEnabled(False)
            search_btn.setText(self._tr("Searching...", "Szukam..."))

        def worker() -> None:
            results: list[dict[str, object]] = []
            error = ""
            try:
                params = urlencode({"name": query, "count": "8", "language": "en", "format": "json"})
                url = f"https://geocoding-api.open-meteo.com/v1/search?{params}"
                req = urllib.request.Request(url, headers={"User-Agent": "OpenTrofeoLCD/1.0"})
                with urllib.request.urlopen(req, timeout=6.0) as response:
                    data = json.loads(response.read().decode("utf-8"))
                raw_results = data.get("results", []) if isinstance(data, dict) else []
                if isinstance(raw_results, list):
                    for item in raw_results:
                        if isinstance(item, dict) and item.get("latitude") is not None and item.get("longitude") is not None:
                            results.append(item)
            except Exception as exc:
                error = str(exc)
            self.weather_city_search_finished.emit(results, error)

        threading.Thread(target=worker, daemon=True).start()

    def search_weather_city(self) -> None:
        if not hasattr(self, "cfg_weather_city_search_edit"):
            return
        query = self.cfg_weather_city_search_edit.text().strip()
        if len(query) < 2:
            QMessageBox.information(
                self,
                self._tr("Weather", "Pogoda"),
                self._tr("Type at least two characters.", "Wpisz co najmniej dwa znaki."),
            )
            return
        self._start_weather_city_search(query, "config")

    def search_designer_weather_city(self) -> None:
        if not hasattr(self, "weather_designer_city_search_edit"):
            return
        query = self.weather_designer_city_search_edit.text().strip()
        if len(query) < 2:
            QMessageBox.information(
                self,
                self._tr("Weather", "Pogoda"),
                self._tr("Type at least two characters.", "Wpisz co najmniej dwa znaki."),
            )
            return
        if hasattr(self, "cfg_weather_city_search_edit"):
            self.cfg_weather_city_search_edit.setText(query)
        self._start_weather_city_search(query, "designer")

    def _finish_weather_city_search(self, results: list[dict[str, object]], error: str = "") -> None:
        target = getattr(self, "_weather_search_target", "config")
        results_combo = self.weather_designer_results_combo if target == "designer" and hasattr(self, "weather_designer_results_combo") else getattr(self, "cfg_weather_results_combo", None)
        search_btn = self.weather_designer_search_btn if target == "designer" and hasattr(self, "weather_designer_search_btn") else getattr(self, "cfg_weather_search_btn", None)
        if results_combo is None or search_btn is None:
            return
        search_btn.setEnabled(True)
        search_btn.setText(self._tr("Search", "Szukaj"))
        if target == "designer" and hasattr(self, "cfg_weather_search_btn"):
            self.cfg_weather_search_btn.setEnabled(True)
            self.cfg_weather_search_btn.setText(self._tr("Search", "Szukaj"))
        results_combo.blockSignals(True)
        results_combo.clear()
        if error:
            results_combo.addItem(self._tr("Search failed", "Wyszukiwanie nieudane"), None)
            self.append_log(f"[weather] geocoding error: {error}")
        elif not results:
            results_combo.addItem(self._tr("No results", "Brak wyników"), None)
        else:
            for item in results:
                name = str(item.get("name", "")).strip()
                admin = str(item.get("admin1", "")).strip()
                country = str(item.get("country", "")).strip()
                lat = item.get("latitude")
                lon = item.get("longitude")
                label = ", ".join(part for part in (name, admin, country) if part)
                if not label:
                    label = f"{lat}, {lon}"
                results_combo.addItem(label, item)
        results_combo.blockSignals(False)
        if results:
            results_combo.setCurrentIndex(0)
            if target == "designer":
                self._apply_selected_designer_weather_city(0)
            else:
                self._apply_selected_weather_city(0)

    def _apply_selected_weather_city(self, index: int) -> None:
        if not hasattr(self, "cfg_weather_results_combo"):
            return
        item = self.cfg_weather_results_combo.itemData(index)
        if not isinstance(item, dict):
            return
        lat = item.get("latitude")
        lon = item.get("longitude")
        name = str(item.get("name", "")).strip()
        admin = str(item.get("admin1", "")).strip()
        country = str(item.get("country", "")).strip()
        label = ", ".join(part for part in (name, admin, country) if part)
        self.cfg_weather_lat_edit.setText("" if lat is None else str(lat))
        self.cfg_weather_lon_edit.setText("" if lon is None else str(lon))
        self.cfg_weather_location_edit.setText(label)

    def _apply_selected_designer_weather_city(self, index: int) -> None:
        if not hasattr(self, "weather_designer_results_combo"):
            return
        item = self.weather_designer_results_combo.itemData(index)
        if not isinstance(item, dict):
            return
        if hasattr(self, "cfg_weather_results_combo"):
            self.cfg_weather_results_combo.blockSignals(True)
            self.cfg_weather_results_combo.clear()
            self.cfg_weather_results_combo.addItem(self.weather_designer_results_combo.currentText(), item)
            self.cfg_weather_results_combo.setCurrentIndex(0)
            self.cfg_weather_results_combo.blockSignals(False)
            self._apply_selected_weather_city(0)

    def apply_designer_weather_config(self) -> None:
        self._apply_selected_designer_weather_city(self.weather_designer_results_combo.currentIndex())
        self.apply_weather_config()

    def refresh_designer_weather_now(self) -> None:
        self._apply_selected_designer_weather_city(self.weather_designer_results_combo.currentIndex())
        self.refresh_weather_now()

    def _reset_configuration_defaults(self) -> None:
        if hasattr(self, "cfg_ui_theme_combo"):
            self.cfg_ui_theme_combo.setCurrentText("Plasma Blue")
        if hasattr(self, "cfg_ui_mode_combo"):
            self.cfg_ui_mode_combo.setCurrentText("Dark")
        if hasattr(self, "cfg_ui_scale_combo"):
            self.cfg_ui_scale_combo.setCurrentText("100%")
        if hasattr(self, "cfg_brightness_slider"):
            self.cfg_brightness_slider.setValue(82)
        if hasattr(self, "cfg_preview_fps_combo"):
            self.cfg_preview_fps_combo.setCurrentText("30")
        if hasattr(self, "cfg_refresh_combo"):
            self.cfg_refresh_combo.setCurrentText("1.5 s")
        self._apply_configuration_preferences()

    def _export_configuration_file(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Eksportuj konfigurację",
            str(Path.cwd() / "trofeo-ui-config.json"),
            "JSON (*.json);;All files (*)",
        )
        if not selected:
            return
        payload = self._load_ui_state_payload()
        payload["theme_json"] = self.theme_doc_path_edit.text().strip() if hasattr(self, "theme_doc_path_edit") else ""
        Path(selected).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.append_log(f"[config] Eksport ustawień: {selected}")

    def _import_configuration_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Importuj konfigurację",
            str(Path.cwd()),
            "JSON (*.json);;All files (*)",
        )
        if not selected:
            return
        payload = json.loads(Path(selected).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Nieprawidłowy plik konfiguracji.")
        UI_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._restore_ui_state()
        self._sync_config_ui_controls_from_header()
        self.apply_ui_chrome()
        self.append_log(f"[config] Import ustawień: {selected}")

    def _clear_cached_state(self) -> None:
        for path in (THEME_AUTOSAVE_PATH, UI_STATE_PATH):
            try:
                if path.exists():
                    path.unlink()
            except Exception as exc:
                self.append_log(f"[config] cache-skip {path}: {exc}")
        self.append_log("[config] Wyczyszczono cache aplikacji.")

    def _restart_application(self) -> None:
        try:
            launcher_path = Path(__file__).resolve().with_name("main.py")
            if not launcher_path.exists():
                raise FileNotFoundError(f"Launcher not found: {launcher_path}")
            subprocess.Popen([sys.executable, str(launcher_path), "--replace-existing-backend"])
            self._close_to_tray_enabled = False
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(self, "Restart", str(exc))

    def _push_system_event(self, level: str, source: str, message: str) -> None:
        if not hasattr(self, "system_events_list"):
            return
        stamp = time.strftime("%H:%M:%S")
        self.system_events_list.insertItem(0, f"{stamp:<10} {level:<6} {source:<18} {message}")
        while self.system_events_list.count() > 40:
            self.system_events_list.takeItem(self.system_events_list.count() - 1)

    def _build_ui(self, base_url: str) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        shell_layout = QHBoxLayout(root)
        shell_layout.setContentsMargins(16, 16, 16, 16)
        shell_layout.setSpacing(16)

        sidebar = QFrame()
        sidebar.setObjectName("shellSidebar")
        sidebar.setFixedWidth(236)
        sidebar_layout = QVBoxLayout(sidebar)
        self.sidebar_layout = sidebar_layout
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(14)

        brand_row = QHBoxLayout()
        brand_icon = QLabel("⟡")
        brand_icon.setObjectName("shellBrandIcon")
        self.brand_label = QLabel("THERMALRIGHT")
        self.brand_label.setObjectName("shellBrandLabel")
        self.brand_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.brand_label.setMinimumWidth(118)
        self.brand_sub = QLabel("TROFEO LCD")
        self.brand_sub.setObjectName("shellBrandSubLabel")
        self.sidebar_toggle_btn = QPushButton("⟨")
        self.sidebar_toggle_btn.setObjectName("secondaryAccentButton")
        self.sidebar_toggle_btn.setMinimumSize(30, 30)
        self.sidebar_toggle_btn.setMaximumWidth(30)
        brand_row.addWidget(brand_icon)
        brand_row.addWidget(self.brand_label)
        brand_row.addStretch(1)
        brand_row.addWidget(self.sidebar_toggle_btn)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addWidget(self.brand_sub)

        self.nav_library_btn = QPushButton("🗂  Theme\nGallery")
        self.nav_designer_btn = QPushButton("✎  Theme\nDesigner")
        self.nav_animation_studio_btn = QPushButton("🎞  Animation\nStudio")
        self.nav_system_btn = QPushButton("◉  System")
        self.nav_logs_btn = QPushButton("☰  Logs")
        self.nav_config_btn = QPushButton("⚙  Configuration")
        self._nav_button_meta = {
            self.nav_library_btn: ("🗂", "Theme Gallery"),
            self.nav_designer_btn: ("✎", "Theme Designer"),
            self.nav_animation_studio_btn: ("🎞", "Animation Studio"),
            self.nav_system_btn: ("◉", "System"),
            self.nav_logs_btn: ("☰", "Logs"),
            self.nav_config_btn: ("⚙", "Configuration"),
        }
        self._shell_nav_buttons = [
            self.nav_library_btn,
            self.nav_designer_btn,
            self.nav_animation_studio_btn,
            self.nav_system_btn,
            self.nav_logs_btn,
            self.nav_config_btn,
        ]
        for btn in self._shell_nav_buttons:
            btn.setCheckable(True)
            btn.setObjectName("shellNavButton")
            btn.setMinimumHeight(88)
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch(1)
        self.sidebar_footer = QFrame()
        self.sidebar_footer.setObjectName("sidebarFooterCard")
        sidebar_footer_layout = QVBoxLayout(self.sidebar_footer)
        sidebar_footer_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_footer_layout.setSpacing(4)
        self.sidebar_version_label = QLabel("v1.0.0")
        self.sidebar_version_label.setObjectName("sidebarFooterTitle")
        self.sidebar_footer_note = QLabel("Open Trofeo LCD\nLinux Open Driver")
        self.sidebar_footer_note.setObjectName("sidebarFooterMeta")
        sidebar_footer_layout.addWidget(self.sidebar_version_label)
        sidebar_footer_layout.addWidget(self.sidebar_footer_note)
        sidebar_layout.addWidget(self.sidebar_footer)
        self.sidebar_frame = sidebar
        self.sidebar_collapsed = False
        shell_layout.addWidget(sidebar)

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        shell_layout.addWidget(content, 1)

        chrome_box = QGroupBox("Control")
        self.chrome_box = chrome_box
        chrome_box.setObjectName("shellHeader")
        chrome_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        chrome_layout = QHBoxLayout(chrome_box)
        chrome_layout.setContentsMargins(16, 8, 16, 8)
        chrome_layout.setSpacing(9)

        title_label = QLabel("Open Trofeo LCD")
        title_label.setObjectName("shellTitleLabel")
        title_sub = QLabel("LCD control and themes.")
        title_sub.setObjectName("shellTitleMeta")
        self.shell_title_sub = title_sub
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(1)
        title_stack.addWidget(title_label)
        title_stack.addWidget(title_sub)
        self.ui_mode_combo = QComboBox()
        self.ui_mode_combo.addItems(["Dark", "Light"])
        self.ui_theme_combo = QComboBox()
        self.ui_theme_combo.addItems(list(UI_THEMES.keys()))
        self.ui_theme_combo.hide()
        self.ui_scale_combo = QComboBox()
        for value in (70, 80, 90, 100, 110, 125, 140):
            self.ui_scale_combo.addItem(f"{value}%", value)
        self.ui_scale_combo.setCurrentText("100%")
        for combo in (self.ui_mode_combo, self.ui_scale_combo):
            combo.setMinimumHeight(34)
            combo.setMaxVisibleItems(8)

        self.header_connection_label = QLabel("● Disconnected")
        self.header_connection_label.setObjectName("headerStatusBadge")
        self.header_device_combo = QComboBox()
        self.header_device_combo.addItem("Trofeo LCD")
        self.header_device_combo.setMinimumHeight(34)
        self.header_ready_label = QLabel("Ready")
        self.header_ready_label.setObjectName("headerReadyBadge")
        self.header_language_combo = QComboBox()
        for label, code in UI_LANGUAGES.items():
            self.header_language_combo.addItem(label, code)
        self.header_language_combo.setMinimumHeight(34)
        self.header_donate_btn = QPushButton("Donate")
        self.header_donate_btn.setObjectName("primaryButton")
        self.header_donate_btn.setMinimumHeight(34)
        self.header_donate_btn.clicked.connect(lambda: self._open_external_link(PROJECT_SPONSOR_URL, "strony wsparcia"))
        self.header_donate_btn.setToolTip("Open GitHub Sponsors for Open Trofeo LCD")

        chrome_layout.addLayout(title_stack, 1)
        mode_label = QLabel("Mode")
        mode_label.setObjectName("headerFieldLabel")
        self.header_mode_label = mode_label
        scale_label = QLabel("Scale")
        scale_label.setObjectName("headerFieldLabel")
        self.header_scale_label = scale_label
        conn_label = QLabel("Connection")
        conn_label.setObjectName("headerFieldLabel")
        self.header_conn_label = conn_label
        device_label = QLabel("Device")
        device_label.setObjectName("headerFieldLabel")
        self.header_device_label = device_label
        language_label = QLabel("Language")
        language_label.setObjectName("headerFieldLabel")
        self.header_language_label = language_label
        chrome_layout.addWidget(mode_label)
        chrome_layout.addWidget(self.ui_mode_combo)
        chrome_layout.addWidget(scale_label)
        chrome_layout.addWidget(self.ui_scale_combo)
        chrome_layout.addSpacing(6)
        chrome_layout.addWidget(conn_label)
        chrome_layout.addWidget(self.header_connection_label)
        chrome_layout.addWidget(device_label)
        chrome_layout.addWidget(self.header_device_combo)
        chrome_layout.addWidget(language_label)
        chrome_layout.addWidget(self.header_language_combo)
        chrome_layout.addWidget(self.header_ready_label)
        chrome_layout.addSpacing(8)
        chrome_layout.addWidget(self.header_donate_btn)
        outer.addWidget(chrome_box)

        tabs = QTabWidget()
        tabs.setObjectName("mainSectionTabs")
        tabs.setDocumentMode(True)
        self.main_tabs = tabs
        outer.addWidget(tabs, 1)

        def make_scroll_tab() -> tuple[QWidget, QVBoxLayout]:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(12, 12, 12, 12)
            container_layout.setSpacing(20)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setWidget(container)
            return scroll, container_layout

        runtime_tab, runtime_layout = make_scroll_tab()
        studio_tab, studio_layout = make_scroll_tab()
        automation_tab, automation_layout = make_scroll_tab()
        logs_tab = QWidget()
        logs_layout = QVBoxLayout(logs_tab)
        logs_layout.setContentsMargins(0, 0, 0, 0)

        tabs.addTab(runtime_tab, "System")
        tabs.addTab(studio_tab, "Theme Designer")
        tabs.addTab(automation_tab, "Configuration")
        tabs.addTab(logs_tab, "Logs")
        tabs.tabBar().hide()
        self.ui_mode_combo.currentTextChanged.connect(self.apply_ui_chrome)
        self.ui_scale_combo.currentIndexChanged.connect(self.apply_ui_chrome)
        self.header_language_combo.currentTextChanged.connect(self._apply_language_selection)
        tabs.currentChanged.connect(lambda _idx: (self._animate_widget_fade(tabs.currentWidget()), self._sync_shell_navigation()))
        self.nav_system_btn.clicked.connect(lambda: self._go_system())
        self.nav_logs_btn.clicked.connect(lambda: self._go_logs())
        self.nav_config_btn.clicked.connect(lambda: self._go_config())

        endpoint_box = QGroupBox("Backend")
        self.endpoint_box = endpoint_box
        endpoint_layout = QHBoxLayout(endpoint_box)
        self.url_edit = QLineEdit(base_url)
        self.apply_url_btn = QPushButton("Set URL")
        self.apply_url_btn.clicked.connect(self.apply_url)
        self.refresh_btn = QPushButton("Refresh status")
        self.refresh_btn.clicked.connect(self.refresh_status)
        endpoint_layout.addWidget(QLabel("URL:"))
        endpoint_layout.addWidget(self.url_edit, 1)
        endpoint_layout.addWidget(self.apply_url_btn)
        endpoint_layout.addWidget(self.refresh_btn)
        runtime_layout.addWidget(endpoint_box)

        control_box = QGroupBox("Device control")
        self.control_box = control_box
        control_layout = QHBoxLayout(control_box)
        control_layout.setContentsMargins(16, 20, 16, 16)
        control_layout.setSpacing(12)
        
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setObjectName("primaryButton")
        self.stop_btn = QPushButton("⏹ Stop")
        self.restart_btn = QPushButton("🔄 Restart")
        self.scan_btn = QPushButton("🔍 Scan")
        self.hide_to_tray_btn = QPushButton("📥 Minimize to tray")
        
        self.start_btn.setMinimumHeight(44)
        self.stop_btn.setMinimumHeight(44)
        self.restart_btn.setMinimumHeight(44)
        
        self.start_btn.clicked.connect(lambda: self.api_call("start", "POST", "/v1/start", {}))
        self.stop_btn.clicked.connect(lambda: self.api_call("stop", "POST", "/v1/stop", {}))
        self.restart_btn.clicked.connect(lambda: self.api_call("restart", "POST", "/v1/restart", {}))
        self.scan_btn.clicked.connect(lambda: self.api_call("scan", "POST", "/v1/scan", {}))
        self.hide_to_tray_btn.clicked.connect(self.hide_to_tray)
        
        control_layout.addWidget(self.start_btn, 1)
        control_layout.addWidget(self.stop_btn, 1)
        control_layout.addWidget(self.restart_btn, 1)
        control_layout.addWidget(self.scan_btn, 1)
        control_layout.addWidget(self.hide_to_tray_btn, 1)
        runtime_layout.addWidget(control_box)

        runtime_hero = AnimatedCardFrame("runtimeHeroCard")
        runtime_hero_layout = QHBoxLayout(runtime_hero)
        runtime_hero_layout.setContentsMargins(18, 16, 18, 16)
        runtime_hero_text = QLabel(
            "Control the panel like a native Plasma app: start the runtime, push single frames "
            "and manage themes from clear cards instead of raw fields."
        )
        self.runtime_hero_text_label = runtime_hero_text
        runtime_hero_text.setObjectName("studioHeroText")
        runtime_hero_text.setWordWrap(True)
        runtime_hero_layout.addWidget(runtime_hero_text, 1)
        runtime_layout.addWidget(runtime_hero)

        runtime_sections_tabs = QTabWidget()
        self.runtime_sections_tabs = runtime_sections_tabs
        runtime_sections_tabs.setDocumentMode(True)
        runtime_layout.addWidget(runtime_sections_tabs, 1)
        runtime_sections_tabs.currentChanged.connect(lambda _idx: self._animate_widget_fade(runtime_sections_tabs.currentWidget()))

        runtime_device_tab = QWidget()
        runtime_device_layout = QVBoxLayout(runtime_device_tab)
        runtime_device_layout.setContentsMargins(0, 0, 0, 0)
        runtime_device_layout.setSpacing(10)
        runtime_sections_tabs.addTab(runtime_device_tab, "Device")

        runtime_image_tab = QWidget()
        runtime_image_layout = QVBoxLayout(runtime_image_tab)
        runtime_image_layout.setContentsMargins(0, 0, 0, 0)
        runtime_image_layout.setSpacing(10)
        runtime_sections_tabs.addTab(runtime_image_tab, "Image")

        runtime_theme_tab = QWidget()
        runtime_theme_layout = QVBoxLayout(runtime_theme_tab)
        runtime_theme_layout.setContentsMargins(0, 0, 0, 0)
        runtime_theme_layout.setSpacing(10)
        runtime_sections_tabs.addTab(runtime_theme_tab, "Themes")

        work_box = QGroupBox("Single image")
        self.work_box = work_box
        work_layout = QVBoxLayout(work_box)
        work_layout.setSpacing(8)
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(0, 1_000_000)
        self.set_frame_btn = QPushButton("Set frame")
        self.set_frame_btn.clicked.connect(self.set_frame)
        frame_row = QHBoxLayout()
        frame_row.addWidget(QLabel("Frame index:"))
        frame_row.addWidget(self.frame_spin)
        frame_row.addWidget(self.set_frame_btn)
        frame_row.addStretch(1)
        work_layout.addLayout(frame_row)

        self.image_edit = QLineEdit(str(Path("reference_frame_trcc.jpg")))
        self.browse_btn = QPushButton("Browse image")
        self.prepare_image_btn = QPushButton("Prepare image")
        self.send_image_btn = QPushButton("Send image")
        self.raw_passthrough_chk = QCheckBox("Raw JPEG passthrough")
        self.raw_passthrough_chk.setChecked(False)
        self.stop_before_send_chk = QCheckBox("Stop runtime before sending")
        self.stop_before_send_chk.setChecked(True)
        self.resume_loop_chk = QCheckBox("Resume loop after send")
        self.resume_loop_chk.setChecked(False)
        self.browse_btn.clicked.connect(self.browse_image)
        self.prepare_image_btn.clicked.connect(lambda: self.prepare_image_asset(self.image_edit))
        self.send_image_btn.clicked.connect(self.send_image)
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Image file:"))
        file_row.addWidget(self.image_edit, 1)
        file_row.addWidget(self.browse_btn)
        file_row.addWidget(self.prepare_image_btn)
        file_row.addWidget(self.send_image_btn)
        work_layout.addLayout(file_row)
        options_row = QHBoxLayout()
        options_row.addWidget(self.raw_passthrough_chk)
        options_row.addWidget(self.stop_before_send_chk)
        options_row.addWidget(self.resume_loop_chk)
        options_row.addStretch(1)
        work_layout.addLayout(options_row)
        runtime_image_layout.addWidget(work_box)

        cfg_status_row = QHBoxLayout()

        cfg_box = QGroupBox("Playback settings")
        self.cfg_box = cfg_box
        cfg_form = QFormLayout(cfg_box)
        self.pcap_edit = QLineEdit("dzis.pcapng")
        self.ack_timeout_spin = QSpinBox()
        self.ack_timeout_spin.setRange(1, 60000)
        self.ack_timeout_spin.setValue(500)
        self.inter_delay_spin = QDoubleSpinBox()
        self.inter_delay_spin.setRange(0.0, 5.0)
        self.inter_delay_spin.setSingleStep(0.005)
        self.inter_delay_spin.setValue(0.01)
        self.frame_delay_spin = QDoubleSpinBox()
        self.frame_delay_spin.setRange(0.0, 5.0)
        self.frame_delay_spin.setSingleStep(0.005)
        self.frame_delay_spin.setValue(0.02)
        self.apply_cfg_btn = QPushButton("Apply config")
        self.apply_cfg_btn.clicked.connect(self.apply_config)
        cfg_form.addRow("PCAP file:", self.pcap_edit)
        cfg_form.addRow("ACK timeout (ms):", self.ack_timeout_spin)
        cfg_form.addRow("Inter packet delay (s):", self.inter_delay_spin)
        cfg_form.addRow("Frame delay (s):", self.frame_delay_spin)
        cfg_form.addRow("", self.apply_cfg_btn)
        cfg_status_row.addWidget(cfg_box, 1)

        status_box = QGroupBox("System monitor")
        self.status_box = status_box
        status_grid = QGridLayout(status_box)
        status_grid.setContentsMargins(16, 24, 16, 16)
        status_grid.setSpacing(12)
        status_grid.setVerticalSpacing(16)
        
        self.lbl_mode = QLabel("-")
        self.lbl_running = QLabel("-")
        self.lbl_pid = QLabel("-")
        self.lbl_uptime = QLabel("-")
        self.lbl_frame_count = QLabel("-")
        self.lbl_playlist = QLabel("-")
        self.lbl_playlist_uptime = QLabel("-")
        self.lbl_last_error = QLabel("-")
        self.lbl_pcap = QLabel("-")

        def make_status_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet("color: #94a3b8; font-weight: 600;")
            return label

        def make_value_label(label: QLabel) -> None:
            label.setStyleSheet("color: #f1f5f9; font-weight: 700; background: #1a202c; border-radius: 6px; padding: 4px 8px;")

        for lbl in [self.lbl_mode, self.lbl_running, self.lbl_pid, self.lbl_uptime, self.lbl_frame_count, self.lbl_playlist, self.lbl_playlist_uptime, self.lbl_pcap]:
            make_value_label(lbl)
            
        self.lbl_last_error.setStyleSheet("color: #f87171; font-family: monospace; font-size: 11px;")

        status_grid.addWidget(make_status_label("📟 Mode:"), 0, 0)
        status_grid.addWidget(self.lbl_mode, 0, 1)
        status_grid.addWidget(make_status_label("🚦 Status:"), 0, 2)
        status_grid.addWidget(self.lbl_running, 0, 3)
        status_grid.addWidget(make_status_label("🆔 PID:"), 1, 0)
        status_grid.addWidget(self.lbl_pid, 1, 1)
        status_grid.addWidget(make_status_label("⏱ Uptime:"), 1, 2)
        status_grid.addWidget(self.lbl_uptime, 1, 3)
        status_grid.addWidget(make_status_label("🖼 Frames:"), 2, 0)
        status_grid.addWidget(self.lbl_frame_count, 2, 1)
        status_grid.addWidget(make_status_label("📂 PCAP:"), 2, 2)
        status_grid.addWidget(self.lbl_pcap, 2, 3)
        status_grid.addWidget(make_status_label("🎵 Playlist:"), 3, 0)
        status_grid.addWidget(self.lbl_playlist, 3, 1)
        status_grid.addWidget(make_status_label("⏳ PL time:"), 3, 2)
        status_grid.addWidget(self.lbl_playlist_uptime, 3, 3)
        status_grid.addWidget(make_status_label("⚠️ Error:"), 4, 0)
        status_grid.addWidget(self.lbl_last_error, 4, 1, 1, 3)
        cfg_status_row.addWidget(status_box, 1)
        runtime_device_layout.addLayout(cfg_status_row)
        runtime_device_layout.addStretch(1)

        theme_box = QGroupBox("Theme library")
        self.runtime_legacy_theme_box = theme_box
        theme_layout = QVBoxLayout(theme_box)
        theme_layout.setSpacing(8)
        self.theme_combo = QComboBox()
        self.theme_refresh_btn = QPushButton("Refresh list")
        self.theme_apply_btn = QPushButton("Apply theme")
        self.theme_remove_btn = QPushButton("Remove theme")
        self.theme_refresh_btn.clicked.connect(self.refresh_themes)
        self.theme_apply_btn.clicked.connect(self.apply_theme)
        self.theme_remove_btn.clicked.connect(self.remove_theme)
        theme_row_1 = QHBoxLayout()
        theme_row_1.addWidget(QLabel("Theme:"))
        theme_row_1.addWidget(self.theme_combo, 1)
        theme_row_1.addWidget(self.theme_refresh_btn)
        theme_row_1.addWidget(self.theme_apply_btn)
        theme_row_1.addWidget(self.theme_remove_btn)
        theme_layout.addLayout(theme_row_1)
        self.theme_name_edit = QLineEdit()
        self.theme_path_edit = QLineEdit(str(Path("reference_frame_trcc.jpg")))
        self.theme_browse_btn = QPushButton("Browse file")
        self.theme_prepare_btn = QPushButton("Prepare image")
        self.theme_add_btn = QPushButton("Add / update theme")
        self.theme_raw_chk = QCheckBox("Raw JPEG passthrough (theme)")
        self.theme_stop_before_apply_chk = QCheckBox("Stop runtime before apply")
        self.theme_stop_before_apply_chk.setChecked(True)
        self.theme_resume_chk = QCheckBox("Resume loop after apply")
        self.theme_raw_chk.setChecked(False)
        self.theme_resume_chk.setChecked(False)
        self.theme_browse_btn.clicked.connect(self.browse_theme_path)
        self.theme_prepare_btn.clicked.connect(lambda: self.prepare_image_asset(self.theme_path_edit))
        self.theme_add_btn.clicked.connect(self.add_or_update_theme)
        theme_row_2 = QHBoxLayout()
        theme_row_2.addWidget(QLabel("Name:"))
        theme_row_2.addWidget(self.theme_name_edit, 1)
        theme_layout.addLayout(theme_row_2)
        theme_row_3 = QHBoxLayout()
        theme_row_3.addWidget(QLabel("File:"))
        theme_row_3.addWidget(self.theme_path_edit, 1)
        theme_row_3.addWidget(self.theme_browse_btn)
        theme_row_3.addWidget(self.theme_prepare_btn)
        theme_row_3.addWidget(self.theme_add_btn)
        theme_layout.addLayout(theme_row_3)
        theme_row_4 = QHBoxLayout()
        theme_row_4.addWidget(self.theme_raw_chk)
        theme_row_4.addWidget(self.theme_stop_before_apply_chk)
        theme_row_4.addWidget(self.theme_resume_chk)
        theme_row_4.addStretch(1)
        theme_layout.addLayout(theme_row_4)
        runtime_theme_layout.addWidget(theme_box)
        runtime_theme_cards_box = QGroupBox("Theme cards")
        self.runtime_theme_cards_box = runtime_theme_cards_box
        runtime_theme_cards_layout = QVBoxLayout(runtime_theme_cards_box)
        runtime_theme_cards_scroll = QScrollArea()
        runtime_theme_cards_scroll.setWidgetResizable(True)
        runtime_theme_cards_scroll.setFrameShape(QScrollArea.NoFrame)
        self.runtime_theme_cards_container = QWidget()
        self.runtime_theme_cards_layout = QVBoxLayout(self.runtime_theme_cards_container)
        self.runtime_theme_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.runtime_theme_cards_layout.setSpacing(12)
        runtime_theme_cards_scroll.setWidget(self.runtime_theme_cards_container)
        runtime_theme_cards_layout.addWidget(runtime_theme_cards_scroll)
        runtime_theme_layout.addWidget(runtime_theme_cards_box, 1)
        runtime_theme_layout.addStretch(1)

        for legacy_widget in (endpoint_box, control_box, runtime_hero, runtime_sections_tabs):
            legacy_widget.hide()

        system_intro = AnimatedCardFrame("runtimeHeroCard")
        system_intro_layout = QHBoxLayout(system_intro)
        system_intro_layout.setContentsMargins(18, 16, 18, 16)
        system_intro_text = QLabel(
            "This tab shows backend status, device state and basic host metrics. "
            "Quick actions use the same live API endpoints as before."
        )
        self.system_intro_text_label = system_intro_text
        system_intro_text.setObjectName("studioHeroText")
        system_intro_text.setWordWrap(True)
        system_intro_layout.addWidget(system_intro_text)
        runtime_layout.addWidget(system_intro)

        system_top_row = QHBoxLayout()
        system_top_row.setSpacing(14)

        backend_status_box = QGroupBox("Backend status")
        self.backend_status_box = backend_status_box
        backend_status_box.setObjectName("dashboardCardBox")
        backend_status_layout = QVBoxLayout(backend_status_box)
        backend_status_layout.setSpacing(10)
        self.system_api_status_row, self.system_api_status_title, self.system_api_status_value = self._create_dashboard_status_row(
            "API Server", "Offline"
        )
        self.system_ws_status_row, self.system_ws_status_title, self.system_ws_status_value = self._create_dashboard_status_row(
            "WebSocket", "Offline"
        )
        self.system_lcd_status_row, self.system_lcd_status_title, self.system_lcd_status_value = self._create_dashboard_status_row(
            "LCD Daemon", "Idle"
        )
        self.system_queue_status_row, self.system_queue_status_title, self.system_queue_status_value = self._create_dashboard_status_row(
            "Queue Worker", "Idle"
        )
        self.system_theme_engine_row, self.system_theme_engine_title, self.system_theme_engine_value = self._create_dashboard_status_row(
            "Theme Engine", "Ready"
        )
        self.system_backup_row, self.system_backup_title, self.system_backup_value = self._create_dashboard_status_row("Auto Backup", "Idle")
        for row in (
            self.system_api_status_row,
            self.system_ws_status_row,
            self.system_lcd_status_row,
            self.system_queue_status_row,
            self.system_theme_engine_row,
            self.system_backup_row,
        ):
            backend_status_layout.addWidget(row)
        backend_status_layout.addStretch(1)
        system_top_row.addWidget(backend_status_box, 1)

        system_info_box = QGroupBox("System information")
        self.system_info_box = system_info_box
        system_info_box.setObjectName("dashboardCardBox")
        system_info_grid = QGridLayout(system_info_box)
        system_info_grid.setColumnStretch(1, 1)
        self.system_os_value = QLabel(platform.system())
        self.system_framework_value = QLabel("Qt 6 / PySide6")
        self.system_app_version_value = QLabel("v1.0.0")
        self.system_uptime_value = QLabel("-")
        self.system_hostname_value = QLabel(socket.gethostname())
        self.system_restart_value = QLabel("-")
        info_rows = [
            ("Operating system:", self.system_os_value),
            ("Framework:", self.system_framework_value),
            ("App version:", self.system_app_version_value),
            ("Uptime:", self.system_uptime_value),
            ("Hostname:", self.system_hostname_value),
            ("Last restart:", self.system_restart_value),
        ]
        for idx, (label_text, value_lbl) in enumerate(info_rows):
            system_info_grid.addWidget(QLabel(label_text), idx, 0)
            system_info_grid.addWidget(value_lbl, idx, 1)
        system_top_row.addWidget(system_info_box, 1)

        resources_box = QGroupBox("System resources")
        self.resources_box = resources_box
        resources_box.setObjectName("dashboardCardBox")
        resources_layout = QHBoxLayout(resources_box)
        resources_layout.setSpacing(10)
        cpu_card, self.system_cpu_title, self.system_cpu_value, self.system_cpu_detail = self._create_system_metric_card("CPU")
        mem_card, self.system_mem_title, self.system_mem_value, self.system_mem_detail = self._create_system_metric_card("RAM")
        disk_card, self.system_disk_title, self.system_disk_value, self.system_disk_detail = self._create_system_metric_card("DISK")
        temp_card, self.system_temp_title, self.system_temp_value, self.system_temp_detail = self._create_system_metric_card("TEMP")
        for card in (cpu_card, mem_card, disk_card, temp_card):
            resources_layout.addWidget(card, 1)
        system_top_row.addWidget(resources_box, 1)
        runtime_layout.addLayout(system_top_row)

        system_bottom_row = QHBoxLayout()
        system_bottom_row.setSpacing(14)

        device_box = QGroupBox("Network & device")
        self.runtime_dashboard_device_box = device_box
        device_box.setObjectName("dashboardCardBox")
        device_grid = QGridLayout(device_box)
        device_grid.setColumnStretch(1, 1)
        self.system_connection_value = QLabel("-")
        self.system_device_value = QLabel("Trofeo LCD")
        self.system_firmware_value = QLabel("-")
        self.system_resolution_value = QLabel("1920 x 462")
        self.system_ip_value = QLabel("127.0.0.1")
        self.system_port_value = QLabel("18777")
        self.system_serial_value = QLabel("-")
        device_rows = [
            ("Connection:", self.system_connection_value),
            ("Device:", self.system_device_value),
            ("Firmware:", self.system_firmware_value),
            ("Resolution:", self.system_resolution_value),
            ("IP address:", self.system_ip_value),
            ("API port:", self.system_port_value),
            ("USB/Serial:", self.system_serial_value),
        ]
        for idx, (label_text, value_lbl) in enumerate(device_rows):
            device_grid.addWidget(QLabel(label_text), idx, 0)
            device_grid.addWidget(value_lbl, idx, 1)
        system_bottom_row.addWidget(device_box, 1)

        events_box = QGroupBox("System events")
        self.system_events_box = events_box
        events_box.setObjectName("dashboardCardBox")
        events_layout = QVBoxLayout(events_box)
        events_header = QHBoxLayout()
        self.system_events_header_labels = []
        for title, stretch in (("Time", 1), ("Level", 1), ("Source", 2), ("Message", 4)):
            lbl = QLabel(title)
            lbl.setObjectName("eventHeaderLabel")
            self.system_events_header_labels.append(lbl)
            events_header.addWidget(lbl, stretch)
        events_layout.addLayout(events_header)
        self.system_events_list = QListWidget()
        self.system_events_list.setMinimumHeight(260)
        self.system_events_list.setObjectName("systemEventsList")
        events_layout.addWidget(self.system_events_list)
        system_bottom_row.addWidget(events_box, 2)

        quick_actions_box = QGroupBox("Quick actions")
        self.system_quick_actions_box = quick_actions_box
        quick_actions_box.setObjectName("dashboardCardBox")
        quick_actions_layout = QVBoxLayout(quick_actions_box)
        self.system_restart_backend_btn = QPushButton("Restart backend")
        self.system_restart_service_btn = QPushButton("Restart service")
        self.system_refresh_status_btn = QPushButton("Refresh status")
        self.system_export_logs_btn = QPushButton("Export logs")
        self.system_diagnostic_btn = QPushButton("Diagnostics")
        self.system_restart_backend_btn.clicked.connect(lambda: self.api_call("restart", "POST", "/v1/restart", {}))
        self.system_restart_service_btn.clicked.connect(lambda: self.api_call("stop", "POST", "/v1/stop", {}))
        self.system_refresh_status_btn.clicked.connect(self.refresh_status)
        self.system_export_logs_btn.clicked.connect(self.copy_filtered_logs)
        self.system_diagnostic_btn.clicked.connect(lambda: self.api_call("scan", "POST", "/v1/scan", {}))
        for button in (
            self.system_restart_backend_btn,
            self.system_restart_service_btn,
            self.system_refresh_status_btn,
            self.system_export_logs_btn,
            self.system_diagnostic_btn,
        ):
            button.setMinimumHeight(44)
            button.setObjectName("quickActionButton")
            quick_actions_layout.addWidget(button)
        quick_actions_layout.addStretch(1)
        system_bottom_row.addWidget(quick_actions_box, 1)
        runtime_layout.addLayout(system_bottom_row)
        runtime_layout.addStretch(1)

        config_intro = AnimatedCardFrame("runtimeHeroCard")
        config_intro_layout = QHBoxLayout(config_intro)
        config_intro_layout.setContentsMargins(18, 16, 18, 16)
        config_intro_text = QLabel(
            "Configuration centralizes interface settings, LCD preferences and integrations in one place. "
            "App theme management now lives here instead of the top control bar."
        )
        self.config_intro_text_label = config_intro_text
        config_intro_text.setObjectName("studioHeroText")
        config_intro_text.setWordWrap(True)
        config_intro_layout.addWidget(config_intro_text)
        automation_layout.addWidget(config_intro)

        config_grid = QGridLayout()
        config_grid.setHorizontalSpacing(14)
        config_grid.setVerticalSpacing(14)

        autostart_box = QGroupBox("Startup")
        autostart_box.setObjectName("configCardBox")
        autostart_layout = QVBoxLayout(autostart_box)
        self.cfg_start_with_system_chk = QCheckBox("Launch with system")
        self.cfg_minimize_to_tray_chk = QCheckBox("Minimize to tray on startup")
        self.cfg_auto_connect_chk = QCheckBox("Auto-connect to device")
        self.cfg_restore_project_chk = QCheckBox("Restore last project on startup")
        self.cfg_check_updates_chk = QCheckBox("Check for updates on startup")
        self.cfg_start_with_system_chk.setChecked(True)
        self.cfg_minimize_to_tray_chk.setChecked(True)
        self.cfg_auto_connect_chk.setChecked(True)
        self.cfg_check_updates_chk.setChecked(True)
        for chk in (
            self.cfg_start_with_system_chk,
            self.cfg_minimize_to_tray_chk,
            self.cfg_auto_connect_chk,
            self.cfg_restore_project_chk,
            self.cfg_check_updates_chk,
        ):
            autostart_layout.addWidget(chk)
        autostart_layout.addStretch(1)
        config_grid.addWidget(autostart_box, 0, 0)

        appearance_box = QGroupBox("App Appearance")
        self.appearance_box = appearance_box
        appearance_box.setObjectName("configCardBox")
        appearance_form = QFormLayout(appearance_box)
        self.cfg_ui_theme_combo = QComboBox()
        self.cfg_ui_theme_combo.addItems(list(UI_THEMES.keys()))
        self.cfg_ui_mode_combo = QComboBox()
        self.cfg_ui_mode_combo.addItems(["Dark", "Light"])
        self.cfg_ui_scale_combo = QComboBox()
        for value in (70, 80, 90, 100, 110, 125, 140):
            self.cfg_ui_scale_combo.addItem(f"{value}%", value)
        self.cfg_font_scale_slider = QSlider(Qt.Horizontal)
        self.cfg_font_scale_slider.setRange(80, 140)
        self.cfg_font_scale_slider.setValue(100)
        self.cfg_animations_chk = QCheckBox("Animation effects")
        self.cfg_animations_chk.setChecked(True)
        self.cfg_compact_layout_chk = QCheckBox("Compact layout")
        appearance_form.addRow("App theme:", self.cfg_ui_theme_combo)
        appearance_form.addRow("Mode:", self.cfg_ui_mode_combo)
        appearance_form.addRow("Interface scale:", self.cfg_ui_scale_combo)
        appearance_form.addRow("Font size:", self.cfg_font_scale_slider)
        appearance_form.addRow("Animation effects:", self.cfg_animations_chk)
        appearance_form.addRow("Compact layout:", self.cfg_compact_layout_chk)
        config_grid.addWidget(appearance_box, 0, 1)

        lcd_box = QGroupBox("LCD Preferences")
        lcd_box.setObjectName("configCardBox")
        lcd_form = QFormLayout(lcd_box)
        self.cfg_brightness_slider = QSlider(Qt.Horizontal)
        self.cfg_brightness_slider.setRange(0, 100)
        self.cfg_brightness_slider.setValue(82)
        self.cfg_preview_fps_combo = QComboBox()
        self.cfg_preview_fps_combo.addItems(["24", "30", "45", "60"])
        self.cfg_preview_fps_combo.setCurrentText("30")
        self.cfg_refresh_combo = QComboBox()
        self.cfg_refresh_combo.addItems(["0.5 s", "1.0 s", "1.5 s", "2.0 s"])
        self.cfg_refresh_combo.setCurrentText("1.5 s")
        self.cfg_smoothing_chk = QCheckBox("Smooth charts")
        self.cfg_smoothing_chk.setChecked(True)
        self.cfg_start_layout_combo = QComboBox()
        self.cfg_start_layout_combo.addItems(["Last used", "Dashboard", "Minimal", "Focus"])
        lcd_form.addRow("Default brightness:", self.cfg_brightness_slider)
        lcd_form.addRow("Default preview FPS:", self.cfg_preview_fps_combo)
        lcd_form.addRow("Data refresh:", self.cfg_refresh_combo)
        lcd_form.addRow("Smooth charts:", self.cfg_smoothing_chk)
        lcd_form.addRow("Startup layout:", self.cfg_start_layout_combo)
        config_grid.addWidget(lcd_box, 0, 2)

        notifications_box = QGroupBox("Notifications and Logs")
        notifications_box.setObjectName("configCardBox")
        notifications_form = QFormLayout(notifications_box)
        self.cfg_system_notifications_chk = QCheckBox("System notifications")
        self.cfg_backend_alerts_chk = QCheckBox("Backend error alerts")
        self.cfg_debug_log_chk = QCheckBox("Write debug logs")
        self.cfg_log_rotation_chk = QCheckBox("Automatic log rotation")
        self.cfg_system_notifications_chk.setChecked(True)
        self.cfg_backend_alerts_chk.setChecked(True)
        self.cfg_log_rotation_chk.setChecked(True)
        self.cfg_log_size_combo = QComboBox()
        self.cfg_log_size_combo.addItems(["25 MB", "50 MB", "100 MB", "250 MB"])
        self.cfg_log_size_combo.setCurrentText("100 MB")
        notifications_form.addRow("Notifications:", self.cfg_system_notifications_chk)
        notifications_form.addRow("Backend alerts:", self.cfg_backend_alerts_chk)
        notifications_form.addRow("Debug:", self.cfg_debug_log_chk)
        notifications_form.addRow("Log rotation:", self.cfg_log_rotation_chk)
        notifications_form.addRow("Maximum size:", self.cfg_log_size_combo)
        config_grid.addWidget(notifications_box, 1, 0)

        paths_box = QGroupBox("Paths and Integration")
        self.paths_box = paths_box
        paths_box.setObjectName("configCardBox")
        paths_form = QFormLayout(paths_box)
        self.cfg_theme_dir_edit = QLineEdit(str((Path.cwd() / "themes").resolve()))
        self.cfg_backup_dir_edit = QLineEdit(str((Path.cwd() / "backups").resolve()))
        self.cfg_api_port_spin = QSpinBox()
        self.cfg_api_port_spin.setRange(1, 65535)
        self.cfg_api_port_spin.setValue(18777)
        self.cfg_start_device_combo = QComboBox()
        self.cfg_start_device_combo.addItems(["Trofeo LCD"])
        self.cfg_comm_mode_combo = QComboBox()
        self.cfg_comm_mode_combo.addItems(["USB / Serial", "Backend API"])
        paths_form.addRow("Themes directory:", self.cfg_theme_dir_edit)
        paths_form.addRow("Backups directory:", self.cfg_backup_dir_edit)
        paths_form.addRow("API port:", self.cfg_api_port_spin)
        paths_form.addRow("Startup device:", self.cfg_start_device_combo)
        paths_form.addRow("Communication mode:", self.cfg_comm_mode_combo)
        config_grid.addWidget(paths_box, 1, 1, 1, 2)

        weather_box = QGroupBox("Weather")
        self.weather_box = weather_box
        weather_box.setObjectName("configCardBox")
        weather_form = QFormLayout(weather_box)
        self.cfg_weather_city_search_edit = QLineEdit()
        self.cfg_weather_city_search_edit.setPlaceholderText("Search city, e.g. Warsaw")
        self.cfg_weather_search_btn = QPushButton("Search")
        self.cfg_weather_results_combo = QComboBox()
        self.cfg_weather_results_combo.addItem("No city selected", None)
        self.cfg_weather_lat_edit = QLineEdit()
        self.cfg_weather_lon_edit = QLineEdit()
        self.cfg_weather_location_edit = QLineEdit()
        self.cfg_weather_refresh_spin = QSpinBox()
        self.cfg_weather_refresh_spin.setRange(300, 86400)
        self.cfg_weather_refresh_spin.setSingleStep(300)
        self.cfg_weather_refresh_spin.setValue(900)
        self.cfg_weather_apply_btn = QPushButton("Apply weather")
        self.cfg_weather_refresh_now_btn = QPushButton("Refresh weather")
        self.cfg_weather_status_label = QLabel("Weather: not configured")
        self.cfg_weather_status_label.setWordWrap(True)
        self.cfg_weather_status_label.setObjectName("selectionSummaryLabel")
        weather_search_row = QWidget()
        weather_search_layout = QHBoxLayout(weather_search_row)
        weather_search_layout.setContentsMargins(0, 0, 0, 0)
        weather_search_layout.setSpacing(6)
        weather_search_layout.addWidget(self.cfg_weather_city_search_edit, 1)
        weather_search_layout.addWidget(self.cfg_weather_search_btn)
        self.cfg_weather_search_btn.clicked.connect(self.search_weather_city)
        self.cfg_weather_city_search_edit.returnPressed.connect(self.search_weather_city)
        self.cfg_weather_results_combo.currentIndexChanged.connect(self._apply_selected_weather_city)
        self.cfg_weather_apply_btn.clicked.connect(self.apply_weather_config)
        self.cfg_weather_refresh_now_btn.clicked.connect(self.refresh_weather_now)
        weather_actions_row = QWidget()
        weather_actions_layout = QHBoxLayout(weather_actions_row)
        weather_actions_layout.setContentsMargins(0, 0, 0, 0)
        weather_actions_layout.setSpacing(6)
        weather_actions_layout.addWidget(self.cfg_weather_apply_btn)
        weather_actions_layout.addWidget(self.cfg_weather_refresh_now_btn)
        weather_form.addRow("City search:", weather_search_row)
        weather_form.addRow("Results:", self.cfg_weather_results_combo)
        weather_form.addRow("Latitude:", self.cfg_weather_lat_edit)
        weather_form.addRow("Longitude:", self.cfg_weather_lon_edit)
        weather_form.addRow("Location label:", self.cfg_weather_location_edit)
        weather_form.addRow("Refresh (s):", self.cfg_weather_refresh_spin)
        weather_form.addRow("", weather_actions_row)
        weather_form.addRow("Status:", self.cfg_weather_status_label)
        config_grid.addWidget(weather_box, 2, 0, 1, 2)

        audio_eq_box = QGroupBox("Audio EQ")
        self.audio_eq_box = audio_eq_box
        audio_eq_box.setObjectName("configCardBox")
        audio_eq_form = QFormLayout(audio_eq_box)
        self.cfg_audio_eq_input_combo = QComboBox()
        self.cfg_audio_eq_input_combo.addItem("Auto: Pulse -> PipeWire -> ALSA", "auto")
        self.cfg_audio_eq_input_combo.addItem("PulseAudio / PipeWire Pulse", "pulse")
        self.cfg_audio_eq_input_combo.addItem("PipeWire native", "pipewire")
        self.cfg_audio_eq_input_combo.addItem("ALSA", "alsa")
        self.cfg_audio_eq_input_combo.activated.connect(lambda _idx: setattr(self, "_audio_eq_config_dirty", True))
        self.cfg_audio_eq_profile_combo = QComboBox()
        self.cfg_audio_eq_profile_combo.addItem("Responsive", "responsive")
        self.cfg_audio_eq_profile_combo.addItem("Balanced", "balanced")
        self.cfg_audio_eq_profile_combo.addItem("Smooth", "smooth")
        self.cfg_audio_eq_profile_combo.activated.connect(lambda _idx: setattr(self, "_audio_eq_config_dirty", True))
        self.cfg_audio_eq_sensitivity_spin = QSpinBox()
        self.cfg_audio_eq_sensitivity_spin.setRange(35, 250)
        self.cfg_audio_eq_sensitivity_spin.setSingleStep(5)
        self.cfg_audio_eq_sensitivity_spin.setSuffix("%")
        self.cfg_audio_eq_sensitivity_spin.setValue(100)
        self.cfg_audio_eq_sensitivity_spin.valueChanged.connect(lambda _value: setattr(self, "_audio_eq_config_dirty", True))
        self.cfg_audio_eq_apply_btn = QPushButton("Apply EQ")
        self.cfg_audio_eq_status_label = QLabel("EQ: waiting for backend status")
        self.cfg_audio_eq_status_label.setWordWrap(True)
        self.cfg_audio_eq_status_label.setObjectName("selectionSummaryLabel")
        self.cfg_audio_eq_apply_btn.clicked.connect(self.apply_audio_eq_config)
        audio_eq_form.addRow("CAVA input:", self.cfg_audio_eq_input_combo)
        audio_eq_form.addRow("Response:", self.cfg_audio_eq_profile_combo)
        audio_eq_form.addRow("Sensitivity:", self.cfg_audio_eq_sensitivity_spin)
        audio_eq_form.addRow("", self.cfg_audio_eq_apply_btn)
        audio_eq_form.addRow("Status:", self.cfg_audio_eq_status_label)
        config_grid.addWidget(audio_eq_box, 2, 2, 1, 2)

        quick_cfg_box = QGroupBox("Quick Actions")
        self.quick_cfg_box = quick_cfg_box
        quick_cfg_box.setObjectName("configCardBox")
        quick_cfg_layout = QVBoxLayout(quick_cfg_box)
        self.cfg_reset_btn = QPushButton("Restore Defaults")
        self.cfg_export_btn = QPushButton("Export Configuration")
        self.cfg_import_btn = QPushButton("Import Configuration")
        self.cfg_clear_cache_btn = QPushButton("Clear Cache")
        self.cfg_restart_app_btn = QPushButton("Restart Application")
        self.cfg_reset_btn.clicked.connect(self._reset_configuration_defaults)
        self.cfg_export_btn.clicked.connect(self._export_configuration_file)
        self.cfg_import_btn.clicked.connect(self._import_configuration_file)
        self.cfg_clear_cache_btn.clicked.connect(self._clear_cached_state)
        self.cfg_restart_app_btn.clicked.connect(self._restart_application)
        for button in (
            self.cfg_reset_btn,
            self.cfg_export_btn,
            self.cfg_import_btn,
            self.cfg_clear_cache_btn,
            self.cfg_restart_app_btn,
        ):
            button.setMinimumHeight(44)
            button.setObjectName("quickActionButton")
            quick_cfg_layout.addWidget(button)
        quick_cfg_layout.addStretch(1)
        config_grid.addWidget(quick_cfg_box, 0, 3, 2, 1)
        automation_layout.addLayout(config_grid)

        self.playlist_list = QListWidget()
        self.bundle_path_edit = QLineEdit(".trofeo-bundle.json")
        automation_tools_box = QGroupBox("Automation and Bundles")
        self.automation_tools_box = automation_tools_box
        automation_tools_box.setObjectName("configCardBox")
        automation_tools_layout = QGridLayout(automation_tools_box)
        self.playlist_duration_spin = QDoubleSpinBox()
        self.playlist_duration_spin.setRange(0.5, 3600.0)
        self.playlist_duration_spin.setSingleStep(0.5)
        self.playlist_duration_spin.setValue(15.0)
        self.playlist_add_btn = QPushButton("Add selected theme to playlist")
        self.playlist_remove_btn = QPushButton("Remove from playlist")
        self.playlist_start_btn = QPushButton("Start playlist")
        self.playlist_stop_btn = QPushButton("Stop playlist")
        self.playlist_add_btn.clicked.connect(self.add_playlist_item)
        self.playlist_remove_btn.clicked.connect(self.remove_playlist_item)
        self.playlist_start_btn.clicked.connect(self.start_playlist)
        self.playlist_stop_btn.clicked.connect(self.stop_playlist)
        self.bundle_merge_chk = QCheckBox("Merge on import")
        self.bundle_browse_btn = QPushButton("Choose bundle")
        self.bundle_save_btn = QPushButton("Save bundle")
        self.bundle_load_btn = QPushButton("Load bundle")
        self.bundle_browse_btn.clicked.connect(self.browse_bundle_path)
        self.bundle_save_btn.clicked.connect(self.save_bundle)
        self.bundle_load_btn.clicked.connect(self.load_bundle)
        automation_tools_layout.addWidget(QLabel("Playlist"), 0, 0)
        automation_tools_layout.addWidget(self.playlist_list, 1, 0, 4, 2)
        automation_tools_layout.addWidget(QLabel("Item duration (s)"), 0, 2)
        automation_tools_layout.addWidget(self.playlist_duration_spin, 0, 3)
        automation_tools_layout.addWidget(self.playlist_add_btn, 1, 2, 1, 2)
        automation_tools_layout.addWidget(self.playlist_remove_btn, 2, 2, 1, 2)
        automation_tools_layout.addWidget(self.playlist_start_btn, 3, 2, 1, 2)
        automation_tools_layout.addWidget(self.playlist_stop_btn, 4, 2, 1, 2)
        automation_tools_layout.addWidget(QLabel("Bundle"), 5, 0)
        automation_tools_layout.addWidget(self.bundle_path_edit, 5, 1, 1, 2)
        automation_tools_layout.addWidget(self.bundle_browse_btn, 5, 3)
        automation_tools_layout.addWidget(self.bundle_merge_chk, 6, 1)
        automation_tools_layout.addWidget(self.bundle_save_btn, 6, 2)
        automation_tools_layout.addWidget(self.bundle_load_btn, 6, 3)
        automation_layout.addWidget(automation_tools_box)
        cfg_actions_row = QHBoxLayout()
        cfg_actions_row.addStretch(1)
        self.cfg_cancel_btn = QPushButton("Cancel")
        self.cfg_apply_btn = QPushButton("Apply")
        self.cfg_save_btn = QPushButton("Save Settings")
        self.cfg_apply_btn.setObjectName("secondaryAccentButton")
        self.cfg_save_btn.setObjectName("primaryButton")
        self.cfg_cancel_btn.clicked.connect(self._sync_config_ui_controls_from_header)
        self.cfg_apply_btn.clicked.connect(self._apply_configuration_preferences)
        self.cfg_save_btn.clicked.connect(lambda: (self._apply_configuration_preferences(), self._save_ui_state(), self.append_log("[config] Zapisano ustawienia.")))
        cfg_actions_row.addWidget(self.cfg_cancel_btn)
        cfg_actions_row.addWidget(self.cfg_apply_btn)
        cfg_actions_row.addWidget(self.cfg_save_btn)
        automation_layout.addLayout(cfg_actions_row)
        automation_layout.addStretch(1)

        self._sync_config_ui_controls_from_header()

        studio_sections_tabs = QTabWidget()
        studio_sections_tabs.setObjectName("studioSectionTabs")
        self.studio_sections_tabs = studio_sections_tabs
        studio_sections_tabs.setDocumentMode(True)
        studio_sections_tabs.tabBar().hide()
        studio_layout.addWidget(studio_sections_tabs, 1)
        studio_sections_tabs.currentChanged.connect(lambda _idx: (self._animate_widget_fade(studio_sections_tabs.currentWidget()), self._sync_shell_navigation()))
        library_tab = QWidget()
        library_layout = QVBoxLayout(library_tab)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(10)
        designer_workspace_tab = QWidget()
        designer_workspace_layout = QVBoxLayout(designer_workspace_tab)
        designer_workspace_layout.setContentsMargins(0, 0, 0, 0)
        designer_workspace_layout.setSpacing(10)
        studio_sections_tabs.addTab(library_tab, "Theme Gallery")
        studio_sections_tabs.addTab(designer_workspace_tab, "Designer")
        self.animation_studio_tab = QWidget()
        self.animation_studio_layout = QVBoxLayout(self.animation_studio_tab)
        self.animation_studio_layout.setContentsMargins(10, 10, 10, 10)
        self.animation_studio_layout.setSpacing(10)
        studio_sections_tabs.addTab(self.animation_studio_tab, "Animation Studio")
        self.nav_library_btn.clicked.connect(lambda: self._go_library())
        self.nav_designer_btn.clicked.connect(lambda: self._go_designer())
        self.nav_animation_studio_btn.clicked.connect(lambda: self._go_animation_studio())
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar_collapsed)

        studio_toolbar_box = QGroupBox("")
        studio_toolbar_box.setObjectName("designerToolbarBox")
        studio_toolbar_box.setFlat(True)
        studio_toolbar_layout = QHBoxLayout(studio_toolbar_box)
        self.studio_toolbar_load_btn = QPushButton("📂 Load theme")
        self.studio_toolbar_save_btn = QPushButton("💾 Save theme")
        self.studio_toolbar_preview_btn = QPushButton("Preview")
        self.studio_toolbar_apply_btn = QPushButton("▶ Apply theme")
        self.studio_toolbar_reload_btn = QPushButton("↻ JSON → Designer")
        self.studio_toolbar_export_btn = QPushButton("⇄ Designer → JSON")
        for btn in (
            self.studio_toolbar_load_btn,
            self.studio_toolbar_save_btn,
            self.studio_toolbar_preview_btn,
            self.studio_toolbar_apply_btn,
            self.studio_toolbar_reload_btn,
            self.studio_toolbar_export_btn,
        ):
            btn.setMinimumHeight(34)
            btn.setMaximumWidth(210)
        self.studio_toolbar_preview_btn.setObjectName("secondaryAccentButton")
        self.studio_toolbar_apply_btn.setObjectName("primaryButton")
        self.studio_toolbar_load_btn.setText("Load theme")
        self.studio_toolbar_save_btn.setText("Save theme")
        self.studio_toolbar_apply_btn.setText("Apply theme")
        self.studio_toolbar_preview_btn.setText("Preview")
        self.studio_toolbar_load_btn.clicked.connect(self.load_theme_doc)
        self.studio_toolbar_save_btn.clicked.connect(self.save_current_theme_to_library)
        self.studio_toolbar_preview_btn.clicked.connect(self.preview_theme_doc)
        self.studio_toolbar_apply_btn.clicked.connect(self.apply_current_theme_to_lcd)
        self.studio_toolbar_reload_btn.clicked.connect(self.reload_designer_from_json)
        self.studio_toolbar_export_btn.clicked.connect(self.write_designer_to_json)
        studio_toolbar_layout.addStretch(1)
        studio_toolbar_layout.addWidget(self.studio_toolbar_load_btn)
        studio_toolbar_layout.addWidget(self.studio_toolbar_save_btn)
        studio_toolbar_layout.addWidget(self.studio_toolbar_preview_btn)
        studio_toolbar_layout.addWidget(self.studio_toolbar_apply_btn)
        studio_toolbar_layout.addSpacing(6)
        studio_toolbar_layout.addWidget(self.studio_toolbar_reload_btn)
        studio_toolbar_layout.addWidget(self.studio_toolbar_export_btn)
        self.studio_toolbar_reload_btn.hide()
        self.studio_toolbar_export_btn.hide()
        studio_toolbar_box.hide()
        # designer_workspace_layout.addWidget(studio_toolbar_box)

        self.quick_preset_dashboard_btn = QPushButton("Dashboard")
        self.quick_preset_minimal_btn = QPushButton("Minimal")
        self.quick_preset_focus_btn = QPushButton("Focus")
        self.quick_preset_dashboard_btn.setObjectName("quickPresetButton")
        self.quick_preset_minimal_btn.setObjectName("quickPresetButton")
        self.quick_preset_focus_btn.setObjectName("quickPresetButton")
        self.quick_preset_dashboard_btn.clicked.connect(lambda: self.apply_builtin_layout_preset("dashboard"))
        self.quick_preset_minimal_btn.clicked.connect(lambda: self.apply_builtin_layout_preset("minimal"))
        self.quick_preset_focus_btn.clicked.connect(lambda: self.apply_builtin_layout_preset("focus"))

        self.new_theme_options_box = QFrame()
        self.new_theme_options_box.setObjectName("libraryActionBar")
        self.new_theme_options_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        new_theme_box_layout = QVBoxLayout(self.new_theme_options_box)
        new_theme_box_layout.setContentsMargins(14, 12, 14, 12)
        new_theme_box_layout.setSpacing(6)
        self.library_summary_label = QLabel("Theme gallery quick actions")
        self.library_summary_label.setObjectName("selectionSummaryLabel")
        self.library_summary_label.setWordWrap(False)
        new_theme_box_layout.addWidget(self.library_summary_label)
        self.new_theme_name_edit = QLineEdit("New Theme")
        self.new_theme_name_edit.setObjectName("newThemeNameEdit")
        self.new_theme_name_edit.setPlaceholderText("e.g. My Dashboard")
        self.new_theme_template_combo = QComboBox()
        self.new_theme_template_combo.setObjectName("newThemeTemplateCombo")
        for template in THEME_TEMPLATE_CATALOG:
            self.new_theme_template_combo.addItem(template["title"], template["path"])
        self.new_theme_create_btn = QPushButton("Create Theme")
        self.new_theme_create_btn.setObjectName("newThemeCreateButton")
        self.new_theme_advanced_btn = QPushButton("File Settings")
        self.new_theme_advanced_btn.setCheckable(True)
        self.library_refresh_btn = QPushButton("Refresh")
        self.library_import_ttcr_btn = QPushButton("Import TTCR")
        self.library_refresh_btn.clicked.connect(self.refresh_themes)
        self.library_import_ttcr_btn.clicked.connect(self.import_ttcr_theme_bundle)
        self.new_theme_path_edit = QLineEdit(str(Path("themes") / "nowy_motyw.json"))
        self.new_theme_path_edit.setObjectName("newThemePathEdit")
        self.new_theme_browse_btn = QPushButton("Choose File")
        self._new_theme_path_user_edited = False
        new_theme_row = QHBoxLayout()
        new_theme_row.setSpacing(8)
        new_theme_row.addWidget(self.library_import_ttcr_btn)
        new_theme_row.addWidget(self.library_refresh_btn)
        new_theme_row.addWidget(QLabel("Name"))
        new_theme_row.addWidget(self.new_theme_name_edit, 2)
        new_theme_row.addWidget(QLabel("Style"))
        new_theme_row.addWidget(self.new_theme_template_combo, 1)
        new_theme_row.addWidget(self.new_theme_create_btn)
        new_theme_row.addWidget(self.new_theme_advanced_btn)
        new_theme_box_layout.addLayout(new_theme_row)
        self.new_theme_path_row = QWidget()
        new_theme_path_row_layout = QHBoxLayout(self.new_theme_path_row)
        new_theme_path_row_layout.setContentsMargins(0, 0, 0, 0)
        new_theme_path_row_layout.setSpacing(8)
        new_theme_path_row_layout.addWidget(QLabel("File"))
        new_theme_path_row_layout.addWidget(self.new_theme_path_edit, 1)
        new_theme_path_row_layout.addWidget(self.new_theme_browse_btn)
        new_theme_box_layout.addWidget(self.new_theme_path_row)
        self.new_theme_path_row.hide()
        self.new_theme_hint_label = QLabel("Enter a name and style. The theme file path will be suggested automatically.")
        self.new_theme_hint_label.setObjectName("selectionSummaryLabel")
        self.new_theme_hint_label.setWordWrap(False)
        new_theme_box_layout.addWidget(self.new_theme_hint_label)
        self.new_theme_browse_btn.clicked.connect(self.browse_new_theme_path)
        self.new_theme_create_btn.clicked.connect(self.create_new_theme_from_template)
        self.new_theme_template_combo.currentIndexChanged.connect(self.suggest_new_theme_path_from_template)
        self.new_theme_name_edit.textChanged.connect(self.suggest_new_theme_path_from_template)
        self.new_theme_path_edit.textEdited.connect(self._mark_new_theme_path_customized)
        self.new_theme_advanced_btn.toggled.connect(self._toggle_new_theme_advanced)
        library_layout.addWidget(self.new_theme_options_box)
        theme_browser_box = QGroupBox("Themes")
        self.theme_browser_box = theme_browser_box
        theme_browser_box.setObjectName("librarySectionBox")
        theme_browser_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        theme_browser_layout = QVBoxLayout(theme_browser_box)
        theme_browser_controls = QHBoxLayout()
        theme_browser_controls.setSpacing(6)
        self.library_theme_filter_edit = QLineEdit()
        self.library_theme_filter_edit.setPlaceholderText("Search by theme name...")
        self.library_theme_type_combo = QComboBox()
        self.library_theme_type_combo.addItems(["All", "Theme", "Image", "Local", "TTCR", "Animated"])
        self.library_theme_sort_combo = QComboBox()
        self.library_theme_sort_combo.addItems(["Name A-Z", "Name Z-A", "Newest", "Oldest"])
        self.theme_browser_controls_search_label = QLabel("Search")
        self.theme_browser_controls_type_label = QLabel("Type")
        self.theme_browser_controls_sort_label = QLabel("Sort")
        theme_browser_controls.addWidget(self.theme_browser_controls_search_label)
        theme_browser_controls.addWidget(self.library_theme_filter_edit, 1)
        theme_browser_controls.addWidget(self.theme_browser_controls_type_label)
        theme_browser_controls.addWidget(self.library_theme_type_combo)
        theme_browser_controls.addWidget(self.theme_browser_controls_sort_label)
        theme_browser_controls.addWidget(self.library_theme_sort_combo)
        theme_browser_layout.addLayout(theme_browser_controls)
        self.library_current_theme_label = QLabel("No active theme.")
        self.library_current_theme_label.setObjectName("selectionSummaryLabel")
        self.library_current_theme_label.setWordWrap(True)
        theme_browser_layout.addWidget(self.library_current_theme_label)
        theme_browser_scroll = QScrollArea()
        self.theme_browser_scroll = theme_browser_scroll
        theme_browser_scroll.setWidgetResizable(True)
        theme_browser_scroll.setFrameShape(QScrollArea.NoFrame)
        theme_browser_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        theme_browser_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        theme_browser_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        theme_browser_scroll.viewport().installEventFilter(self)
        self.library_theme_cards_container = QWidget()
        self.library_theme_cards_layout = QGridLayout(self.library_theme_cards_container)
        self.library_theme_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.library_theme_cards_layout.setHorizontalSpacing(12)
        self.library_theme_cards_layout.setVerticalSpacing(12)
        self.library_theme_cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        theme_browser_scroll.setWidget(self.library_theme_cards_container)
        theme_browser_layout.addWidget(theme_browser_scroll)
        library_layout.addWidget(theme_browser_box, 0)
        self.library_theme_filter_edit.textChanged.connect(self._rebuild_library_theme_browser)
        self.library_theme_type_combo.currentTextChanged.connect(self._rebuild_library_theme_browser)
        self.library_theme_sort_combo.currentTextChanged.connect(self._rebuild_library_theme_browser)
        asset_gallery_box = QGroupBox("Theme Assets")
        self.asset_gallery_box = asset_gallery_box
        asset_gallery_box.setObjectName("librarySectionBox")
        asset_gallery_layout = QVBoxLayout(asset_gallery_box)
        asset_gallery_scroll = QScrollArea()
        asset_gallery_scroll.setWidgetResizable(True)
        asset_gallery_scroll.setFrameShape(QScrollArea.NoFrame)
        self.asset_gallery_container = QWidget()
        self.asset_gallery_layout = QGridLayout(self.asset_gallery_container)
        self.asset_gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.asset_gallery_layout.setHorizontalSpacing(10)
        self.asset_gallery_layout.setVerticalSpacing(10)
        asset_gallery_scroll.setWidget(self.asset_gallery_container)
        asset_gallery_layout.addWidget(asset_gallery_scroll)
        asset_gallery_box.hide()
        library_layout.addStretch(1)

        studio_left_scroll = QScrollArea()
        studio_left_scroll.setWidgetResizable(True)
        studio_left_scroll.setFrameShape(QScrollArea.NoFrame)
        studio_left_container = QWidget()
        studio_left_layout = QVBoxLayout(studio_left_container)
        studio_left_layout.setContentsMargins(0, 0, 0, 0)
        studio_left_layout.setSpacing(10)
        studio_left_scroll.setWidget(studio_left_container)
        designer_workspace_layout.addWidget(studio_left_scroll, 1)
        self.studio_splitter = None
        self.studio_right_container = None
        studio_left_scroll.setMinimumWidth(0)

        studio_left_tabs = QTabWidget()
        self.studio_left_tabs = studio_left_tabs
        studio_left_tabs.setDocumentMode(True)
        studio_left_tabs.tabBar().hide()
        studio_left_tabs.setMinimumHeight(760)
        studio_left_layout.addWidget(studio_left_tabs, 1)
        studio_left_tabs.currentChanged.connect(lambda _idx: self._animate_widget_fade(studio_left_tabs.currentWidget()))
        json_tab = QWidget()
        json_tab_layout = QVBoxLayout(json_tab)
        json_tab_layout.setContentsMargins(0, 0, 0, 0)
        json_tab_layout.setSpacing(10)
        designer_tab = QWidget()
        designer_tab_layout = QVBoxLayout(designer_tab)
        designer_tab_layout.setContentsMargins(0, 0, 0, 0)
        designer_tab_layout.setSpacing(4)
        studio_left_tabs.addTab(designer_tab, "Designer")
        studio_left_tabs.addTab(json_tab, "JSON")

        self.theme_doc_box = QGroupBox("Theme")
        theme_doc_grid = QGridLayout(self.theme_doc_box)
        theme_doc_grid.setColumnStretch(1, 1)
        self.theme_doc_path_edit = QLineEdit(str(Path("themes/linux_matrix_blue.json")))
        self.theme_doc_browse_btn = QPushButton("Browse theme…")
        self.theme_doc_use_selected_btn = QPushButton("From active theme")
        self.theme_doc_load_btn = QPushButton("Load")
        self.theme_doc_save_btn = QPushButton("Save")
        self.theme_doc_save_as_btn = QPushButton("Save As")
        self.theme_doc_apply_btn = QPushButton("Apply")
        self.theme_doc_apply_btn.setObjectName("primaryButton")
        self.theme_doc_stop_before_apply_chk = QCheckBox("Stop runtime before apply")
        self.theme_doc_stop_before_apply_chk.setChecked(True)
        self.theme_doc_resume_chk = QCheckBox("Resume loop after apply")
        self.theme_doc_resume_chk.setChecked(False)
        self.theme_schema_label = QLabel("-")
        self.theme_doc_editor = QTextEdit()
        self.theme_doc_editor.setPlaceholderText("{\n  \"schema_version\": 1,\n  ...\n}")
        self.theme_doc_editor.setMinimumHeight(460)
        self.theme_doc_editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.theme_doc_editor.textChanged.connect(self._handle_theme_doc_editor_changed)
        self.theme_doc_browse_btn.clicked.connect(self.browse_theme_doc_path)
        self.theme_doc_use_selected_btn.clicked.connect(self.use_selected_theme_doc)
        self.theme_doc_load_btn.clicked.connect(self.load_theme_doc)
        self.theme_doc_save_btn.clicked.connect(self.save_theme_doc)
        self.theme_doc_save_as_btn.clicked.connect(lambda: self.save_theme_doc_as(from_animation_studio=False))
        self.theme_doc_apply_btn.clicked.connect(self.apply_theme_doc)
        self.theme_doc_open_external_btn = QPushButton("Open JSON file…")
        self.theme_doc_open_external_btn.setObjectName("secondaryAccentButton")
        self.theme_doc_insert_guide_btn = QPushButton("Insert field guide")
        self.theme_doc_open_external_btn.clicked.connect(
            lambda: self.open_current_theme_json_externally(from_animation_studio=False)
        )
        self.theme_doc_insert_guide_btn.clicked.connect(self.insert_theme_json_field_guide_in_editor)
        self.theme_doc_path_caption = QLabel("Theme file:")
        theme_doc_grid.addWidget(self.theme_doc_path_caption, 0, 0)
        theme_doc_grid.addWidget(self.theme_doc_path_edit, 0, 1, 1, 3)
        theme_doc_grid.addWidget(self.theme_doc_browse_btn, 0, 4)
        theme_doc_grid.addWidget(self.theme_doc_use_selected_btn, 0, 5)
        theme_doc_grid.addWidget(self.theme_doc_stop_before_apply_chk, 1, 1, 1, 2)
        theme_doc_grid.addWidget(self.theme_doc_resume_chk, 1, 3)
        theme_doc_grid.addWidget(self.theme_doc_load_btn, 1, 4)
        theme_doc_grid.addWidget(self.theme_doc_save_btn, 1, 5)
        self.theme_doc_manual_json_label = QLabel("Manual JSON:")
        theme_doc_grid.addWidget(self.theme_doc_manual_json_label, 2, 0)
        theme_doc_grid.addWidget(self.theme_doc_open_external_btn, 2, 1, 1, 2)
        theme_doc_grid.addWidget(self.theme_doc_insert_guide_btn, 2, 3)
        theme_doc_grid.addWidget(self.theme_doc_save_as_btn, 2, 4)
        theme_doc_grid.addWidget(self.theme_doc_apply_btn, 2, 5)
        self.theme_doc_sources_caption = QLabel("Declared stats:")
        theme_doc_grid.addWidget(self.theme_doc_sources_caption, 3, 0)
        theme_doc_grid.addWidget(self.theme_schema_label, 3, 1, 1, 4)
        theme_doc_grid.addWidget(self.theme_doc_editor, 4, 0, 1, 6)
        json_tab_layout.addWidget(self.theme_doc_box, 1)
        self.theme_doc_box.hide()

        designer_box = QGroupBox("")
        designer_box.setObjectName("designerWorkspaceBox")
        designer_box.setFlat(True)
        designer_outer = QVBoxLayout(designer_box)
        designer_outer.setContentsMargins(0, 0, 0, 0)
        designer_outer.setSpacing(4)

        # 1. INICJALIZACJA WSZYSTKICH WIDŻETÓW (BEZPIECZNIE NA POCZĄTKU)
        self.preview_label = PreviewLabel(self)
        self.designer_element_list = LayerListWidget()
        self.designer_element_list.setObjectName("designerLayerList")
        self.designer_kind_combo = QComboBox()
        self.designer_kind_combo.addItem("Teksty", "texts"); self.designer_kind_combo.addItem("Statystyki", "stats")
        self.designer_kind_combo.addItem("Obrazy", "images"); self.designer_kind_combo.addItem("Panele", "panels")
        self.designer_kind_combo.addItem("Widgety", "widgets")
        self.designer_selection_label = QLabel("Zaznacz element")
        
        self.designer_id_edit = QLineEdit()
        self.designer_x_spin = QSpinBox(); self.designer_x_spin.setRange(-5000, 5000)
        self.designer_y_spin = QSpinBox(); self.designer_y_spin.setRange(-5000, 5000)
        self.designer_w_spin = QSpinBox(); self.designer_w_spin.setRange(1, 5000)
        self.designer_h_spin = QSpinBox(); self.designer_h_spin.setRange(1, 5000)
        self.designer_z_spin = QSpinBox(); self.designer_z_spin.setRange(-1000, 1000)
        self.designer_rotation_spin = QSpinBox(); self.designer_rotation_spin.setRange(0, 360)
        self.designer_opacity_spin = QDoubleSpinBox(); self.designer_opacity_spin.setRange(0.0, 1.0); self.designer_opacity_spin.setSingleStep(0.1)
        self.designer_text_edit = QLineEdit(); self.designer_label_edit = QLineEdit(); self.designer_format_edit = QLineEdit()
        self.designer_source_combo = QComboBox(); self._populate_designer_source_combo()
        self.designer_stat_display_combo = QComboBox(); self.designer_stat_display_combo.addItems(
            [mode for mode in ("text", "progress", "gauge", "sparkline", "equalizer") if mode in KNOWN_STAT_DISPLAY]
        )
        self.designer_stat_min_spin = QDoubleSpinBox(); self.designer_stat_min_spin.setRange(-999999.0, 999999.0); self.designer_stat_min_spin.setDecimals(2)
        self.designer_stat_max_spin = QDoubleSpinBox(); self.designer_stat_max_spin.setRange(-999999.0, 999999.0); self.designer_stat_max_spin.setDecimals(2); self.designer_stat_max_spin.setValue(100.0)
        self.designer_stat_show_value_chk = QCheckBox("Pokaż wartość")
        self.designer_color_edit = QLineEdit(); self.designer_label_color_edit = QLineEdit(); self.designer_value_color_edit = QLineEdit()
        self.designer_track_color_edit = QLineEdit(); self.designer_fill_color_edit = QLineEdit()
        self.designer_align_combo = QComboBox(); self.designer_align_combo.addItems(["left", "center", "right"])
        self.designer_font_family_combo = QComboBox(); self.designer_font_family_combo.addItems(available_font_families())
        self.designer_font_size_spin = QSpinBox(); self.designer_font_size_spin.setRange(6, 200)
        self.designer_stat_stroke_width_spin = QSpinBox()
        self.designer_stat_stroke_width_spin.setRange(0, 64)
        self.designer_stat_stroke_width_spin.setSpecialValueText("auto")
        self.designer_stat_stroke_width_spin.setValue(12)
        self.designer_stat_gauge_preset_combo = QComboBox()
        self._populate_designer_stat_gauge_preset_combo()
        self.designer_gauge_low_edit = QLineEdit()
        self.designer_gauge_mid_edit = QLineEdit()
        self.designer_gauge_high_edit = QLineEdit()
        self.designer_gauge_smooth_spin = QDoubleSpinBox()
        self.designer_gauge_smooth_spin.setRange(0.05, 1.0)
        self.designer_gauge_smooth_spin.setSingleStep(0.05)
        self.designer_gauge_smooth_spin.setDecimals(2)
        self.designer_gauge_smooth_spin.setValue(0.32)
        self.designer_gauge_match_value_chk = QCheckBox("Kolor wartości jak łuk")
        self.designer_gauge_match_value_chk.setChecked(True)
        self.designer_gauge_inner_alpha_spin = QDoubleSpinBox()
        self.designer_gauge_inner_alpha_spin.setRange(0.0, 1.0)
        self.designer_gauge_inner_alpha_spin.setSingleStep(0.05)
        self.designer_gauge_inner_alpha_spin.setDecimals(2)
        self.designer_gauge_inner_alpha_spin.setValue(1.0)
        self.designer_gauge_inner_alpha_spin.setToolTip(
            "Przezroczystość wypełnienia środka gauge (nie wpływa na łuk ani tekst)."
        )
        self.designer_gauge_ring_spin = QSpinBox()
        self.designer_gauge_ring_spin.setRange(40, 900)
        self.designer_gauge_ring_spin.setSuffix(" px")
        self.designer_gauge_ring_spin.setToolTip(
            "Średnica pierścienia (okręgu) gauge. Pole ramki (Szer./Wys. w Pozycja) powinno być większe "
            "— przy układzie „Pod gauge” lub „Z boku” zwiększ wysokość lub szerokość."
        )
        self.designer_gauge_value_layout_combo = QComboBox()
        self.designer_gauge_value_layout_combo.addItem("W środku pierścienia", "center")
        self.designer_gauge_value_layout_combo.addItem("Pod spodem (wartość pod łukiem)", "below")
        self.designer_gauge_value_layout_combo.addItem("Z boku (wartość po prawej)", "beside")
        self.designer_sparkline_points_spin = QSpinBox()
        self.designer_sparkline_points_spin.setRange(8, 240)
        self.designer_sparkline_points_spin.setValue(42)
        self.designer_sparkline_fill_opacity_spin = QDoubleSpinBox()
        self.designer_sparkline_fill_opacity_spin.setRange(0.0, 1.0)
        self.designer_sparkline_fill_opacity_spin.setSingleStep(0.05)
        self.designer_sparkline_fill_opacity_spin.setDecimals(2)
        self.designer_sparkline_fill_opacity_spin.setValue(0.18)
        self.designer_sparkline_show_points_chk = QCheckBox("Pokaż punkt końcowy")
        self.designer_sparkline_show_points_chk.setChecked(True)
        self.designer_equalizer_bars_spin = QSpinBox()
        self.designer_equalizer_bars_spin.setRange(6, 64)
        self.designer_equalizer_bars_spin.setValue(18)
        self.designer_equalizer_gap_spin = QSpinBox()
        self.designer_equalizer_gap_spin.setRange(0, 16)
        self.designer_equalizer_gap_spin.setValue(4)
        self.designer_equalizer_mirror_chk = QCheckBox("Mirror from center")
        self.designer_equalizer_mirror_chk.setChecked(False)
        self.widget_title_font_spin = QSpinBox(); self.widget_title_font_spin.setRange(6, 120); self.widget_title_font_spin.setValue(28)
        self.widget_body_font_spin = QSpinBox(); self.widget_body_font_spin.setRange(6, 120); self.widget_body_font_spin.setValue(22)
        self.widget_detail_font_spin = QSpinBox(); self.widget_detail_font_spin.setRange(6, 120); self.widget_detail_font_spin.setValue(18)
        self.widget_title_color_edit = QLineEdit()
        self.widget_body_color_edit = QLineEdit()
        self.widget_detail_color_edit = QLineEdit()
        self.widget_panel_color_edit = QLineEdit()
        self.widget_cover_enabled_chk = QCheckBox("Cover")
        self.widget_cover_enabled_chk.setChecked(True)
        self.widget_backdrop_enabled_chk = QCheckBox("Cover backdrop")
        self.widget_backdrop_enabled_chk.setChecked(True)
        self.widget_title_marquee_chk = QCheckBox("Title marquee")
        self.widget_title_marquee_chk.setChecked(True)
        self.widget_equalizer_enabled_chk = QCheckBox("EQ")
        self.widget_equalizer_enabled_chk.setChecked(True)
        self.weather_widget_title_font_spin = QSpinBox(); self.weather_widget_title_font_spin.setRange(6, 120); self.weather_widget_title_font_spin.setValue(18)
        self.weather_widget_body_font_spin = QSpinBox(); self.weather_widget_body_font_spin.setRange(6, 120); self.weather_widget_body_font_spin.setValue(38)
        self.weather_widget_detail_font_spin = QSpinBox(); self.weather_widget_detail_font_spin.setRange(6, 120); self.weather_widget_detail_font_spin.setValue(18)
        self.weather_widget_title_color_edit = QLineEdit()
        self.weather_widget_body_color_edit = QLineEdit()
        self.weather_widget_detail_color_edit = QLineEdit()
        self.weather_widget_panel_color_edit = QLineEdit()
        self.weather_widget_transparent_bg_chk = QCheckBox("Transparent background")
        self.weather_widget_animate_icons_chk = QCheckBox("Animated icons")
        self.weather_widget_animate_icons_chk.setChecked(True)
        self.designer_theme_gauge_style_combo = QComboBox()
        self._populate_designer_theme_gauge_style_combo()
        self.designer_font_bold_chk = QCheckBox("B")
        self.designer_font_italic_chk = QCheckBox("I")
        self.designer_font_underline_chk = QCheckBox("U")

        self.designer_path_edit = QLineEdit()
        self.designer_fit_combo = QComboBox(); self.designer_fit_combo.addItems(["contain", "cover", "stretch"])
        self.designer_visible_chk = QCheckBox("Visible"); self.designer_locked_chk = QCheckBox("Locked")

        # Inicjalizacja brakujących widżetów paska narzędzi i opcji
        self.designer_mode_combo = QComboBox(); self.designer_mode_combo.addItems(["Simple", "Advanced"])
        self.designer_auto_preview_chk = QCheckBox("Auto-preview"); self.designer_auto_preview_chk.setChecked(True)
        self.designer_snap_chk = QCheckBox("Snap"); self.designer_snap_chk.setChecked(True)
        self.designer_snap_spin = QSpinBox(); self.designer_snap_spin.setRange(1, 128); self.designer_snap_spin.setValue(8)
        self.designer_undo_btn = QPushButton("Undo")
        self.designer_redo_btn = QPushButton("Redo")
        self.designer_animation_mode_btn = QPushButton("Animation"); self.designer_animation_mode_btn.setCheckable(True)
        self.designer_assets_toggle_btn = QPushButton("Media"); self.designer_assets_toggle_btn.setCheckable(True)
        self.designer_details_toggle_btn = QPushButton("Show bottom"); self.designer_details_toggle_btn.setCheckable(True)

        # Inicjalizacja widżetów animacji (ruchu)
        self.motion_enabled_chk = QCheckBox("Animate element")
        self.motion_start_spin = QSpinBox(); self.motion_start_spin.setRange(0, 99999)
        self.motion_end_spin = QSpinBox(); self.motion_end_spin.setRange(0, 99999)
        self.motion_target_x_spin = QSpinBox(); self.motion_target_x_spin.setRange(-5000, 5000)
        self.motion_target_y_spin = QSpinBox(); self.motion_target_y_spin.setRange(-5000, 5000)
        self.motion_target_opacity_spin = QDoubleSpinBox(); self.motion_target_opacity_spin.setRange(0.0, 1.0); self.motion_target_opacity_spin.setSingleStep(0.05)
        self.motion_capture_current_btn = QPushButton("Set end from current")
        self.motion_remove_btn = QPushButton("Remove motion")

        # Widżety Tła / Presetów / Logów
        self.bg_kind_combo = QComboBox(); self.bg_kind_combo.addItems(["generated", "image", "color"])
        self.bg_rotation_spin = QSpinBox(); self.bg_rotation_spin.setRange(0, 270); self.bg_rotation_spin.setSingleStep(90)
        self.bg_base_color_edit = QLineEdit(); self.bg_base_color_btn = QPushButton("🎨")
        self.bg_accent_color_edit = QLineEdit(); self.bg_accent_color_btn = QPushButton("🎨")
        self.bg_texture_alpha_spin = QDoubleSpinBox(); self.bg_texture_alpha_spin.setRange(0.0, 1.0); self.bg_texture_alpha_spin.setSingleStep(0.05)
        self.bg_path_edit = QLineEdit(); self.bg_path_browse_btn = QPushButton("...")
        self.bg_prepare_btn = QPushButton("Import background")
        self.bg_fit_combo = QComboBox(); self.bg_fit_combo.addItems(["cover", "contain", "stretch"])
        self.bg_opacity_spin = QDoubleSpinBox(); self.bg_opacity_spin.setRange(0.0, 1.0); self.bg_opacity_spin.setSingleStep(0.05)
        self.bg_clear_btn = QPushButton("Clear"); self.bg_cover_btn = QPushButton("Cover"); self.bg_contain_btn = QPushButton("Contain")
        self.bg_preset_ocean_btn = QPushButton("Ocean"); self.bg_preset_amber_btn = QPushButton("Amber")
        self.bg_preset_mono_btn = QPushButton("Mono"); self.bg_preset_neon_btn = QPushButton("Neon")
        self.bg_show_grid_chk = QCheckBox("Grid"); self.bg_show_safe_chk = QCheckBox("Safe Area")
        self.panel_fill_edit = QLineEdit(); self.panel_fill_btn = QPushButton("🎨")
        self.panel_radius_spin = QSpinBox(); self.panel_radius_spin.setRange(0, 500)
        self.panel_opacity_spin = QDoubleSpinBox(); self.panel_opacity_spin.setRange(0.0, 1.0); self.panel_opacity_spin.setSingleStep(0.05)
        self.background_preview_label = QLabel("Background preview")
        
        # Inicjalizacja widżetów animacji tła
        self.bg_animation_enabled_chk = QCheckBox("Animation enabled")
        self.bg_animation_use_bg_chk = QCheckBox("Use as background")
        self.bg_animation_fps_spin = QDoubleSpinBox(); self.bg_animation_fps_spin.setRange(1.0, 60.0); self.bg_animation_fps_spin.setValue(12.0)
        self.bg_animation_frame_spin = QSpinBox(); self.bg_animation_frame_spin.setRange(0, 99999)
        self.bg_animation_duration_spin = QSpinBox(); self.bg_animation_duration_spin.setRange(1, 60000); self.bg_animation_duration_spin.setValue(83)
        self.bg_animation_prev_btn = QPushButton("◀")
        self.bg_animation_next_btn = QPushButton("▶")
        self.bg_animation_clear_btn = QPushButton("Clear animation")
        self.bg_animation_timeline = AnimationTimelineWidget()
        self.bg_animation_remove_btn = QPushButton("Remove")
        self.bg_animation_duplicate_btn = QPushButton("Duplicate")
        self.animation_duplicate_repeat_spin = QSpinBox()
        self.animation_duplicate_repeat_spin.setRange(1, 99)
        self.animation_duplicate_repeat_spin.setValue(1)
        self.animation_duplicate_repeat_spin.setMaximumWidth(72)
        self.bg_animation_hold_repeat_btn = QPushButton("Hold ×N")
        self.bg_animation_reverse_btn = QPushButton("Reverse")
        self.bg_animation_pingpong_btn = QPushButton("Ping-pong")
        self.bg_animation_normalize_duration_btn = QPushButton("Normalize")
        self.animation_stabilize_btn = QPushButton("Stabilize")
        self.animation_stabilize_mode_combo = QComboBox()
        self.animation_stabilize_mode_combo.addItem("Safe Translation", "safe_translation")
        self.animation_stabilize_mode_combo.addItem("Auto Safe", "auto_safe")
        self.animation_stabilize_mode_combo.addItem("Affine", "affine")
        self.animation_stabilize_mode_combo.addItem("Euclidean", "euclidean")
        self.animation_stabilize_mode_combo.addItem("Translation", "translation")
        self.animation_select_range_btn = QPushButton("Range")
        self.animation_invert_selection_btn = QPushButton("Invert")
        self.animation_clear_selection_btn = QPushButton("Clear Sel")
        self.animation_loop_from_selection_btn = QPushButton("Loop Sel")
        self.animation_trim_selection_btn = QPushButton("Trim Sel")
        self.bg_animation_repeat_all_btn = QPushButton("Duplicate sequence ×N")
        self.animation_timeline_zoom_combo = QComboBox()
        self.animation_timeline_zoom_combo.addItems(["75%", "100%", "150%", "200%", "300%"])
        self.animation_timeline_zoom_combo.setCurrentText("100%")
        self.animation_timeline_home_btn = QPushButton("Start")
        self.animation_timeline_end_btn = QPushButton("End")
        self.animation_loop_in_btn = QPushButton("Set In")
        self.animation_loop_out_btn = QPushButton("Set Out")
        self.animation_loop_clear_btn = QPushButton("Clear Loop")
        self.animation_loop_close_seam_btn = QPushButton("Close Seam")
        self.animation_loop_label = QLabel("Loop: full")
        self.animation_onion_skin_chk = QCheckBox("Onion skin")
        self.animation_onion_opacity_spin = QDoubleSpinBox()
        self.animation_onion_opacity_spin.setRange(0.05, 0.85)
        self.animation_onion_opacity_spin.setSingleStep(0.05)
        self.animation_onion_opacity_spin.setValue(0.28)
        self.animation_onion_opacity_spin.setMaximumWidth(84)
        self.bg_animation_up_btn = QPushButton("▲")
        self.bg_animation_down_btn = QPushButton("▼")
        self.bg_animation_play_btn = QPushButton("▶ Play")
        self.bg_animation_count_label = QLabel("0 frames")
        self.bg_animation_list = LayerListWidget()
        self.bg_animation_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.bg_animation_add_btn = QPushButton("Add")
        self.bg_animation_blank_btn = QPushButton("Blank")
        self.bg_animation_export_btn = QPushButton("Export")
        self.animation_export_loop_btn = QPushButton("Export Loop")
        self.animation_export_selection_btn = QPushButton("Export Sel")
        self.bg_animation_import_btn = QPushButton("Import")
        self.animation_bulk_duration_spin = QSpinBox()
        self.animation_bulk_duration_spin.setRange(1, 60000)
        self.animation_bulk_duration_spin.setValue(83)
        self.animation_bulk_apply_duration_btn = QPushButton("Apply duration to selection")
        self.layout_preset_name_edit = QLineEdit(); self.layout_preset_combo = QComboBox()
        self.layout_preset_save_btn = QPushButton("Save preset"); self.layout_preset_load_btn = QPushButton("Load preset")
        self.layout_preset_delete_btn = QPushButton("Delete preset")
        self.designer_toolbar_feedback_label = QLabel("Designer ready.")
        self.designer_toolbar_feedback_label.setObjectName("previewHintLabel")
        self.designer_toolbar_feedback_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.designer_toolbar_feedback_label.setMinimumWidth(0)
        self.designer_toolbar_feedback_label.setMaximumWidth(210)
        self.designer_toolbar_feedback_label.hide()
        self.designer_toolbar_feedback_timer = QTimer(self)
        self.designer_toolbar_feedback_timer.setSingleShot(True)
        self.designer_toolbar_feedback_timer.timeout.connect(lambda: self._set_designer_toolbar_feedback("", auto_clear_ms=None))
        self.designer_save_state_label = QLabel("")
        self.designer_save_state_label.setObjectName("layerBadgeLabel")
        self.designer_save_state_label.setMinimumWidth(86)
        self.designer_save_state_label.setAlignment(Qt.AlignCenter)

        # 2. GŁÓWNY UKŁAD (Sidebar + Content) Z UŻYCIEM SPLITTERÓW
        self.designer_main_splitter = QSplitter(Qt.Horizontal)
        self.designer_main_splitter.setChildrenCollapsible(False)
        designer_outer.addWidget(self.designer_main_splitter, 1)

        # LEWY PANEL (Warstwy) - domyślnie szerszy
        self.designer_layers_container = QWidget()
        self.designer_layers_container.setMinimumWidth(380)
        self._setup_designer_layers_panel(QVBoxLayout(self.designer_layers_container))
        self.designer_main_splitter.addWidget(self.designer_layers_container)

        # PRAWY PANEL (Studio) - rozciągalny
        studio_right = QWidget()
        studio_layout = QVBoxLayout(studio_right)
        studio_layout.setContentsMargins(0, 0, 0, 0)
        studio_layout.setSpacing(4)
        self.designer_main_splitter.addWidget(studio_right)

        # Ustawienie domyślnych proporcji głównego splittera
        self.designer_main_splitter.setStretchFactor(0, 0)
        self.designer_main_splitter.setStretchFactor(1, 1)
        self.designer_main_splitter.setSizes([580, 1340])

        # TOOLBAR (Przyciski akcji nad LCD)
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("background: rgba(30, 41, 59, 0.6); border-radius: 14px; border: 1px solid #334155;")
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(6)

        self.designer_reload_btn = AnimatedToolbarButton("Load theme")
        self.designer_reload_btn.setObjectName("secondaryAccentButton")
        self.designer_write_btn = AnimatedToolbarButton("Save theme")
        self.designer_write_btn.setObjectName("secondaryAccentButton")
        self.designer_save_as_btn = AnimatedToolbarButton("Save As")
        self.designer_save_as_btn.setObjectName("secondaryAccentButton")
        self.designer_open_json_btn = AnimatedToolbarButton("Open JSON…")
        self.designer_open_json_btn.setObjectName("secondaryAccentButton")
        self.designer_animation_mode_btn = AnimatedToolbarButton("Animation")
        self.designer_animation_mode_btn.setCheckable(True)
        self.designer_animation_mode_btn.setObjectName("modeToggleButton")
        self.designer_assets_toggle_btn = AnimatedToolbarButton("Media")
        self.designer_assets_toggle_btn.setCheckable(True)
        self.designer_assets_toggle_btn.setObjectName("modeToggleButton")
        self.designer_preview_btn = AnimatedToolbarButton("Preview")
        self.designer_preview_btn.setObjectName("secondaryAccentButton")
        self.designer_apply_btn = AnimatedToolbarButton("Apply theme")
        self.designer_apply_btn.setObjectName("primaryButton")

        for btn in [
            self.designer_reload_btn,
            self.designer_write_btn,
            self.designer_save_as_btn,
            self.designer_open_json_btn,
            self.designer_animation_mode_btn,
            self.designer_assets_toggle_btn,
            self.designer_preview_btn,
            self.designer_apply_btn,
        ]:
            btn.setMinimumHeight(36)
            btn.setMaximumHeight(40)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            font = btn.font()
            font.setPointSize(max(10, font.pointSize()))
            font.setBold(True)
            btn.setFont(font)

        toolbar_layout.addWidget(self.designer_reload_btn)
        toolbar_layout.addWidget(self.designer_write_btn)
        toolbar_layout.addWidget(self.designer_save_as_btn)
        toolbar_layout.addWidget(self.designer_open_json_btn)
        toolbar_layout.addWidget(self.designer_animation_mode_btn)
        toolbar_layout.addWidget(self.designer_assets_toggle_btn)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.designer_save_state_label, 0, Qt.AlignVCenter)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self.designer_toolbar_feedback_label, 0, Qt.AlignVCenter)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.designer_preview_btn)
        toolbar_layout.addWidget(self.designer_apply_btn)
        studio_layout.addWidget(toolbar_frame)

        theme_gauge_bar = QWidget()
        theme_gauge_layout = QHBoxLayout(theme_gauge_bar)
        theme_gauge_layout.setContentsMargins(0, 0, 0, 2)
        theme_gauge_layout.setSpacing(6)
        self.designer_theme_gauge_bar_label = QLabel("Default gauge preset (meta.gauge_style):")
        theme_gauge_layout.addWidget(self.designer_theme_gauge_bar_label)
        theme_gauge_layout.addWidget(self.designer_theme_gauge_style_combo, 1)
        studio_layout.addWidget(theme_gauge_bar)

        # PIONOWY SPLITTER DLA LCD I INSPECTORA
        self.designer_top_splitter = QSplitter(Qt.Vertical)
        self.designer_top_splitter.setChildrenCollapsible(False)
        self.designer_top_splitter.splitterMoved.connect(lambda _pos, _idx: self._clamp_designer_splitter_later())
        studio_layout.addWidget(self.designer_top_splitter, 1)

        # LCD PREVIEW (Góra prawego panelu)
        self.designer_canvas_workbench = QFrame()
        self.designer_canvas_workbench.setObjectName("designerSectionBox")
        self.designer_canvas_workbench.setMinimumHeight(300)
        self.designer_canvas_workbench.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas_vbox = QVBoxLayout(self.designer_canvas_workbench)
        canvas_vbox.setContentsMargins(0, 0, 0, 0) # Przejmujemy niewykorzystaną część
        canvas_vbox.setSpacing(2)

        preview_tools_row = QHBoxLayout()
        preview_tools_row.setContentsMargins(10, 6, 10, 0)
        preview_tools_row.setSpacing(6)
        self.preview_tools_label = QLabel("Mouse:")
        self.preview_tools_label.setObjectName("selectionSummaryLabel")
        preview_tools_row.addWidget(self.preview_tools_label)
        self.designer_active_tool_label = QLabel("Auto")
        self.designer_active_tool_label.setObjectName("selectionSummaryLabel")
        self.designer_active_tool_label.setMinimumWidth(78)
        self.designer_active_tool_label.setAlignment(Qt.AlignCenter)
        self.designer_active_tool_label.setStyleSheet(
            "background: rgba(31, 111, 235, 0.18); border: 1px solid rgba(94, 200, 255, 0.35); "
            "border-radius: 8px; padding: 3px 8px; font-weight: 700;"
        )
        preview_tools_row.addWidget(self.designer_active_tool_label)
        self.designer_tool_auto_btn = AnimatedToolbarButton("Auto")
        self.designer_tool_select_btn = AnimatedToolbarButton("Select")
        self.designer_tool_move_btn = AnimatedToolbarButton("Move")
        self.designer_tool_scale_btn = AnimatedToolbarButton("Scale")
        self.designer_tool_crop_btn = AnimatedToolbarButton("Crop")
        self.designer_crop_reset_btn = AnimatedToolbarButton("Reset crop")
        self.designer_preview_undo_btn = AnimatedToolbarButton("↶")
        self.designer_preview_redo_btn = AnimatedToolbarButton("↷")
        self.designer_align_left_btn = AnimatedToolbarButton("⟸")
        self.designer_align_top_btn = AnimatedToolbarButton("⇑")
        self.designer_align_center_h_btn = AnimatedToolbarButton("↔")
        self.designer_align_center_v_btn = AnimatedToolbarButton("↕")
        self.designer_align_bottom_btn = AnimatedToolbarButton("⇓")
        self.designer_align_right_btn = AnimatedToolbarButton("⟹")
        self.designer_crop_reset_btn.setObjectName("secondaryAccentButton")
        for btn in (
            self.designer_tool_auto_btn,
            self.designer_tool_select_btn,
            self.designer_tool_move_btn,
            self.designer_tool_scale_btn,
            self.designer_tool_crop_btn,
        ):
            btn.setCheckable(True)
            btn.setMinimumHeight(26)
            btn.setMaximumHeight(28)
            btn.setMinimumWidth(56)
            btn.setObjectName("modeToggleButton")
        for btn in (
            self.designer_crop_reset_btn,
            self.designer_preview_undo_btn,
            self.designer_preview_redo_btn,
            self.designer_align_left_btn,
            self.designer_align_top_btn,
            self.designer_align_center_h_btn,
            self.designer_align_center_v_btn,
            self.designer_align_bottom_btn,
            self.designer_align_right_btn,
        ):
            btn.setMinimumHeight(26)
            btn.setMaximumHeight(28)
        for btn in (
            self.designer_preview_undo_btn,
            self.designer_preview_redo_btn,
            self.designer_align_left_btn,
            self.designer_align_top_btn,
            self.designer_align_center_h_btn,
            self.designer_align_center_v_btn,
            self.designer_align_bottom_btn,
            self.designer_align_right_btn,
        ):
            btn.setMinimumWidth(30)
            btn.setMaximumWidth(34)
            btn.setObjectName("secondaryAccentButton")
        self.designer_preview_undo_btn.setToolTip(self._tr("Undo designer change", "Cofnij zmianę w projektancie"))
        self.designer_preview_redo_btn.setToolTip(self._tr("Redo designer change", "Ponów zmianę w projektancie"))
        self.designer_align_left_btn.setToolTip(self._tr("Align selected element to the left edge", "Wyrównaj zaznaczenie do lewej krawędzi"))
        self.designer_align_top_btn.setToolTip(self._tr("Align selected element to the top edge", "Wyrównaj zaznaczenie do górnej krawędzi"))
        self.designer_align_center_h_btn.setToolTip(self._tr("Center selected element horizontally", "Wycentruj zaznaczenie w poziomie"))
        self.designer_align_center_v_btn.setToolTip(self._tr("Center selected element vertically", "Wycentruj zaznaczenie w pionie"))
        self.designer_align_bottom_btn.setToolTip(self._tr("Align selected element to the bottom edge", "Wyrównaj zaznaczenie do dolnej krawędzi"))
        self.designer_align_right_btn.setToolTip(self._tr("Align selected element to the right edge", "Wyrównaj zaznaczenie do prawej krawędzi"))
        self.designer_tool_auto_btn.setToolTip(
            self._tr(
                "Auto: click to select, drag selected bounds to move, drag handles to resize.",
                "Auto: klik zaznacza, przeciąganie ramki przesuwa, uchwyty zmieniają rozmiar.",
            )
        )
        self.designer_tool_select_btn.setToolTip(
            self._tr(
                "Select: click an element or drag a box to select multiple layers.",
                "Zaznaczanie: kliknij element albo przeciągnij ramkę, aby wybrać kilka warstw.",
            )
        )
        self.designer_tool_move_btn.setToolTip(
            self._tr(
                "Move: drag elements on the LCD preview without resizing them.",
                "Przesuwanie: przeciągaj elementy na podglądzie LCD bez zmiany rozmiaru.",
            )
        )
        self.designer_tool_scale_btn.setToolTip(
            self._tr(
                "Scale: drag an element edge or corner to resize it on the preview.",
                "Skalowanie: przeciągnij bok albo narożnik elementu, aby zmienić rozmiar.",
            )
        )
        preview_tools_row.addWidget(self.designer_tool_auto_btn)
        preview_tools_row.addWidget(self.designer_tool_select_btn)
        preview_tools_row.addWidget(self.designer_tool_move_btn)
        preview_tools_row.addWidget(self.designer_tool_scale_btn)
        preview_tools_row.addWidget(self.designer_tool_crop_btn)
        preview_tools_row.addSpacing(4)
        preview_tools_row.addWidget(self.designer_preview_undo_btn)
        preview_tools_row.addWidget(self.designer_preview_redo_btn)
        preview_tools_row.addSpacing(4)
        preview_tools_row.addWidget(self.designer_snap_chk)
        preview_tools_row.addWidget(self.designer_snap_spin)
        preview_tools_row.addSpacing(4)
        preview_tools_row.addWidget(self.designer_align_left_btn)
        preview_tools_row.addWidget(self.designer_align_top_btn)
        preview_tools_row.addWidget(self.designer_align_center_h_btn)
        preview_tools_row.addWidget(self.designer_align_center_v_btn)
        preview_tools_row.addWidget(self.designer_align_bottom_btn)
        preview_tools_row.addWidget(self.designer_align_right_btn)
        preview_tools_row.addSpacing(6)
        preview_tools_row.addWidget(self.designer_crop_reset_btn)
        preview_tools_row.addStretch(1)
        canvas_vbox.addLayout(preview_tools_row)
        
        preview_scroll = LcdPreviewScrollArea()
        self.designer_preview_scroll = preview_scroll
        preview_scroll.setWidgetResizable(True); preview_scroll.setAlignment(Qt.AlignCenter)
        preview_scroll.setFrameShape(QFrame.NoFrame); preview_scroll.setWidget(self.preview_label)
        canvas_vbox.addWidget(preview_scroll, 0)
        
        info_row = QHBoxLayout()
        info_row.setContentsMargins(10, 0, 10, 10)
        self.preview_info_label = QLabel("💡 Wskazówka: Możesz przesuwać elementy bezpośrednio na podglądzie.")
        self.preview_info_label.setObjectName("previewHintLabel")
        self.preview_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.preview_coords_label = QLabel("x: -, y: -")
        self.preview_coords_label.setObjectName("previewHintLabel")
        self.preview_delta_label = QLabel("Δx: 0, Δy: 0")
        self.preview_delta_label.setObjectName("previewHintLabel")
        self.preview_guides_chk = QCheckBox("Show layer bounds")
        self.preview_guides_chk.setChecked(True)
        self.preview_guides_chk.toggled.connect(self._update_preview_canvas_overlay)
        
        info_row.addWidget(self.preview_info_label, 1)
        info_row.addWidget(self.preview_guides_chk)
        info_row.addWidget(self.preview_coords_label)
        info_row.addWidget(self.preview_delta_label)
        canvas_vbox.addLayout(info_row)
        
        self.designer_top_splitter.addWidget(self.designer_canvas_workbench)

        # INSPECTOR (Właściwości - Powiększony do góry)
        self.designer_inspector_container = QWidget()
        self.designer_inspector_container.setMinimumHeight(180)
        self.designer_inspector_container.setMaximumHeight(440)
        self.designer_inspector_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._setup_inspector_tabs(QVBoxLayout(self.designer_inspector_container))
        self.designer_stat_display_combo.currentTextChanged.connect(
            lambda _t: self._update_gauge_stat_inspector_visibility()
        )
        self.designer_theme_gauge_style_combo.currentIndexChanged.connect(self._on_designer_theme_gauge_style_changed)
        self.designer_top_splitter.addWidget(self.designer_inspector_container)

        # Ograniczamy wysokość Inspectora, dajemy więcej miejsca dla LCD
        self.designer_top_splitter.setStretchFactor(0, 5) # Canvas
        self.designer_top_splitter.setStretchFactor(1, 0) # Inspector
        self.designer_top_splitter.setSizes([430, 360])

        designer_tab_layout.addWidget(designer_box, 1)

        # LOGI API (Przeniesione na osobny layout, by nie przeszkadzały w Designerze)
        log_box = QGroupBox("API & application logs")
        self.log_panel_box = log_box
        log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(14, 14, 14, 14)
        log_layout.setSpacing(10)
        
        log_toolbar = QHBoxLayout()
        self.log_filter_edit = QLineEdit()
        self.log_filter_edit.setPlaceholderText("Filter logs…")
        self.log_filter_edit.textChanged.connect(lambda: self._refresh_log_view(force=True))
        self.log_only_errors_chk = QCheckBox("Errors only")
        self.log_only_errors_chk.toggled.connect(lambda: self._refresh_log_view(force=True))
        self.log_hide_status_chk = QCheckBox("Hide status lines")
        self.log_hide_status_chk.setChecked(True)
        self.log_hide_status_chk.toggled.connect(lambda: self._refresh_log_view(force=True))
        self.log_copy_btn = QPushButton("Copy view")
        self.log_copy_btn.clicked.connect(self.copy_filtered_logs)
        self.log_copy_selection_btn = QPushButton("Copy selection")
        self.log_copy_selection_btn.clicked.connect(self.copy_selected_logs)
        self.log_clear_btn = QPushButton("Clear")
        self.log_clear_btn.clicked.connect(self.clear_logs)

        self.log_search_label = QLabel("Search:")
        log_toolbar.addWidget(self.log_search_label)
        log_toolbar.addWidget(self.log_filter_edit, 1)
        log_toolbar.addWidget(self.log_only_errors_chk); log_toolbar.addWidget(self.log_hide_status_chk)
        log_toolbar.addWidget(self.log_copy_btn); log_toolbar.addWidget(self.log_copy_selection_btn)
        log_toolbar.addWidget(self.log_clear_btn)
        log_layout.addLayout(log_toolbar)
        
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_view.setMinimumHeight(420)
        log_layout.addWidget(self.log_view)
        logs_layout.addWidget(log_box, 1)

        # PODPIĘCIE SYGNAŁÓW
        self.designer_reload_btn.clicked.connect(self._trigger_designer_load_theme)
        self.designer_write_btn.clicked.connect(self._trigger_designer_save_theme)
        self.designer_save_as_btn.clicked.connect(lambda: self.save_theme_doc_as(from_animation_studio=False))
        self.designer_open_json_btn.clicked.connect(
            lambda: self.open_current_theme_json_externally(from_animation_studio=False)
        )
        self.designer_preview_btn.clicked.connect(self._trigger_designer_preview)
        self.designer_apply_btn.clicked.connect(self._trigger_designer_apply)
        self.designer_undo_btn.clicked.connect(self.undo_designer_change)
        self.designer_redo_btn.clicked.connect(self.redo_designer_change)
        self.designer_mode_combo.currentTextChanged.connect(self.apply_designer_mode)
        self.designer_animation_mode_btn.toggled.connect(self._sync_designer_preview_policy)
        self.designer_assets_toggle_btn.toggled.connect(self._sync_designer_preview_policy)
        self.designer_details_toggle_btn.toggled.connect(self._sync_designer_preview_policy)
        self.preview_label.element_selected.connect(self._handle_preview_element_selected)
        self.preview_label.element_moved.connect(self.move_designer_element)
        self.preview_label.element_resized.connect(self.resize_designer_element)
        self.preview_label.elements_box_selected.connect(self._handle_preview_elements_box_selected)
        self.preview_label.crop_rect_selected.connect(self._handle_preview_crop_rect_selected)
        self.preview_label.cursor_changed.connect(self.update_preview_coords)
        self.preview_label.drag_started.connect(self.begin_designer_drag)
        self.preview_label.drag_finished.connect(self.finish_designer_drag)
        self.designer_tool_auto_btn.clicked.connect(lambda: self._set_designer_mouse_tool("auto"))
        self.designer_tool_select_btn.clicked.connect(lambda: self._set_designer_mouse_tool("select"))
        self.designer_tool_move_btn.clicked.connect(lambda: self._set_designer_mouse_tool("move"))
        self.designer_tool_scale_btn.clicked.connect(lambda: self._set_designer_mouse_tool("scale"))
        self.designer_tool_crop_btn.clicked.connect(lambda: self._set_designer_mouse_tool("crop"))
        self.designer_crop_reset_btn.clicked.connect(self._reset_selected_image_crop)
        self.designer_preview_undo_btn.clicked.connect(self.undo_designer_change)
        self.designer_preview_redo_btn.clicked.connect(self.redo_designer_change)
        self.designer_align_left_btn.clicked.connect(lambda: self._align_selected_elements_to_canvas("left"))
        self.designer_align_top_btn.clicked.connect(lambda: self._align_selected_elements_to_canvas("top"))
        self.designer_align_center_h_btn.clicked.connect(lambda: self._align_selected_elements_to_canvas("center-h"))
        self.designer_align_center_v_btn.clicked.connect(lambda: self._align_selected_elements_to_canvas("center-v"))
        self.designer_align_bottom_btn.clicked.connect(lambda: self._align_selected_elements_to_canvas("bottom"))
        self.designer_align_right_btn.clicked.connect(lambda: self._align_selected_elements_to_canvas("right"))
        self.designer_snap_spin.valueChanged.connect(lambda value: self.preview_label.set_snap_threshold(int(value)))
        self.designer_snap_chk.toggled.connect(lambda _checked: self._update_preview_canvas_overlay())

        
        self.bg_path_browse_btn.clicked.connect(self.browse_background_path)
        self.bg_prepare_btn.clicked.connect(self.import_background_image)
        self.bg_base_color_btn.clicked.connect(lambda _checked=False: self.pick_color_for_edit(self.bg_base_color_edit))
        self.bg_accent_color_btn.clicked.connect(lambda _checked=False: self.pick_color_for_edit(self.bg_accent_color_edit))
        self.bg_cover_btn.clicked.connect(lambda: self.bg_fit_combo.setCurrentText("cover"))
        self.bg_contain_btn.clicked.connect(lambda: self.bg_fit_combo.setCurrentText("contain"))
        self.bg_preset_ocean_btn.clicked.connect(lambda: self._apply_background_style_preset([9, 14, 22], [20, 34, 48], 0.35))
        self.bg_preset_amber_btn.clicked.connect(lambda: self._apply_background_style_preset([28, 18, 10], [141, 92, 32], 0.28))
        self.bg_preset_mono_btn.clicked.connect(lambda: self._apply_background_style_preset([16, 18, 22], [76, 84, 97], 0.22))
        self.bg_preset_neon_btn.clicked.connect(lambda: self._apply_background_style_preset([6, 10, 20], [0, 186, 255], 0.42))
        self.layout_preset_load_btn.clicked.connect(self.load_layout_preset)

        for widget, signal in [
            (self.designer_id_edit, "textChanged"), (self.designer_x_spin, "valueChanged"),
            (self.designer_y_spin, "valueChanged"), (self.designer_w_spin, "valueChanged"),
            (self.designer_h_spin, "valueChanged"), (self.designer_z_spin, "valueChanged"),
            (self.designer_rotation_spin, "valueChanged"), (self.designer_opacity_spin, "valueChanged"),
            (self.designer_text_edit, "textChanged"), (self.designer_label_edit, "textChanged"),
            (self.designer_format_edit, "textChanged"), (self.designer_path_edit, "textChanged"),
            (self.designer_visible_chk, "toggled"), (self.designer_locked_chk, "toggled"),
            (self.designer_source_combo, "currentIndexChanged"), (self.designer_align_combo, "currentIndexChanged"),
            (self.designer_stat_display_combo, "currentTextChanged"), (self.designer_stat_min_spin, "valueChanged"),
            (self.designer_stat_max_spin, "valueChanged"), (self.designer_stat_show_value_chk, "toggled"),
            (self.designer_font_family_combo, "currentTextChanged"), (self.designer_font_size_spin, "valueChanged"),
            (self.designer_font_bold_chk, "toggled"), (self.designer_font_italic_chk, "toggled"),
            (self.designer_font_underline_chk, "toggled"),
            (self.designer_color_edit, "textChanged"), (self.designer_label_color_edit, "textChanged"),
            (self.designer_value_color_edit, "textChanged"), (self.designer_track_color_edit, "textChanged"),
            (self.designer_fill_color_edit, "textChanged"), (self.designer_stat_stroke_width_spin, "valueChanged"),
            (self.designer_stat_gauge_preset_combo, "currentIndexChanged"),
            (self.designer_gauge_low_edit, "textChanged"),
            (self.designer_gauge_mid_edit, "textChanged"),
            (self.designer_gauge_high_edit, "textChanged"),
            (self.designer_gauge_smooth_spin, "valueChanged"),
            (self.designer_gauge_match_value_chk, "toggled"),
            (self.designer_gauge_ring_spin, "valueChanged"),
            (self.designer_gauge_value_layout_combo, "currentIndexChanged"),
            (self.designer_gauge_inner_alpha_spin, "valueChanged"),
            (self.designer_sparkline_points_spin, "valueChanged"),
            (self.designer_sparkline_fill_opacity_spin, "valueChanged"),
            (self.designer_sparkline_show_points_chk, "toggled"),
            (self.designer_equalizer_bars_spin, "valueChanged"),
            (self.designer_equalizer_gap_spin, "valueChanged"),
            (self.designer_equalizer_mirror_chk, "toggled"),
            (self.widget_title_font_spin, "valueChanged"),
            (self.widget_body_font_spin, "valueChanged"),
            (self.widget_detail_font_spin, "valueChanged"),
            (self.widget_title_color_edit, "textChanged"),
            (self.widget_body_color_edit, "textChanged"),
            (self.widget_detail_color_edit, "textChanged"),
            (self.widget_panel_color_edit, "textChanged"),
            (self.widget_cover_enabled_chk, "toggled"),
            (self.widget_backdrop_enabled_chk, "toggled"),
            (self.widget_title_marquee_chk, "toggled"),
            (self.widget_equalizer_enabled_chk, "toggled"),
            (self.weather_widget_title_font_spin, "valueChanged"),
            (self.weather_widget_body_font_spin, "valueChanged"),
            (self.weather_widget_detail_font_spin, "valueChanged"),
            (self.weather_widget_title_color_edit, "textChanged"),
            (self.weather_widget_body_color_edit, "textChanged"),
            (self.weather_widget_detail_color_edit, "textChanged"),
            (self.weather_widget_panel_color_edit, "textChanged"),
            (self.weather_widget_transparent_bg_chk, "toggled"),
            (self.weather_widget_animate_icons_chk, "toggled"),
            (self.bg_kind_combo, "currentTextChanged"), (self.bg_path_edit, "textChanged")
        ]:
            try: getattr(widget, signal).connect(self.on_designer_field_changed)
            except: pass
        self.bg_animation_timeline.selection_changed.connect(self._on_animation_timeline_selection_changed)
        self.layout_preset_save_btn.clicked.connect(self.save_layout_preset)
        self.layout_preset_load_btn.clicked.connect(self.load_layout_preset)
        self.layout_preset_delete_btn.clicked.connect(self.delete_layout_preset)
        self.bg_animation_import_btn.clicked.connect(self.import_background_animation)
        self.bg_animation_add_btn.clicked.connect(self.append_background_animation_frames)
        self.bg_animation_blank_btn.clicked.connect(self.insert_blank_animation_frame)
        self.bg_animation_duplicate_btn.clicked.connect(self.duplicate_selected_animation_frames_bulk)
        self.bg_animation_hold_repeat_btn.clicked.connect(self.hold_selected_animation_frames_timing)
        self.bg_animation_reverse_btn.clicked.connect(self.reverse_selected_animation_frames)
        self.bg_animation_pingpong_btn.clicked.connect(self.pingpong_selected_animation_frames)
        self.bg_animation_normalize_duration_btn.clicked.connect(self.normalize_selected_animation_frame_durations)
        self.animation_stabilize_btn.clicked.connect(self.stabilize_animation_frames)
        self.bg_animation_repeat_all_btn.clicked.connect(self.duplicate_full_animation_sequence_bulk)
        self.animation_timeline_zoom_combo.currentTextChanged.connect(self.set_animation_timeline_zoom)
        self.animation_timeline_home_btn.clicked.connect(self.scroll_animation_timeline_to_start)
        self.animation_timeline_end_btn.clicked.connect(self.scroll_animation_timeline_to_end)
        self.animation_loop_in_btn.clicked.connect(self.set_animation_loop_in)
        self.animation_loop_out_btn.clicked.connect(self.set_animation_loop_out)
        self.animation_loop_clear_btn.clicked.connect(self.clear_animation_loop_range)
        self.animation_loop_close_seam_btn.clicked.connect(self.close_animation_loop_seam)
        self.animation_onion_skin_chk.toggled.connect(lambda _checked: self._refresh_animation_studio_preview())
        self.animation_onion_opacity_spin.valueChanged.connect(lambda _value: self._refresh_animation_studio_preview())
        self.animation_select_range_btn.clicked.connect(self.select_animation_range_between_edges)
        self.animation_invert_selection_btn.clicked.connect(self.invert_animation_frame_selection)
        self.animation_clear_selection_btn.clicked.connect(self.clear_animation_frame_selection)
        self.animation_loop_from_selection_btn.clicked.connect(self.set_animation_loop_from_selection)
        self.animation_trim_selection_btn.clicked.connect(self.trim_animation_to_selection)
        self.bg_animation_remove_btn.clicked.connect(self.remove_selected_animation_frames)
        self.bg_animation_clear_btn.clicked.connect(self.clear_background_animation)
        self.bg_animation_up_btn.clicked.connect(lambda: self.move_selected_animation_frames(-1))
        self.bg_animation_down_btn.clicked.connect(lambda: self.move_selected_animation_frames(1))
        self.bg_animation_export_btn.clicked.connect(self.export_animation_sequence)
        self.animation_export_loop_btn.clicked.connect(self.export_animation_loop_range)
        self.animation_export_selection_btn.clicked.connect(self.export_animation_selection)
        self.bg_animation_play_btn.clicked.connect(self.toggle_animation_preview_playback)
        self.bg_animation_prev_btn.clicked.connect(lambda: self.select_animation_frame(max(0, self.bg_animation_list.currentRow() - 1)))
        self.bg_animation_next_btn.clicked.connect(lambda: self.select_animation_frame(min(self.bg_animation_list.count() - 1, self.bg_animation_list.currentRow() + 1)))
        self.bg_animation_list.itemSelectionChanged.connect(self._on_bg_animation_list_selection_sync)
        self.bg_animation_list.currentRowChanged.connect(self._on_animation_current_row_changed)
        self.bg_animation_list.installEventFilter(self)
        self.bg_animation_list.rows_reordered.connect(self.on_animation_frames_reordered)
        self.animation_bulk_apply_duration_btn.clicked.connect(self.apply_bulk_animation_duration)
        self._build_animation_studio_page()
        for widget, signal in [
            (self.bg_kind_combo, "currentTextChanged"), (self.bg_base_color_edit, "textChanged"),
            (self.bg_accent_color_edit, "textChanged"), (self.bg_texture_alpha_spin, "valueChanged"),
            (self.bg_rotation_spin, "valueChanged"), (self.bg_path_edit, "textChanged"),
            (self.bg_fit_combo, "currentTextChanged"), (self.bg_opacity_spin, "valueChanged"),
            (self.bg_show_grid_chk, "toggled"), (self.bg_show_safe_chk, "toggled"),
            (self.bg_animation_enabled_chk, "toggled"), (self.bg_animation_use_bg_chk, "toggled"),
            (self.bg_animation_fps_spin, "valueChanged"), (self.bg_animation_frame_spin, "valueChanged"),
            (self.bg_animation_duration_spin, "valueChanged"),
            (self.panel_fill_edit, "textChanged"), (self.panel_opacity_spin, "valueChanged"), (self.panel_radius_spin, "valueChanged"),
        ]:
            try: getattr(widget, signal).connect(self.on_background_field_changed)
            except: pass

        logs_layout.addWidget(log_box, 1)
        self._update_image_tools_availability()
        self.preview_label.set_snap_threshold(int(self.designer_snap_spin.value()))
        self._set_designer_mouse_tool("auto")
        self.apply_designer_mode(self.designer_mode_combo.currentText())
        self._sync_shell_navigation()
        self._apply_sidebar_mode()
        self._apply_designer_aux_visibility()

    def append_log(self, text: str) -> None:
        normalized = str(text).rstrip()
        if not normalized:
            return
        self._log_entries.append(normalized)
        if len(self._log_entries) > self._max_log_entries:
            self._log_entries = self._log_entries[-self._max_log_entries :]
        self._refresh_log_view()

    def clear_logs(self) -> None:
        self._log_entries = []
        self._log_refresh_pending = False
        self.log_view.clear()

    def copy_filtered_logs(self) -> None:
        text = self._filtered_log_text()
        if not text:
            QMessageBox.information(
                self,
                self._tr("Logs", "Logi"),
                self._tr("No log lines to copy.", "Brak logów do skopiowania."),
            )
            return
        QApplication.clipboard().setText(text)
        self._refresh_log_view(force=True)
        self.append_log("[logs] Skopiowano przefiltrowane logi do schowka.")

    def copy_selected_logs(self) -> None:
        if not hasattr(self, "log_view"):
            return
        selected = self.log_view.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not selected:
            QMessageBox.information(
                self,
                self._tr("Logs", "Logi"),
                self._tr("No log selection to copy.", "Brak zaznaczonego fragmentu logów."),
            )
            return
        QApplication.clipboard().setText(selected)
        self._refresh_log_view(force=True)
        self.append_log("[logs] Skopiowano zaznaczony fragment logów do schowka.")

    def _filtered_log_entries(self) -> list[str]:
        needle = self.log_filter_edit.text().strip().lower()
        only_errors = self.log_only_errors_chk.isChecked()
        hide_status = self.log_hide_status_chk.isChecked()
        out: list[str] = []
        for line in self._log_entries:
            lowered = line.lower()
            if hide_status and lowered.startswith("[status]"):
                continue
            if only_errors and ("error" not in lowered and "failed" not in lowered and "traceback" not in lowered):
                continue
            if needle and needle not in lowered:
                continue
            out.append(line)
        return out

    def _filtered_log_text(self) -> str:
        entries = self._filtered_log_entries()
        if len(entries) > 250:
            entries = entries[-250:]
        return "\n".join(entries)

    def _open_external_link(self, url: str, label: str) -> None:
        target = QUrl(url)
        if not target.isValid():
            QMessageBox.warning(
                self,
                self._tr("Invalid link", "Niepoprawny link"),
                self._tr(
                    "Could not prepare the URL for {label}:\n{url}",
                    "Nie udało się przygotować adresu do {label}:\n{url}",
                ).format(label=label, url=url),
            )
            return
        if QDesktopServices.openUrl(target):
            self.append_log(f"[link] Otwarto {label}: {url}")
            return
        QMessageBox.warning(
            self,
            self._tr("Could not open link", "Nie udało się otworzyć linku"),
            self._tr(
                "The system did not open {label}.\nCopy the address manually:\n{url}",
                "System nie otworzył {label}.\nSkopiuj adres ręcznie:\n{url}",
            ).format(label=label, url=url),
        )

    def _refresh_log_view(self, *, force: bool = False) -> None:
        if not hasattr(self, "log_view"):
            return
        next_text = self._filtered_log_text()
        current_text = self.log_view.toPlainText()
        if not force and current_text == next_text:
            return
        cursor = self.log_view.textCursor()
        if not force and cursor.hasSelection():
            self._log_refresh_pending = True
            return
        self._log_refresh_pending = False
        self.log_view.setPlainText(next_text)
        if cursor.position() >= len(current_text):
            end_cursor = self.log_view.textCursor()
            end_cursor.movePosition(end_cursor.MoveOperation.End)
            self.log_view.setTextCursor(end_cursor)
        elif force and cursor.hasSelection():
            self.log_view.setTextCursor(cursor)

    def _summarize_status_payload(self, data: dict[str, Any]) -> str:
        mode = data.get("mode", "?")
        running = data.get("running", False)
        playlist_running = data.get("playlist_running", False)
        frame_count = data.get("frame_count", "?")
        last_error = data.get("last_error")
        return (
            f"mode={mode} running={running} playlist={playlist_running} "
            f"frames={frame_count} last_error={last_error if last_error else '-'}"
        )

    def _format_log_payload(self, action: str, data: dict[str, Any]) -> str:
        if action == "status":
            return f"[status] {self._summarize_status_payload(data)}"
        if action.startswith("theme-doc-preview"):
            result = data.get("result", {})
            if isinstance(result, dict):
                image_path = result.get("image_path", "-")
                theme_name = result.get("theme_name", "-")
                return f"[theme-doc-preview] theme={theme_name} image={image_path}"
        if action == "theme-doc-apply":
            result = data.get("result", {})
            if isinstance(result, dict):
                exit_code = result.get("exit_code", "?")
                rendered = result.get("rendered_theme", {})
                theme_name = rendered.get("theme_name", "-") if isinstance(rendered, dict) else "-"
                stdout_tail = str(result.get("stdout_tail", "")).replace("\n", " | ")
                if len(stdout_tail) > 400:
                    stdout_tail = stdout_tail[:400] + "..."
                return f"[theme-doc-apply] theme={theme_name} exit={exit_code} {stdout_tail}"
        compact = json.dumps(data, ensure_ascii=False)
        if len(compact) > 4000:
            compact = compact[:4000] + "...[truncated]"
        if len(compact) > 600:
            compact = compact[:600] + "..."
        return f"[{action}] {compact}"

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("Open Trofeo LCD")
        tray_menu = QMenu(self)
        show_action = QAction("Pokaż", self)
        hide_action = QAction("Ukryj do tray", self)
        refresh_action = QAction("Odśwież status", self)
        start_action = QAction("Start backend", self)
        stop_action = QAction("Stop backend", self)
        restart_action = QAction("Restart backend", self)
        quit_action = QAction("Zamknij", self)
        show_action.triggered.connect(self.show_from_tray)
        hide_action.triggered.connect(self.hide_to_tray)
        refresh_action.triggered.connect(self.refresh_status)
        start_action.triggered.connect(lambda: self.api_call("start", "POST", "/v1/start", {}))
        stop_action.triggered.connect(lambda: self.api_call("stop", "POST", "/v1/stop", {}))
        restart_action.triggered.connect(lambda: self.api_call("restart", "POST", "/v1/restart", {}))
        quit_action.triggered.connect(self.quit_from_tray)
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(refresh_action)
        tray_menu.addAction(start_action)
        tray_menu.addAction(stop_action)
        tray_menu.addAction(restart_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            if self.isVisible():
                self.hide_to_tray()
            else:
                self.show_from_tray()

    def hide_to_tray(self) -> None:
        self.hide()
        if self._tray_icon is not None and not self._tray_message_shown:
            self._tray_icon.showMessage(
                "Open Trofeo LCD",
                "Aplikacja działa w trayu. Kliknij ikonę, aby przywrócić okno.",
                QSystemTrayIcon.Information,
                3000,
            )
            self._tray_message_shown = True

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self) -> None:
        self._close_to_tray_enabled = False
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._close_to_tray_enabled and self._tray_icon is not None and self._tray_icon.isVisible():
            event.ignore()
            self.hide_to_tray()
            return
        if not self._confirm_discard_unsaved_theme_changes(self._tr("close application", "zamknięcie aplikacji")):
            event.ignore()
            return
        self._save_ui_state()
        super().closeEvent(event)

    def _setup_shortcuts(self) -> None:
        undo_action = QAction(self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo_designer_change)
        self.addAction(undo_action)

        redo_action = QAction(self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo_designer_change)
        self.addAction(redo_action)

        delete_action = QAction(self)
        delete_action.setShortcut(QKeySequence(Qt.Key_Delete))
        delete_action.triggered.connect(self.remove_designer_element)
        self.addAction(delete_action)

        save_action = QAction(self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_theme_doc)
        self.addAction(save_action)

        preview_action = QAction(self)
        preview_action.setShortcut(QKeySequence("Ctrl+Return"))
        preview_action.triggered.connect(self.preview_theme_doc)
        self.addAction(preview_action)

        for key, key_name, dx, dy in (
            (Qt.Key_Left, "Left", -1, 0),
            (Qt.Key_Right, "Right", 1, 0),
            (Qt.Key_Up, "Up", 0, -1),
            (Qt.Key_Down, "Down", 0, 1),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda _checked=False, dx=dx, dy=dy: self.nudge_selected_elements(dx, dy, big_step=False))
            self.addAction(action)

            big_action = QAction(self)
            big_action.setShortcut(QKeySequence(f"Shift+{key_name}"))
            big_action.triggered.connect(lambda _checked=False, dx=dx, dy=dy: self.nudge_selected_elements(dx, dy, big_step=True))
            self.addAction(big_action)

    def _schedule_theme_autosave(self) -> None:
        if self.theme_doc_model is None:
            return
        self.autosave_debounce.start(500)

    def _handle_theme_doc_editor_changed(self) -> None:
        if getattr(self, "_theme_doc_editor_syncing", False):
            return
        if self.theme_doc_editor.toPlainText().strip():
            self._mark_theme_doc_dirty("json-editor")

    def _mark_theme_doc_dirty(self, reason: str = "") -> None:
        if self.theme_doc_model is None and not self.theme_doc_editor.toPlainText().strip():
            return
        if not self._theme_doc_dirty:
            self._theme_doc_dirty = True
            if reason:
                self.append_log(f"[theme-doc] unsaved changes: {reason}")
        self._update_theme_doc_save_state()
        self._schedule_theme_autosave()

    def _mark_theme_doc_clean(self) -> None:
        self._theme_doc_dirty = False
        self._update_theme_doc_save_state()
        try:
            if THEME_AUTOSAVE_PATH.exists():
                THEME_AUTOSAVE_PATH.unlink()
        except Exception as exc:
            self.append_log(f"[autosave] cleanup-skip: {exc}")

    def _update_theme_doc_save_state(self) -> None:
        dirty = bool(getattr(self, "_theme_doc_dirty", False))
        self.setWindowModified(dirty)
        if hasattr(self, "designer_save_state_label"):
            label = self.designer_save_state_label
            if dirty:
                label.setText(self._tr("Unsaved", "Niezapisane"))
                label.setToolTip(self._tr("Theme has unsaved changes.", "Motyw ma niezapisane zmiany."))
            else:
                label.setText(self._tr("Saved", "Zapisane"))
                label.setToolTip(self._tr("Theme is saved.", "Motyw jest zapisany."))

    def _save_theme_doc_to_current_path_sync(self) -> bool:
        path = self.theme_doc_path_edit.text().strip()
        if not path:
            QMessageBox.information(self, "Info", "Podaj ścieżkę do pliku motywu.")
            return False
        document = self._current_theme_document()
        if document is None:
            return False
        resolved = Path(path).expanduser()
        if not resolved.is_absolute():
            resolved = (Path.cwd() / resolved).resolve()
        try:
            normalized = normalize_theme_document(deepcopy(document))
            save_theme_document(resolved, normalized, include_doc_header=True)
            self.theme_doc_path_edit.setText(str(resolved))
            self.theme_doc_model = deepcopy(normalized)
            self._set_theme_doc_editor_document(normalized)
            self._mark_theme_doc_clean()
            self._set_designer_toolbar_feedback(
                self._tr(f"Theme saved: {resolved.name}", f"Motyw zapisany: {resolved.name}")
            )
            return True
        except Exception as exc:
            QMessageBox.warning(self, self._tr("Theme error", "Błąd motywu"), str(exc))
            return False

    def _confirm_discard_unsaved_theme_changes(self, action_label: str) -> bool:
        if not bool(getattr(self, "_theme_doc_dirty", False)):
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(self._tr("Unsaved theme", "Niezapisany motyw"))
        box.setText(
            self._tr(
                f"The current theme has unsaved changes before: {action_label}.",
                f"Aktualny motyw ma niezapisane zmiany przed akcją: {action_label}.",
            )
        )
        box.setInformativeText(
            self._tr(
                "Save the theme now, discard changes, or cancel.",
                "Zapisz motyw teraz, odrzuć zmiany albo anuluj.",
            )
        )
        save_btn = box.addButton(self._tr("Save", "Zapisz"), QMessageBox.AcceptRole)
        discard_btn = box.addButton(self._tr("Discard", "Odrzuć"), QMessageBox.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_btn:
            return self._save_theme_doc_to_current_path_sync()
        if clicked == discard_btn:
            self._theme_doc_dirty = False
            self._update_theme_doc_save_state()
            return True
        if clicked == cancel_btn:
            return False
        return False

    def _image_tools_available(self) -> bool:
        return prepare_image_for_canvas is not None and render_prepared_image is not None

    def _update_image_tools_availability(self) -> None:
        available = self._image_tools_available()
        message = (
            ""
            if available
            else self._tr("Unavailable: Pillow is not installed in the GUI environment.", "Funkcja niedostępna: brak Pillow w środowisku GUI.")
        )
        for button in (
            getattr(self, "designer_import_image_btn", None),
            getattr(self, "designer_path_prepare_btn", None),
            getattr(self, "bg_prepare_btn", None),
        ):
            if button is None:
                continue
            button.setEnabled(available)
            button.setToolTip(message)

    def _designer_preview_tool_mode(self) -> str:
        label = getattr(self, "preview_label", None)
        if label is None:
            return "auto"
        return str(getattr(label, "_tool_mode", "auto")).strip().lower() or "auto"

    def _selected_image_entry_for_crop(self) -> tuple[str, int, dict[str, Any]] | None:
        selected = self._selected_items_multi_any()
        if len(selected) != 1:
            return None
        collection, row, item = selected[0]
        if collection != "images":
            return None
        rect = item.get("rect", [])
        if not isinstance(rect, list) or len(rect) != 4 or int(rect[2]) <= 0 or int(rect[3]) <= 0:
            return None
        return collection, row, item

    def _update_designer_mouse_tools_availability(self) -> None:
        image_entry = self._selected_image_entry_for_crop()
        crop_available = image_entry is not None
        crop_reset_btn = getattr(self, "designer_crop_reset_btn", None)
        if crop_reset_btn is not None:
            has_crop = crop_available and bool(image_entry[2].get("crop_box"))
            crop_reset_btn.setEnabled(bool(has_crop))
        crop_btn = getattr(self, "designer_tool_crop_btn", None)
        if crop_btn is not None:
            crop_btn.setEnabled(bool(crop_available))
            crop_btn.setToolTip(
                self._tr(
                    "Draw a crop area on the preview for the selected image.",
                    "Narysuj kadr na podglądzie dla wybranego obrazu.",
                )
                if crop_available
                else self._tr(
                    "Select exactly one image layer to crop it on the preview.",
                    "Wybierz dokładnie jedną warstwę obrazu, aby kadrować ją na podglądzie.",
                )
            )
        if not crop_available and self._designer_preview_tool_mode() == "crop":
            self._set_designer_mouse_tool("auto")

    def _set_designer_mouse_tool(self, mode: str) -> None:
        normalized = str(mode).strip().lower() or "auto"
        if normalized not in {"auto", "select", "move", "scale", "crop"}:
            normalized = "auto"
        if hasattr(self, "preview_label"):
            self.preview_label.set_tool_mode(normalized)
        button_map = {
            "auto": getattr(self, "designer_tool_auto_btn", None),
            "select": getattr(self, "designer_tool_select_btn", None),
            "move": getattr(self, "designer_tool_move_btn", None),
            "scale": getattr(self, "designer_tool_scale_btn", None),
            "crop": getattr(self, "designer_tool_crop_btn", None),
        }
        for tool_name, button in button_map.items():
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(tool_name == normalized)
            button.blockSignals(False)
        hint_map = {
            "auto": self._tr(
                "Auto mode: click to select, drag to move, use the corner handle to scale.",
                "Tryb auto: kliknij, aby zaznaczyć, przeciągnij, aby przesunąć, użyj narożnika do skalowania.",
            ),
            "select": self._tr(
                "Select mode: click to select or draw a box to select a whole group.",
                "Tryb zaznaczania: kliknij, aby zaznaczyć, albo narysuj ramkę wyboru dla całej grupy.",
            ),
            "move": self._tr(
                "Move mode: drag the selected element on the preview.",
                "Tryb przesuwania: przeciągnij zaznaczony element bezpośrednio na podglądzie.",
            ),
            "scale": self._tr(
                "Scale mode: drag on the preview to resize the selected element.",
                "Tryb skalowania: przeciągnij na podglądzie, aby zmienić rozmiar zaznaczonego elementu.",
            ),
            "crop": self._tr(
                "Crop mode: draw a crop rectangle for the selected image.",
                "Tryb kadrowania: narysuj prostokąt kadru dla zaznaczonego obrazu.",
            ),
        }
        if hasattr(self, "preview_info_label"):
            self.preview_info_label.setText(hint_map.get(normalized, hint_map["auto"]))
        tool_label_map = {
            "auto": self._tr("Tool: Auto", "Narzędzie: Auto"),
            "select": self._tr("Tool: Select", "Narzędzie: Zaznacz"),
            "move": self._tr("Tool: Move", "Narzędzie: Przesuń"),
            "scale": self._tr("Tool: Scale", "Narzędzie: Skaluj"),
            "crop": self._tr("Tool: Crop", "Narzędzie: Kadruj"),
        }
        if hasattr(self, "designer_active_tool_label"):
            self.designer_active_tool_label.setText(tool_label_map.get(normalized, tool_label_map["auto"]))
        self._update_designer_mouse_tools_availability()

    def _designer_snap_threshold(self) -> int:
        base = max(1, int(self.designer_snap_spin.value())) if hasattr(self, "designer_snap_spin") else 8
        return max(6, min(24, base))

    def _apply_canvas_element_snap(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        collection: str,
        index: int,
    ) -> tuple[int, int, list[tuple[str, int]]]:
        if not getattr(self, "designer_snap_chk", None) or not self.designer_snap_chk.isChecked():
            return int(x), int(y), []
        threshold = self._designer_snap_threshold()
        candidates_x = [("left", x), ("center", x + w // 2), ("right", x + w)]
        candidates_y = [("top", y), ("center", y + h // 2), ("bottom", y + h)]
        targets_x = [
            24,
            max(0, self.preview_label._canvas_size.width() - 24),
            self.preview_label._canvas_size.width() // 2,
        ]
        targets_y = [
            18,
            max(0, self.preview_label._canvas_size.height() - 18),
            self.preview_label._canvas_size.height() // 2,
        ]
        for item in self._all_canvas_elements():
            if item["collection"] == collection and int(item["index"]) == index:
                continue
            if not bool(item.get("visible", True)):
                continue
            rx, ry, rw, rh = item["rect"]
            targets_x.extend([int(rx), int(rx + rw // 2), int(rx + rw)])
            targets_y.extend([int(ry), int(ry + rh // 2), int(ry + rh)])

        best_x: tuple[int, int] | None = None
        best_y: tuple[int, int] | None = None
        for _kind, candidate in candidates_x:
            for target in targets_x:
                delta = target - candidate
                if abs(delta) <= threshold and (best_x is None or abs(delta) < abs(best_x[1])):
                    best_x = (target, delta)
        for _kind, candidate in candidates_y:
            for target in targets_y:
                delta = target - candidate
                if abs(delta) <= threshold and (best_y is None or abs(delta) < abs(best_y[1])):
                    best_y = (target, delta)
        snapped_x = int(x + (best_x[1] if best_x is not None else 0))
        snapped_y = int(y + (best_y[1] if best_y is not None else 0))
        guides = self.preview_label._compute_snap_guides(snapped_x, snapped_y, w, h, collection, index)
        return snapped_x, snapped_y, guides

    def _align_selected_elements_to_canvas(self, mode: str) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        canvas = self.theme_doc_model.get("canvas", {}) if isinstance(self.theme_doc_model, dict) else {}
        canvas_width = int(canvas.get("width", 1920))
        canvas_height = int(canvas.get("height", 462))
        self.push_designer_history()
        for collection, _row, item in selected:
            if bool(item.get("locked", False)):
                continue
            rect_x, rect_y, rect_w, rect_h = self._selected_item_rect(item, collection)
            next_x = rect_x
            next_y = rect_y
            if mode == "center-h":
                next_x = (canvas_width - rect_w) // 2
            elif mode == "center-v":
                next_y = (canvas_height - rect_h) // 2
            elif mode == "left":
                next_x = 0
            elif mode == "right":
                next_x = canvas_width - rect_w
            elif mode == "top":
                next_y = 0
            elif mode == "bottom":
                next_y = canvas_height - rect_h
            if collection in {"images", "panels", "widgets"}:
                item["rect"] = [
                    self._snap_value(int(next_x)),
                    self._snap_value(int(next_y)),
                    int(rect_w),
                    int(rect_h),
                ]
            else:
                item["x"] = self._snap_value(int(next_x))
                item["y"] = self._snap_value(int(next_y))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def _ensure_preview_selection_visible(self, entries: list[tuple[str, int]]) -> None:
        if not entries:
            return
        domain = self._designer_domain_mode()
        if domain == "all":
            return
        for collection, row in entries:
            items = self._theme_items_for_collection(collection)
            if 0 <= row < len(items) and not self._item_matches_designer_domain(items[row], collection, domain):
                combo = getattr(self, "designer_domain_combo", None)
                if combo is not None:
                    idx = combo.findData("all")
                    if idx >= 0 and idx != combo.currentIndex():
                        combo.setCurrentIndex(idx)
                return

    def _select_designer_entries_from_preview(
        self,
        entries: list[tuple[str, int]],
        *,
        group_label: str = "",
    ) -> None:
        normalized = self._normalize_designer_selection(entries)
        if not normalized:
            return
        self._ensure_preview_selection_visible(normalized)
        current_collection = self._selected_collection()
        target_collection = current_collection
        target_rows = [row for collection, row in normalized if collection == current_collection]
        if not target_rows:
            target_collection = normalized[0][0]
            combo_index = self.designer_kind_combo.findData(target_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
            target_rows = [row for collection, row in normalized if collection == target_collection]
        self.designer_element_list.blockSignals(True)
        self.designer_element_list.clearSelection()
        for row in target_rows:
            item = self.designer_element_list.item(row)
            if item is not None and not item.isHidden():
                item.setSelected(True)
        self.designer_element_list.setCurrentRow(min(target_rows) if target_rows else -1)
        self.designer_element_list.blockSignals(False)
        self._set_designer_selection_group(
            normalized,
            group_label=group_label or self._selection_group_label_for_entries(normalized),
        )
        self.update_layer_row_visuals()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def _handle_preview_element_selected(self, collection: str, index: int) -> None:
        self._select_designer_entries_from_preview([(collection, index)])

    def _handle_preview_elements_box_selected(self, entries: object) -> None:
        if not isinstance(entries, list):
            return
        normalized: list[tuple[str, int]] = []
        for entry in entries:
            if (
                isinstance(entry, tuple)
                and len(entry) == 2
                and isinstance(entry[0], str)
                and isinstance(entry[1], int)
            ):
                normalized.append((entry[0], entry[1]))
        if not normalized:
            return
        self._select_designer_entries_from_preview(normalized, group_label=self._tr("Selection Box", "Zaznaczenie ramką"))

    def _reset_selected_image_crop(self) -> None:
        image_entry = self._selected_image_entry_for_crop()
        if image_entry is None:
            QMessageBox.information(
                self,
                self._tr("Crop", "Kadrowanie"),
                self._tr(
                    "Select exactly one image layer before clearing the crop.",
                    "Wybierz dokładnie jedną warstwę obrazu przed czyszczeniem kadru.",
                ),
            )
            return
        _collection, row, item = image_entry
        if item.get("crop_box") is None:
            return
        self.push_designer_history()
        item.pop("crop_box", None)
        self.write_designer_to_json()
        self._refresh_designer_list_row(row)
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()
        self._set_designer_toolbar_feedback(
            self._tr("Image crop cleared.", "Kadr obrazu został wyczyszczony."),
        )

    def _handle_preview_crop_rect_selected(self, rect: object) -> None:
        image_entry = self._selected_image_entry_for_crop()
        if image_entry is None:
            self._set_designer_toolbar_feedback(
                self._tr(
                    "Select one image layer first, then draw a crop rectangle.",
                    "Najpierw wybierz jedną warstwę obrazu, a potem narysuj prostokąt kadru.",
                )
            )
            return
        if not (isinstance(rect, tuple) and len(rect) == 4):
            return
        try:
            left, top, right, bottom = [int(v) for v in rect]
        except Exception:
            return
        _collection, row, item = image_entry
        item_rect = item.get("rect", [0, 0, 1, 1])
        if not isinstance(item_rect, list) or len(item_rect) != 4:
            return
        img_x, img_y, img_w, img_h = [int(v) for v in item_rect]
        if img_w <= 0 or img_h <= 0:
            return
        inter_left = max(img_x, min(left, right))
        inter_top = max(img_y, min(top, bottom))
        inter_right = min(img_x + img_w, max(left, right))
        inter_bottom = min(img_y + img_h, max(top, bottom))
        if inter_right - inter_left < 4 or inter_bottom - inter_top < 4:
            self._set_designer_toolbar_feedback(
                self._tr(
                    "The crop area must overlap the selected image.",
                    "Obszar kadru musi pokrywać się z zaznaczonym obrazem.",
                )
            )
            return
        crop_box = [
            max(0.0, min(1.0, (inter_left - img_x) / max(1, img_w))),
            max(0.0, min(1.0, (inter_top - img_y) / max(1, img_h))),
            max(0.0, min(1.0, (inter_right - img_x) / max(1, img_w))),
            max(0.0, min(1.0, (inter_bottom - img_y) / max(1, img_h))),
        ]
        if crop_box[2] - crop_box[0] < 0.01 or crop_box[3] - crop_box[1] < 0.01:
            return
        self.push_designer_history()
        if (
            crop_box[0] <= 0.01
            and crop_box[1] <= 0.01
            and crop_box[2] >= 0.99
            and crop_box[3] >= 0.99
        ):
            item.pop("crop_box", None)
            message = self._tr("Image crop cleared.", "Kadr obrazu został wyczyszczony.")
        else:
            item["crop_box"] = [round(value, 4) for value in crop_box]
            message = self._tr("Image crop updated from preview.", "Kadr obrazu został zaktualizowany z podglądu.")
        self.write_designer_to_json()
        self._refresh_designer_list_row(row)
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()
        self._set_designer_toolbar_feedback(message)

    def _setup_designer_layers_panel(self, parent_layout: QVBoxLayout) -> None:
        """Konfiguruje lewy panel z listą warstw."""
        box = QGroupBox("")
        box.setObjectName("designerElementsBox")
        box.setFlat(True)
        box.setStyleSheet(
            "QGroupBox#designerElementsBox { margin-top: 0px; padding: 6px; font-size: 11px; }"
            "QGroupBox#designerElementsBox::title { height: 0px; padding: 0px; margin: 0px; }"
        )
        self.designer_elements_box = box
        self.designer_elements_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.designer_elements_box.setMaximumHeight(16777215)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(3)

        self.designer_elements_title_label = QLabel("Layers & components")
        self.designer_elements_title_label.setObjectName("sectionTinyTitle")
        self.designer_elements_title_label.setMaximumHeight(18)
        self.designer_elements_title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.designer_elements_title_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(3)
        self.designer_component_search = QLineEdit()
        self.designer_component_search.setPlaceholderText("Search layers or text…")
        self.designer_component_search.setClearButtonEnabled(True)
        self.designer_component_search.setMaximumHeight(26)
        search_row.addWidget(self.designer_component_search, 1)
        self.designer_domain_combo = QComboBox()
        self.designer_domain_combo.setMaximumWidth(68)
        self.designer_domain_combo.setMaximumHeight(26)
        for key, label in DESIGNER_DOMAIN_MODES:
            self.designer_domain_combo.addItem(label, key)
        search_row.addWidget(self.designer_domain_combo, 0)
        self.designer_kind_combo.setMaximumWidth(84)
        self.designer_kind_combo.setMaximumHeight(26)
        search_row.addWidget(self.designer_kind_combo, 0)
        self.designer_quick_add_toggle_btn = QPushButton("+")
        self.designer_quick_add_toggle_btn.setMinimumHeight(24)
        self.designer_quick_add_toggle_btn.setMaximumHeight(26)
        self.designer_quick_add_toggle_btn.setMaximumWidth(28)
        search_row.addWidget(self.designer_quick_add_toggle_btn)
        layout.addLayout(search_row)
        self.designer_selection_label.setObjectName("selectionSummaryLabel")
        self.designer_selection_label.setWordWrap(False)
        self.designer_selection_label.setMaximumHeight(16)
        self.designer_selection_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.designer_selection_label.setStyleSheet("font-size: 10px; margin: 0; padding: 0; color: #9fb0c6;")
        self.designer_selection_label.setToolTip("")
        layout.addWidget(self.designer_selection_label)
        self.designer_kind_combo.currentIndexChanged.connect(self.refresh_designer_element_list)
        self.designer_domain_combo.currentIndexChanged.connect(self._on_designer_domain_changed)
        
        # Szybkie dodawanie (grupy: podstawowe / muzyka / pozostałe widgety)
        self.designer_quick_add_container = QWidget()
        quick_container_layout = QVBoxLayout(self.designer_quick_add_container)
        quick_container_layout.setContentsMargins(0, 0, 0, 0)
        quick_container_layout.setSpacing(6)
        self.designer_quick_add_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.quick_add_group_basics = QGroupBox("Basics")
        self.quick_add_group_basics.setFlat(True)
        basics_grid = QGridLayout(self.quick_add_group_basics)
        basics_grid.setHorizontalSpacing(3)
        basics_grid.setVerticalSpacing(3)
        self.quick_add_text_btn = QPushButton("Text")
        self.quick_add_stat_btn = QPushButton("Stat")
        self.quick_add_image_btn = QPushButton("Image")
        self.quick_add_panel_btn = QPushButton("Panel")
        self.quick_add_progress_btn = QPushButton("Progress")
        self.quick_add_sparkline_btn = QPushButton("Sparkline")
        for btn in (
            self.quick_add_text_btn,
            self.quick_add_stat_btn,
            self.quick_add_image_btn,
            self.quick_add_panel_btn,
            self.quick_add_progress_btn,
            self.quick_add_sparkline_btn,
        ):
            btn.setObjectName("quickAddButton")
            btn.setMinimumHeight(24)
        basics_grid.addWidget(self.quick_add_text_btn, 0, 0)
        basics_grid.addWidget(self.quick_add_stat_btn, 0, 1)
        basics_grid.addWidget(self.quick_add_image_btn, 1, 0)
        basics_grid.addWidget(self.quick_add_panel_btn, 1, 1)
        basics_grid.addWidget(self.quick_add_progress_btn, 2, 0)
        basics_grid.addWidget(self.quick_add_sparkline_btn, 2, 1)

        self.quick_add_group_music = QGroupBox("Music & audio")
        self.quick_add_group_music.setFlat(True)
        music_grid = QGridLayout(self.quick_add_group_music)
        music_grid.setHorizontalSpacing(3)
        music_grid.setVerticalSpacing(3)
        self.quick_add_now_playing_btn = QPushButton("Now Playing")
        self.quick_add_now_playing_btn.setObjectName("quickAddButton")
        self.quick_add_now_playing_btn.setMinimumHeight(24)
        self.quick_add_now_playing_hero_btn = QPushButton("Now Playing Hero")
        self.quick_add_now_playing_hero_btn.setObjectName("quickAddButton")
        self.quick_add_now_playing_hero_btn.setMinimumHeight(24)
        self.quick_add_now_playing_mini_btn = QPushButton("Now Playing Mini")
        self.quick_add_now_playing_mini_btn.setObjectName("quickAddButton")
        self.quick_add_now_playing_mini_btn.setMinimumHeight(24)
        self.quick_add_volume_btn = QPushButton("Volume")
        self.quick_add_volume_btn.setObjectName("quickAddButton")
        self.quick_add_volume_btn.setMinimumHeight(24)
        self.quick_add_equalizer_btn = QPushButton("Graphic EQ")
        self.quick_add_equalizer_btn.setObjectName("quickAddButton")
        self.quick_add_equalizer_btn.setMinimumHeight(24)
        music_grid.addWidget(self.quick_add_now_playing_btn, 0, 0)
        music_grid.addWidget(self.quick_add_now_playing_hero_btn, 0, 1)
        music_grid.addWidget(self.quick_add_now_playing_mini_btn, 1, 0)
        music_grid.addWidget(self.quick_add_volume_btn, 1, 1)
        music_grid.addWidget(self.quick_add_equalizer_btn, 2, 0, 1, 2)

        self.quick_add_group_weather = QGroupBox("Weather")
        self.quick_add_group_weather.setFlat(True)
        weather_grid = QGridLayout(self.quick_add_group_weather)
        weather_grid.setHorizontalSpacing(3)
        weather_grid.setVerticalSpacing(3)
        self.quick_add_weather_current_btn = QPushButton("Weather Current")
        self.quick_add_weather_current_btn.setObjectName("quickAddButton")
        self.quick_add_weather_current_btn.setMinimumHeight(24)
        self.quick_add_weather_forecast_btn = QPushButton("Weather 7D")
        self.quick_add_weather_forecast_btn.setObjectName("quickAddButton")
        self.quick_add_weather_forecast_btn.setMinimumHeight(24)
        weather_grid.addWidget(self.quick_add_weather_current_btn, 0, 0)
        weather_grid.addWidget(self.quick_add_weather_forecast_btn, 0, 1)

        self.quick_add_group_widgets = QGroupBox("Widgets")
        self.quick_add_group_widgets.setFlat(True)
        widgets_grid = QGridLayout(self.quick_add_group_widgets)
        widgets_grid.setHorizontalSpacing(3)
        widgets_grid.setVerticalSpacing(3)
        self.quick_add_analog_clock_btn = QPushButton("Analog Clock")
        self.quick_add_analog_clock_btn.setObjectName("quickAddButton")
        self.quick_add_analog_clock_btn.setMinimumHeight(24)
        self.quick_add_clock_modern_btn = QPushButton("Clock Modern")
        self.quick_add_clock_modern_btn.setObjectName("quickAddButton")
        self.quick_add_clock_modern_btn.setMinimumHeight(24)
        self.quick_add_clock_nordic_btn = QPushButton("Clock Nordic")
        self.quick_add_clock_nordic_btn.setObjectName("quickAddButton")
        self.quick_add_clock_nordic_btn.setMinimumHeight(24)
        self.quick_add_gauge_set_btn = QPushButton("Gauge Set")
        self.quick_add_gauge_set_btn.setObjectName("quickAddButton")
        self.quick_add_gauge_set_btn.setMinimumHeight(24)
        self.quick_add_gauge_cyber_btn = QPushButton("Gauge Cyber")
        self.quick_add_gauge_cyber_btn.setObjectName("quickAddButton")
        self.quick_add_gauge_cyber_btn.setMinimumHeight(24)
        self.quick_add_gauge_thermal_btn = QPushButton("Gauge Thermal")
        self.quick_add_gauge_thermal_btn.setObjectName("quickAddButton")
        self.quick_add_gauge_thermal_btn.setMinimumHeight(24)
        widgets_grid.addWidget(self.quick_add_analog_clock_btn, 0, 0)
        widgets_grid.addWidget(self.quick_add_clock_modern_btn, 0, 1)
        widgets_grid.addWidget(self.quick_add_clock_nordic_btn, 1, 0)
        widgets_grid.addWidget(self.quick_add_gauge_set_btn, 1, 1)
        widgets_grid.addWidget(self.quick_add_gauge_cyber_btn, 2, 0)
        widgets_grid.addWidget(self.quick_add_gauge_thermal_btn, 2, 1)

        quick_container_layout.addWidget(self.quick_add_group_basics)
        quick_container_layout.addWidget(self.quick_add_group_music)
        quick_container_layout.addWidget(self.quick_add_group_weather)
        quick_container_layout.addWidget(self.quick_add_group_widgets)
        self.designer_quick_add_container.hide()
        layout.addWidget(self.designer_quick_add_container)
        self.quick_add_text_btn.clicked.connect(lambda: self.quick_add_designer_element("texts"))
        self.quick_add_stat_btn.clicked.connect(lambda: self.quick_add_designer_element("stats"))
        self.quick_add_image_btn.clicked.connect(lambda: self.quick_add_designer_element("images"))
        self.quick_add_panel_btn.clicked.connect(lambda: self.quick_add_designer_element("panels"))
        self.quick_add_progress_btn.clicked.connect(lambda: self.add_stat_visual_widget("progress"))
        self.quick_add_sparkline_btn.clicked.connect(lambda: self.add_stat_visual_widget("sparkline"))
        self.quick_add_now_playing_btn.clicked.connect(self.add_now_playing_widget)
        self.quick_add_now_playing_hero_btn.clicked.connect(self.add_now_playing_widget_hero)
        self.quick_add_now_playing_mini_btn.clicked.connect(self.add_now_playing_widget_mini)
        self.quick_add_analog_clock_btn.clicked.connect(lambda: self.add_analog_clock_widget("classic"))
        self.quick_add_clock_modern_btn.clicked.connect(lambda: self.add_analog_clock_widget("modern"))
        self.quick_add_clock_nordic_btn.clicked.connect(lambda: self.add_analog_clock_widget("nordic"))
        self.quick_add_gauge_set_btn.clicked.connect(lambda: self.add_gauge_ring_bundle("system"))
        self.quick_add_gauge_cyber_btn.clicked.connect(lambda: self.add_gauge_ring_bundle("cyber"))
        self.quick_add_gauge_thermal_btn.clicked.connect(lambda: self.add_gauge_ring_bundle("thermal"))
        self.quick_add_volume_btn.clicked.connect(self.add_volume_widget)
        self.quick_add_equalizer_btn.clicked.connect(self.add_graphic_equalizer_widget)
        self.quick_add_weather_current_btn.clicked.connect(self.add_weather_current_widget)
        self.quick_add_weather_forecast_btn.clicked.connect(self.add_weather_forecast_widget)
        self.designer_quick_add_menu = QMenu(self.designer_quick_add_toggle_btn)
        self.designer_quick_add_menu.setObjectName("designerQuickAddMenu")
        self.designer_quick_add_menu.setStyleSheet(
            """
            QMenu#designerQuickAddMenu {
                background: #0f141b;
                border: 1px solid #3b82f6;
                border-radius: 10px;
                padding: 6px;
                color: #f8fafc;
            }
            QMenu#designerQuickAddMenu::item {
                padding: 7px 14px 7px 14px;
                border-radius: 7px;
                min-width: 190px;
            }
            QMenu#designerQuickAddMenu::item:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QMenu#designerQuickAddMenu::item:pressed {
                background: #1d4ed8;
            }
            QMenu#designerQuickAddMenu::separator {
                height: 1px;
                background: #263242;
                margin: 6px 4px;
            }
            QMenu#designerQuickAddMenu::item:disabled {
                color: #60a5fa;
                background: transparent;
                font-weight: 800;
            }
            """
        )
        self._populate_designer_quick_add_menu()
        self.designer_quick_add_menu.aboutToShow.connect(self._populate_designer_quick_add_menu)
        self._refresh_designer_quick_add_groups()
        self.designer_quick_add_toggle_btn.setMenu(self.designer_quick_add_menu)
        
        self.designer_element_list.setMinimumHeight(140)
        self.designer_element_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.designer_element_list.setSpacing(3)
        self.designer_element_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.designer_element_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.designer_element_list.setDefaultDropAction(Qt.MoveAction)
        self.designer_element_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.designer_element_list.currentRowChanged.connect(lambda _row: (self.update_layer_row_visuals(), self.load_selected_designer_item(), self._update_preview_canvas_overlay()))
        self.designer_element_list.itemSelectionChanged.connect(lambda: (self.update_layer_row_visuals(), self.load_selected_designer_item(), self._update_preview_canvas_overlay()))
        self.designer_element_list.customContextMenuRequested.connect(self.show_designer_layer_menu)
        self.designer_element_list.rows_reordered.connect(self.on_designer_rows_reordered)
        self.designer_component_search.textChanged.connect(self.filter_designer_element_list)
        layout.addWidget(self.designer_element_list, 1)
        
        move_box = QGroupBox("Nudge selection")
        self.designer_move_box = move_box
        move_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        move_layout = QVBoxLayout(move_box)
        move_layout.setContentsMargins(6, 5, 6, 5)
        move_layout.setSpacing(4)
        move_step_row = QHBoxLayout()
        move_step_row.setSpacing(5)
        self.designer_nudge_step_label = QLabel("Step:")
        move_step_row.addWidget(self.designer_nudge_step_label)
        self.designer_nudge_step_combo = QComboBox()
        for step in (1, 2, 3, 5, 8, 10, 16, 24, 32):
            self.designer_nudge_step_combo.addItem(f"{step} px", step)
        self.designer_nudge_step_combo.setCurrentIndex(3)  # 5 px
        self.designer_nudge_step_combo.setMaximumWidth(120)
        move_step_row.addWidget(self.designer_nudge_step_combo, 1)
        move_layout.addLayout(move_step_row)
        dpad = QGridLayout()
        dpad.setHorizontalSpacing(5)
        dpad.setVerticalSpacing(4)
        _nudge_icon_sz = QSize(22, 22)
        _sty = self.style()
        self.designer_nudge_up_btn = QPushButton()
        self.designer_nudge_up_btn.setIcon(_sty.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.designer_nudge_up_btn.setIconSize(_nudge_icon_sz)
        self.designer_nudge_up_btn.setToolTip("Nudge up")
        self.designer_nudge_left_btn = QPushButton()
        self.designer_nudge_left_btn.setIcon(_sty.standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
        self.designer_nudge_left_btn.setIconSize(_nudge_icon_sz)
        self.designer_nudge_left_btn.setToolTip("Nudge left")
        self.designer_nudge_right_btn = QPushButton()
        self.designer_nudge_right_btn.setIcon(_sty.standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
        self.designer_nudge_right_btn.setIconSize(_nudge_icon_sz)
        self.designer_nudge_right_btn.setToolTip("Nudge right")
        self.designer_nudge_down_btn = QPushButton()
        self.designer_nudge_down_btn.setIcon(_sty.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.designer_nudge_down_btn.setIconSize(_nudge_icon_sz)
        self.designer_nudge_down_btn.setToolTip("Nudge down")
        for btn in (
            self.designer_nudge_up_btn,
            self.designer_nudge_left_btn,
            self.designer_nudge_right_btn,
            self.designer_nudge_down_btn,
        ):
            btn.setMinimumHeight(32)
            btn.setMaximumHeight(36)
            btn.setMinimumWidth(36)
            btn.setMaximumWidth(44)
        dpad.addWidget(self.designer_nudge_up_btn, 0, 1)
        dpad.addWidget(self.designer_nudge_left_btn, 1, 0)
        dpad.addWidget(self.designer_nudge_right_btn, 1, 2)
        dpad.addWidget(self.designer_nudge_down_btn, 2, 1)
        move_layout.addLayout(dpad)
        self.designer_nudge_up_btn.clicked.connect(lambda: self.nudge_selected_elements(0, -1, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_nudge_left_btn.clicked.connect(lambda: self.nudge_selected_elements(-1, 0, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_nudge_right_btn.clicked.connect(lambda: self.nudge_selected_elements(1, 0, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_nudge_down_btn.clicked.connect(lambda: self.nudge_selected_elements(0, 1, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_layer_actions_label = QLabel("Layer actions")
        self.designer_layer_actions_label.setObjectName("selectionSummaryLabel")
        self.designer_layer_actions_label.setMaximumHeight(16)
        move_layout.addWidget(self.designer_layer_actions_label)
        layer_actions_grid = QGridLayout()
        layer_actions_grid.setContentsMargins(0, 0, 0, 0)
        layer_actions_grid.setHorizontalSpacing(5)
        layer_actions_grid.setVerticalSpacing(4)
        self.designer_layer_down_btn = QPushButton("−Z")
        self.designer_layer_up_btn = QPushButton("+Z")
        self.designer_layer_back_btn = QPushButton("Back")
        self.designer_layer_front_btn = QPushButton("Front")
        self.designer_visibility_toggle_btn = QPushButton("Show")
        self.designer_lock_toggle_btn = QPushButton("Lock")
        for btn in (
            self.designer_layer_down_btn,
            self.designer_layer_up_btn,
            self.designer_layer_back_btn,
            self.designer_layer_front_btn,
            self.designer_visibility_toggle_btn,
            self.designer_lock_toggle_btn,
        ):
            btn.setObjectName("quickAddButton")
            btn.setMinimumHeight(24)
            btn.setMaximumHeight(28)
            btn.setMinimumWidth(58)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.designer_layer_down_btn.clicked.connect(self.lower_designer_layer)
        self.designer_layer_up_btn.clicked.connect(self.raise_designer_layer)
        self.designer_layer_back_btn.clicked.connect(lambda: self.move_designer_layer_to_edge("back"))
        self.designer_layer_front_btn.clicked.connect(lambda: self.move_designer_layer_to_edge("front"))
        self.designer_visibility_toggle_btn.clicked.connect(self.toggle_selected_visible)
        self.designer_lock_toggle_btn.clicked.connect(self.toggle_selected_locked)
        layer_actions_grid.addWidget(self.designer_layer_down_btn, 0, 0)
        layer_actions_grid.addWidget(self.designer_layer_up_btn, 0, 1)
        layer_actions_grid.addWidget(self.designer_layer_back_btn, 0, 2)
        layer_actions_grid.addWidget(self.designer_layer_front_btn, 1, 0)
        layer_actions_grid.addWidget(self.designer_visibility_toggle_btn, 1, 1)
        layer_actions_grid.addWidget(self.designer_lock_toggle_btn, 1, 2)
        for action_col in range(3):
            layer_actions_grid.setColumnStretch(action_col, 1)
        move_layout.addLayout(layer_actions_grid)
        move_actions_row = QHBoxLayout()
        move_actions_row.setContentsMargins(0, 0, 0, 0)
        move_actions_row.setSpacing(6)
        move_actions_row.addStretch(1)
        self.designer_remove_btn = QPushButton("🗑 Delete")
        self.designer_remove_btn.setMinimumHeight(28)
        self.designer_remove_btn.setMaximumWidth(112)
        self.designer_remove_btn.setStyleSheet(
            "QPushButton { background: #3a1f25; border: 1px solid #a33a48; color: #ffd7dc; }"
            "QPushButton:hover { background: #512730; border: 1px solid #d05b6b; }"
            "QPushButton:pressed { background: #2a1418; }"
        )
        self.designer_remove_btn.clicked.connect(self.remove_designer_element)
        move_actions_row.addWidget(self.designer_remove_btn)
        move_layout.addLayout(move_actions_row)
        move_box.setMaximumHeight(270)
        layout.addWidget(move_box)
        parent_layout.addWidget(box, 1)

    def _setup_inspector_tabs(self, container_layout: QVBoxLayout) -> None:
        """Konfiguruje prawy panel właściwości z zakładkami."""
        box = QGroupBox("Element properties")
        box.setObjectName("designerSectionBox")
        self.props_box = box
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.inspector_selection_summary = QLabel("Select an element to edit its properties.")
        self.inspector_selection_summary.setObjectName("selectionSummaryLabel")
        self.inspector_selection_summary.setWordWrap(True)
        layout.addWidget(self.inspector_selection_summary)

        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setDocumentMode(True)
        self.inspector_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.inspector_tabs.currentChanged.connect(lambda _idx: self._clamp_designer_splitter_later())

        def make_tab() -> tuple[QWidget, QFormLayout]:
            tab = QWidget()
            tab_layout = QFormLayout(tab)
            tab_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            tab_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            tab_layout.setFormAlignment(Qt.AlignTop)
            tab_layout.setHorizontalSpacing(6)
            tab_layout.setVerticalSpacing(4)
            tab_layout.setContentsMargins(4, 4, 4, 4)
            return tab, tab_layout

        def make_scrolled_tab() -> tuple[QScrollArea, QFormLayout]:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            inner = QWidget()
            tab_layout = QFormLayout(inner)
            tab_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            tab_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            tab_layout.setFormAlignment(Qt.AlignTop)
            tab_layout.setHorizontalSpacing(6)
            tab_layout.setVerticalSpacing(4)
            tab_layout.setContentsMargins(4, 4, 4, 4)
            scroll.setWidget(inner)
            return scroll, tab_layout

        def make_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("headerFieldLabel")
            return label

        def wrap_row(*widgets: QWidget, stretch_first: bool = False) -> QWidget:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            for idx, widget in enumerate(widgets):
                row_layout.addWidget(widget, 1 if stretch_first and idx == 0 else 0)
            if stretch_first:
                row_layout.setStretch(0, 1)
            return row

        def add_color_row(target_edit: QLineEdit) -> tuple[QWidget, QPushButton]:
            button = QPushButton("🎨")
            button.setMinimumWidth(40)
            button.clicked.connect(lambda _checked=False, edit=target_edit: self.pick_color_for_edit(edit))
            row = wrap_row(target_edit, button, stretch_first=True)
            return row, button

        def add_compact_color_cell(caption: str, target_edit: QLineEdit) -> QWidget:
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)
            caption_label = QLabel(caption)
            caption_label.setObjectName("selectionSummaryLabel")
            target_edit.setMinimumWidth(120)
            target_edit.setMaximumWidth(210)
            button = QPushButton("🎨")
            button.setMaximumWidth(32)
            button.setMinimumHeight(24)
            button.clicked.connect(lambda _checked=False, edit=target_edit: self.pick_color_for_edit(edit))
            cell_layout.addWidget(caption_label)
            cell_layout.addWidget(target_edit, 1)
            cell_layout.addWidget(button)
            return cell

        def make_compact_color_grid(*cells: QWidget) -> QWidget:
            grid_widget = QWidget()
            grid = QGridLayout(grid_widget)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(4)
            for idx, cell in enumerate(cells):
                grid.addWidget(cell, idx // 2, idx % 2)
            return grid_widget

        def make_compact_labeled_row(
            *pairs: tuple[QLabel, QWidget],
            stretch_first: bool = False,
            stretch_last: bool = False,
        ) -> QWidget:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            for idx, (caption, widget) in enumerate(pairs):
                caption.setObjectName("selectionSummaryLabel")
                row_layout.addWidget(caption)
                stretch = (stretch_first and idx == 0) or (stretch_last and idx == len(pairs) - 1)
                row_layout.addWidget(widget, 1 if stretch else 0)
            return row

        self.inspector_general, self.inspector_general_layout = make_tab()
        self.inspector_content, self.inspector_content_layout = make_tab()
        self.inspector_music, self.inspector_music_layout = make_scrolled_tab()
        self.inspector_weather, self.inspector_weather_layout = make_scrolled_tab()
        self.inspector_appearance, self.inspector_appearance_layout = make_scrolled_tab()
        self.inspector_gauge, self.inspector_gauge_layout = make_scrolled_tab()
        self.inspector_geometry, self.inspector_geometry_layout = make_scrolled_tab()
        self.inspector_image, self.inspector_image_layout = make_scrolled_tab()
        self.inspector_media, self.inspector_media_layout = make_scrolled_tab()
        self.inspector_animation, self.inspector_animation_layout = make_scrolled_tab()

        self.inspector_music_spectrum_placeholder = QLabel(
            "Animated spectrum / EQ visualizer: reserved for a future update."
        )
        self.inspector_music_spectrum_placeholder.setWordWrap(True)
        self.inspector_music_spectrum_placeholder.setObjectName("selectionSummaryLabel")
        self.inspector_music_tools_row = QWidget()
        music_tools_layout = QHBoxLayout(self.inspector_music_tools_row)
        music_tools_layout.setContentsMargins(0, 0, 0, 0)
        music_tools_layout.setSpacing(6)
        self.music_tool_now_playing_btn = QPushButton("Now Playing")
        self.music_tool_hero_btn = QPushButton("Hero")
        self.music_tool_mini_btn = QPushButton("Mini")
        self.music_tool_volume_btn = QPushButton("Volume")
        self.music_tool_eq_btn = QPushButton("Graphic EQ")
        for btn in (
            self.music_tool_now_playing_btn,
            self.music_tool_hero_btn,
            self.music_tool_mini_btn,
            self.music_tool_volume_btn,
            self.music_tool_eq_btn,
        ):
            btn.setObjectName("quickAddButton")
            btn.setMinimumHeight(24)
            music_tools_layout.addWidget(btn)
        self.music_tool_now_playing_btn.clicked.connect(self.add_now_playing_widget)
        self.music_tool_hero_btn.clicked.connect(self.add_now_playing_widget_hero)
        self.music_tool_mini_btn.clicked.connect(self.add_now_playing_widget_mini)
        self.music_tool_volume_btn.clicked.connect(self.add_volume_widget)
        self.music_tool_eq_btn.clicked.connect(self.add_graphic_equalizer_widget)
        self.row_music_tools = make_label("Music tools")
        self.inspector_music_layout.addRow(self.row_music_tools, self.inspector_music_tools_row)
        self.row_music_equalizer_bars = make_label("EQ bars")
        self.row_music_equalizer_gap = make_label("Bar gap")
        self.row_music_equalizer_mirror = make_label("Mirror mode")
        self.inspector_music_layout.addRow(self.row_music_equalizer_bars, self.designer_equalizer_bars_spin)
        self.inspector_music_layout.addRow(self.row_music_equalizer_gap, self.designer_equalizer_gap_spin)
        self.inspector_music_layout.addRow(self.row_music_equalizer_mirror, self.designer_equalizer_mirror_chk)
        self.row_music_widget_options = make_label("Options")
        self.music_widget_options_row = wrap_row(
            self.widget_cover_enabled_chk,
            self.widget_backdrop_enabled_chk,
            self.widget_title_marquee_chk,
            self.widget_equalizer_enabled_chk,
        )
        self.row_music_widget_title_font = make_label("Title font")
        self.row_music_widget_artist_font = make_label("Artist font")
        self.row_music_widget_detail_font = make_label("Detail font")
        self.row_music_widget_title_color = make_label("Title color")
        self.row_music_widget_artist_color = make_label("Artist color")
        self.row_music_widget_detail_color = make_label("Detail color")
        self.row_music_widget_panel_color = make_label("Panel color")
        self.widget_title_color_row, _ = add_color_row(self.widget_title_color_edit)
        self.widget_body_color_row, _ = add_color_row(self.widget_body_color_edit)
        self.widget_detail_color_row, _ = add_color_row(self.widget_detail_color_edit)
        self.widget_panel_color_row, _ = add_color_row(self.widget_panel_color_edit)
        self.inspector_music_layout.addRow(self.row_music_widget_options, self.music_widget_options_row)
        self.inspector_music_layout.addRow(self.row_music_widget_title_font, self.widget_title_font_spin)
        self.inspector_music_layout.addRow(self.row_music_widget_artist_font, self.widget_body_font_spin)
        self.inspector_music_layout.addRow(self.row_music_widget_detail_font, self.widget_detail_font_spin)
        self.inspector_music_layout.addRow(self.row_music_widget_title_color, self.widget_title_color_row)
        self.inspector_music_layout.addRow(self.row_music_widget_artist_color, self.widget_body_color_row)
        self.inspector_music_layout.addRow(self.row_music_widget_detail_color, self.widget_detail_color_row)
        self.inspector_music_layout.addRow(self.row_music_widget_panel_color, self.widget_panel_color_row)
        self.inspector_music_hint = QLabel("")
        self.inspector_music_hint.setWordWrap(True)
        self.inspector_music_hint.setObjectName("selectionSummaryLabel")
        self.inspector_music_layout.addRow(self.inspector_music_spectrum_placeholder)
        self.inspector_music_layout.addRow(self.inspector_music_hint)

        self.inspector_weather_hint = QLabel(
            "Weather widgets use Open-Meteo data configured in Configuration > Weather."
        )
        self.inspector_weather_hint.setWordWrap(True)
        self.inspector_weather_hint.setObjectName("selectionSummaryLabel")
        self.weather_tool_current_btn = QPushButton("Weather Current")
        self.weather_tool_wide_btn = QPushButton("Wide")
        self.weather_tool_hero_btn = QPushButton("Hero")
        self.weather_tool_forecast_btn = QPushButton("Weather 7D")
        self.weather_tool_convert_legacy_btn = QPushButton("Convert legacy")
        for btn in (self.weather_tool_current_btn, self.weather_tool_wide_btn, self.weather_tool_hero_btn, self.weather_tool_forecast_btn, self.weather_tool_convert_legacy_btn):
            btn.setObjectName("quickAddButton")
            btn.setMinimumHeight(24)
        self.weather_tool_current_btn.clicked.connect(self.add_weather_current_widget)
        self.weather_tool_wide_btn.clicked.connect(lambda: self.add_weather_current_widget("wide"))
        self.weather_tool_hero_btn.clicked.connect(lambda: self.add_weather_current_widget("hero"))
        self.weather_tool_forecast_btn.clicked.connect(self.add_weather_forecast_widget)
        self.weather_tool_convert_legacy_btn.clicked.connect(self.convert_legacy_weather_widgets)
        weather_tools_row = wrap_row(
            self.weather_tool_current_btn,
            self.weather_tool_wide_btn,
            self.weather_tool_hero_btn,
            self.weather_tool_forecast_btn,
            self.weather_tool_convert_legacy_btn,
        )
        self.weather_tools_row = weather_tools_row
        self.row_weather_tools = make_label("Weather tools")
        self.inspector_weather_layout.addRow(self.row_weather_tools, weather_tools_row)
        self.weather_designer_city_search_edit = QLineEdit()
        self.weather_designer_city_search_edit.setPlaceholderText("Search city, e.g. Warsaw")
        self.weather_designer_search_btn = QPushButton("Search")
        self.weather_designer_results_combo = QComboBox()
        self.weather_designer_results_combo.addItem("No city selected", None)
        self.weather_designer_apply_btn = QPushButton("Apply city")
        self.weather_designer_refresh_btn = QPushButton("Refresh weather")
        self.weather_designer_results_combo.setMinimumWidth(160)
        self.weather_city_row = wrap_row(
            self.weather_designer_city_search_edit,
            self.weather_designer_search_btn,
            self.weather_designer_results_combo,
            self.weather_designer_apply_btn,
            self.weather_designer_refresh_btn,
            stretch_first=True,
        )
        self.weather_designer_search_row = self.weather_city_row
        self.weather_designer_actions_row = self.weather_city_row
        self.row_weather_city = make_label("City")
        self.row_weather_city_search = self.row_weather_city
        self.row_weather_city_results = make_label("Results")
        self.row_weather_city_actions = make_label("Weather config")
        self.inspector_weather_layout.addRow(self.row_weather_city, self.weather_city_row)
        self.weather_designer_search_btn.clicked.connect(self.search_designer_weather_city)
        self.weather_designer_city_search_edit.returnPressed.connect(self.search_designer_weather_city)
        self.weather_designer_results_combo.currentIndexChanged.connect(self._apply_selected_designer_weather_city)
        self.weather_designer_apply_btn.clicked.connect(self.apply_designer_weather_config)
        self.weather_designer_refresh_btn.clicked.connect(self.refresh_designer_weather_now)
        self.weather_source_combo = QComboBox()
        self.weather_format_combo = QComboBox()
        self.weather_format_combo.addItem("{value}", "{value}")
        self.weather_format_combo.addItem("City: {value}", "City: {value}")
        self.weather_format_combo.addItem("Temp: {value}", "Temp: {value}")
        self.weather_format_combo.addItem("Weather: {value}", "Weather: {value}")
        self.weather_format_combo.addItem("Wind: {value}", "Wind: {value}")
        self.weather_format_combo.addItem("Humidity: {value}", "Humidity: {value}")
        self.weather_format_combo.addItem("High: {value}", "High: {value}")
        self.weather_format_combo.addItem("Low: {value}", "Low: {value}")
        self.weather_source_compact_label = QLabel("Source")
        self.weather_format_compact_label = QLabel("Format")
        self.weather_binding_row = make_compact_labeled_row(
            (self.weather_source_compact_label, self.weather_source_combo),
            (self.weather_format_compact_label, self.weather_format_combo),
            stretch_first=True,
        )
        self.row_weather_source = make_label("Weather binding")
        self.row_weather_format = make_label("Weather format")
        self.inspector_weather_layout.addRow(self.row_weather_source, self.weather_binding_row)
        for spin in (
            self.weather_widget_title_font_spin,
            self.weather_widget_body_font_spin,
            self.weather_widget_detail_font_spin,
        ):
            spin.setMaximumWidth(84)
        self.weather_widget_fonts_row = wrap_row(
            QLabel("Location"),
            self.weather_widget_title_font_spin,
            QLabel("Temp"),
            self.weather_widget_body_font_spin,
            QLabel("Detail"),
            self.weather_widget_detail_font_spin,
        )
        self.weather_widget_colors_row = make_compact_color_grid(
            add_compact_color_cell("Location", self.weather_widget_title_color_edit),
            add_compact_color_cell("Temp", self.weather_widget_body_color_edit),
            add_compact_color_cell("Detail", self.weather_widget_detail_color_edit),
            add_compact_color_cell("Panel", self.weather_widget_panel_color_edit),
        )
        self.row_weather_widget_fonts = make_label("Fonts")
        self.row_weather_widget_colors = make_label("Colors")
        self.row_weather_widget_transparent_bg = make_label("Background")
        self.row_weather_widget_animate_icons = make_label("Icon motion")
        self.inspector_weather_layout.addRow(self.row_weather_widget_fonts, self.weather_widget_fonts_row)
        self.inspector_weather_layout.addRow(self.row_weather_widget_colors, self.weather_widget_colors_row)
        self.inspector_weather_layout.addRow(self.row_weather_widget_transparent_bg, self.weather_widget_transparent_bg_chk)
        self.inspector_weather_layout.addRow(self.row_weather_widget_animate_icons, self.weather_widget_animate_icons_chk)
        self.weather_source_combo.currentIndexChanged.connect(self._on_weather_source_changed)
        self.weather_format_combo.currentIndexChanged.connect(self._on_weather_format_changed)
        self._populate_weather_source_combo()
        self.inspector_weather_layout.addRow(self.inspector_weather_hint)

        for l in [
            self.inspector_general_layout,
            self.inspector_content_layout,
            self.inspector_music_layout,
            self.inspector_weather_layout,
            self.inspector_appearance_layout,
            self.inspector_gauge_layout,
            self.inspector_geometry_layout,
            self.inspector_image_layout,
            self.inspector_media_layout,
            self.inspector_animation_layout,
        ]:
            l.setSpacing(4)
            l.setContentsMargins(4, 4, 4, 4)

        self.row_general_id = make_label("ID elementu")
        self.inspector_general_layout.addRow(self.row_general_id, self.designer_id_edit)
        self.row_general_visible = make_label("Widoczność")
        self.inspector_general_layout.addRow(self.row_general_visible, self.designer_visible_chk)
        self.row_general_locked = make_label("Zablokowany")
        self.inspector_general_layout.addRow(self.row_general_locked, self.designer_locked_chk)
        self.row_general_z = make_label("Warstwa")
        self.inspector_general_layout.addRow(self.row_general_z, self.designer_z_spin)

        self.row_content_text = make_label("Tekst")
        self.inspector_content_layout.addRow(self.row_content_text, self.designer_text_edit)
        self.row_content_label = make_label("Etykieta")
        self.inspector_content_layout.addRow(self.row_content_label, self.designer_label_edit)
        self.row_content_source = make_label("Źródło")
        self.inspector_content_layout.addRow(self.row_content_source, self.designer_source_combo)
        self.row_content_format = make_label("Format wartości")
        self.inspector_content_layout.addRow(self.row_content_format, self.designer_format_edit)
        self.row_content_stat_display = make_label("Tryb wyświetlania")
        self.inspector_content_layout.addRow(self.row_content_stat_display, self.designer_stat_display_combo)
        self.row_content_stat_range = make_label("Zakres")
        self.designer_stat_range_row = wrap_row(self.designer_stat_min_spin, self.designer_stat_max_spin)
        self.inspector_content_layout.addRow(self.row_content_stat_range, self.designer_stat_range_row)
        self.row_content_stat_show_value = make_label("Tekst wartości")
        self.inspector_content_layout.addRow(self.row_content_stat_show_value, self.designer_stat_show_value_chk)
        self._stat_binding_rows_layout = self.inspector_content_layout

        self.designer_font_minus_btn = QPushButton("−")
        self.designer_font_minus_btn.setMinimumWidth(36)
        self.designer_font_plus_btn = QPushButton("+")
        self.designer_font_plus_btn.setMinimumWidth(36)
        self.designer_font_minus_btn.clicked.connect(
            lambda: self.designer_font_size_spin.setValue(max(self.designer_font_size_spin.minimum(), self.designer_font_size_spin.value() - 1))
        )
        self.designer_font_plus_btn.clicked.connect(
            lambda: self.designer_font_size_spin.setValue(min(self.designer_font_size_spin.maximum(), self.designer_font_size_spin.value() + 1))
        )
        self.font_row = wrap_row(
            self.designer_font_family_combo,
            self.designer_font_minus_btn,
            self.designer_font_size_spin,
            self.designer_font_plus_btn,
            stretch_first=True,
        )
        self.row_appearance_font = make_label("Czcionka")
        self.inspector_appearance_layout.addRow(self.row_appearance_font, self.font_row)
        self.font_style_row = wrap_row(
            self.designer_font_bold_chk,
            self.designer_font_italic_chk,
            self.designer_font_underline_chk,
        )
        self.row_appearance_font_style = make_label("Styl")
        self.inspector_appearance_layout.addRow(self.row_appearance_font_style, self.font_style_row)
        self.row_appearance_align = make_label("Wyrównanie")
        self.inspector_appearance_layout.addRow(self.row_appearance_align, self.designer_align_combo)

        self.designer_color_row, self.designer_color_btn = add_color_row(self.designer_color_edit)
        self.row_appearance_color = make_label("Kolor")
        self.inspector_appearance_layout.addRow(self.row_appearance_color, self.designer_color_row)

        self.designer_label_color_row, self.designer_label_color_btn = add_color_row(self.designer_label_color_edit)
        self.row_appearance_label_color = make_label("Kolor etykiety")
        self.inspector_appearance_layout.addRow(self.row_appearance_label_color, self.designer_label_color_row)

        self.designer_value_color_row, self.designer_value_color_btn = add_color_row(self.designer_value_color_edit)
        self.row_appearance_value_color = make_label("Kolor wartości")
        self.inspector_appearance_layout.addRow(self.row_appearance_value_color, self.designer_value_color_row)
        self.designer_track_color_row, self.designer_track_color_btn = add_color_row(self.designer_track_color_edit)
        self.row_appearance_track_color = make_label("Kolor tła gauge / paska / wykresu")
        self.inspector_appearance_layout.addRow(self.row_appearance_track_color, self.designer_track_color_row)
        self.designer_fill_color_row, self.designer_fill_color_btn = add_color_row(self.designer_fill_color_edit)
        self.row_appearance_fill_color = make_label("Kolor linii / wypełnienia / wartości")
        self.inspector_appearance_layout.addRow(self.row_appearance_fill_color, self.designer_fill_color_row)
        self.row_sparkline_points = make_label("Punkty historii")
        self.inspector_appearance_layout.addRow(self.row_sparkline_points, self.designer_sparkline_points_spin)
        self.row_sparkline_fill_opacity = make_label("Przezrocz. wypełnienia")
        self.inspector_appearance_layout.addRow(self.row_sparkline_fill_opacity, self.designer_sparkline_fill_opacity_spin)
        self.row_sparkline_show_points = make_label("Punkt końcowy")
        self.inspector_appearance_layout.addRow(self.row_sparkline_show_points, self.designer_sparkline_show_points_chk)

        self.row_appearance_stroke_width = make_label("Grubość linii / gauge (0 = auto)")
        self.row_gauge_ring = make_label("Średnica pierścienia")
        self.row_gauge_value_layout = make_label("Układ wartości")
        self.designer_gauge_low_row, self.designer_gauge_low_btn = add_color_row(self.designer_gauge_low_edit)
        self.designer_gauge_mid_row, self.designer_gauge_mid_btn = add_color_row(self.designer_gauge_mid_edit)
        self.designer_gauge_high_row, self.designer_gauge_high_btn = add_color_row(self.designer_gauge_high_edit)
        self.designer_gauge_low_edit.setPlaceholderText("[R,G,B,A] — opcjonalnie, puste = z presetu")
        self.designer_gauge_mid_edit.setPlaceholderText("[R,G,B,A] — opcjonalnie")
        self.designer_gauge_high_edit.setPlaceholderText("[R,G,B,A] — opcjonalnie")
        self.row_gauge_preset = make_label("Preset kolorów")
        self.row_gauge_grad_low = make_label("Łuk: kolor niski")
        self.row_gauge_grad_mid = make_label("Łuk: środek")
        self.row_gauge_grad_high = make_label("Łuk: wysoki")
        self.row_gauge_smooth = make_label("Wygładzanie igły")
        self.row_gauge_match_value = make_label("Kolor wartości jak łuk")
        self.row_gauge_inner_alpha = make_label("Przezrocz. środka")

        self.inspector_gauge_layout.addRow(self.row_appearance_stroke_width, self.designer_stat_stroke_width_spin)
        self.inspector_gauge_layout.addRow(self.row_gauge_ring, self.designer_gauge_ring_spin)
        self.inspector_gauge_layout.addRow(self.row_gauge_value_layout, self.designer_gauge_value_layout_combo)
        self.inspector_gauge_layout.addRow(self.row_gauge_inner_alpha, self.designer_gauge_inner_alpha_spin)
        self.inspector_gauge_layout.addRow(self.row_gauge_preset, self.designer_stat_gauge_preset_combo)
        self.inspector_gauge_layout.addRow(self.row_gauge_grad_low, self.designer_gauge_low_row)
        self.inspector_gauge_layout.addRow(self.row_gauge_grad_mid, self.designer_gauge_mid_row)
        self.inspector_gauge_layout.addRow(self.row_gauge_grad_high, self.designer_gauge_high_row)
        self.inspector_gauge_layout.addRow(self.row_gauge_smooth, self.designer_gauge_smooth_spin)
        self.inspector_gauge_layout.addRow(self.row_gauge_match_value, self.designer_gauge_match_value_chk)

        self.row_panel_fill = make_label("Panel style")
        self.panel_fill_row = wrap_row(self.panel_fill_edit, self.panel_fill_btn, stretch_first=True)
        self.panel_fill_btn.clicked.connect(lambda _checked=False: self.pick_color_for_edit(self.panel_fill_edit))
        self.panel_fill_compact_label = QLabel("Fill")
        self.panel_opacity_compact_label = QLabel("Opacity")
        self.panel_radius_compact_label = QLabel("Radius")
        self.panel_opacity_spin.setMaximumWidth(84)
        self.panel_radius_spin.setMaximumWidth(84)
        self.panel_style_row = make_compact_labeled_row(
            (self.panel_fill_compact_label, self.panel_fill_row),
            (self.panel_opacity_compact_label, self.panel_opacity_spin),
            (self.panel_radius_compact_label, self.panel_radius_spin),
            stretch_first=True,
        )
        self.inspector_appearance_layout.addRow(self.row_panel_fill, self.panel_style_row)
        self.row_panel_opacity = make_label("Panel opacity")
        self.row_panel_radius = make_label("Corner radius")

        self.row_geometry_x = make_label("X")
        self.inspector_geometry_layout.addRow(self.row_geometry_x, self.designer_x_spin)
        self.row_geometry_y = make_label("Y")
        self.inspector_geometry_layout.addRow(self.row_geometry_y, self.designer_y_spin)
        self.row_geometry_w = make_label("Szerokość")
        self.inspector_geometry_layout.addRow(self.row_geometry_w, self.designer_w_spin)
        self.row_geometry_h = make_label("Wysokość")
        self.inspector_geometry_layout.addRow(self.row_geometry_h, self.designer_h_spin)
        self.geometry_group_bounds_label = QLabel("Group bounds: -")
        self.geometry_group_bounds_label.setObjectName("selectionSummaryLabel")
        self.geometry_group_bounds_label.setWordWrap(True)
        self.row_geometry_group_bounds = make_label("Group")
        self.inspector_geometry_layout.addRow(self.row_geometry_group_bounds, self.geometry_group_bounds_label)
        self.geometry_preset_top_btn = QPushButton("Top")
        self.geometry_preset_bottom_btn = QPushButton("Bottom")
        self.geometry_preset_left_btn = QPushButton("Left")
        self.geometry_preset_right_btn = QPushButton("Right")
        self.geometry_preset_center_btn = QPushButton("Center")
        for btn in (
            self.geometry_preset_top_btn,
            self.geometry_preset_bottom_btn,
            self.geometry_preset_left_btn,
            self.geometry_preset_right_btn,
            self.geometry_preset_center_btn,
        ):
            btn.setObjectName("quickAddButton")
            btn.setMinimumHeight(24)
        self.geometry_preset_top_btn.clicked.connect(lambda: self.apply_geometry_rect_preset("top"))
        self.geometry_preset_bottom_btn.clicked.connect(lambda: self.apply_geometry_rect_preset("bottom"))
        self.geometry_preset_left_btn.clicked.connect(lambda: self.apply_geometry_rect_preset("left"))
        self.geometry_preset_right_btn.clicked.connect(lambda: self.apply_geometry_rect_preset("right"))
        self.geometry_preset_center_btn.clicked.connect(lambda: self.apply_geometry_rect_preset("center"))
        self.geometry_preset_row = wrap_row(
            self.geometry_preset_top_btn,
            self.geometry_preset_bottom_btn,
            self.geometry_preset_left_btn,
            self.geometry_preset_right_btn,
            self.geometry_preset_center_btn,
        )
        self.row_geometry_presets = make_label("Presets")
        self.inspector_geometry_layout.addRow(self.row_geometry_presets, self.geometry_preset_row)
        self.row_motion_enabled = make_label("Ruch")
        self.inspector_geometry_layout.addRow(self.row_motion_enabled, self.motion_enabled_chk)
        self.row_motion_range = make_label("Zakres klatek")
        self.motion_range_row = wrap_row(self.motion_start_spin, self.motion_end_spin)
        self.inspector_geometry_layout.addRow(self.row_motion_range, self.motion_range_row)
        self.row_motion_target_x = make_label("Koniec X")
        self.inspector_geometry_layout.addRow(self.row_motion_target_x, self.motion_target_x_spin)
        self.row_motion_target_y = make_label("Koniec Y")
        self.inspector_geometry_layout.addRow(self.row_motion_target_y, self.motion_target_y_spin)
        self.row_motion_target_opacity = make_label("Końcowa przezr.")
        self.inspector_geometry_layout.addRow(self.row_motion_target_opacity, self.motion_target_opacity_spin)
        self.row_motion_actions = make_label("Akcje ruchu")
        self.motion_actions_row = wrap_row(self.motion_capture_current_btn, self.motion_remove_btn)
        self.inspector_geometry_layout.addRow(self.row_motion_actions, self.motion_actions_row)

        self.designer_path_browse_btn = QPushButton("Wybierz")
        self.designer_path_browse_btn.clicked.connect(self.browse_designer_image_path)
        self.designer_path_prepare_btn = QPushButton("Przygotuj")
        self.designer_path_prepare_btn.clicked.connect(self.browse_designer_image_path)
        self.designer_image_fullscreen_btn = QPushButton("Ustaw fullscreen")
        self.designer_image_fullscreen_btn.clicked.connect(lambda: self.apply_image_rect_preset("fullscreen"))
        self.designer_image_left_half_btn = QPushButton("Lewa połowa")
        self.designer_image_left_half_btn.clicked.connect(lambda: self.apply_image_rect_preset("left-half"))
        self.designer_image_right_half_btn = QPushButton("Prawa połowa")
        self.designer_image_right_half_btn.clicked.connect(lambda: self.apply_image_rect_preset("right-half"))
        self.designer_image_reset_btn = QPushButton("Reset kadru")
        self.designer_image_reset_btn.clicked.connect(lambda: self.apply_image_rect_preset("contain-full"))
        self.designer_import_image_btn = QPushButton("Importuj obraz do motywu")
        self.designer_import_image_btn.clicked.connect(self.import_image_as_designer_element)
        self.designer_path_row = wrap_row(
            self.designer_path_edit,
            self.designer_path_browse_btn,
            self.designer_path_prepare_btn,
            stretch_first=True,
        )
        self.row_image_path = make_label("Plik obrazu")
        self.inspector_image_layout.addRow(self.row_image_path, self.designer_path_row)
        self.row_image_fit = make_label("Transform")
        self.image_fit_compact_label = QLabel("Fit")
        self.image_opacity_compact_label = QLabel("Opacity")
        self.image_rotation_compact_label = QLabel("Rotation")
        self.designer_opacity_spin.setMaximumWidth(84)
        self.designer_rotation_spin.setMaximumWidth(84)
        self.image_transform_row = make_compact_labeled_row(
            (self.image_fit_compact_label, self.designer_fit_combo),
            (self.image_opacity_compact_label, self.designer_opacity_spin),
            (self.image_rotation_compact_label, self.designer_rotation_spin),
            stretch_first=True,
        )
        self.inspector_image_layout.addRow(self.row_image_fit, self.image_transform_row)
        self.row_image_opacity = make_label("Opacity")
        self.row_image_rotation = make_label("Rotation")
        self.row_image_import = make_label("Import")
        self.inspector_image_layout.addRow(self.row_image_import, self.designer_import_image_btn)
        self.row_image_actions = make_label("Szybkie akcje")
        self.designer_image_actions_row = wrap_row(
            self.designer_image_fullscreen_btn,
            self.designer_image_left_half_btn,
            self.designer_image_right_half_btn,
            self.designer_image_reset_btn,
        )
        self.inspector_image_layout.addRow(self.row_image_actions, self.designer_image_actions_row)
        self.row_image_preview = make_label("Podgląd")
        self.designer_image_preview_label = QLabel("Image preview")
        self.designer_image_preview_label.setAlignment(Qt.AlignCenter)
        self.designer_image_preview_label.setMinimumHeight(104)
        self.designer_image_preview_label.setObjectName("selectionSummaryLabel")
        self.inspector_image_layout.addRow(self.row_image_preview, self.designer_image_preview_label)

        self.background_preview_label.setAlignment(Qt.AlignCenter)
        self.background_preview_label.setMinimumHeight(92)
        self.background_preview_label.setObjectName("selectionSummaryLabel")
        self.media_background_path_row = wrap_row(
            self.bg_path_edit,
            self.bg_path_browse_btn,
            self.bg_prepare_btn,
            stretch_first=True,
        )
        self.row_media_bg_mode = make_label("Background mode")
        self.inspector_media_layout.addRow(self.row_media_bg_mode, self.bg_kind_combo)
        self.row_media_bg_path = make_label("File / import")
        self.inspector_media_layout.addRow(self.row_media_bg_path, self.media_background_path_row)
        self.row_media_bg_fit = make_label("Fit")
        self.inspector_media_layout.addRow(self.row_media_bg_fit, self.bg_fit_combo)
        self.row_media_bg_opacity = make_label("Opacity")
        self.inspector_media_layout.addRow(self.row_media_bg_opacity, self.bg_opacity_spin)
        self.row_media_bg_rotation = make_label("Rotation")
        self.inspector_media_layout.addRow(self.row_media_bg_rotation, self.bg_rotation_spin)
        media_colors_row = wrap_row(self.bg_base_color_edit, self.bg_base_color_btn, self.bg_accent_color_edit, self.bg_accent_color_btn)
        self.row_media_bg_colors = make_label("Colors")
        self.inspector_media_layout.addRow(self.row_media_bg_colors, media_colors_row)
        media_presets_row = wrap_row(
            self.bg_cover_btn,
            self.bg_contain_btn,
            self.bg_preset_ocean_btn,
            self.bg_preset_amber_btn,
            self.bg_preset_mono_btn,
            self.bg_preset_neon_btn,
        )
        self.row_media_bg_presets = make_label("Presets")
        self.inspector_media_layout.addRow(self.row_media_bg_presets, media_presets_row)
        self.row_media_bg_texture = make_label("Texture")
        self.inspector_media_layout.addRow(self.row_media_bg_texture, self.bg_texture_alpha_spin)
        self.row_media_bg_preview = make_label("Background preview")
        self.inspector_media_layout.addRow(self.row_media_bg_preview, self.background_preview_label)

        self.inspector_animation_details_hint = QLabel(
            "Use Animation Studio for the timeline, multi-frame timing, and a large preview. "
            "After editing frames, switch to Theme Designer to place stats and widgets like on a static theme."
        )
        self.inspector_animation_details_hint.setWordWrap(True)
        self.inspector_animation_details_hint.setObjectName("selectionSummaryLabel")
        self.row_animation_overview = make_label("Animation")
        self.inspector_animation_layout.addRow(self.row_animation_overview, self.inspector_animation_details_hint)
        self.open_animation_studio_btn = QPushButton("Open Animation Studio")
        self.open_animation_studio_btn.setObjectName("secondaryAccentButton")
        self.open_animation_studio_btn.clicked.connect(self._go_animation_studio)
        self.row_animation_editor = make_label("Editor")
        self.inspector_animation_layout.addRow(self.row_animation_editor, self.open_animation_studio_btn)

        self.inspector_tabs.addTab(self.inspector_general, "General")
        self.inspector_tabs.addTab(self.inspector_content, "Content")
        self.inspector_tabs.addTab(self.inspector_music, "Music")
        self.inspector_tabs.addTab(self.inspector_weather, "Weather")
        self.inspector_tabs.addTab(self.inspector_appearance, "Style")
        self.inspector_tabs.addTab(self.inspector_gauge, "Gauge")
        self.inspector_tabs.addTab(self.inspector_geometry, "Position")
        self.inspector_tabs.addTab(self.inspector_image, "Image")
        self.inspector_tabs.addTab(self.inspector_media, "Media")
        self.inspector_tabs.addTab(self.inspector_animation, "Animation")

        compact_widgets = [
            self.designer_id_edit,
            self.designer_text_edit,
            self.designer_label_edit,
            self.designer_format_edit,
            self.designer_source_combo,
            self.designer_stat_display_combo,
            self.designer_stat_min_spin,
            self.designer_stat_max_spin,
            self.designer_align_combo,
            self.designer_font_family_combo,
            self.designer_font_size_spin,
            self.designer_color_edit,
            self.designer_label_color_edit,
            self.designer_value_color_edit,
            self.designer_track_color_edit,
            self.designer_fill_color_edit,
            self.designer_x_spin,
            self.designer_y_spin,
            self.designer_w_spin,
            self.designer_h_spin,
            self.designer_z_spin,
            self.designer_path_edit,
            self.designer_fit_combo,
            self.designer_opacity_spin,
            self.designer_rotation_spin,
            self.panel_fill_edit,
            self.panel_opacity_spin,
            self.panel_radius_spin,
            self.designer_stat_stroke_width_spin,
            self.designer_gauge_ring_spin,
            self.designer_gauge_value_layout_combo,
            self.designer_gauge_inner_alpha_spin,
            self.designer_sparkline_points_spin,
            self.designer_sparkline_fill_opacity_spin,
            self.motion_start_spin,
            self.motion_end_spin,
            self.motion_target_x_spin,
            self.motion_target_y_spin,
            self.motion_target_opacity_spin,
        ]
        for widget in compact_widgets:
            widget.setMaximumHeight(32)
        for button in (
            self.designer_font_minus_btn,
            self.designer_font_plus_btn,
            self.designer_path_browse_btn,
            self.designer_path_prepare_btn,
            self.designer_import_image_btn,
            self.motion_capture_current_btn,
            self.motion_remove_btn,
            self.bg_path_browse_btn,
            self.bg_prepare_btn,
            self.bg_cover_btn,
            self.bg_contain_btn,
            self.bg_preset_ocean_btn,
            self.bg_preset_amber_btn,
            self.bg_preset_mono_btn,
            self.bg_preset_neon_btn,
            self.bg_animation_prev_btn,
            self.bg_animation_next_btn,
            self.bg_animation_play_btn,
            self.bg_animation_import_btn,
            self.bg_animation_add_btn,
            self.bg_animation_blank_btn,
            self.bg_animation_export_btn,
            self.bg_animation_duplicate_btn,
            self.bg_animation_repeat_all_btn,
            self.bg_animation_remove_btn,
            self.bg_animation_up_btn,
            self.bg_animation_down_btn,
            self.bg_animation_clear_btn,
        ):
            button.setMinimumHeight(28)
            button.setMaximumHeight(30)
        for check in (
            self.designer_visible_chk,
            self.designer_locked_chk,
            self.designer_font_bold_chk,
            self.designer_font_italic_chk,
            self.designer_font_underline_chk,
            self.motion_enabled_chk,
        ):
            check.setMaximumHeight(26)

        layout.addWidget(self.inspector_tabs)
        container_layout.addWidget(box)

    def _build_app_stylesheet(self, theme_name: str, scale_percent: int) -> str:
        theme = UI_THEMES.get(theme_name, UI_THEMES["Plasma Blue"])
        light_mode = hasattr(self, "ui_mode_combo") and self.ui_mode_combo.currentText() == "Light"
        base_font = max(12, int(round(13 * scale_percent / 100)))
        small_font = max(11, int(round(11 * scale_percent / 100)))
        title_font = max(15, int(round(16 * scale_percent / 100)))
        bg_page = "#f0f4f9" if light_mode else "#15191e"
        bg_panel = "#ffffff" if light_mode else "#1e232b"
        bg_input = "#fdfdfe" if light_mode else "#101419"
        bg_tab = "#e2e8f0" if light_mode else "#1e2531"
        bg_tab_selected = "#ffffff" if light_mode else "#283244"
        text_main = "#1e293b" if light_mode else "#f1f5f9"
        text_soft = "#64748b" if light_mode else "#94a3b8"
        border_main = "#e2e8f0" if light_mode else "#2d3440"
        border_soft = "#cbd5e1" if light_mode else "#3b4453"
        accent_color = theme['accent']
        primary_color = theme['primary']
        
        return f"""
            QWidget {{
                background: {bg_page};
                color: {text_main};
                font-size: {base_font}px;
                font-family: "Segoe UI", "Roboto", "DejaVu Sans", sans-serif;
            }}
            QFrame#shellSidebar {{
                background: {bg_panel};
                border: 1px solid {border_main};
                border-radius: 18px;
            }}
            QLabel#shellBrandIcon {{
                color: {primary_color};
                font-size: {title_font + 8}px;
                font-weight: 900;
            }}
            QLabel#shellBrandLabel {{
                color: {text_main};
                font-size: {title_font - 2}px;
                font-weight: 800;
            }}
            QLabel#shellBrandSubLabel {{
                color: {primary_color};
                font-size: {small_font}px;
                font-weight: 700;
                padding-left: 6px;
                margin-bottom: 8px;
            }}
            QFrame#sidebarFooterCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg_input}, stop:1 {bg_tab_selected});
                border: 1px solid {border_soft};
                border-radius: 14px;
            }}
            QLabel#sidebarFooterTitle {{
                color: {text_main};
                font-size: {small_font + 1}px;
                font-weight: 800;
            }}
            QLabel#sidebarFooterMeta {{
                color: {text_soft};
                font-size: {small_font - 1}px;
                line-height: 1.3em;
            }}
            QGroupBox#shellHeader {{
                border: 1px solid {border_main};
                border-radius: 16px;
                background: {bg_panel};
                margin-top: 8px;
                padding: 10px 12px 12px 12px;
            }}
            QGroupBox#designerToolbarBox {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {bg_panel}, stop:1 {bg_tab_selected});
                border: 1px solid {border_main};
                border-radius: 16px;
            }}
            QLabel#shellTitleLabel {{
                font-size: {title_font + 2}px;
                font-weight: 800;
                color: {text_main};
            }}
            QLabel#shellTitleMeta {{
                color: {text_soft};
                font-size: {small_font}px;
                font-weight: 500;
            }}
            QLabel#headerFieldLabel {{
                color: {text_soft};
                font-size: {small_font}px;
                font-weight: 700;
                padding-right: 2px;
            }}
            QPushButton#shellNavButton {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 16px;
                padding: 18px 16px;
                text-align: left;
                font-size: {title_font - 1}px;
                font-weight: 700;
                color: {text_main};
            }}
            QPushButton#shellNavButton:hover {{
                border: 1px solid {primary_color};
                background: {bg_tab_selected};
            }}
            QPushButton#shellNavButton:checked {{
                border: 1px solid {primary_color};
                background: {bg_tab_selected};
                color: {primary_color};
            }}
            QPushButton#shellNavButton[collapsed="true"] {{
                text-align: center;
                padding: 10px 6px;
                font-size: {title_font + 2}px;
                border-radius: 14px;
            }}
            QLabel#headerStatusBadge {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 10px;
                padding: 5px 10px;
                color: {text_main};
                font-weight: 700;
            }}
            QLabel#headerReadyBadge {{
                background: #17361f;
                border: 1px solid #1f7a39;
                border-radius: 10px;
                padding: 5px 10px;
                color: #7cf59a;
                font-weight: 800;
            }}
            QLabel#sectionTinyTitle {{
                color: {primary_color};
                font-size: {small_font}px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.4px;
                padding: 0px 0px 2px 2px;
            }}
            QGroupBox {{
                border: 1px solid {border_main};
                border-radius: 12px;
                margin-top: 20px;
                padding: 16px 12px 12px 12px;
                font-weight: 700;
                background: {bg_panel};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                color: {primary_color};
            }}
            QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 8px;
                padding: 6px 8px;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {primary_color};
            }}
            QPushButton {{
                background: #2d3648;
                border: 1px solid #4a5568;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 600;
                color: #f8fafc;
            }}
            QPushButton:hover {{
                background: #3a475d;
                border: 1px solid #718096;
            }}
            QPushButton:pressed {{
                background: #1e2533;
            }}
            QPushButton#primaryButton {{
                background: {primary_color};
                border: 1px solid {theme['primary_border']};
                color: white;
            }}
            QPushButton#primaryButton:hover {{
                background: {theme['primary_border']};
            }}
            QPushButton#primaryButton:pressed {{
                background: {theme['primary_border']};
                border: 1px solid {theme['primary_border']};
                padding-top: 9px;
                padding-bottom: 7px;
            }}
            QPushButton#secondaryAccentButton {{
                background: #2d3748;
                border: 1px solid {accent_color};
                color: {accent_color};
            }}
            QPushButton#secondaryAccentButton:hover {{
                background: #344358;
                border: 1px solid #8fdcff;
                color: #f0fbff;
            }}
            QPushButton#secondaryAccentButton:pressed {{
                background: #233146;
                border: 1px solid #67d2ff;
                color: #ffffff;
                padding-top: 9px;
                padding-bottom: 7px;
            }}
            QPushButton#modeToggleButton {{
                background: #233044;
                border: 1px solid #4c627e;
                color: #dbeafe;
            }}
            QPushButton#modeToggleButton:hover {{
                background: #2b3b54;
                border: 1px solid {accent_color};
            }}
            QPushButton#modeToggleButton:checked {{
                background: {accent_color};
                border: 1px solid {theme['primary_border']};
                color: #08111f;
            }}
            QPushButton#quickAddButton {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 14px;
                padding: 12px 14px;
                font-size: {small_font}px;
                text-align: center;
                font-weight: 700;
            }}
            QPushButton#quickAddButton:hover {{
                border: 1px solid {primary_color};
                background: {bg_tab_selected};
            }}
            QPushButton#quickPresetButton {{
                background: {bg_input};
                border: 1px solid {border_soft};
                color: {text_main};
                padding: 14px 18px;
                min-width: 128px;
                font-weight: 700;
            }}
            QPushButton#quickPresetButton:hover {{
                border: 1px solid {primary_color};
                background: {bg_tab_selected};
            }}
            
            QFrame#templateCard, QFrame#libraryCard, QFrame#assetCard {{
                background: {bg_panel};
                border: 1px solid {border_main};
                border-radius: 16px;
            }}
            QFrame#templateCard:hover, QFrame#libraryCard:hover, QFrame#assetCard:hover {{
                border: 1px solid {primary_color};
                background: {bg_tab_selected};
            }}
            
            QLabel#templateCardTitle, QLabel#libraryCardTitle {{
                font-size: {title_font}px;
                font-weight: 800;
                color: {text_main};
            }}
            QLabel#templateCardDesc, QLabel#libraryCardDesc {{
                color: {text_soft};
                font-size: {small_font}px;
            }}
            QGroupBox#librarySectionBox {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg_panel}, stop:1 {bg_tab_selected});
                border: 1px solid {border_main};
                border-radius: 18px;
                margin-top: 20px;
                padding: 18px 14px 14px 14px;
            }}
            QFrame#libraryActionBar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg_panel}, stop:1 {bg_tab_selected});
                border: 1px solid {border_main};
                border-radius: 16px;
                padding: 8px;
            }}
            QGroupBox#designerWorkspaceBox {{
                background: {bg_panel};
                border: 1px solid {border_main};
                border-radius: 18px;
                margin-top: 16px;
                padding: 16px 14px 14px 14px;
            }}
            QGroupBox#designerSectionBox, QGroupBox#designerCanvasBox {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg_panel}, stop:1 {bg_tab_selected});
                border: 1px solid {border_main};
                border-radius: 16px;
                margin-top: 18px;
                padding: 16px 12px 12px 12px;
            }}
            QGroupBox#designerCanvasBox {{
                border: 1px solid {primary_color};
            }}
            QGroupBox#designerSectionBox::title, QGroupBox#designerCanvasBox::title, QGroupBox#librarySectionBox::title {{
                color: {accent_color};
                font-size: {small_font + 1}px;
                font-weight: 800;
                text-transform: uppercase;
            }}
            QLineEdit[placeholderText="Szukaj komponentów..."], QLineEdit[placeholderText="Filtruj po nazwie pliku lub typu..."] {{
                padding: 10px 12px;
                border-radius: 10px;
            }}

            QTabWidget::pane {{
                border: 1px solid {border_main};
                border-radius: 12px;
                background: {bg_panel};
                top: -1px;
            }}
            QTabWidget#mainSectionTabs::pane, QTabWidget#studioSectionTabs::pane {{
                border-radius: 16px;
            }}
            QTabBar::tab {{
                background: {bg_tab};
                border: 1px solid {border_main};
                padding: 7px 12px;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                color: {text_soft};
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {bg_panel};
                border-bottom: 2px solid {primary_color};
                color: {primary_color};
            }}
            QTabBar::tab:hover {{
                background: {bg_tab_selected};
            }}
            QTabWidget#mainSectionTabs QTabBar::tab {{
                padding: 12px 24px;
                min-width: 150px;
                font-size: {base_font}px;
                font-weight: 700;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
            QTabWidget#studioSectionTabs QTabBar::tab {{
                padding: 11px 22px;
                min-width: 170px;
                font-weight: 700;
            }}

            QSplitter::handle {{
                background: {border_main};
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {border_soft};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {accent_color};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QFrame#runtimeHeroCard {{
                background: {bg_panel};
                border: 2px solid {primary_color};
                border-radius: 20px;
            }}
            QGroupBox#dashboardCardBox, QGroupBox#configCardBox {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg_panel}, stop:1 {bg_tab_selected});
                border: 1px solid {border_main};
                border-radius: 18px;
                margin-top: 20px;
                padding: 16px 14px 14px 14px;
            }}
            QLabel#eventHeaderLabel {{
                color: {text_soft};
                font-size: {small_font}px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            QListWidget#designerLayerList {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 14px;
                padding: 6px;
            }}
            QListWidget#designerLayerList::item {{
                border-radius: 12px;
                padding: 4px;
                margin: 2px 0px;
            }}
            QLabel#layerTitleLabel {{
                color: {text_main};
                font-size: {base_font}px;
                font-weight: 800;
            }}
            QLabel#layerSubtitleLabel {{
                color: {text_soft};
                font-size: {small_font}px;
            }}
            QLabel#layerBadgeLabel {{
                color: {accent_color};
                background: rgba(31, 111, 235, 0.14);
                border: 1px solid rgba(94, 200, 255, 0.25);
                border-radius: 8px;
                padding: 4px 8px;
                font-size: {small_font - 1}px;
                font-weight: 800;
            }}
            QListWidget#systemEventsList {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 12px;
                padding: 4px;
                font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
            }}
            QListWidget#systemEventsList::item {{
                background: transparent;
                border-bottom: 1px solid {border_main};
                padding: 8px 10px;
            }}
            QListWidget#systemEventsList::item:selected {{
                background: rgba(31, 111, 235, 0.18);
                border: 1px solid {primary_color};
                border-radius: 8px;
            }}
            QPushButton#quickActionButton {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 12px;
                padding: 12px 14px;
                text-align: left;
                font-weight: 700;
            }}
            QPushButton#quickActionButton:hover {{
                border: 1px solid {primary_color};
                background: {bg_tab_selected};
            }}
            QLabel#statPillValue {{
                background: #111827;
                color: {accent_color};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 800;
                font-family: monospace;
                font-size: {base_font}px;
            }}
            QLabel#statPillLabel {{
                color: {text_soft};
                font-weight: 600;
                font-size: {small_font}px;
            }}
            QFrame#statPillFrame {{
                background: {bg_input};
                border: 1px solid {border_soft};
                border-radius: 10px;
            }}
        """

    def apply_ui_chrome(self) -> None:
        theme_name = self.ui_theme_combo.currentText() if hasattr(self, "ui_theme_combo") else "Plasma Blue"
        scale_percent = int(self.ui_scale_combo.currentData() or 100) if hasattr(self, "ui_scale_combo") else 100
        self.setStyleSheet(self._build_app_stylesheet(theme_name, scale_percent))
        self._apply_responsive_layout_metrics(scale_percent)
        self._apply_content_width_rules(scale_percent)

    def _apply_equal_width_for_group(
        self,
        widgets: list[QWidget],
        *,
        extra_px: int = 20,
        min_px: int = 72,
        max_px: int = 280,
    ) -> None:
        valid = [w for w in widgets if w is not None]
        if not valid:
            return
        target = min_px
        for widget in valid:
            text = ""
            if hasattr(widget, "text"):
                try:
                    text = str(widget.text()).strip()
                except Exception:
                    text = ""
            if not text:
                continue
            target = max(target, int(widget.fontMetrics().horizontalAdvance(text) + extra_px))
        target = max(min_px, min(max_px, target))
        for widget in valid:
            widget.setMinimumWidth(target)

    def _apply_tabbar_equal_width(self, tabs: QTabWidget, *, extra_px: int = 26, min_px: int = 76, max_px: int = 220) -> None:
        bar = tabs.tabBar()
        if bar is None:
            return
        bar.setExpanding(False)
        bar.setUsesScrollButtons(True)
        widest = min_px
        for idx in range(tabs.count()):
            text = tabs.tabText(idx).strip()
            if text:
                widest = max(widest, int(bar.fontMetrics().horizontalAdvance(text) + extra_px))
        widest = max(min_px, min(max_px, widest))
        bar.setStyleSheet(
            f"QTabBar::tab {{ min-width: {widest}px; padding: 6px 10px; }}"
            f"QTabBar::tab:selected {{ padding: 6px 10px; }}"
        )

    def _apply_content_width_rules(self, scale_percent: int) -> None:
        scale = max(0.8, min(1.3, scale_percent / 100.0))
        if hasattr(self, "inspector_tabs"):
            self._apply_tabbar_equal_width(
                self.inspector_tabs,
                extra_px=int(24 * scale),
                min_px=int(70 * scale),
                max_px=int(180 * scale),
            )
        if hasattr(self, "quick_add_text_btn"):
            self._apply_equal_width_for_group(
                [
                    self.quick_add_text_btn,
                    self.quick_add_stat_btn,
                    self.quick_add_image_btn,
                    self.quick_add_panel_btn,
                ],
                extra_px=int(24 * scale),
                min_px=int(92 * scale),
                max_px=int(180 * scale),
            )
            self._apply_equal_width_for_group(
                [
                    self.quick_add_now_playing_btn,
                    self.quick_add_now_playing_hero_btn,
                    self.quick_add_now_playing_mini_btn,
                    self.quick_add_volume_btn,
                ],
                extra_px=int(24 * scale),
                min_px=int(92 * scale),
                max_px=int(180 * scale),
            )
            self._apply_equal_width_for_group(
                [
                    self.quick_add_analog_clock_btn,
                    self.quick_add_gauge_set_btn,
                ],
                extra_px=int(24 * scale),
                min_px=int(92 * scale),
                max_px=int(180 * scale),
            )
        if hasattr(self, "designer_quick_add_toggle_btn"):
            self._apply_equal_width_for_group(
                [self.designer_quick_add_toggle_btn],
                extra_px=int(20 * scale),
                min_px=int(94 * scale),
                max_px=int(150 * scale),
            )
        if hasattr(self, "designer_reload_btn"):
            self._apply_equal_width_for_group(
                [
                    self.designer_reload_btn,
                    self.designer_write_btn,
                    self.designer_undo_btn,
                    self.designer_redo_btn,
                    self.designer_preview_btn,
                    self.designer_animation_mode_btn,
                    self.designer_assets_toggle_btn,
                    self.designer_details_toggle_btn,
                ],
                extra_px=int(24 * scale),
                min_px=int(88 * scale),
                max_px=int(240 * scale),
            )
        if hasattr(self, "designer_remove_btn"):
            self._apply_equal_width_for_group(
                [
                    self.designer_remove_btn,
                ],
                extra_px=int(22 * scale),
                min_px=int(92 * scale),
                max_px=int(128 * scale),
            )

    def _apply_responsive_layout_metrics(self, scale_percent: int | None = None) -> None:
        if scale_percent is None:
            scale_percent = int(self.ui_scale_combo.currentData() or 100) if hasattr(self, "ui_scale_combo") else 100
        scale = scale_percent / 100.0
        width = max(1200, self.width() or 0)
        height = max(840, self.height() or 0)
        compact = width < 1650
        short = height < 1180
        if hasattr(self, "_shell_nav_buttons") and self._shell_nav_buttons:
            sidebar_width = 102 if getattr(self, "sidebar_collapsed", False) else (224 if compact else 242)
            parent_sidebar = getattr(self, "sidebar_frame", None)
            if parent_sidebar is not None:
                if getattr(self, "sidebar_collapsed", False):
                    computed_width = int(sidebar_width * min(scale, 1.15))
                else:
                    computed_width = max(214, int(sidebar_width * max(scale, 0.95)))
                parent_sidebar.setFixedWidth(computed_width)
        if hasattr(self, "designer_elements_box"):
            self.designer_elements_box.setMinimumWidth(max(340, int((380 if compact else 430) * scale)))
            self.designer_elements_box.setMaximumWidth(max(560, int((600 if compact else 660) * scale)))
        if hasattr(self, "designer_component_search"):
            self.designer_component_search.setMaximumHeight(26 if short else 28)
        if hasattr(self, "designer_quick_add_toggle_btn"):
            self.designer_quick_add_toggle_btn.setMaximumHeight(26 if short else 28)
        if hasattr(self, "props_box"):
            self.props_box.setMinimumWidth(max(270, int((300 if compact else 360) * scale)))
        min_canvas, max_inspector = self._designer_splitter_limits()
        if hasattr(self, "designer_canvas_workbench"):
            self.designer_canvas_workbench.setMinimumHeight(min_canvas)
        if hasattr(self, "designer_inspector_container"):
            self.designer_inspector_container.setMaximumHeight(max_inspector)
        if getattr(self, "studio_splitter", None) is not None:
            total = int((1480 if compact else 1760) * scale)
            self.studio_splitter.setSizes([max(980, total), 0])
        # Usunięto sztywne ustawianie rozmiarów dla designer_main_splitter i designer_top_splitter
        if hasattr(self, "designer_controls_splitter"):
            self.designer_controls_splitter.setSizes([max(380, int(500 * scale)), max(180, int(240 * scale))])
        if hasattr(self, "designer_assets_box") and hasattr(self, "designer_animation_box"):
            animation_mode = bool(hasattr(self, "designer_animation_mode_btn") and self.designer_animation_mode_btn.isChecked())
            if animation_mode:
                self.designer_assets_box.setMaximumHeight(560 if short else 720)
                self.designer_animation_box.setMaximumHeight(520 if short else 660)
            else:
                self.designer_assets_box.setMaximumHeight(210 if short else 260)
                self.designer_animation_box.setMaximumHeight(170 if short else 220)
        self._apply_designer_aux_visibility(auto_short=short)
        self._clamp_designer_splitter_later()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if hasattr(self, "ui_scale_combo"):
            self._apply_responsive_layout_metrics()
            self._apply_content_width_rules(int(self.ui_scale_combo.currentData() or 100))

    def _apply_designer_aux_visibility(self, *_args: object, auto_short: bool | None = None) -> None:
        short = (self.height() or 0) < 1180 if auto_short is None else bool(auto_short)
        compact_window = (self.width() or 0) < 1650
        animation_mode = bool(getattr(self, "designer_animation_mode_btn", None) and self.designer_animation_mode_btn.isChecked())
        assets_expanded = animation_mode or bool(getattr(self, "designer_assets_toggle_btn", None) and self.designer_assets_toggle_btn.isChecked())
        details_expanded = bool(getattr(self, "designer_details_toggle_btn", None) and self.designer_details_toggle_btn.isChecked())

        dock_inspector_bottom = False
        self._set_designer_inspector_docked_bottom(dock_inspector_bottom)
        if hasattr(self, "designer_elements_box"):
            self.designer_elements_box.setVisible(True)
        if hasattr(self, "designer_quick_add_container"):
            self.designer_quick_add_container.setVisible(False)
        if hasattr(self, "designer_quick_add_toggle_btn"):
            self.designer_quick_add_toggle_btn.setVisible(True)
            self.designer_quick_add_toggle_btn.setText(self._tr("+ component", "+ komponent"))
        if hasattr(self, "designer_inspector_container"):
            self.designer_inspector_container.setVisible(True)
        if hasattr(self, "designer_collection_hint"):
            self.designer_collection_hint.setVisible(not short)
        if hasattr(self, "designer_selection_label"):
            self.designer_selection_label.setVisible(True)
        if hasattr(self, "inspector_selection_summary"):
            self.inspector_selection_summary.setVisible(not short)
        if hasattr(self, "inspector_tabs"):
            media_idx = self.inspector_tabs.indexOf(getattr(self, "inspector_media", None))
            animation_idx = self.inspector_tabs.indexOf(getattr(self, "inspector_animation", None))
            if animation_mode and animation_idx >= 0:
                self.inspector_tabs.setCurrentIndex(animation_idx)
            elif assets_expanded and media_idx >= 0:
                self.inspector_tabs.setCurrentIndex(media_idx)
        if hasattr(self, "designer_assets_toggle_btn"):
            self.designer_assets_toggle_btn.setText(
                self._tr("Hide media", "Ukryj multi")
                if assets_expanded and not animation_mode
                else self._tr("Media", "Multimedia")
            )
            self.designer_assets_toggle_btn.setVisible(True)
        if hasattr(self, "designer_animation_mode_btn"):
            self.designer_animation_mode_btn.setText(
                self._tr("Exit animation", "Wyjdź z anim.") if animation_mode else self._tr("Animation", "Animacja")
            )
        if hasattr(self, "designer_details_toggle_btn"):
            self.designer_details_toggle_btn.setText(
                self._tr("Hide tips", "Ukryj wsk.") if details_expanded else self._tr("Tips", "Wsk.")
            )
        if short and hasattr(self, "preview_info_label"):
            self.preview_info_label.setText(
                self._tr(
                    "Click, drag, or select an element on the preview.",
                    "Kliknij, przeciągnij lub zaznacz element na podglądzie.",
                )
            )

    def _set_designer_toolbar_feedback(self, text: str, *, auto_clear_ms: int | None = 4200) -> None:
        message = str(text).strip()
        if hasattr(self, "designer_toolbar_feedback_label"):
            label = self.designer_toolbar_feedback_label
            if hasattr(self, "designer_toolbar_feedback_timer"):
                self.designer_toolbar_feedback_timer.stop()
            if not message:
                label.clear()
                label.setToolTip("")
                label.hide()
            else:
                shown = label.fontMetrics().elidedText(message, Qt.ElideRight, max(80, label.maximumWidth() - 8))
                label.setText(shown)
                label.setToolTip(message if shown != message else "")
                label.show()
                if auto_clear_ms is not None and hasattr(self, "designer_toolbar_feedback_timer"):
                    self.designer_toolbar_feedback_timer.start(max(1200, int(auto_clear_ms)))
        if message and hasattr(self, "preview_info_label"):
            self.preview_info_label.setText(message)

    def _apply_background_style_preset(self, base: list[int], accent: list[int], texture: float) -> None:
        self.bg_kind_combo.setCurrentText("generated")
        self.bg_base_color_edit.setText(str([int(v) for v in base]))
        self.bg_accent_color_edit.setText(str([int(v) for v in accent]))
        self.bg_texture_alpha_spin.setValue(float(texture))
        self._set_designer_toolbar_feedback("Zastosowano preset tła. Odśwież podgląd lub użyj auto-preview.")

    def _set_designer_toolbar_busy(self, action: str, busy: bool) -> None:
        mapping = {
            "theme-doc-load": getattr(self, "designer_reload_btn", None),
            "studio-theme-save": getattr(self, "designer_write_btn", None),
            "theme-doc-preview": getattr(self, "designer_preview_btn", None),
            "studio-theme-apply": getattr(self, "designer_apply_btn", None),
            "theme-doc-apply": getattr(self, "designer_apply_btn", None),
        }
        btn = mapping.get(action)
        if btn is not None:
            btn.setEnabled(not busy)

    def _trigger_designer_load_theme(self) -> None:
        self._set_designer_toolbar_busy("theme-doc-load", True)
        self._set_designer_toolbar_feedback("Wczytywanie motywu z pliku...", auto_clear_ms=None)
        self.load_theme_doc()

    def _trigger_designer_save_theme(self) -> None:
        self._set_designer_toolbar_busy("studio-theme-save", True)
        self._set_designer_toolbar_feedback("Zapisywanie motywu do biblioteki...", auto_clear_ms=None)
        self.save_current_theme_to_library()

    def _trigger_designer_preview(self) -> None:
        self._set_designer_toolbar_busy("theme-doc-preview", True)
        self._set_designer_toolbar_feedback("Renderowanie podglądu LCD...", auto_clear_ms=None)
        self.preview_theme_doc()

    def _trigger_designer_apply(self) -> None:
        self._set_designer_toolbar_busy("theme-doc-apply", True)
        self._set_designer_toolbar_feedback("Wysyłanie motywu na LCD...", auto_clear_ms=None)
        self.apply_theme_doc()

    def _load_ui_state_payload(self) -> dict[str, Any]:
        try:
            if UI_STATE_PATH.exists():
                raw = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
        except Exception:
            pass
        return {}

    def _current_ui_language(self) -> str:
        return str(getattr(self, "_ui_language", "en")).strip().lower() or "en"

    def _tr(self, en_text: str, pl_text: str) -> str:
        return pl_text if self._current_ui_language() == "pl" else en_text

    def _populate_designer_quick_add_menu(self) -> None:
        menu = getattr(self, "designer_quick_add_menu", None)
        if menu is None:
            return
        menu.clear()
        tr = self._tr
        domain = self._designer_domain_mode()

        def add_section(title: str) -> None:
            try:
                menu.addSection(title)
            except Exception:
                menu.addSeparator()

        basics: list[tuple[str, object]] = [
            (tr("Text", "Tekst"), lambda: self.quick_add_designer_element("texts")),
            (tr("Stat", "Statystyka"), lambda: self.quick_add_designer_element("stats")),
            (tr("Progress Bar", "Pasek postępu"), lambda: self.add_stat_visual_widget("progress")),
            (tr("Sparkline", "Sparkline"), lambda: self.add_stat_visual_widget("sparkline")),
            (tr("Image", "Obraz"), lambda: self.quick_add_designer_element("images")),
            (tr("Panel", "Panel"), lambda: self.quick_add_designer_element("panels")),
        ]
        music_audio: list[tuple[str, object]] = [
            (tr("Now Playing", "Now Playing"), self.add_now_playing_widget),
            (tr("Now Playing Hero", "Now Playing Hero"), self.add_now_playing_widget_hero),
            (tr("Now Playing Mini", "Now Playing Mini"), self.add_now_playing_widget_mini),
            (tr("Volume", "Głośność"), self.add_volume_widget),
            (tr("Graphic EQ", "Korektor graficzny"), self.add_graphic_equalizer_widget),
        ]
        weather_widgets: list[tuple[str, object]] = [
            (tr("Weather Current", "Pogoda teraz"), self.add_weather_current_widget),
            (tr("Weather Wide", "Pogoda szeroka"), lambda: self.add_weather_current_widget("wide")),
            (tr("Weather Hero", "Pogoda hero"), lambda: self.add_weather_current_widget("hero")),
            (tr("Weather 7D Forecast", "Prognoza 7 dni"), self.add_weather_forecast_widget),
        ]
        widgets: list[tuple[str, object]] = [
            (tr("Analog Clock Classic", "Analog Clock Classic"), lambda: self.add_analog_clock_widget("classic")),
            (tr("Analog Clock Modern", "Analog Clock Modern"), lambda: self.add_analog_clock_widget("modern")),
            (tr("Analog Clock Nordic", "Analog Clock Nordic"), lambda: self.add_analog_clock_widget("nordic")),
            (tr("Gauge Set: System Trio", "Gauge Set: System Trio"), lambda: self.add_gauge_ring_bundle("system")),
            (tr("Gauge Set: Nordic Trio", "Gauge Set: Nordic Trio"), lambda: self.add_gauge_ring_bundle("nordic")),
            (tr("Gauge Set: Cyber Trio", "Gauge Set: Cyber Trio"), lambda: self.add_gauge_ring_bundle("cyber")),
            (tr("Gauge Set: Thermal Trio", "Gauge Set: Thermal Trio"), lambda: self.add_gauge_ring_bundle("thermal")),
        ]

        if domain in {"all", "system"}:
            add_section(tr("Basics", "Podstawowe"))
            for label, handler in basics:
                action = menu.addAction(label)
                action.triggered.connect(handler)
        if domain in {"all", "weather"}:
            add_section(tr("Weather", "Pogoda"))
            for label, handler in weather_widgets:
                action = menu.addAction(label)
                action.triggered.connect(handler)
        if domain in {"all", "music"}:
            add_section(tr("Music & audio", "Muzyka i audio"))
            for label, handler in music_audio:
                action = menu.addAction(label)
                action.triggered.connect(handler)
        if domain != "music":
            add_section(tr("Widgets", "Widgety"))
            for label, handler in widgets:
                action = menu.addAction(label)
                action.triggered.connect(handler)

    def _refresh_designer_quick_add_groups(self) -> None:
        domain = self._designer_domain_mode()
        if hasattr(self, "quick_add_group_basics"):
            self.quick_add_group_basics.setVisible(domain in {"all", "system"})
        if hasattr(self, "quick_add_group_music"):
            self.quick_add_group_music.setVisible(domain in {"all", "music"})
        if hasattr(self, "quick_add_group_weather"):
            self.quick_add_group_weather.setVisible(domain in {"all", "weather"})
        if hasattr(self, "quick_add_group_widgets"):
            self.quick_add_group_widgets.setVisible(domain not in {"music", "weather"})

    def _on_designer_domain_changed(self, _index: int) -> None:
        current_source = str(self.designer_source_combo.currentData() or "").strip()
        self._populate_designer_source_combo(current_source)
        self._populate_designer_quick_add_menu()
        self._refresh_designer_quick_add_groups()
        self.filter_designer_element_list()

    def _refresh_inspector_form_labels(self, tr) -> None:
        """Inspector / media / motion row captions and related buttons (EN default, PL via tr)."""
        for attr, en, pl in (
            ("row_general_id", "Element ID", "ID elementu"),
            ("row_general_visible", "Visibility", "Widoczność"),
            ("row_general_locked", "Locked", "Zablokowany"),
            ("row_general_z", "Layer (Z)", "Warstwa"),
            ("row_music_tools", "Music tools", "Narzędzia muzyczne"),
            ("row_music_equalizer_bars", "EQ bars", "Słupki EQ"),
            ("row_music_equalizer_gap", "Bar gap", "Odstęp słupków"),
            ("row_music_equalizer_mirror", "Mirror mode", "Tryb lustrzany"),
            ("row_weather_city", "City", "Miasto"),
            ("row_weather_source", "Weather binding", "Dane pogody"),
            ("row_content_text", "Text", "Tekst"),
            ("row_content_label", "Label", "Etykieta"),
            ("row_content_source", "Data source", "Źródło"),
            ("row_content_format", "Value format", "Format wartości"),
            ("row_content_stat_display", "Display mode", "Tryb wyświetlania"),
            ("row_content_stat_range", "Range", "Zakres"),
            ("row_content_stat_show_value", "Show value text", "Tekst wartości"),
            ("row_appearance_font", "Font", "Czcionka"),
            ("row_appearance_font_style", "Style", "Styl"),
            ("row_appearance_align", "Alignment", "Wyrównanie"),
            ("row_appearance_color", "Color", "Kolor"),
            ("row_appearance_label_color", "Label color", "Kolor etykiety"),
            ("row_appearance_value_color", "Value color", "Kolor wartości"),
            ("row_appearance_track_color", "Track / chart background", "Kolor tła gauge / paska / wykresu"),
            ("row_appearance_fill_color", "Line / fill color", "Kolor linii / wypełnienia / wartości"),
            ("row_sparkline_points", "History points", "Punkty historii"),
            ("row_sparkline_fill_opacity", "Fill opacity", "Przezrocz. wypełnienia"),
            ("row_sparkline_show_points", "Endpoint marker", "Punkt końcowy"),
            ("row_appearance_stroke_width", "Line / gauge stroke (0 = auto)", "Grubość linii / gauge (0 = auto)"),
            ("row_gauge_ring", "Ring diameter", "Średnica pierścienia"),
            ("row_gauge_value_layout", "Value layout", "Układ wartości"),
            ("row_gauge_preset", "Color preset", "Preset kolorów"),
            ("row_gauge_grad_low", "Arc: low color", "Łuk: kolor niski"),
            ("row_gauge_grad_mid", "Arc: mid color", "Łuk: środek"),
            ("row_gauge_grad_high", "Arc: high color", "Łuk: wysoki"),
            ("row_gauge_smooth", "Needle smoothing", "Wygładzanie igły"),
            ("row_gauge_match_value", "Value color matches arc", "Kolor wartości jak łuk"),
            ("row_gauge_inner_alpha", "Inner transparency", "Przezrocz. środka"),
            ("row_panel_fill", "Panel style", "Styl panelu"),
            ("row_panel_opacity", "Panel opacity", "Przezroczystość panelu"),
            ("row_panel_radius", "Corner radius", "Promień narożników"),
            ("row_geometry_x", "X", "X"),
            ("row_geometry_y", "Y", "Y"),
            ("row_geometry_w", "Width", "Szerokość"),
            ("row_geometry_h", "Height", "Wysokość"),
            ("row_geometry_group_bounds", "Group", "Grupa"),
            ("row_geometry_presets", "Presets", "Presety"),
            ("row_motion_enabled", "Motion", "Ruch"),
            ("row_motion_range", "Frame range", "Zakres klatek"),
            ("row_motion_target_x", "End X", "Koniec X"),
            ("row_motion_target_y", "End Y", "Koniec Y"),
            ("row_motion_target_opacity", "End opacity", "Końcowa przezr."),
            ("row_motion_actions", "Motion actions", "Akcje ruchu"),
            ("row_image_path", "Image file", "Plik obrazu"),
            ("row_image_fit", "Transform", "Transformacja"),
            ("row_image_opacity", "Opacity", "Przezroczystość"),
            ("row_image_rotation", "Rotation", "Obrót"),
            ("row_image_import", "Import", "Import"),
            ("row_image_actions", "Quick actions", "Szybkie akcje"),
            ("row_image_preview", "Preview", "Podgląd"),
            ("row_media_bg_mode", "Background mode", "Tryb tła"),
            ("row_media_bg_path", "File / import", "Plik / import"),
            ("row_media_bg_fit", "Fit", "Dopasowanie"),
            ("row_media_bg_opacity", "Opacity", "Przezroczystość"),
            ("row_media_bg_rotation", "Rotation", "Obrót"),
            ("row_media_bg_colors", "Colors", "Kolory"),
            ("row_media_bg_presets", "Presets", "Presety"),
            ("row_media_bg_texture", "Texture", "Tekstura"),
            ("row_media_bg_preview", "Background preview", "Podgląd tła"),
            ("row_animation_overview", "Animation", "Animacja"),
        ):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.setText(tr(en, pl))
        for attr, en, pl in (
            ("panel_fill_compact_label", "Fill", "Kolor"),
            ("panel_opacity_compact_label", "Opacity", "Przezr."),
            ("panel_radius_compact_label", "Radius", "Promień"),
            ("image_fit_compact_label", "Fit", "Dopas."),
            ("image_opacity_compact_label", "Opacity", "Przezr."),
            ("image_rotation_compact_label", "Rotation", "Obrót"),
            ("weather_source_compact_label", "Source", "Źródło"),
            ("weather_format_compact_label", "Format", "Format"),
        ):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.setText(tr(en, pl))
        if hasattr(self, "inspector_animation_details_hint"):
            self.inspector_animation_details_hint.setText(
                tr(
                    "Use Animation Studio for the timeline, multi-frame timing, and a large preview. "
                    "After editing frames, switch to Theme Designer to place stats and widgets like on a static theme.",
                    "W Studio animacji masz oś czasu, zbiorcze czasy i duży podgląd. "
                    "Po edycji klatek wróć do Projektanta, by ułożyć statystyki i widgety jak na statycznym motywie.",
                )
            )
        if hasattr(self, "open_animation_studio_btn"):
            self.open_animation_studio_btn.setText(tr("Open Animation Studio", "Otwórz Studio animacji"))
        if hasattr(self, "motion_enabled_chk"):
            self.motion_enabled_chk.setText(tr("Animate element", "Animuj element"))
        if hasattr(self, "motion_capture_current_btn"):
            self.motion_capture_current_btn.setText(tr("Set end from current", "Ustaw koniec z bieżącej"))
        if hasattr(self, "motion_remove_btn"):
            self.motion_remove_btn.setText(tr("Remove motion", "Usuń ruch"))
        if hasattr(self, "designer_path_browse_btn"):
            self.designer_path_browse_btn.setText(tr("Browse…", "Wybierz…"))
        if hasattr(self, "designer_path_prepare_btn"):
            self.designer_path_prepare_btn.setText(tr("Prepare", "Przygotuj"))
        if hasattr(self, "designer_image_fullscreen_btn"):
            self.designer_image_fullscreen_btn.setText(tr("Fullscreen", "Ustaw fullscreen"))
        if hasattr(self, "designer_image_left_half_btn"):
            self.designer_image_left_half_btn.setText(tr("Left half", "Lewa połowa"))
        if hasattr(self, "designer_image_right_half_btn"):
            self.designer_image_right_half_btn.setText(tr("Right half", "Prawa połowa"))
        if hasattr(self, "designer_image_reset_btn"):
            self.designer_image_reset_btn.setText(tr("Reset frame", "Reset kadru"))
        if hasattr(self, "designer_import_image_btn"):
            self.designer_import_image_btn.setText(tr("Import image into theme", "Importuj obraz do motywu"))
        if hasattr(self, "designer_image_preview_label"):
            pm = self.designer_image_preview_label.pixmap()
            if pm is None or pm.isNull():
                self.designer_image_preview_label.setText(tr("Image preview", "Podgląd obrazu"))
        ph_g = tr("[R,G,B,A] — optional, empty = from preset", "[R,G,B,A] — opcjonalnie, puste = z presetu")
        ph_m = tr("[R,G,B,A] — optional", "[R,G,B,A] — opcjonalnie")
        if hasattr(self, "designer_gauge_low_edit"):
            self.designer_gauge_low_edit.setPlaceholderText(ph_g)
        if hasattr(self, "designer_gauge_mid_edit"):
            self.designer_gauge_mid_edit.setPlaceholderText(ph_m)
        if hasattr(self, "designer_gauge_high_edit"):
            self.designer_gauge_high_edit.setPlaceholderText(ph_m)
        if hasattr(self, "preview_tools_label"):
            self.preview_tools_label.setText(tr("Mouse:", "Mysz:"))
        return self._tr("Background preview", "Podgląd tła")

    def _empty_image_preview_caption(self) -> str:
        return self._tr("Image preview", "Podgląd obrazu")

    def _refresh_extended_ui_labels(self) -> None:
        tr = self._tr
        self._refresh_inspector_form_labels(tr)
        if hasattr(self, "endpoint_box"):
            self.endpoint_box.setTitle(tr("Backend", "Backend"))
        if hasattr(self, "control_box"):
            self.control_box.setTitle(tr("Device control", "Kontrola urządzenia"))
        if hasattr(self, "runtime_hero_text_label"):
            self.runtime_hero_text_label.setText(
                tr(
                    "Control the panel like a native Plasma app: start the runtime, push single frames "
                    "and manage themes from clear cards instead of raw fields.",
                    "Steruj panelem jak natywną aplikacją Plasma: uruchom runtime, wyślij pojedyncze klatki "
                    "i zarządzaj motywami z czytelnych kart zamiast surowych pól.",
                )
            )
        if hasattr(self, "runtime_sections_tabs"):
            self.runtime_sections_tabs.setTabText(0, tr("Device", "Urządzenie"))
            self.runtime_sections_tabs.setTabText(1, tr("Image", "Obraz"))
            self.runtime_sections_tabs.setTabText(2, tr("Themes", "Motywy"))
        if hasattr(self, "work_box"):
            self.work_box.setTitle(tr("Single image", "Pojedynczy obraz"))
        if hasattr(self, "cfg_box"):
            self.cfg_box.setTitle(tr("Playback settings", "Ustawienia odtwarzania"))
        if hasattr(self, "status_box"):
            self.status_box.setTitle(tr("System monitor", "Monitor systemu"))
        if hasattr(self, "runtime_legacy_theme_box"):
            self.runtime_legacy_theme_box.setTitle(tr("Theme library", "Biblioteka motywów"))
        if hasattr(self, "runtime_theme_cards_box"):
            self.runtime_theme_cards_box.setTitle(tr("Theme cards", "Karty motywów"))
        if hasattr(self, "system_intro_text_label"):
            self.system_intro_text_label.setText(
                tr(
                    "This tab shows backend status, device state and basic host metrics. "
                    "Quick actions use the same live API endpoints as before.",
                    "Ta zakładka pokazuje status backendu, stan urządzenia i podstawowe metryki hosta. "
                    "Szybkie akcje korzystają z tych samych endpointów API co wcześniej.",
                )
            )
        if hasattr(self, "backend_status_box"):
            self.backend_status_box.setTitle(tr("Backend status", "Status backendu"))
        if hasattr(self, "system_api_status_title"):
            self.system_api_status_title.setText(tr("API Server", "Serwer API"))
        if hasattr(self, "system_ws_status_title"):
            self.system_ws_status_title.setText(tr("WebSocket", "WebSocket"))
        if hasattr(self, "system_lcd_status_title"):
            self.system_lcd_status_title.setText(tr("LCD Daemon", "Demon LCD"))
        if hasattr(self, "system_queue_status_title"):
            self.system_queue_status_title.setText(tr("Queue Worker", "Worker kolejki"))
        if hasattr(self, "system_theme_engine_title"):
            self.system_theme_engine_title.setText(tr("Theme Engine", "Silnik motywów"))
        if hasattr(self, "system_backup_title"):
            self.system_backup_title.setText(tr("Auto Backup", "Auto backup"))
        if hasattr(self, "system_info_box"):
            self.system_info_box.setTitle(tr("System information", "Informacje o systemie"))
        if hasattr(self, "resources_box"):
            self.resources_box.setTitle(tr("System resources", "Zasoby systemu"))
        if hasattr(self, "system_cpu_title"):
            self.system_cpu_title.setText(tr("CPU", "CPU"))
        if hasattr(self, "system_mem_title"):
            self.system_mem_title.setText(tr("RAM", "RAM"))
        if hasattr(self, "system_disk_title"):
            self.system_disk_title.setText(tr("DISK", "DYSK"))
        if hasattr(self, "system_temp_title"):
            self.system_temp_title.setText(tr("TEMP", "TEMP"))
        if hasattr(self, "runtime_dashboard_device_box"):
            self.runtime_dashboard_device_box.setTitle(tr("Network & device", "Sieć i urządzenie"))
        if hasattr(self, "system_events_box"):
            self.system_events_box.setTitle(tr("System events", "Zdarzenia systemowe"))
        if hasattr(self, "system_events_header_labels") and len(getattr(self, "system_events_header_labels", [])) == 4:
            hdr = self.system_events_header_labels
            hdr[0].setText(tr("Time", "Czas"))
            hdr[1].setText(tr("Level", "Poziom"))
            hdr[2].setText(tr("Source", "Źródło"))
            hdr[3].setText(tr("Message", "Komunikat"))
        if hasattr(self, "system_quick_actions_box"):
            self.system_quick_actions_box.setTitle(tr("Quick actions", "Szybkie akcje"))
        if hasattr(self, "system_restart_backend_btn"):
            self.system_restart_backend_btn.setText(tr("Restart backend", "Restart backendu"))
        if hasattr(self, "system_restart_service_btn"):
            self.system_restart_service_btn.setText(tr("Restart service", "Restart usługi"))
        if hasattr(self, "system_refresh_status_btn"):
            self.system_refresh_status_btn.setText(tr("Refresh status", "Odśwież status"))
        if hasattr(self, "system_export_logs_btn"):
            self.system_export_logs_btn.setText(tr("Export logs", "Eksport logów"))
        if hasattr(self, "system_diagnostic_btn"):
            self.system_diagnostic_btn.setText(tr("Diagnostics", "Diagnostyka"))
        if hasattr(self, "config_intro_text_label"):
            self.config_intro_text_label.setText(
                tr(
                    "Configuration centralizes interface settings, LCD preferences and integrations in one place. "
                    "App theme management now lives here instead of the top control bar.",
                    "Konfiguracja grupuje ustawienia interfejsu, preferencje LCD i integracje w jednym miejscu. "
                    "Motyw aplikacji jest ustawiany tutaj zamiast na górnym pasku.",
                )
            )
        if hasattr(self, "designer_elements_box"):
            self.designer_elements_box.setTitle("")
        if hasattr(self, "designer_elements_title_label"):
            self.designer_elements_title_label.setText(tr("Layers & components", "Warstwy i komponenty"))
        if hasattr(self, "quick_add_group_basics"):
            self.quick_add_group_basics.setTitle(tr("Basics", "Podstawowe"))
        if hasattr(self, "quick_add_group_music"):
            self.quick_add_group_music.setTitle(tr("Music & audio", "Muzyka i audio"))
        if hasattr(self, "quick_add_group_widgets"):
            self.quick_add_group_widgets.setTitle(tr("Widgets", "Widgety"))
        if hasattr(self, "designer_component_search"):
            self.designer_component_search.setPlaceholderText(tr("Search layers or text…", "Szukaj warstwy lub tekstu…"))
        if hasattr(self, "designer_kind_combo"):
            kind_labels = [
                (tr("Texts", "Teksty"), "texts"),
                (tr("Stats", "Statystyki"), "stats"),
                (tr("Images", "Obrazy"), "images"),
                (tr("Panels", "Panele"), "panels"),
                (tr("Widgets", "Widgety"), "widgets"),
            ]
            current_kind = str(self.designer_kind_combo.currentData() or "texts")
            self.designer_kind_combo.blockSignals(True)
            self.designer_kind_combo.clear()
            for text, data in kind_labels:
                self.designer_kind_combo.addItem(text, data)
            idx = self.designer_kind_combo.findData(current_kind)
            self.designer_kind_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.designer_kind_combo.blockSignals(False)
        if hasattr(self, "designer_domain_combo"):
            labels = [
                (tr("All", "Wszystko"), "all"),
                (tr("System", "System"), "system"),
                (tr("Music", "Muzyka"), "music"),
                (tr("Weather", "Pogoda"), "weather"),
            ]
            current = str(self.designer_domain_combo.currentData() or "all")
            self.designer_domain_combo.blockSignals(True)
            self.designer_domain_combo.clear()
            for text, data in labels:
                self.designer_domain_combo.addItem(text, data)
            idx = self.designer_domain_combo.findData(current)
            self.designer_domain_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.designer_domain_combo.blockSignals(False)
        if hasattr(self, "designer_quick_add_toggle_btn"):
            self.designer_quick_add_toggle_btn.setText("+")
            self.designer_quick_add_toggle_btn.setToolTip(tr("Add component", "Dodaj komponent"))
        if hasattr(self, "designer_source_combo"):
            current_source = str(self.designer_source_combo.currentData() or "").strip()
            self._populate_designer_source_combo(current_source)
        if hasattr(self, "quick_add_text_btn"):
            self.quick_add_text_btn.setText(tr("Text", "Tekst"))
        if hasattr(self, "quick_add_stat_btn"):
            self.quick_add_stat_btn.setText(tr("Stat", "Statystyka"))
        if hasattr(self, "quick_add_image_btn"):
            self.quick_add_image_btn.setText(tr("Image", "Obraz"))
        if hasattr(self, "quick_add_panel_btn"):
            self.quick_add_panel_btn.setText(tr("Panel", "Panel"))
        if hasattr(self, "quick_add_progress_btn"):
            self.quick_add_progress_btn.setText(tr("Progress", "Postęp"))
        if hasattr(self, "quick_add_sparkline_btn"):
            self.quick_add_sparkline_btn.setText(tr("Sparkline", "Wykres mini"))
        if hasattr(self, "quick_add_now_playing_btn"):
            self.quick_add_now_playing_btn.setText(tr("Now Playing", "Now Playing"))
        if hasattr(self, "quick_add_now_playing_hero_btn"):
            self.quick_add_now_playing_hero_btn.setText(tr("Now Playing Hero", "Now Playing Hero"))
        if hasattr(self, "quick_add_now_playing_mini_btn"):
            self.quick_add_now_playing_mini_btn.setText(tr("Now Playing Mini", "Now Playing Mini"))
        if hasattr(self, "quick_add_volume_btn"):
            self.quick_add_volume_btn.setText(tr("Volume", "Głośność"))
        if hasattr(self, "quick_add_equalizer_btn"):
            self.quick_add_equalizer_btn.setText(tr("Graphic EQ", "Korektor"))
        if hasattr(self, "quick_add_analog_clock_btn"):
            self.quick_add_analog_clock_btn.setText(tr("Analog Clock", "Zegar analogowy"))
        if hasattr(self, "quick_add_clock_modern_btn"):
            self.quick_add_clock_modern_btn.setText(tr("Clock Modern", "Zegar modern"))
        if hasattr(self, "quick_add_clock_nordic_btn"):
            self.quick_add_clock_nordic_btn.setText(tr("Clock Nordic", "Zegar nordic"))
        if hasattr(self, "quick_add_gauge_set_btn"):
            self.quick_add_gauge_set_btn.setText(tr("Gauge Set", "Zestaw gauge"))
        if hasattr(self, "quick_add_gauge_cyber_btn"):
            self.quick_add_gauge_cyber_btn.setText(tr("Gauge Cyber", "Gauge cyber"))
        if hasattr(self, "quick_add_gauge_thermal_btn"):
            self.quick_add_gauge_thermal_btn.setText(tr("Gauge Thermal", "Gauge temp"))
        if hasattr(self, "designer_move_box"):
            self.designer_move_box.setTitle(tr("Nudge selection", "Przesuwanie zaznaczenia"))
        if hasattr(self, "designer_nudge_step_label"):
            self.designer_nudge_step_label.setText(tr("Step:", "Krok:"))
        if hasattr(self, "designer_nudge_up_btn"):
            self.designer_nudge_up_btn.setToolTip(tr("Nudge up", "Przesuń w górę"))
        if hasattr(self, "designer_nudge_left_btn"):
            self.designer_nudge_left_btn.setToolTip(tr("Nudge left", "Przesuń w lewo"))
        if hasattr(self, "designer_nudge_right_btn"):
            self.designer_nudge_right_btn.setToolTip(tr("Nudge right", "Przesuń w prawo"))
        if hasattr(self, "designer_nudge_down_btn"):
            self.designer_nudge_down_btn.setToolTip(tr("Nudge down", "Przesuń w dół"))
        if hasattr(self, "designer_layer_actions_label"):
            self.designer_layer_actions_label.setText(tr("Layer actions", "Akcje warstw"))
        if hasattr(self, "designer_remove_btn"):
            self.designer_remove_btn.setText(tr("🗑 Delete", "🗑 Usuń"))
        if hasattr(self, "props_box"):
            self.props_box.setTitle(tr("Element properties", "Właściwości elementu"))
        if hasattr(self, "inspector_selection_summary"):
            self.inspector_selection_summary.setText(
                tr("Select an element to edit its properties.", "Wybierz element, aby edytować jego właściwości.")
            )
        if hasattr(self, "inspector_tabs"):
            self.inspector_tabs.setTabText(0, tr("General", "Ogólne"))
            self.inspector_tabs.setTabText(1, tr("Content", "Treść"))
            self.inspector_tabs.setTabText(2, tr("Music", "Muzyka"))
            self.inspector_tabs.setTabText(3, tr("Weather", "Pogoda"))
            self.inspector_tabs.setTabText(4, tr("Style", "Styl"))
            self.inspector_tabs.setTabText(5, tr("Gauge", "Gauge"))
            self.inspector_tabs.setTabText(6, tr("Position", "Pozycja"))
            self.inspector_tabs.setTabText(7, tr("Image", "Obraz"))
            self.inspector_tabs.setTabText(8, tr("Background", "Tło"))
            self.inspector_tabs.setTabText(9, tr("Animation", "Animacja"))
        if hasattr(self, "music_tool_now_playing_btn"):
            self.music_tool_now_playing_btn.setText(tr("Now Playing", "Now Playing"))
        if hasattr(self, "music_tool_hero_btn"):
            self.music_tool_hero_btn.setText(tr("Hero", "Hero"))
        if hasattr(self, "music_tool_mini_btn"):
            self.music_tool_mini_btn.setText(tr("Mini", "Mini"))
        if hasattr(self, "music_tool_volume_btn"):
            self.music_tool_volume_btn.setText(tr("Volume", "Głośność"))
        if hasattr(self, "music_tool_eq_btn"):
            self.music_tool_eq_btn.setText(tr("Graphic EQ", "Korektor"))
        if hasattr(self, "weather_tool_current_btn"):
            self.weather_tool_current_btn.setText(tr("Weather Current", "Pogoda teraz"))
        if hasattr(self, "weather_tool_wide_btn"):
            self.weather_tool_wide_btn.setText(tr("Wide", "Szeroki"))
        if hasattr(self, "weather_tool_hero_btn"):
            self.weather_tool_hero_btn.setText(tr("Hero", "Hero"))
        if hasattr(self, "weather_tool_forecast_btn"):
            self.weather_tool_forecast_btn.setText(tr("Weather 7D", "Prognoza 7 dni"))
        if hasattr(self, "weather_designer_search_btn"):
            self.weather_designer_search_btn.setText(tr("Search", "Szukaj"))
        if hasattr(self, "weather_designer_apply_btn"):
            self.weather_designer_apply_btn.setText(tr("Apply", "Zastosuj"))
        if hasattr(self, "weather_designer_refresh_btn"):
            self.weather_designer_refresh_btn.setText(tr("Refresh", "Odśwież"))
        if hasattr(self, "geometry_preset_top_btn"):
            self.geometry_preset_top_btn.setText(tr("Top", "Góra"))
        if hasattr(self, "geometry_preset_bottom_btn"):
            self.geometry_preset_bottom_btn.setText(tr("Bottom", "Dół"))
        if hasattr(self, "geometry_preset_left_btn"):
            self.geometry_preset_left_btn.setText(tr("Left", "Lewo"))
        if hasattr(self, "geometry_preset_right_btn"):
            self.geometry_preset_right_btn.setText(tr("Right", "Prawo"))
        if hasattr(self, "geometry_preset_center_btn"):
            self.geometry_preset_center_btn.setText(tr("Center", "Środek"))
        if hasattr(self, "designer_layer_down_btn"):
            self.designer_layer_down_btn.setText(tr("-Z", "-Z"))
            self.designer_layer_down_btn.setToolTip(tr("Lower selected layer", "Przesuń warstwę niżej"))
        if hasattr(self, "designer_layer_up_btn"):
            self.designer_layer_up_btn.setText(tr("+Z", "+Z"))
            self.designer_layer_up_btn.setToolTip(tr("Raise selected layer", "Przesuń warstwę wyżej"))
        if hasattr(self, "designer_layer_back_btn"):
            self.designer_layer_back_btn.setText(tr("Back", "Tył"))
            self.designer_layer_back_btn.setToolTip(tr("Send selected layer to back", "Wyślij warstwę na tył"))
        if hasattr(self, "designer_layer_front_btn"):
            self.designer_layer_front_btn.setText(tr("Front", "Przód"))
            self.designer_layer_front_btn.setToolTip(tr("Bring selected layer to front", "Przenieś warstwę na przód"))
        if hasattr(self, "designer_visibility_toggle_btn"):
            self.designer_visibility_toggle_btn.setText(tr("Show", "Pokaż"))
            self.designer_visibility_toggle_btn.setToolTip(tr("Show or hide selected layers", "Pokaż lub ukryj zaznaczone warstwy"))
        if hasattr(self, "designer_lock_toggle_btn"):
            self.designer_lock_toggle_btn.setText(tr("Lock", "Blokuj"))
            self.designer_lock_toggle_btn.setToolTip(tr("Lock or unlock selected layers", "Zablokuj lub odblokuj zaznaczone warstwy"))
        if hasattr(self, "cfg_weather_refresh_now_btn"):
            self.cfg_weather_refresh_now_btn.setText(tr("Refresh weather", "Odśwież pogodę"))
        if hasattr(self, "inspector_weather_hint"):
            self.inspector_weather_hint.setText(
                tr(
                    "Weather components use the city and refresh interval from Configuration > Weather. Use the buttons above to insert ready-made weather layouts.",
                    "Komponenty pogody używają miasta i odświeżania z Konfiguracja > Pogoda. Przyciski powyżej dodają gotowe układy pogody.",
                )
            )
        if hasattr(self, "weather_box"):
            self.weather_box.setTitle(tr("Weather", "Pogoda"))
        if hasattr(self, "cfg_weather_city_search_edit"):
            self.cfg_weather_city_search_edit.setPlaceholderText(tr("Search city, e.g. Warsaw", "Szukaj miasta, np. Warszawa"))
        if hasattr(self, "cfg_weather_search_btn") and self.cfg_weather_search_btn.isEnabled():
            self.cfg_weather_search_btn.setText(tr("Search", "Szukaj"))
        if hasattr(self, "cfg_weather_apply_btn"):
            self.cfg_weather_apply_btn.setText(tr("Apply weather", "Zastosuj pogodę"))
        if hasattr(self, "log_panel_box"):
            self.log_panel_box.setTitle(tr("API & application logs", "Logi API i aplikacji"))
        if hasattr(self, "log_filter_edit"):
            self.log_filter_edit.setPlaceholderText(tr("Filter logs…", "Filtr logów…"))
        if hasattr(self, "log_only_errors_chk"):
            self.log_only_errors_chk.setText(tr("Errors only", "Tylko błędy"))
        if hasattr(self, "log_hide_status_chk"):
            self.log_hide_status_chk.setText(tr("Hide status lines", "Ukryj status"))
        if hasattr(self, "log_copy_btn"):
            self.log_copy_btn.setText(tr("Copy view", "Kopiuj widok"))
        if hasattr(self, "log_copy_selection_btn"):
            self.log_copy_selection_btn.setText(tr("Copy selection", "Kopiuj zaznaczenie"))
        if hasattr(self, "log_clear_btn"):
            self.log_clear_btn.setText(tr("Clear", "Wyczyść"))
        if hasattr(self, "log_search_label"):
            self.log_search_label.setText(tr("Search:", "Szukaj:"))
        if hasattr(self, "preview_guides_chk"):
            self.preview_guides_chk.setText(tr("Show layer bounds", "Pokaż ramki warstw"))
        if hasattr(self, "theme_doc_manual_json_label"):
            self.theme_doc_manual_json_label.setText(tr("Manual JSON:", "JSON ręczny:"))
        if hasattr(self, "theme_doc_open_external_btn"):
            self.theme_doc_open_external_btn.setText(tr("Open JSON file…", "Otwórz plik JSON…"))
            self.theme_doc_open_external_btn.setToolTip(
                tr(
                    "Writes the theme with an English field guide and opens it in your default app. "
                    "After saving in the editor, use Load theme. // and /* */ comments are ignored when loading.",
                    "Zapisuje motyw z angielskim opisem pól i otwiera go w domyślnej aplikacji. "
                    "Po zapisie w edytorze użyj „Wczytaj motyw”. Komentarze // oraz /* */ są pomijane przy wczytywaniu.",
                )
            )
        if hasattr(self, "theme_doc_insert_guide_btn"):
            self.theme_doc_insert_guide_btn.setText(tr("Insert field guide", "Wstaw opis pól"))
            self.theme_doc_insert_guide_btn.setToolTip(
                tr(
                    "Prepends the guide to the JSON tab (persist with Save / Load flow as usual).",
                    "Wstawia opis na początku zakładki JSON (zapis jak przy zwykłym Zapisz / Wczytaj).",
                )
            )
        if hasattr(self, "designer_open_json_btn"):
            self.designer_open_json_btn.setText(tr("Open JSON…", "Otwórz JSON…"))
            self.designer_open_json_btn.setToolTip(
                tr(
                    "Save the theme file with a field guide and open it externally, then use Load theme.",
                    "Zapisuje plik motywu z opisem pól i otwiera go na zewnątrz, potem użyj „Wczytaj motyw”.",
                )
            )
        if hasattr(self, "designer_save_as_btn"):
            self.designer_save_as_btn.setText(tr("Save As…", "Zapisz jako…"))
            self.designer_save_as_btn.setToolTip(
                tr("Save the current theme as a new editable file.", "Zapisz bieżący motyw jako nowy plik do edycji.")
            )
        if hasattr(self, "theme_doc_save_as_btn"):
            self.theme_doc_save_as_btn.setText(tr("Save As", "Zapisz jako"))
        if hasattr(self, "animation_studio_open_json_btn"):
            self.animation_studio_open_json_btn.setText(tr("Open JSON…", "Otwórz JSON…"))
            self.animation_studio_open_json_btn.setToolTip(
                tr(
                    "Same theme file; background animation is under effects.animation.",
                    "Ten sam plik motywu; animacja tła jest w effects.animation.",
                )
            )
        if hasattr(self, "animation_studio_save_as_btn"):
            self.animation_studio_save_as_btn.setText(tr("Save As…", "Zapisz jako…"))
            self.animation_studio_save_as_btn.setToolTip(
                tr(
                    "Create a new theme file from the current animation edit.",
                    "Utwórz nowy plik motywu z bieżącej edycji animacji.",
                )
            )
        if hasattr(self, "animation_studio_back_btn"):
            self.animation_studio_back_btn.setText(tr("← Theme Designer", "← Projektant motywów"))
        if hasattr(self, "animation_studio_quick_export_btn"):
            self.animation_studio_quick_export_btn.setText(tr("Export", "Eksportuj"))
            self.animation_studio_quick_export_btn.setToolTip(
                tr("Export the full animation sequence to ZIP.", "Eksportuj całą sekwencję animacji do ZIP.")
            )
        if hasattr(self, "animation_studio_title_label"):
            self.animation_studio_title_label.setText(tr("Animation Studio", "Studio animacji"))
        if hasattr(self, "animation_studio_subtitle_label"):
            self.animation_studio_subtitle_label.setText(
                tr(
                    "Create and manage frame-based animations for Trofeo LCD.",
                    "Twórz i zarządzaj animacjami klatkowymi dla Trofeo LCD.",
                )
            )
        if hasattr(self, "animation_worker_status_label"):
            self._refresh_animation_worker_status()
        if hasattr(self, "animation_cancel_worker_btn"):
            self.animation_cancel_worker_btn.setText(tr("Cancel task", "Anuluj zadanie"))
            self.animation_cancel_worker_btn.setToolTip(
                tr(
                    "Request cancellation for the current animation import or export.",
                    "Poproś o przerwanie bieżącego importu lub eksportu animacji.",
                )
            )
        if hasattr(self, "animation_preview_title_label"):
            self.animation_preview_title_label.setText(tr("Preview", "Podgląd"))
        if hasattr(self, "animation_auto_composite_chk"):
            self.animation_auto_composite_chk.setText(tr("Auto composite", "Auto kompozycja"))
            self.animation_auto_composite_chk.setToolTip(
                tr(
                    "Render the full theme preview whenever the selected frame changes.",
                    "Renderuj pełny podgląd motywu przy każdej zmianie wybranej klatki.",
                )
            )
        if hasattr(self, "animation_refresh_composite_btn"):
            self.animation_refresh_composite_btn.setText(tr("Refresh composite", "Odśwież kompozycję"))
            self.animation_refresh_composite_btn.setToolTip(
                tr("Render the full theme with the current animation frame.", "Wyrenderuj pełny motyw z bieżącą klatką animacji.")
            )
        if hasattr(self, "animation_onion_skin_chk"):
            self.animation_onion_skin_chk.setText(tr("Onion skin", "Onion skin"))
            self.animation_onion_skin_chk.setToolTip(
                tr(
                    "Overlay previous and next animation frames over the current frame.",
                    "Nałóż poprzednią i następną klatkę animacji na bieżącą klatkę.",
                )
            )
        if hasattr(self, "bg_animation_export_btn") and not getattr(self, "_animation_export_in_flight", False):
            self.bg_animation_export_btn.setText(tr("Export", "Eksportuj"))
            self.bg_animation_export_btn.setToolTip(
                tr(
                    "Render animation frames to a ZIP archive in a background worker.",
                    "Renderuj klatki animacji do archiwum ZIP w tle.",
                )
            )
            if hasattr(self, "animation_export_loop_btn"):
                self.animation_export_loop_btn.setText(tr("Export Loop", "Eksport pętli"))
                self.animation_export_loop_btn.setToolTip(
                    tr(
                        "Export only the active animation loop range to ZIP.",
                        "Eksportuj do ZIP tylko aktywny zakres pętli animacji.",
                    )
                )
            if hasattr(self, "animation_export_selection_btn"):
                self.animation_export_selection_btn.setText(tr("Export Sel", "Eksport zazn."))
                self.animation_export_selection_btn.setToolTip(
                    tr(
                        "Export only selected animation frames to ZIP.",
                        "Eksportuj do ZIP tylko zaznaczone klatki animacji.",
                    )
                )
        if not getattr(self, "_animation_import_in_flight", False):
            if hasattr(self, "bg_animation_import_btn"):
                self.bg_animation_import_btn.setText(tr("Import", "Importuj"))
                self.bg_animation_import_btn.setToolTip(
                    tr(
                        "Replace the current sequence with selected frames or a TTCR container. Files are prepared in the background.",
                        "Zastąp bieżącą sekwencję wybranymi klatkami lub kontenerem TTCR. Pliki są przygotowywane w tle.",
                    )
                )
            if hasattr(self, "bg_animation_add_btn"):
                self.bg_animation_add_btn.setText(tr("Add", "Dodaj"))
                self.bg_animation_add_btn.setToolTip(
                    tr(
                        "Append selected frames to the current sequence. Files are prepared in the background.",
                        "Dopisz wybrane klatki do bieżącej sekwencji. Pliki są przygotowywane w tle.",
                    )
                )
        if hasattr(self, "bg_animation_duplicate_btn"):
            self.bg_animation_duplicate_btn.setText(tr("Duplicate asset", "Duplikuj asset"))
            self.bg_animation_duplicate_btn.setToolTip(
                tr("Create real copied frame files.", "Utwórz fizyczne kopie plików klatek.")
            )
        if hasattr(self, "bg_animation_hold_repeat_btn"):
            self.bg_animation_hold_repeat_btn.setText(tr("Hold ×N", "Hold ×N"))
            self.bg_animation_hold_repeat_btn.setToolTip(
                tr(
                    "Extend selected frame durations without copying files.",
                    "Wydłuż czas zaznaczonych klatek bez kopiowania plików.",
                )
            )
        if hasattr(self, "animation_bulk_apply_duration_btn"):
            self.animation_bulk_apply_duration_btn.setText(tr("Retime selection", "Ustaw czas zaznaczenia"))
            self.animation_bulk_apply_duration_btn.setToolTip(
                tr(
                    "Set the duration for selected frames only.",
                    "Ustaw czas tylko dla zaznaczonych klatek.",
                )
            )
        if hasattr(self, "animation_stabilize_btn") and not getattr(self, "_animation_stabilize_in_flight", False):
            self.animation_stabilize_btn.setText(tr("Stabilize", "Stabilizuj"))
            self.animation_stabilize_btn.setToolTip(
                tr(
                    "Align selected frames to the first selected frame using OpenCV ECC. If no range is selected, align the full sequence.",
                    "Wyrównaj zaznaczone klatki do pierwszej zaznaczonej przez OpenCV ECC. Bez zaznaczenia wyrównuje całą sekwencję.",
                )
            )
        combo = getattr(self, "animation_stabilize_mode_combo", None)
        if combo is not None:
            cur_data = combo.currentData()
            combo.blockSignals(True)
            labels = [
                tr("Safe Translation", "Safe Translation"),
                tr("Auto Safe", "Auto Safe"),
                tr("Affine", "Affine"),
                tr("Euclidean", "Euclidean"),
                tr("Translation", "Translation"),
            ]
            for idx, label in enumerate(labels):
                if idx < combo.count():
                    combo.setItemText(idx, label)
            match = combo.findData(cur_data)
            if match >= 0:
                combo.setCurrentIndex(match)
            combo.blockSignals(False)
            combo.setToolTip(
                tr(
                    "Stabilization model. Safe modes reject aggressive warps and avoid visible frame deformation.",
                    "Model stabilizacji. Tryby Safe odrzucają agresywne transformacje i unikają widocznej deformacji klatek.",
                )
            )
        if hasattr(self, "bg_animation_normalize_duration_btn"):
            self.bg_animation_normalize_duration_btn.setText(tr("Normalize", "Wyrównaj"))
            self.bg_animation_normalize_duration_btn.setToolTip(
                tr(
                    "Set all selected frames, or the whole sequence if nothing is selected, to this duration.",
                    "Ustaw ten czas dla zaznaczonych klatek albo całej sekwencji, gdy nic nie zaznaczono.",
                )
            )
        if hasattr(self, "bg_animation_reverse_btn"):
            self.bg_animation_reverse_btn.setText(tr("Reverse", "Odwróć"))
            self.bg_animation_reverse_btn.setToolTip(
                tr(
                    "Reverse selected frames, or the whole sequence if nothing is selected.",
                    "Odwróć zaznaczone klatki albo całą sekwencję, gdy nic nie zaznaczono.",
                )
            )
        if hasattr(self, "bg_animation_pingpong_btn"):
            self.bg_animation_pingpong_btn.setText(tr("Ping-pong", "Ping-pong"))
            self.bg_animation_pingpong_btn.setToolTip(
                tr(
                    "Append a mirrored tail using frame references, without copying files.",
                    "Dodaj lustrzany ogon z referencji klatek, bez kopiowania plików.",
                )
            )
        if hasattr(self, "animation_select_range_btn"):
            self.animation_select_range_btn.setText(tr("Range", "Zakres"))
            self.animation_select_range_btn.setToolTip(
                tr(
                    "Select every frame between the first and last selected frame. Shortcut: R.",
                    "Zaznacz wszystkie klatki między pierwszą i ostatnią zaznaczoną. Skrót: R.",
                )
            )
        if hasattr(self, "animation_invert_selection_btn"):
            self.animation_invert_selection_btn.setText(tr("Invert", "Odwróć zazn."))
            self.animation_invert_selection_btn.setToolTip(
                tr("Invert frame selection. Shortcut: Ctrl+I.", "Odwróć zaznaczenie klatek. Skrót: Ctrl+I.")
            )
        if hasattr(self, "animation_clear_selection_btn"):
            self.animation_clear_selection_btn.setText(tr("Clear Sel", "Wyczyść zazn."))
            self.animation_clear_selection_btn.setToolTip(
                tr("Clear frame selection. Shortcut: Esc.", "Wyczyść zaznaczenie klatek. Skrót: Esc.")
            )
        if hasattr(self, "animation_timeline_home_btn"):
            self.animation_timeline_home_btn.setText(tr("Start", "Start"))
            self.animation_timeline_home_btn.setToolTip(
                tr("Scroll timeline to the first frame. Shortcut: Home.", "Przewiń oś czasu do pierwszej klatki. Skrót: Home.")
            )
        if hasattr(self, "animation_timeline_end_btn"):
            self.animation_timeline_end_btn.setText(tr("End", "Koniec"))
            self.animation_timeline_end_btn.setToolTip(
                tr("Scroll timeline to the last frame. Shortcut: End.", "Przewiń oś czasu do ostatniej klatki. Skrót: End.")
            )
        if hasattr(self, "animation_loop_from_selection_btn"):
            self.animation_loop_from_selection_btn.setText(tr("Loop Sel", "Pętla z zazn."))
            self.animation_loop_from_selection_btn.setToolTip(
                tr(
                    "Set preview loop from selected frame range. Shortcut: Ctrl+R.",
                    "Ustaw pętlę podglądu z zaznaczonego zakresu. Skrót: Ctrl+R.",
                )
            )
        if hasattr(self, "animation_trim_selection_btn"):
            self.animation_trim_selection_btn.setText(tr("Trim Sel", "Przytnij zazn."))
            self.animation_trim_selection_btn.setToolTip(
                tr(
                    "Keep only selected frames in the sequence. Asset files are not deleted. Shortcut: Ctrl+T.",
                    "Zostaw w sekwencji tylko zaznaczone klatki. Pliki assetów nie są usuwane. Skrót: Ctrl+T.",
                )
            )
        if hasattr(self, "animation_timeline_label"):
            self.animation_timeline_label.setText(tr("Timeline", "Oś czasu"))
            self.animation_timeline_label.setToolTip(
                tr(
                    "Shortcuts: Space play/pause, I/O loop in/out, Ctrl+L clear loop, Delete remove, Ctrl+A select all, R range, Ctrl+I invert, Esc clear, Ctrl+R loop selection, Ctrl+T trim, +/- zoom.",
                    "Skróty: Spacja play/pause, I/O loop in/out, Ctrl+L czyść pętlę, Delete usuń, Ctrl+A zaznacz wszystko, R zakres, Ctrl+I odwróć, Esc wyczyść, Ctrl+R pętla z zazn., Ctrl+T przytnij, +/- zoom.",
                )
            )
        if hasattr(self, "animation_timeline_hint_label"):
            self.animation_timeline_hint_label.setText(
                tr(
                    "Click a frame to select it. Drag to select a range. Use Set In / Set Out to mark a loop.",
                    "Kliknij klatkę, aby ją wybrać. Przeciągnij, aby zaznaczyć zakres. Użyj In / Out do pętli.",
                )
            )
        if hasattr(self, "animation_loop_in_btn"):
            self.animation_loop_in_btn.setText(tr("Set In", "Ustaw In"))
            self.animation_loop_in_btn.setToolTip(
                tr("Set loop start to the current frame.", "Ustaw początek pętli na bieżącej klatce.")
            )
        if hasattr(self, "animation_loop_out_btn"):
            self.animation_loop_out_btn.setText(tr("Set Out", "Ustaw Out"))
            self.animation_loop_out_btn.setToolTip(
                tr("Set loop end to the current frame.", "Ustaw koniec pętli na bieżącej klatce.")
            )
        if hasattr(self, "animation_loop_clear_btn"):
            self.animation_loop_clear_btn.setText(tr("Clear Loop", "Wyczyść pętlę"))
            self.animation_loop_clear_btn.setToolTip(
                tr("Preview the full animation sequence again.", "Podglądaj ponownie całą sekwencję animacji.")
            )
        if hasattr(self, "bg_animation_repeat_all_btn"):
            self.bg_animation_repeat_all_btn.setText(tr("Duplicate sequence ×N", "Duplikuj sekwencję ×N"))
        if hasattr(self, "theme_doc_box"):
            self.theme_doc_box.setTitle(tr("Theme", "Motyw"))
        if hasattr(self, "theme_doc_path_caption"):
            self.theme_doc_path_caption.setText(tr("Theme file:", "Plik motywu:"))
        if hasattr(self, "theme_doc_sources_caption"):
            self.theme_doc_sources_caption.setText(tr("Declared stats:", "Źródła danych:"))
        if hasattr(self, "theme_doc_browse_btn"):
            self.theme_doc_browse_btn.setText(tr("Browse theme…", "Wybierz motyw…"))
        if hasattr(self, "theme_doc_use_selected_btn"):
            self.theme_doc_use_selected_btn.setText(tr("From active theme", "Z aktywnego motywu"))
        if hasattr(self, "theme_doc_load_btn"):
            self.theme_doc_load_btn.setText(tr("Load", "Wczytaj"))
        if hasattr(self, "theme_doc_save_btn"):
            self.theme_doc_save_btn.setText(tr("Save", "Zapisz"))
        if hasattr(self, "theme_doc_save_as_btn"):
            self.theme_doc_save_as_btn.setText(tr("Save As", "Zapisz jako"))
        if hasattr(self, "theme_doc_apply_btn"):
            self.theme_doc_apply_btn.setText(tr("Apply", "Zastosuj"))
        if hasattr(self, "theme_doc_stop_before_apply_chk"):
            self.theme_doc_stop_before_apply_chk.setText(tr("Stop runtime before apply", "Zatrzymaj runtime przed apply"))
        if hasattr(self, "theme_doc_resume_chk"):
            self.theme_doc_resume_chk.setText(tr("Resume loop after apply", "Wznów loop po apply"))
        if hasattr(self, "studio_toolbar_load_btn"):
            self.studio_toolbar_load_btn.setText(tr("Load theme", "Wczytaj motyw"))
        if hasattr(self, "studio_toolbar_save_btn"):
            self.studio_toolbar_save_btn.setText(tr("Save theme", "Zapisz motyw"))
        if hasattr(self, "studio_toolbar_preview_btn"):
            self.studio_toolbar_preview_btn.setText(tr("Preview", "Podgląd"))
        if hasattr(self, "studio_toolbar_apply_btn"):
            self.studio_toolbar_apply_btn.setText(tr("Apply theme", "Zastosuj motyw"))
        if hasattr(self, "studio_toolbar_reload_btn"):
            self.studio_toolbar_reload_btn.setText(tr("JSON → Designer", "JSON → Projektant"))
        if hasattr(self, "studio_toolbar_export_btn"):
            self.studio_toolbar_export_btn.setText(tr("Designer → JSON", "Projektant → JSON"))
        if hasattr(self, "studio_left_tabs"):
            self.studio_left_tabs.setTabText(0, tr("Designer", "Projektant"))
            self.studio_left_tabs.setTabText(1, tr("JSON", "JSON"))
        if hasattr(self, "designer_theme_gauge_bar_label"):
            self.designer_theme_gauge_bar_label.setText(
                tr("Default gauge preset (meta.gauge_style):", "Domyślny preset gauge (meta.gauge_style):")
            )
        if hasattr(self, "designer_reload_btn"):
            self.designer_reload_btn.setText(tr("Load theme", "Wczytaj motyw"))
        if hasattr(self, "designer_write_btn"):
            self.designer_write_btn.setText(tr("Save theme", "Zapisz motyw"))
        if hasattr(self, "designer_save_as_btn"):
            self.designer_save_as_btn.setText(tr("Save As", "Zapisz jako"))
        if hasattr(self, "designer_animation_mode_btn"):
            self.designer_animation_mode_btn.setText(tr("Animation", "Animacja"))
        if hasattr(self, "designer_assets_toggle_btn"):
            self.designer_assets_toggle_btn.setText(tr("Media", "Multimedia"))
        if hasattr(self, "designer_preview_btn"):
            self.designer_preview_btn.setText(tr("Preview", "Podgląd"))
        if hasattr(self, "designer_apply_btn"):
            self.designer_apply_btn.setText(tr("Apply theme", "Zastosuj motyw"))
        if hasattr(self, "bg_animation_enabled_chk"):
            self.bg_animation_enabled_chk.setText(tr("Animation enabled", "Animacja aktywna"))
        if hasattr(self, "bg_animation_use_bg_chk"):
            self.bg_animation_use_bg_chk.setText(tr("Use as background", "Użyj jako tła"))
        if hasattr(self, "animation_studio_fps_label"):
            self.animation_studio_fps_label.setText(tr("FPS", "FPS"))
        if hasattr(self, "animation_studio_frame_index_label"):
            self.animation_studio_frame_index_label.setText(tr("Frame", "Klatka"))
        if hasattr(self, "animation_studio_duration_label"):
            self.animation_studio_duration_label.setText(tr("Duration (ms)", "Czas (ms)"))
        if hasattr(self, "animation_studio_bulk_duration_label"):
            self.animation_studio_bulk_duration_label.setText(tr("Bulk duration (ms)", "Zbiorczy czas (ms)"))
        if hasattr(self, "animation_onion_skin_opacity_label"):
            self.animation_onion_skin_opacity_label.setText(tr("Opacity", "Przezrocz."))
        if hasattr(self, "animation_loop_close_seam_btn"):
            self.animation_loop_close_seam_btn.setText(tr("Close Seam", "Domknij pętlę"))
        combo = getattr(self, "animation_preview_scale_combo", None)
        if combo is not None and combo.count() >= 4:
            cur = combo.currentIndex()
            combo.blockSignals(True)
            combo.setItemText(0, tr("Fit width", "Dopasuj szerokość"))
            combo.setItemText(1, "100%")
            combo.setItemText(2, "150%")
            combo.setItemText(3, "200%")
            combo.setCurrentIndex(cur)
            combo.blockSignals(False)
        if hasattr(self, "animation_duplicate_repeat_spin"):
            self.animation_duplicate_repeat_spin.setToolTip(
                tr(
                    "Duplicate the selected frames this many times (copies files).",
                    "Tyle razy zduplikuj zaznaczone klatki (kopiuje pliki).",
                )
            )
        if hasattr(self, "designer_theme_gauge_style_combo") and self.designer_theme_gauge_style_combo.count() > 0:
            self.designer_theme_gauge_style_combo.setItemText(
                0,
                tr("(default from theme name)", "(domyślny z nazwy motywu)"),
            )
        if hasattr(self, "bg_animation_play_btn"):
            self._update_animation_preview_timer()
        self._populate_designer_quick_add_menu()
        self._update_image_tools_availability()
        # Avoid calling _apply_designer_aux_visibility here: _refresh_localized_texts already runs
        # _apply_sidebar_mode → _apply_responsive_layout_metrics → _apply_designer_aux_visibility.

    def _refresh_localized_texts(self) -> None:
        if hasattr(self, "brand_sub"):
            self.brand_sub.setText("TROFEO LCD")
        if hasattr(self, "sidebar_footer_note"):
            self.sidebar_footer_note.setText("Open Trofeo LCD\nLinux Open Driver")
        if hasattr(self, "chrome_box"):
            self.chrome_box.setTitle(self._tr("Control", "Sterowanie"))
        if hasattr(self, "shell_title_sub"):
            self.shell_title_sub.setText(self._tr("LCD control and themes.", "Sterowanie LCD i motywami."))
        if hasattr(self, "header_mode_label"):
            self.header_mode_label.setText(self._tr("Mode", "Tryb"))
        if hasattr(self, "header_scale_label"):
            self.header_scale_label.setText(self._tr("Scale", "Skala"))
        if hasattr(self, "header_conn_label"):
            self.header_conn_label.setText(self._tr("Connection", "Połączenie"))
        if hasattr(self, "header_device_label"):
            self.header_device_label.setText(self._tr("Device", "Urządzenie"))
        if hasattr(self, "header_language_label"):
            self.header_language_label.setText(self._tr("Language", "Język"))
        if hasattr(self, "header_donate_btn"):
            self.header_donate_btn.setText(self._tr("Donate", "Donate"))
            self.header_donate_btn.setToolTip(self._tr("Open GitHub Sponsors for Open Trofeo LCD", "Otwórz GitHub Sponsors dla Open Trofeo LCD"))
        if hasattr(self, "header_ready_label"):
            current = self.header_ready_label.text().strip().lower()
            if current in {"start", "ready", "gotowe"}:
                self.header_ready_label.setText(self._tr("Ready", "Gotowe"))
            elif current in {"error", "błąd"}:
                self.header_ready_label.setText(self._tr("Error", "Błąd"))
        if hasattr(self, "header_connection_label"):
            current = self.header_connection_label.text()
            if "Połączono" in current or "Connected" in current:
                self.header_connection_label.setText(self._tr("● Connected", "● Połączono"))
            elif "Rozłączono" in current or "Disconnected" in current:
                self.header_connection_label.setText(self._tr("● Disconnected", "● Rozłączono"))
        self._nav_button_meta = {
            self.nav_library_btn: ("🗂", self._tr("Theme Gallery", "Galeria motywów")),
            self.nav_designer_btn: ("✎", self._tr("Theme Designer", "Projektant motywów")),
            self.nav_animation_studio_btn: ("🎞", self._tr("Animation Studio", "Studio animacji")),
            self.nav_system_btn: ("◉", self._tr("System", "System")),
            self.nav_logs_btn: ("☰", self._tr("Logs", "Logi")),
            self.nav_config_btn: ("⚙", self._tr("Configuration", "Konfiguracja")),
        }
        if hasattr(self, "main_tabs"):
            self.main_tabs.setTabText(0, self._tr("System", "System"))
            self.main_tabs.setTabText(1, self._tr("Theme Designer", "Projektant motywów"))
            self.main_tabs.setTabText(2, self._tr("Configuration", "Konfiguracja"))
            self.main_tabs.setTabText(3, self._tr("Logs", "Logi"))
        if hasattr(self, "studio_sections_tabs"):
            self.studio_sections_tabs.setTabText(0, self._tr("Theme Gallery", "Galeria motywów"))
            self.studio_sections_tabs.setTabText(1, self._tr("Designer", "Projektant"))
            self.studio_sections_tabs.setTabText(2, self._tr("Animation Studio", "Studio animacji"))
        if hasattr(self, "appearance_box"):
            self.appearance_box.setTitle(self._tr("App Appearance", "Wygląd Aplikacji"))
        if hasattr(self, "paths_box"):
            self.paths_box.setTitle(self._tr("Paths and Integration", "Ścieżki i Integracja"))
        if hasattr(self, "audio_eq_box"):
            self.audio_eq_box.setTitle(self._tr("Audio EQ", "Korektor audio"))
        if hasattr(self, "cfg_audio_eq_apply_btn"):
            self.cfg_audio_eq_apply_btn.setText(self._tr("Apply EQ", "Zastosuj EQ"))
        if hasattr(self, "quick_cfg_box"):
            self.quick_cfg_box.setTitle(self._tr("Quick Actions", "Szybkie Akcje"))
        if hasattr(self, "automation_tools_box"):
            self.automation_tools_box.setTitle(self._tr("Automation and Bundles", "Automatyzacja i Bundles"))
        if hasattr(self, "cfg_cancel_btn"):
            self.cfg_cancel_btn.setText(self._tr("Cancel", "Anuluj"))
        if hasattr(self, "cfg_apply_btn"):
            self.cfg_apply_btn.setText(self._tr("Apply", "Zastosuj"))
        if hasattr(self, "cfg_save_btn"):
            self.cfg_save_btn.setText(self._tr("Save Settings", "Zapisz ustawienia"))
        if hasattr(self, "cfg_reset_btn"):
            self.cfg_reset_btn.setText(self._tr("Restore Defaults", "Przywróć domyślne"))
        if hasattr(self, "cfg_export_btn"):
            self.cfg_export_btn.setText(self._tr("Export Configuration", "Eksportuj konfigurację"))
        if hasattr(self, "cfg_import_btn"):
            self.cfg_import_btn.setText(self._tr("Import Configuration", "Importuj konfigurację"))
        if hasattr(self, "cfg_clear_cache_btn"):
            self.cfg_clear_cache_btn.setText(self._tr("Clear Cache", "Wyczyść cache"))
        if hasattr(self, "cfg_restart_app_btn"):
            self.cfg_restart_app_btn.setText(self._tr("Restart Whole App", "Uruchom całą aplikację ponownie"))
        if hasattr(self, "library_summary_label"):
            self.library_summary_label.setText(self._tr("Theme gallery quick actions", "Szybkie akcje galerii motywów"))
        if hasattr(self, "library_import_ttcr_btn"):
            self.library_import_ttcr_btn.setText(self._tr("Import TTCR", "Import TTCR"))
        if hasattr(self, "library_refresh_btn"):
            self.library_refresh_btn.setText(self._tr("Refresh", "Odśwież"))
        if hasattr(self, "new_theme_create_btn"):
            self.new_theme_create_btn.setText(self._tr("Create Theme", "Utwórz motyw"))
        if hasattr(self, "new_theme_advanced_btn"):
            self.new_theme_advanced_btn.setText(self._tr("File Settings", "Ustawienia pliku"))
        if hasattr(self, "new_theme_hint_label"):
            self.new_theme_hint_label.setText(self._tr("Enter a name and style. The theme file path will be suggested automatically.", "Podaj nazwę i styl. Plik motywu zostanie zaproponowany automatycznie."))
        if hasattr(self, "new_theme_name_edit"):
            self.new_theme_name_edit.setPlaceholderText(self._tr("e.g. My Dashboard", "Np. Mój dashboard"))
        if hasattr(self, "theme_browser_box"):
            self.theme_browser_box.setTitle(self._tr("Themes", "Motywy"))
        if hasattr(self, "asset_gallery_box"):
            self.asset_gallery_box.setTitle(self._tr("Theme Assets", "Zasoby motywu"))
        if hasattr(self, "library_current_theme_label"):
            current = getattr(self, "theme_combo", None)
            current_name = current.currentText().strip() if current is not None else ""
            self.library_current_theme_label.setText(
                self._tr(f"Currently selected: {current_name}", f"Aktualnie wybrany: {current_name}") if current_name
                else self._tr("No active theme.", "Brak aktywnego motywu.")
            )
        self._apply_sidebar_mode()
        if hasattr(self, "theme_browser_controls_search_label"):
            self.theme_browser_controls_search_label.setText(self._tr("Search", "Szukaj"))
        if hasattr(self, "theme_browser_controls_type_label"):
            self.theme_browser_controls_type_label.setText(self._tr("Type", "Typ"))
        if hasattr(self, "theme_browser_controls_sort_label"):
            self.theme_browser_controls_sort_label.setText(self._tr("Sort", "Sortuj"))
        self._refresh_extended_ui_labels()

    def _apply_language_selection(self, _value: str | None = None, *, persist: bool = True) -> None:
        if hasattr(self, "header_language_combo"):
            self._ui_language = self.header_language_combo.currentData() or "en"
        self._refresh_localized_texts()
        if persist:
            self._save_ui_state()

    def _restore_ui_state(self) -> None:
        payload = self._load_ui_state_payload()
        try:
            self._ui_language = str(payload.get("ui_language", "en")).strip() or "en"
            if hasattr(self, "header_language_combo"):
                idx = self.header_language_combo.findData(self._ui_language)
                if idx >= 0:
                    self.header_language_combo.blockSignals(True)
                    try:
                        self.header_language_combo.setCurrentIndex(idx)
                    finally:
                        self.header_language_combo.blockSignals(False)
            ui_mode = str(payload.get("ui_mode", "")).strip()
            if ui_mode and hasattr(self, "ui_mode_combo"):
                self.ui_mode_combo.setCurrentText(ui_mode)
            ui_theme = str(payload.get("ui_theme", "")).strip()
            if ui_theme and hasattr(self, "ui_theme_combo"):
                self.ui_theme_combo.setCurrentText(ui_theme)
            ui_scale = int(payload.get("ui_scale", 100))
            if hasattr(self, "ui_scale_combo"):
                for idx in range(self.ui_scale_combo.count()):
                    if int(self.ui_scale_combo.itemData(idx) or 100) == ui_scale:
                        self.ui_scale_combo.setCurrentIndex(idx)
                        break
            designer_mode = str(payload.get("designer_mode", "")).strip()
            if designer_mode and hasattr(self, "designer_mode_combo"):
                self.designer_mode_combo.setCurrentText(designer_mode)
            self._startup_theme_name = str(payload.get("startup_theme", "")).strip()
            self._startup_theme_applied = False
            if hasattr(self, "cfg_weather_lat_edit"):
                self.cfg_weather_lat_edit.setText(str(payload.get("weather_lat", "") or ""))
                self.cfg_weather_lon_edit.setText(str(payload.get("weather_lon", "") or ""))
                self.cfg_weather_location_edit.setText(str(payload.get("weather_location", "") or ""))
                try:
                    self.cfg_weather_refresh_spin.setValue(int(payload.get("weather_refresh_s", 900) or 900))
                except Exception:
                    self.cfg_weather_refresh_spin.setValue(900)
            if hasattr(self, "cfg_audio_eq_input_combo"):
                idx = self.cfg_audio_eq_input_combo.findData(str(payload.get("audio_eq_input", "auto") or "auto"))
                if idx >= 0:
                    self.cfg_audio_eq_input_combo.setCurrentIndex(idx)
            if hasattr(self, "cfg_audio_eq_profile_combo"):
                idx = self.cfg_audio_eq_profile_combo.findData(str(payload.get("audio_eq_profile", "responsive") or "responsive"))
                if idx >= 0:
                    self.cfg_audio_eq_profile_combo.setCurrentIndex(idx)
            if hasattr(self, "cfg_audio_eq_sensitivity_spin"):
                try:
                    self.cfg_audio_eq_sensitivity_spin.setValue(int(round(float(payload.get("audio_eq_sensitivity", 1.0) or 1.0) * 100.0)))
                except Exception:
                    self.cfg_audio_eq_sensitivity_spin.setValue(100)
            for attr, key, default in (
                ("cfg_start_with_system_chk", "cfg_start_with_system", True),
                ("cfg_minimize_to_tray_chk", "cfg_minimize_to_tray", True),
                ("cfg_auto_connect_chk", "cfg_auto_connect", True),
                ("cfg_restore_project_chk", "cfg_restore_project", False),
                ("cfg_check_updates_chk", "cfg_check_updates", True),
                ("cfg_system_notifications_chk", "cfg_system_notifications", True),
                ("cfg_backend_alerts_chk", "cfg_backend_alerts", True),
                ("cfg_debug_log_chk", "cfg_debug_log", False),
                ("cfg_log_rotation_chk", "cfg_log_rotation", True),
                ("cfg_smoothing_chk", "cfg_smoothing", True),
                ("cfg_animations_chk", "cfg_animations", True),
                ("cfg_compact_layout_chk", "cfg_compact_layout", False),
            ):
                widget = getattr(self, attr, None)
                if widget is not None:
                    widget.setChecked(bool(payload.get(key, default)))
            self._sync_config_ui_controls_from_header()
            self._refresh_localized_texts()
        except Exception:
            pass

    def _save_ui_state(self, *, onboarding_done: bool | None = None) -> None:
        payload = self._load_ui_state_payload()
        payload["ui_language"] = self._current_ui_language()
        if hasattr(self, "ui_mode_combo"):
            payload["ui_mode"] = self.ui_mode_combo.currentText()
        if hasattr(self, "ui_theme_combo"):
            payload["ui_theme"] = self.ui_theme_combo.currentText()
        if hasattr(self, "ui_scale_combo"):
            payload["ui_scale"] = int(self.ui_scale_combo.currentData() or 100)
        if hasattr(self, "designer_mode_combo"):
            payload["designer_mode"] = self.designer_mode_combo.currentText()
        payload["startup_theme"] = str(getattr(self, "_startup_theme_name", "")).strip()
        if hasattr(self, "cfg_weather_lat_edit"):
            payload["weather_lat"] = self.cfg_weather_lat_edit.text().strip()
            payload["weather_lon"] = self.cfg_weather_lon_edit.text().strip()
            payload["weather_location"] = self.cfg_weather_location_edit.text().strip()
            payload["weather_refresh_s"] = int(self.cfg_weather_refresh_spin.value())
        if hasattr(self, "cfg_audio_eq_input_combo"):
            payload["audio_eq_input"] = str(self.cfg_audio_eq_input_combo.currentData() or "auto")
        if hasattr(self, "cfg_audio_eq_profile_combo"):
            payload["audio_eq_profile"] = str(self.cfg_audio_eq_profile_combo.currentData() or "responsive")
        if hasattr(self, "cfg_audio_eq_sensitivity_spin"):
            payload["audio_eq_sensitivity"] = float(self.cfg_audio_eq_sensitivity_spin.value()) / 100.0
        for attr, key in (
            ("cfg_start_with_system_chk", "cfg_start_with_system"),
            ("cfg_minimize_to_tray_chk", "cfg_minimize_to_tray"),
            ("cfg_auto_connect_chk", "cfg_auto_connect"),
            ("cfg_restore_project_chk", "cfg_restore_project"),
            ("cfg_check_updates_chk", "cfg_check_updates"),
            ("cfg_system_notifications_chk", "cfg_system_notifications"),
            ("cfg_backend_alerts_chk", "cfg_backend_alerts"),
            ("cfg_debug_log_chk", "cfg_debug_log"),
            ("cfg_log_rotation_chk", "cfg_log_rotation"),
            ("cfg_smoothing_chk", "cfg_smoothing"),
            ("cfg_animations_chk", "cfg_animations"),
            ("cfg_compact_layout_chk", "cfg_compact_layout"),
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                payload[key] = bool(widget.isChecked())
        if onboarding_done is not None:
            payload["onboarding_done"] = bool(onboarding_done)
            payload["seen_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            UI_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _animate_widget_fade(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        widget.update()

    def _show_onboarding_once(self) -> None:
        payload = self._load_ui_state_payload()
        if bool(payload.get("onboarding_done")):
            return

        def _safe_set_tooltip(attr_name: str, text: str) -> None:
            widget = getattr(self, attr_name, None)
            if widget is None:
                return
            try:
                widget.setToolTip(text)
            except RuntimeError:
                # Some legacy toolbar buttons may still exist as Python attributes
                # after their backing Qt object has already been deleted.
                return

        _safe_set_tooltip(
            "designer_apply_btn",
            self._tr("Renders the theme and sends it to the LCD.", "Renderuje motyw i wysyła go na LCD."),
        )
        _safe_set_tooltip(
            "studio_toolbar_apply_btn",
            self._tr("Renders the theme and sends it to the LCD.", "Renderuje motyw i wysyła go na LCD."),
        )
        _safe_set_tooltip(
            "designer_import_image_btn",
            self._tr(
                "Imports an image, prepares it for the LCD, and adds it as an Image layer.",
                "Importuje obraz, przygotowuje go pod LCD i dodaje jako warstwę Image.",
            ),
        )
        _safe_set_tooltip(
            "bg_prepare_btn",
            self._tr(
                "Imports and prepares a background image into the theme asset folder.",
                "Importuje i przygotowuje obraz tła w katalogu assetów motywu.",
            ),
        )
        QMessageBox.information(
            self,
            self._tr("Getting started", "Pierwsze kroki"),
            self._tr(
                "1. Theme Gallery: start from a template or browse themes.\n"
                "2. Designer: click and drag elements directly on the preview.\n"
                "3. Import background / image: assets are saved into the current theme folder.",
                "1. Biblioteka Motywów: zacznij od szablonu albo galerii motywów.\n"
                "2. Designer: klikaj i przeciągaj elementy bezpośrednio na preview.\n"
                "3. Importuj tło / obraz: assety zapisują się automatycznie do katalogu bieżącego motywu.",
            ),
        )
        self._save_ui_state(onboarding_done=True)

    def _set_shell_nav_active(self, active_btn: QPushButton | None) -> None:
        for btn in getattr(self, "_shell_nav_buttons", []):
            btn.blockSignals(True)
            btn.setChecked(btn is active_btn)
            btn.blockSignals(False)

    def _apply_sidebar_mode(self) -> None:
        collapsed = bool(getattr(self, "sidebar_collapsed", False))
        if hasattr(self, "sidebar_layout"):
            if collapsed:
                self.sidebar_layout.setContentsMargins(10, 12, 10, 12)
                self.sidebar_layout.setSpacing(10)
            else:
                self.sidebar_layout.setContentsMargins(18, 18, 18, 18)
                self.sidebar_layout.setSpacing(14)
        if hasattr(self, "sidebar_toggle_btn"):
            self.sidebar_toggle_btn.setText("⟩" if collapsed else "⟨")
            self.sidebar_toggle_btn.setToolTip(self._tr("Expand menu", "Rozwiń menu") if collapsed else self._tr("Collapse menu", "Zwiń menu"))
        if hasattr(self, "brand_label"):
            self.brand_label.setVisible(not collapsed)
        if hasattr(self, "brand_sub"):
            self.brand_sub.setVisible(not collapsed)
        if hasattr(self, "sidebar_footer_note"):
            self.sidebar_footer_note.setVisible(not collapsed)
        for btn, meta in getattr(self, "_nav_button_meta", {}).items():
            icon_text, full_text = meta
            btn.setProperty("collapsed", collapsed)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            wrapped = full_text.replace(" ", chr(10), 1) if full_text.count(" ") >= 1 and len(full_text) > 11 else full_text
            btn.setText(icon_text if collapsed else f"{icon_text}  {wrapped}")
            btn.setToolTip(full_text)
            btn.setMinimumHeight(66 if collapsed else 88)
        self._apply_responsive_layout_metrics()

    def toggle_sidebar_collapsed(self) -> None:
        self.sidebar_collapsed = not bool(getattr(self, "sidebar_collapsed", False))
        self._apply_sidebar_mode()

    def _sync_shell_navigation(self) -> None:
        if not hasattr(self, "main_tabs"):
            return
        current = self.main_tabs.currentIndex()
        if current == 3:
            self._set_shell_nav_active(getattr(self, "nav_logs_btn", None))
            return
        if current == 2:
            self._set_shell_nav_active(getattr(self, "nav_config_btn", None))
            return
        if current == 0:
            self._set_shell_nav_active(getattr(self, "nav_system_btn", None))
            return
        if current == 1 and hasattr(self, "studio_sections_tabs"):
            idx = self.studio_sections_tabs.currentIndex()
            if idx == 0:
                self._set_shell_nav_active(getattr(self, "nav_library_btn", None))
            elif idx == 1:
                self._set_shell_nav_active(getattr(self, "nav_designer_btn", None))
            else:
                self._set_shell_nav_active(getattr(self, "nav_animation_studio_btn", None))

    def _go_animation_studio(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(1)
        if hasattr(self, "studio_sections_tabs"):
            self.studio_sections_tabs.setCurrentIndex(2)
        self._sync_shell_navigation()
        self._update_animation_performance_hint()
        self._refresh_animation_studio_preview()
        self._update_animation_preview_timer()

    def _build_animation_studio_page(self) -> None:
        if self._animation_studio_built or not hasattr(self, "animation_studio_layout"):
            return
        self._animation_studio_built = True
        lay = self.animation_studio_layout

        def make_card(title: str) -> tuple[QGroupBox, QVBoxLayout]:
            box = QGroupBox(title)
            box.setObjectName("designerToolbarBox")
            box.setFlat(False)
            layout = QVBoxLayout(box)
            layout.setContentsMargins(8, 6, 8, 8)
            layout.setSpacing(5)
            return box, layout

        def make_button_grid(buttons: list[QWidget], columns: int = 2) -> QGridLayout:
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(6)
            grid.setVerticalSpacing(5)
            for idx, button in enumerate(buttons):
                if isinstance(button, (QPushButton, QComboBox, QSpinBox, QDoubleSpinBox)):
                    button.setMinimumHeight(26)
                    button.setMaximumHeight(30)
                grid.addWidget(button, idx // columns, idx % columns)
            return grid

        header = QHBoxLayout()
        header.setSpacing(10)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.animation_studio_title_label = QLabel("Animation Studio")
        self.animation_studio_title_label.setObjectName("sectionTitle")
        self.animation_studio_subtitle_label = QLabel("Create and manage frame-based animations for Trofeo LCD.")
        self.animation_studio_subtitle_label.setObjectName("previewHintLabel")
        title_col.addWidget(self.animation_studio_title_label)
        title_col.addWidget(self.animation_studio_subtitle_label)
        header.addLayout(title_col, 1)
        self.animation_studio_back_btn = QPushButton("← Theme Designer")
        self.animation_studio_back_btn.setObjectName("secondaryAccentButton")
        self.animation_studio_back_btn.clicked.connect(self._go_designer)
        header.addWidget(self.animation_studio_back_btn)
        self.animation_studio_open_json_btn = QPushButton("Open JSON…")
        self.animation_studio_open_json_btn.setObjectName("secondaryAccentButton")
        self.animation_studio_open_json_btn.clicked.connect(
            lambda: self.open_current_theme_json_externally(from_animation_studio=True)
        )
        header.addWidget(self.animation_studio_open_json_btn)
        self.animation_studio_save_as_btn = QPushButton("Save As…")
        self.animation_studio_save_as_btn.setObjectName("secondaryAccentButton")
        self.animation_studio_save_as_btn.clicked.connect(lambda: self.save_theme_doc_as(from_animation_studio=True))
        header.addWidget(self.animation_studio_save_as_btn)
        self.animation_studio_quick_export_btn = QPushButton("Export")
        self.animation_studio_quick_export_btn.setObjectName("secondaryAccentButton")
        self.animation_studio_quick_export_btn.clicked.connect(self.export_animation_sequence)
        header.addWidget(self.animation_studio_quick_export_btn)
        lay.addLayout(header)

        meta_row = QHBoxLayout()
        self.animation_performance_hint_label = QLabel("")
        self.animation_performance_hint_label.setWordWrap(True)
        self.animation_performance_hint_label.setObjectName("previewHintLabel")
        meta_row.addWidget(self.animation_performance_hint_label, 1)
        self.animation_worker_status_label = QLabel("")
        self.animation_worker_status_label.setObjectName("previewHintLabel")
        self.animation_worker_status_label.setMinimumWidth(180)
        self.animation_worker_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta_row.addWidget(self.animation_worker_status_label)
        self.animation_cancel_worker_btn = QPushButton("Cancel task")
        self.animation_cancel_worker_btn.setObjectName("secondaryAccentButton")
        self.animation_cancel_worker_btn.setVisible(False)
        self.animation_cancel_worker_btn.clicked.connect(self.cancel_animation_background_tasks)
        meta_row.addWidget(self.animation_cancel_worker_btn)
        lay.addLayout(meta_row)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)
        self.animation_preview_title_label = QLabel("Preview")
        preview_row.addWidget(self.animation_preview_title_label)
        self.animation_preview_scale_combo = QComboBox()
        self.animation_preview_scale_combo.setObjectName("animationPreviewScaleCombo")
        for text, data in (
            ("Fit width", "fit_width"),
            ("100%", "100"),
            ("150%", "150"),
            ("200%", "200"),
        ):
            self.animation_preview_scale_combo.addItem(text, data)
        self.animation_preview_scale_combo.currentIndexChanged.connect(lambda _idx: self._refresh_animation_studio_preview())
        preview_row.addWidget(self.animation_preview_scale_combo)
        self.animation_auto_composite_chk = QCheckBox("Auto composite")
        self.animation_auto_composite_chk.setChecked(True)
        self.animation_auto_composite_chk.toggled.connect(lambda _checked: self._refresh_animation_studio_preview(force_composite=True))
        self.animation_refresh_composite_btn = QPushButton("Refresh composite")
        self.animation_refresh_composite_btn.setObjectName("secondaryAccentButton")
        self.animation_refresh_composite_btn.clicked.connect(lambda: self._refresh_animation_studio_preview(force_composite=True))
        preview_row.addWidget(self.animation_auto_composite_chk)
        preview_row.addWidget(self.animation_refresh_composite_btn)
        preview_row.addSpacing(12)
        preview_row.addWidget(self.animation_onion_skin_chk)
        self.animation_onion_skin_opacity_label = QLabel("Opacity")
        preview_row.addWidget(self.animation_onion_skin_opacity_label)
        preview_row.addWidget(self.animation_onion_opacity_spin)
        preview_row.addStretch(1)
        lay.addLayout(preview_row)

        preview_splitter = QSplitter(Qt.Horizontal)
        preview_splitter.setChildrenCollapsible(False)
        preview_splitter.setMinimumHeight(205)
        preview_splitter.setMaximumHeight(300)
        self.animation_frame_preview_label = QLabel("Frame preview")
        self.animation_frame_preview_label.setAlignment(Qt.AlignCenter)
        self.animation_frame_preview_label.setMinimumHeight(185)
        self.animation_frame_preview_label.setMaximumHeight(280)
        self.animation_frame_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.animation_frame_preview_label.setObjectName("selectionSummaryLabel")

        device_box, device_lay = make_card("Device Preview (Trofeo LCD)")
        device_box.setMaximumHeight(300)
        self.animation_composite_preview_label = QLabel("Composite preview")
        self.animation_composite_preview_label.setAlignment(Qt.AlignCenter)
        self.animation_composite_preview_label.setMinimumHeight(112)
        self.animation_composite_preview_label.setMaximumHeight(150)
        self.animation_composite_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.animation_composite_preview_label.setObjectName("selectionSummaryLabel")
        self.animation_device_info_label = QLabel(
            "Aspect: 480 x 128 (3.75 : 1)  •  Format: RGB888\n"
            "Estimated memory: -  •  Transfer over USB"
        )
        self.animation_device_info_label.setWordWrap(True)
        self.animation_device_info_label.setObjectName("previewHintLabel")
        device_lay.addWidget(self.animation_composite_preview_label)
        device_lay.addWidget(self.animation_device_info_label)
        preview_splitter.addWidget(self.animation_frame_preview_label)
        preview_splitter.addWidget(device_box)
        preview_splitter.setStretchFactor(0, 2)
        preview_splitter.setStretchFactor(1, 1)
        self.animation_studio_preview_label = self.animation_frame_preview_label
        lay.addWidget(preview_splitter, 1)

        controls_grid = QGridLayout()
        controls_grid.setHorizontalSpacing(10)
        controls_grid.setVerticalSpacing(10)

        playback_box, playback_lay = make_card("Playback")
        play_buttons = QHBoxLayout()
        play_buttons.setSpacing(6)
        play_buttons.addWidget(self.bg_animation_prev_btn)
        play_buttons.addWidget(self.bg_animation_play_btn)
        play_buttons.addWidget(self.bg_animation_next_btn)
        play_buttons.addWidget(self.bg_animation_count_label)
        playback_lay.addLayout(play_buttons)
        flags_row = QHBoxLayout()
        flags_row.setSpacing(8)
        flags_row.addWidget(self.bg_animation_enabled_chk)
        flags_row.addWidget(self.bg_animation_use_bg_chk)
        flags_row.addStretch(1)
        playback_lay.addLayout(flags_row)
        self.animation_studio_fps_label = QLabel("FPS")
        self.animation_studio_frame_index_label = QLabel("Frame")
        self.animation_studio_duration_label = QLabel("Duration (ms)")
        timing_form = QGridLayout()
        timing_form.setHorizontalSpacing(6)
        timing_form.setVerticalSpacing(4)
        timing_form.addWidget(self.animation_studio_fps_label, 0, 0)
        timing_form.addWidget(self.bg_animation_fps_spin, 0, 1)
        timing_form.addWidget(self.animation_studio_frame_index_label, 1, 0)
        timing_form.addWidget(self.bg_animation_frame_spin, 1, 1)
        timing_form.addWidget(self.animation_studio_duration_label, 2, 0)
        timing_form.addWidget(self.bg_animation_duration_spin, 2, 1)
        playback_lay.addLayout(timing_form)

        timing_box, timing_lay = make_card("Timing")
        self.animation_studio_bulk_duration_label = QLabel("Bulk duration (ms)")
        duration_row = QGridLayout()
        duration_row.setContentsMargins(0, 0, 0, 0)
        duration_row.setHorizontalSpacing(6)
        duration_row.addWidget(self.animation_studio_bulk_duration_label, 0, 0)
        duration_row.addWidget(self.animation_bulk_duration_spin, 0, 1)
        duration_row.addWidget(QLabel("×"), 0, 2)
        duration_row.addWidget(self.animation_duplicate_repeat_spin, 0, 3)
        duration_row.setColumnStretch(4, 1)
        timing_lay.addLayout(duration_row)
        timing_lay.addLayout(
            make_button_grid(
                [
                    self.animation_bulk_apply_duration_btn,
                    self.bg_animation_normalize_duration_btn,
                    self.bg_animation_reverse_btn,
                    self.bg_animation_pingpong_btn,
                    self.animation_stabilize_btn,
                    self.animation_stabilize_mode_combo,
                    self.bg_animation_hold_repeat_btn,
                    self.bg_animation_duplicate_btn,
                    self.bg_animation_repeat_all_btn,
                ],
                columns=3,
            )
        )

        loop_box, loop_lay = make_card("Loop")
        loop_lay.addWidget(self.animation_loop_label)
        loop_lay.addLayout(
            make_button_grid(
                [
                    self.animation_loop_in_btn,
                    self.animation_loop_out_btn,
                    self.animation_loop_clear_btn,
                    self.animation_loop_close_seam_btn,
                    self.animation_loop_from_selection_btn,
                    self.animation_select_range_btn,
                    self.animation_trim_selection_btn,
                    self.animation_invert_selection_btn,
                    self.animation_clear_selection_btn,
                ],
                columns=2,
            )
        )

        tools_box, tools_lay = make_card("Frame Tools")
        tools_lay.addLayout(
            make_button_grid(
                [
                    self.bg_animation_import_btn,
                    self.bg_animation_add_btn,
                    self.bg_animation_blank_btn,
                    self.bg_animation_remove_btn,
                    self.bg_animation_up_btn,
                    self.bg_animation_down_btn,
                    self.bg_animation_export_btn,
                    self.animation_export_loop_btn,
                    self.animation_export_selection_btn,
                    self.bg_animation_clear_btn,
                ],
                columns=3,
            )
        )

        controls_grid.addWidget(playback_box, 0, 0)
        controls_grid.addWidget(timing_box, 0, 1)
        controls_grid.addWidget(loop_box, 0, 2)
        controls_grid.addWidget(tools_box, 0, 3)
        controls_grid.setColumnStretch(0, 1)
        controls_grid.setColumnStretch(1, 1)
        controls_grid.setColumnStretch(2, 1)
        controls_grid.setColumnStretch(3, 1)
        lay.addLayout(controls_grid)

        timeline_header = QHBoxLayout()
        self.animation_timeline_label = QLabel("Timeline")
        self.animation_timeline_label.setToolTip(
            "Shortcuts: Space play/pause, I/O loop in/out, Ctrl+L clear loop, Delete remove, Ctrl+A select all, R range, Ctrl+I invert, Esc clear, +/- zoom."
        )
        self.animation_timeline_hint_label = QLabel("Click a frame to select it. Drag to select a range. Use Set In / Set Out to mark a loop.")
        self.animation_timeline_hint_label.setObjectName("previewHintLabel")
        timeline_header.addWidget(self.animation_timeline_label)
        timeline_header.addWidget(self.animation_timeline_hint_label, 1)
        timeline_header.addWidget(QLabel("Zoom"))
        timeline_header.addWidget(self.animation_timeline_zoom_combo)
        timeline_header.addWidget(self.animation_timeline_home_btn)
        timeline_header.addWidget(self.animation_timeline_end_btn)
        lay.addLayout(timeline_header)

        self.bg_animation_timeline_scroll = QScrollArea()
        self.bg_animation_timeline_scroll.setWidgetResizable(False)
        self.bg_animation_timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.bg_animation_timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bg_animation_timeline_scroll.setFrameShape(QFrame.NoFrame)
        self.bg_animation_timeline_scroll.setMinimumHeight(148)
        self.bg_animation_timeline_scroll.setWidget(self.bg_animation_timeline)
        self.bg_animation_timeline.installEventFilter(self)
        self.bg_animation_timeline_scroll.viewport().installEventFilter(self)
        lay.addWidget(self.bg_animation_timeline_scroll)
        self.bg_animation_list.setVisible(False)
        self.bg_animation_list.setParent(self.animation_studio_tab)
        self._register_animation_studio_shortcuts()
        tr = self._tr
        self.animation_studio_open_json_btn.setText(tr("Open JSON…", "Otwórz JSON…"))
        self.animation_studio_open_json_btn.setToolTip(
            tr(
                "Same theme file; background animation is under effects.animation.",
                "Ten sam plik motywu; animacja tła jest w effects.animation.",
            )
        )

    def _go_library(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(1)
        if hasattr(self, "studio_sections_tabs"):
            self.studio_sections_tabs.setCurrentIndex(0)
        self._maybe_rebuild_visible_theme_views()
        self._sync_shell_navigation()

    def _go_designer(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(1)
        if hasattr(self, "studio_sections_tabs"):
            self.studio_sections_tabs.setCurrentIndex(1)
        self._sync_shell_navigation()

    def _go_system(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(0)
        self._maybe_rebuild_visible_theme_views()
        self._sync_shell_navigation()

    def _go_logs(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(3)
        self._sync_shell_navigation()

    def _go_config(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(2)
        self._sync_shell_navigation()

    def _on_animation_timeline_selection_changed(self, indices: list[int]) -> None:
        if not indices or not hasattr(self, "bg_animation_list"):
            return
        self._animation_syncing_from_timeline = True
        self._designer_updating = True
        try:
            self.bg_animation_list.clearSelection()
            for i in indices:
                it = self.bg_animation_list.item(i)
                if it is not None:
                    it.setSelected(True)
            self.bg_animation_list.setCurrentRow(indices[-1])
        finally:
            self._designer_updating = False
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_playhead(indices[-1])
        self._set_current_animation_frame(indices[-1], persist=True, render_preview=True)
        self._animation_syncing_from_timeline = False

    def _on_bg_animation_list_selection_sync(self) -> None:
        if self._designer_updating:
            return
        rows = sorted({i.row() for i in self.bg_animation_list.selectedIndexes()})
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_selection(rows, emit_signal=False)
        self._refresh_animation_studio_preview()
        self._update_animation_performance_hint()

    def _on_animation_current_row_changed(self, row: int) -> None:
        if self._designer_updating or self._animation_syncing_from_timeline:
            return
        if row < 0:
            return
        self.select_animation_frame(row)

    def _register_animation_studio_shortcuts(self) -> None:
        if not hasattr(self, "animation_studio_tab") or self._animation_studio_shortcuts:
            return

        def add_shortcut(sequence: str, callback) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self.animation_studio_tab)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._animation_studio_shortcuts.append(shortcut)

        add_shortcut("Space", lambda: self._run_animation_shortcut(self.toggle_animation_preview_playback, allow_text_inputs=False))
        add_shortcut("I", lambda: self._run_animation_shortcut(self.set_animation_loop_in, allow_text_inputs=False))
        add_shortcut("O", lambda: self._run_animation_shortcut(self.set_animation_loop_out, allow_text_inputs=False))
        add_shortcut("Ctrl+L", lambda: self._run_animation_shortcut(self.clear_animation_loop_range, allow_text_inputs=False))
        add_shortcut("Delete", lambda: self._run_animation_shortcut(self.remove_selected_animation_frames, allow_text_inputs=False))
        add_shortcut("Ctrl+A", lambda: self._run_animation_shortcut(self.select_all_animation_frames, allow_text_inputs=False))
        add_shortcut("R", lambda: self._run_animation_shortcut(self.select_animation_range_between_edges, allow_text_inputs=False))
        add_shortcut("Ctrl+I", lambda: self._run_animation_shortcut(self.invert_animation_frame_selection, allow_text_inputs=False))
        add_shortcut("Esc", lambda: self._run_animation_shortcut(self.clear_animation_frame_selection, allow_text_inputs=False))
        add_shortcut("Ctrl+R", lambda: self._run_animation_shortcut(self.set_animation_loop_from_selection, allow_text_inputs=False))
        add_shortcut("Ctrl+T", lambda: self._run_animation_shortcut(self.trim_animation_to_selection, allow_text_inputs=False))
        add_shortcut("+", lambda: self._run_animation_shortcut(self.zoom_animation_timeline_in, allow_text_inputs=False))
        add_shortcut("=", lambda: self._run_animation_shortcut(self.zoom_animation_timeline_in, allow_text_inputs=False))
        add_shortcut("-", lambda: self._run_animation_shortcut(self.zoom_animation_timeline_out, allow_text_inputs=False))
        add_shortcut("Home", lambda: self._run_animation_shortcut(self.scroll_animation_timeline_to_start, allow_text_inputs=False))
        add_shortcut("End", lambda: self._run_animation_shortcut(self.scroll_animation_timeline_to_end, allow_text_inputs=False))

    def _run_animation_shortcut(self, callback, *, allow_text_inputs: bool = True) -> None:
        if not self._animation_studio_active():
            return
        if not allow_text_inputs and self._focus_is_text_input():
            return
        callback()

    def _animation_studio_active(self) -> bool:
        return (
            hasattr(self, "main_tabs")
            and hasattr(self, "studio_sections_tabs")
            and self.main_tabs.currentIndex() == 1
            and self.studio_sections_tabs.currentIndex() == 2
        )

    def _focus_is_text_input(self) -> bool:
        focus = QApplication.focusWidget()
        return isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox))

    def _animation_preview_scaled_pixmap(self, pixmap: QPixmap, label: QLabel) -> QPixmap:
        mode = "fit_width"
        combo = getattr(self, "animation_preview_scale_combo", None)
        if combo is not None:
            data = combo.currentData()
            if isinstance(data, str) and data:
                mode = data
            else:
                text = combo.currentText()
                if text == "100%":
                    mode = "100"
                elif text == "150%":
                    mode = "150"
                elif text == "200%":
                    mode = "200"
                elif "%" not in text:
                    mode = "fit_width"
        tw = max(280, label.width() - 8)
        th = max(220, label.height() - 8)
        if mode == "fit_width":
            return pixmap.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if mode == "100":
            return pixmap
        if mode == "150":
            return pixmap.scaled(int(pixmap.width() * 1.5), int(pixmap.height() * 1.5), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pixmap.scaled(int(pixmap.width() * 2.0), int(pixmap.height() * 2.0), Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _set_animation_preview_pixmap(self, label: QLabel, pixmap: QPixmap, empty_text: str) -> None:
        if pixmap.isNull():
            label.setPixmap(QPixmap())
            label.setText(empty_text)
            return
        label.setPixmap(self._animation_preview_scaled_pixmap(pixmap, label))
        label.setText("")

    def _animation_onion_skin_pixmap(self, current_path: str) -> QPixmap:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if len(frame_paths) < 2:
            return QPixmap(str(self._resolve_theme_asset_path(current_path)))
        try:
            current = int(animation.get("current_frame", 0))
        except Exception:
            current = 0
        current = min(max(0, current), len(frame_paths) - 1)
        base = QPixmap(str(self._resolve_theme_asset_path(str(frame_paths[current]))))
        if base.isNull():
            return base
        opacity = 0.28
        if hasattr(self, "animation_onion_opacity_spin"):
            opacity = max(0.05, min(float(self.animation_onion_opacity_spin.value()), 0.85))
        result = QPixmap(base)
        painter = QPainter(result)
        try:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            neighbors = [
                (current - 1, QColor("#f97316"), self._tr("PREV", "POPRZ")),
                (current + 1, QColor("#38bdf8"), self._tr("NEXT", "NAST")),
            ]
            for index, color, label in neighbors:
                if index < 0 or index >= len(frame_paths):
                    continue
                pix = QPixmap(str(self._resolve_theme_asset_path(str(frame_paths[index]))))
                if pix.isNull():
                    continue
                if pix.size() != result.size():
                    pix = pix.scaled(result.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                painter.setOpacity(opacity)
                painter.drawPixmap(0, 0, pix)
                painter.setOpacity(min(0.8, opacity + 0.25))
                painter.setPen(QPen(color, max(2, result.width() // 480)))
                inset = max(4, result.width() // 240)
                painter.drawRect(result.rect().adjusted(inset, inset, -inset, -inset))
                painter.drawText(result.rect().adjusted(12, 10, -12, -10), Qt.AlignTop | Qt.AlignLeft, label)
        finally:
            painter.end()
        return result

    def _render_animation_composite_pixmap(self) -> QPixmap:
        if render_theme_document is None or self.theme_doc_model is None:
            return QPixmap()
        try:
            document = normalize_theme_document(deepcopy(self.theme_doc_model))
            image = render_theme_document(
                ThemeDocument(document),
                base_dir=self._theme_base_dir(),
                stats_provider=self._preview_stats_provider,
            )
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue(), "PNG")
            try:
                rotation = int(document.get("canvas", {}).get("rotation", 0)) % 360
            except Exception:
                rotation = 0
            if rotation:
                pixmap = pixmap.transformed(QTransform().rotate((-rotation) % 360), Qt.SmoothTransformation)
            return pixmap
        except Exception as exc:
            self.append_log(f"[animation-composite-preview] ERROR: {exc}")
            return QPixmap()

    def _refresh_animation_studio_preview(self, *, force_composite: bool = False) -> None:
        if not hasattr(self, "animation_frame_preview_label"):
            return
        animation = self._current_animation_effect()
        if bool(animation.get("use_as_background", True)):
            path = self._current_animation_preview_path()
        else:
            path = self.bg_path_edit.text().strip()
        frame_label = self.animation_frame_preview_label
        if not path.strip():
            frame_label.setPixmap(QPixmap())
            frame_label.setText(self._tr("Add frames to preview them here.", "Dodaj klatki, aby zobaczyć podgląd."))
        else:
            resolved = self._resolve_theme_asset_path(path)
            if bool(getattr(self, "animation_onion_skin_chk", None) and self.animation_onion_skin_chk.isChecked()):
                pix = self._animation_onion_skin_pixmap(path)
            else:
                pix = QPixmap(str(resolved))
            self._set_animation_preview_pixmap(
                frame_label,
                pix,
                self._tr("Could not load frame image.", "Nie udało się wczytać klatki."),
            )

        composite_label = getattr(self, "animation_composite_preview_label", None)
        if composite_label is None:
            return
        auto_composite = bool(getattr(self, "animation_auto_composite_chk", None) and self.animation_auto_composite_chk.isChecked())
        if not force_composite and not auto_composite:
            if composite_label.pixmap() is None or composite_label.pixmap().isNull():
                composite_label.setText(self._tr("Refresh composite to render the full theme.", "Odśwież kompozycję, aby wyrenderować pełny motyw."))
            return
        pixmap = self._render_animation_composite_pixmap()
        self._set_animation_preview_pixmap(
            composite_label,
            pixmap,
            self._tr("Could not render composite preview.", "Nie udało się wyrenderować kompozycji."),
        )

    def _format_animation_frame_count(self, n: int) -> str:
        if self._current_ui_language() == "pl":
            if n == 1:
                return "1 klatka"
            rem10 = n % 10
            rem100 = n % 100
            if 2 <= rem10 <= 4 and not (12 <= rem100 <= 14):
                return f"{n} klatki"
            return f"{n} klatek"
        return f"{n} frame" if n == 1 else f"{n} frames"

    def _update_animation_performance_hint(self) -> None:
        if not hasattr(self, "animation_performance_hint_label"):
            return
        if self.theme_doc_model is None:
            self.animation_performance_hint_label.setText("")
            if hasattr(self, "animation_device_info_label"):
                self.animation_device_info_label.setText("")
            return
        effects = self.theme_doc_model.get("effects", {})
        animation = effects.get("animation", {}) if isinstance(effects, dict) else {}
        if not isinstance(animation, dict) or not bool(animation.get("enabled")):
            self.animation_performance_hint_label.setText("")
            if hasattr(self, "animation_device_info_label"):
                self.animation_device_info_label.setText(
                    self._tr(
                        "Aspect: 480 x 128 (3.75 : 1)  •  Format: RGB888\nEstimated memory: -  •  Transfer over USB",
                        "Format: 480 x 128 (3.75 : 1)  •  RGB888\nSzacowana pamięć: -  •  Transfer przez USB",
                    )
                )
            return
        fp = animation.get("frame_paths", [])
        if not isinstance(fp, list) or len(fp) <= 1:
            self.animation_performance_hint_label.setText("")
            if hasattr(self, "animation_device_info_label"):
                self.animation_device_info_label.setText(
                    self._tr(
                        "Aspect: 480 x 128 (3.75 : 1)  •  Format: RGB888\nEstimated memory: -  •  Transfer over USB",
                        "Format: 480 x 128 (3.75 : 1)  •  RGB888\nSzacowana pamięć: -  •  Transfer przez USB",
                    )
                )
            return
        n = len(fp)
        estimated_bytes = n * 480 * 128 * 3
        estimated_mb = estimated_bytes / (1024 * 1024)
        if hasattr(self, "animation_device_info_label"):
            self.animation_device_info_label.setText(
                self._tr(
                    f"Aspect: 480 x 128 (3.75 : 1)  •  Format: RGB888\nEstimated memory: ~{estimated_mb:.1f} MB  •  Transfer over USB",
                    f"Format: 480 x 128 (3.75 : 1)  •  RGB888\nSzacowana pamięć: ~{estimated_mb:.1f} MB  •  Transfer przez USB",
                )
            )
        parts: list[str] = []
        if n >= ANIMATION_FRAMES_SOFT_WARN:
            parts.append(
                self._tr(
                    f"{n} frames: higher LCD cost (each RGB bitmap uses memory and USB bandwidth).",
                    f"{n} klatek: wyższy koszt LCD (każda bitmapa RGB używa pamięci i transferu USB).",
                )
            )
        if n >= ANIMATION_FRAMES_EXTREME_WARN:
            parts.append(
                self._tr(
                    "This can still work, but verify loop smoothness on the LCD and avoid heavy live overlays.",
                    "To nadal może działać, ale sprawdź płynność pętli na LCD i unikaj ciężkich nakładek live.",
                )
            )
        has_eq = False
        has_media = False
        for s in self.theme_doc_model.get("stats", []):
            if not isinstance(s, dict) or not bool(s.get("visible", True)):
                continue
            if str(s.get("display", "")).strip().lower() == "equalizer":
                has_eq = True
            src = str(s.get("source", "")).strip()
            if src.startswith("media_"):
                has_media = True
        for im in self.theme_doc_model.get("images", []):
            if not isinstance(im, dict) or not bool(im.get("visible", True)):
                continue
            if str(im.get("source", "")).strip() in {"media_cover", "media_video_frame"}:
                has_media = True
        if has_eq or has_media:
            parts.append(
                self._tr(
                    "Animated background + live EQ/media refreshes the USB overlay often. If motion stutters on the LCD, "
                    "lower FPS, raise ms per frame, or simplify overlay widgets.",
                    "Tło animowane + na żywo EQ/media często odświeża nakładkę USB. Jeśli obraz się tnie, zmniejsz FPS, "
                    "zwiększ ms na klatkę lub uprość widżety na nakładce.",
                )
            )
        self.animation_performance_hint_label.setText("\n".join(parts) if parts else "")

    def _set_animation_worker_state(self, key: str, label: str | None) -> None:
        if label:
            self._animation_worker_states[key] = label
        else:
            self._animation_worker_states.pop(key, None)
        self._refresh_animation_worker_status()

    def _refresh_animation_worker_status(self) -> None:
        if not hasattr(self, "animation_worker_status_label"):
            return
        active = list(self._animation_worker_states.values())
        if not active:
            self.animation_worker_status_label.setText(self._tr("Workers: idle", "Zadania: bezczynne"))
            self.animation_worker_status_label.setToolTip("")
            if hasattr(self, "animation_cancel_worker_btn"):
                self.animation_cancel_worker_btn.setVisible(False)
                self.animation_cancel_worker_btn.setEnabled(False)
            return
        text = self._tr("Working: ", "Praca: ") + ", ".join(active[:2])
        if len(active) > 2:
            text += f" +{len(active) - 2}"
        self.animation_worker_status_label.setText(text)
        self.animation_worker_status_label.setToolTip("\n".join(active))
        cancellable = bool(
            getattr(self, "_animation_export_in_flight", False)
            or getattr(self, "_animation_import_in_flight", False)
        )
        if hasattr(self, "animation_cancel_worker_btn"):
            self.animation_cancel_worker_btn.setVisible(cancellable)
            self.animation_cancel_worker_btn.setEnabled(cancellable)

    def cancel_animation_background_tasks(self) -> None:
        cancelled = False
        for event in (
            getattr(self, "_animation_export_cancel_event", None),
            getattr(self, "_animation_import_cancel_event", None),
        ):
            if event is not None and not event.is_set():
                event.set()
                cancelled = True
        if cancelled:
            self._set_animation_worker_state(
                "cancel",
                self._tr("cancelling current task", "anulowanie zadania"),
            )
            if hasattr(self, "animation_cancel_worker_btn"):
                self.animation_cancel_worker_btn.setEnabled(False)
            if hasattr(self, "preview_info_label"):
                self.preview_info_label.setText(self._tr("Cancelling animation task…", "Anuluję zadanie animacji…"))

    def _animation_task_cancelled(self, event: threading.Event | None) -> bool:
        return bool(event is not None and event.is_set())

    def _raise_if_animation_task_cancelled(self, event: threading.Event | None) -> None:
        if self._animation_task_cancelled(event):
            raise RuntimeError("Animation task cancelled.")

    def _emit_animation_progress(self, worker: str, current: int, total: int, label: str = "") -> None:
        self.api_result.emit(
            "animation-progress",
            True,
            {
                "result": {
                    "worker": worker,
                    "current": max(0, int(current)),
                    "total": max(0, int(total)),
                    "label": str(label),
                }
            },
        )

    def _apply_animation_progress_payload(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        result = data.get("result", {})
        if not isinstance(result, dict):
            return
        worker = str(result.get("worker", "task"))
        current = int(result.get("current", 0) or 0)
        total = int(result.get("total", 0) or 0)
        label = str(result.get("label", "")).strip()
        pct = int(round((current * 100.0) / total)) if total > 0 else 0
        if label:
            text = f"{label}: {current}/{total} ({pct}%)" if total else label
        else:
            text = f"{worker}: {current}/{total} ({pct}%)" if total else worker
        self._set_animation_worker_state(worker, text)
        if hasattr(self, "preview_info_label"):
            self.preview_info_label.setText(text)

    def _selected_animation_rows(self, *, fallback_current: bool = True, fallback_all: bool = False) -> list[int]:
        controller = self._animation_controller()
        seq = controller.normalize() if controller is not None else None
        count = seq.frame_count if seq is not None else 0
        rows = sorted({i.row() for i in self.bg_animation_list.selectedIndexes() if 0 <= i.row() < count})
        if not rows and fallback_current:
            row = self.bg_animation_list.currentRow()
            if 0 <= row < count:
                rows = [row]
        if not rows and fallback_all and count:
            rows = list(range(count))
        return rows

    def _current_animation_loop_range(self) -> tuple[int, int] | None:
        controller = self._animation_controller()
        if controller is None:
            return None
        seq = controller.normalize()
        if seq.loop_start is None or seq.loop_end is None:
            return None
        return seq.loop_start, seq.loop_end

    def set_animation_timeline_zoom(self, text: str) -> None:
        try:
            zoom = max(0.6, float(str(text).strip().rstrip("%")) / 100.0)
        except Exception:
            zoom = 1.0
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_zoom(zoom)
        self._scroll_animation_timeline_to_playhead()

    def scroll_animation_timeline_to_start(self) -> None:
        scroll = getattr(self, "bg_animation_timeline_scroll", None)
        if scroll is None:
            return
        scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().minimum())
        if hasattr(self, "bg_animation_list") and self.bg_animation_list.count() > 0:
            self.select_animation_frame(0)

    def scroll_animation_timeline_to_end(self) -> None:
        scroll = getattr(self, "bg_animation_timeline_scroll", None)
        if scroll is None:
            return
        scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().maximum())
        if hasattr(self, "bg_animation_list") and self.bg_animation_list.count() > 0:
            self.select_animation_frame(self.bg_animation_list.count() - 1)

    def _animation_timeline_zoom_values(self) -> list[str]:
        if not hasattr(self, "animation_timeline_zoom_combo"):
            return []
        return [self.animation_timeline_zoom_combo.itemText(i) for i in range(self.animation_timeline_zoom_combo.count())]

    def zoom_animation_timeline_in(self) -> None:
        values = self._animation_timeline_zoom_values()
        if not values:
            return
        current = self.animation_timeline_zoom_combo.currentIndex()
        self.animation_timeline_zoom_combo.setCurrentIndex(min(len(values) - 1, current + 1))

    def zoom_animation_timeline_out(self) -> None:
        values = self._animation_timeline_zoom_values()
        if not values:
            return
        current = self.animation_timeline_zoom_combo.currentIndex()
        self.animation_timeline_zoom_combo.setCurrentIndex(max(0, current - 1))

    def select_all_animation_frames(self) -> None:
        if not hasattr(self, "bg_animation_list") or self.bg_animation_list.count() <= 0:
            return
        self._set_animation_frame_selection(list(range(self.bg_animation_list.count())))

    def select_animation_range_between_edges(self) -> None:
        if not hasattr(self, "bg_animation_list") or self.bg_animation_list.count() <= 0:
            return
        rows = sorted({i.row() for i in self.bg_animation_list.selectedIndexes()})
        if len(rows) < 2:
            current = self.bg_animation_list.currentRow()
            if current < 0:
                return
            rows = [current]
        if len(rows) == 1:
            self._set_animation_frame_selection(rows)
            return
        self._set_animation_frame_selection(list(range(rows[0], rows[-1] + 1)))

    def invert_animation_frame_selection(self) -> None:
        if not hasattr(self, "bg_animation_list") or self.bg_animation_list.count() <= 0:
            return
        selected = {i.row() for i in self.bg_animation_list.selectedIndexes()}
        inverted = [row for row in range(self.bg_animation_list.count()) if row not in selected]
        self._set_animation_frame_selection(inverted)

    def clear_animation_frame_selection(self) -> None:
        self._set_animation_frame_selection([])

    def set_animation_loop_from_selection(self) -> None:
        controller = self._animation_controller()
        if controller is None or not hasattr(self, "bg_animation_list"):
            return
        rows = sorted({i.row() for i in self.bg_animation_list.selectedIndexes()})
        if not rows:
            row = self.bg_animation_list.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            return
        self.push_designer_history()
        seq = controller.set_loop_range(rows[0], rows[-1])
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._refresh_animation_frame_list()
        loop_start = seq.loop_start if seq.loop_start is not None else rows[0]
        loop_end = seq.loop_end if seq.loop_end is not None else rows[-1]
        self.preview_info_label.setText(
            self._tr(
                f"Preview loop set from selection: {loop_start + 1}-{loop_end + 1}.",
                f"Pętla podglądu ustawiona z zaznaczenia: {loop_start + 1}-{loop_end + 1}.",
            )
        )
        self.schedule_preview_theme_doc()

    def close_animation_loop_seam(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if seq.frame_count < 2:
            return
        loop_range = self._current_animation_loop_range()
        if loop_range is not None:
            rows = list(range(loop_range[0], loop_range[1] + 1))
        else:
            rows = self._selected_animation_rows(fallback_current=False, fallback_all=True)
        if len(rows) < 2:
            return
        self.push_designer_history()
        result = controller.close_loop_seam(rows)
        inserted = min(rows[-1] + 1, result.frame_count - 1)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list(preserve_selection=False)
        self._set_animation_frame_selection([inserted])
        self._maybe_warn_animation_frame_count(result.frame_count)
        self.preview_info_label.setText(
            self._tr(
                f"Closed loop seam by appending frame {rows[0] + 1} after frame {rows[-1] + 1}.",
                f"Domknięto pętlę: dodano klatkę {rows[0] + 1} za klatką {rows[-1] + 1}.",
            )
        )
        self.schedule_preview_theme_doc()

    def trim_animation_to_selection(self) -> None:
        controller = self._animation_controller()
        if controller is None or not hasattr(self, "bg_animation_list"):
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        rows = sorted({i.row() for i in self.bg_animation_list.selectedIndexes()})
        if not rows:
            return
        if len(rows) == seq.frame_count:
            self.preview_info_label.setText(
                self._tr("Trim skipped: all frames are selected.", "Przycinanie pominięte: zaznaczono wszystkie klatki.")
            )
            return
        self.push_designer_history()
        result = controller.keep_indices(rows)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list(preserve_selection=False)
        self._set_animation_frame_selection(list(range(result.frame_count)))
        self.preview_info_label.setText(
            self._tr(
                f"Trimmed sequence to {result.frame_count} selected frame(s). Asset files were not deleted.",
                f"Przycięto sekwencję do {result.frame_count} zaznaczonych klat. Pliki assetów nie zostały usunięte.",
            )
        )
        self.schedule_preview_theme_doc()

    def _set_animation_frame_selection(self, rows: list[int]) -> None:
        if not hasattr(self, "bg_animation_list"):
            return
        valid = sorted({int(row) for row in rows if 0 <= int(row) < self.bg_animation_list.count()})
        self._designer_updating = True
        try:
            self.bg_animation_list.clearSelection()
            for row in valid:
                item = self.bg_animation_list.item(row)
                if item is not None:
                    item.setSelected(True)
            if valid:
                self.bg_animation_list.setCurrentRow(valid[-1])
        finally:
            self._designer_updating = False
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_selection(valid, emit_signal=False)
        self._refresh_animation_studio_preview()
        self._update_animation_performance_hint()

    def select_last_animation_frame(self) -> None:
        if not hasattr(self, "bg_animation_list") or self.bg_animation_list.count() <= 0:
            return
        self.select_animation_frame(self.bg_animation_list.count() - 1)

    def set_animation_loop_in(self) -> None:
        self._set_animation_loop_edge("in")

    def set_animation_loop_out(self) -> None:
        self._set_animation_loop_edge("out")

    def _set_animation_loop_edge(self, edge: str) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        current = seq.current_frame
        start = seq.loop_start if seq.loop_start is not None else 0
        end = seq.loop_end if seq.loop_end is not None else seq.frame_count - 1
        if edge == "in":
            start = current
        else:
            end = current
        self.push_designer_history()
        seq = controller.set_loop_range(start, end)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._refresh_animation_frame_list()
        loop_start = seq.loop_start if seq.loop_start is not None else 0
        loop_end = seq.loop_end if seq.loop_end is not None else max(0, seq.frame_count - 1)
        self.preview_info_label.setText(
            self._tr(
                f"Preview loop set to frames {loop_start + 1}-{loop_end + 1}.",
                f"Pętla podglądu ustawiona na klatki {loop_start + 1}-{loop_end + 1}.",
            )
        )
        self.schedule_preview_theme_doc()

    def clear_animation_loop_range(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if seq.loop_start is None and seq.loop_end is None:
            return
        self.push_designer_history()
        controller.clear_loop_range()
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._refresh_animation_frame_list()
        self.preview_info_label.setText(self._tr("Preview loop cleared.", "Wyczyszczono pętlę podglądu."))
        self.schedule_preview_theme_doc()

    def apply_bulk_animation_duration(self) -> None:
        if self.theme_doc_model is None:
            return
        rows = self._selected_animation_rows(fallback_current=False)
        if not rows:
            QMessageBox.information(
                self,
                self._tr("Animation", "Animacja"),
                self._tr(
                    "Select one or more frames in the list (Ctrl/Shift+click).",
                    "Zaznacz jedną lub więcej klatek na liście (Ctrl/Shift+klik).",
                ),
            )
            return
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        ms = max(1, int(self.animation_bulk_duration_spin.value()))
        self.push_designer_history()
        controller.apply_duration(rows, ms)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self.schedule_preview_theme_doc()

    def _theme_base_dir(self) -> Path:
        raw = self.theme_doc_path_edit.text().strip()
        if raw:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            if path.suffix.lower() == ".json":
                return path.parent
            return path
        return (Path.cwd() / "themes").resolve()

    def _theme_assets_dir(self) -> Path:
        raw = self.theme_doc_path_edit.text().strip()
        day_stamp = time.strftime("%Y-%m-%d")
        if raw:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            if path.suffix.lower() == ".json":
                return path.parent / f"{path.stem}_assets" / day_stamp
        return self._theme_base_dir() / "assets" / day_stamp

    def _suggest_theme_asset_output(self, source_path: Path, asset_kind: str) -> Path:
        assets_dir = self._theme_assets_dir() / asset_kind
        assets_dir.mkdir(parents=True, exist_ok=True)
        theme_name = "theme"
        raw = self.theme_doc_path_edit.text().strip()
        if raw:
            path = Path(raw).expanduser()
            theme_name = path.stem or "theme"
        stem = f"{theme_name}_{source_path.stem}"
        suffix = ".jpg"
        candidate = assets_dir / f"{stem}_{asset_kind}_trofeo{suffix}"
        idx = 2
        while candidate.exists():
            candidate = assets_dir / f"{stem}_{asset_kind}_trofeo_{idx}{suffix}"
            idx += 1
        return candidate

    def _theme_display_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self._theme_base_dir().resolve()))
        except Exception:
            return str(path.resolve())

    def _resolve_theme_asset_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        theme_candidate = (self._theme_base_dir() / candidate).resolve()
        if theme_candidate.exists():
            return theme_candidate
        theme_name_candidate = (self._theme_base_dir() / candidate.name).resolve()
        if theme_name_candidate.exists():
            return theme_name_candidate
        cwd_candidate = (Path.cwd() / candidate).resolve()
        if cwd_candidate.exists():
            return cwd_candidate
        cwd_name_candidate = (Path.cwd() / candidate.name).resolve()
        if cwd_name_candidate.exists():
            return cwd_name_candidate
        return cwd_candidate

    def _suggest_ttcr_import_output_path(self, source_path: Path) -> Path:
        themes_dir = (Path.cwd() / "themes").resolve()
        themes_dir.mkdir(parents=True, exist_ok=True)
        stem = source_path.stem if source_path.is_file() else source_path.name
        stem = "".join(ch.lower() if ch.isalnum() else "_" for ch in stem).strip("_") or "motyw"
        candidate = themes_dir / f"{stem}_ttcr_import.json"
        index = 2
        while candidate.exists():
            candidate = themes_dir / f"{stem}_ttcr_import_{index}.json"
            index += 1
        return candidate

    def _set_image_preview_label(self, label: QLabel, raw_path: str, *, empty_text: str) -> None:
        path = raw_path.strip()
        if not path:
            label.setPixmap(QPixmap())
            label.setText(empty_text)
            return
        resolved = self._resolve_theme_asset_path(path)
        pixmap = QPixmap(str(resolved))
        if pixmap.isNull():
            label.setPixmap(QPixmap())
            label.setText(empty_text)
            return
        label.setText("")
        label.setPixmap(pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _empty_background_preview_caption(self) -> str:
        return self._tr(
            "No background preview. Select an image, animation frame, or generated background.",
            "Brak podglądu tła. Wybierz obraz, klatkę animacji albo tło generowane.",
        )

    def _current_media_dynamic_path(self, source: str = "media_cover") -> str:
        if not shutil.which("playerctl"):
            return ""
        try:
            payload = subprocess.check_output(
                [
                    "playerctl",
                    "-a",
                    "metadata",
                    "--format",
                    "{{playerName}}\t{{status}}\t{{xesam:title}}\t{{xesam:artist}}\t{{mpris:artUrl}}\t{{xesam:url}}\t{{xesam:album}}",
                ],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
                timeout=0.5,
            ).strip()
        except Exception:
            return ""
        best_path = ""
        best_score = -1
        if not hasattr(self, "_media_preview_stats_provider"):
            self._media_preview_stats_provider = StatsProvider()
        for line in payload.splitlines():
            parts = line.split("\t")
            player = parts[0].strip() if len(parts) > 0 else ""
            state = parts[1].strip().lower() if len(parts) > 1 else "stopped"
            title = parts[2].strip() if len(parts) > 2 else ""
            artist = parts[3].strip() if len(parts) > 3 else ""
            art_url = parts[4].strip() if len(parts) > 4 else ""
            media_url = parts[5].strip() if len(parts) > 5 else ""
            album = parts[6].strip() if len(parts) > 6 else ""
            cover_path = self._media_preview_stats_provider.resolve_media_cover_path(
                art_url,
                player_name=player,
                title=title,
                artist=artist,
                album=album,
            )
            score = 2 if state == "playing" else (1 if state == "paused" else 0)
            if score > best_score:
                if source == "media_video_frame" and media_url:
                    frame_path = self._media_preview_stats_provider.resolve_media_video_frame_path(media_url, cover_path)
                    candidate_path = frame_path or cover_path
                else:
                    candidate_path = cover_path
                if candidate_path and os.path.exists(candidate_path):
                    best_score = score
                    best_path = candidate_path
        if source == "media_video_frame":
            return best_path
        return best_path

    def _current_media_cover_path(self) -> str:
        return self._current_media_dynamic_path("media_cover")

    def animate_preview_flash(self) -> None:
        if hasattr(self, "preview_label"):
            self.preview_label.update()

    def pick_color_for_edit(self, target_edit: QLineEdit) -> None:
        current = self._parse_color_line(target_edit.text(), [255, 255, 255])
        qcolor = QColor(current[0], current[1], current[2])
        chosen = QColorDialog.getColor(qcolor, self, "Wybierz kolor")
        if not chosen.isValid():
            return
        target_edit.setText(json.dumps([chosen.red(), chosen.green(), chosen.blue()], ensure_ascii=False))
        self._refresh_all_color_previews()

    def _apply_color_preview_style(self, button: QPushButton, target_edit: QLineEdit) -> None:
        color = self._parse_color_line(target_edit.text(), [40, 48, 60])
        fg = "#000000" if sum(color[:3]) > 420 else "#ffffff"
        button.setStyleSheet(
            f"background: rgb({color[0]}, {color[1]}, {color[2]});"
            "border: 1px solid #46506a; border-radius: 8px; padding: 4px 8px;"
            f"color: {fg};"
        )

    def _refresh_all_color_previews(self) -> None:
        mapping = [
            (getattr(self, "designer_color_btn", None), getattr(self, "designer_color_edit", None)),
            (getattr(self, "designer_label_color_btn", None), getattr(self, "designer_label_color_edit", None)),
            (getattr(self, "designer_value_color_btn", None), getattr(self, "designer_value_color_edit", None)),
            (getattr(self, "bg_base_color_btn", None), getattr(self, "bg_base_color_edit", None)),
            (getattr(self, "bg_accent_color_btn", None), getattr(self, "bg_accent_color_edit", None)),
            (getattr(self, "panel_fill_btn", None), getattr(self, "panel_fill_edit", None)),
            (getattr(self, "designer_gauge_low_btn", None), getattr(self, "designer_gauge_low_edit", None)),
            (getattr(self, "designer_gauge_mid_btn", None), getattr(self, "designer_gauge_mid_edit", None)),
            (getattr(self, "designer_gauge_high_btn", None), getattr(self, "designer_gauge_high_edit", None)),
        ]
        for button, edit in mapping:
            if button is not None and edit is not None:
                self._apply_color_preview_style(button, edit)

    def apply_theme_color_preset(self, preset_name: str) -> None:
        preset = THEME_COLOR_PRESETS.get(preset_name)
        if not preset:
            return
        self.bg_base_color_edit.setText(json.dumps(preset["base"], ensure_ascii=False))
        self.bg_accent_color_edit.setText(json.dumps(preset["accent"], ensure_ascii=False))
        self.panel_fill_edit.setText(json.dumps(preset["panel"], ensure_ascii=False))
        collection = self._selected_collection()
        if collection == "texts":
            self.designer_color_edit.setText(json.dumps(preset["text"], ensure_ascii=False))
        elif collection == "stats":
            self.designer_label_color_edit.setText(json.dumps(preset["label"], ensure_ascii=False))
            self.designer_value_color_edit.setText(json.dumps(preset["value"], ensure_ascii=False))
        self._refresh_all_color_previews()
        self.on_background_field_changed()
        if collection in {"texts", "stats"}:
            self.on_designer_field_changed()

    def _run_theme_image_import(self, source_path: Path, *, asset_kind: str, button_text: str) -> Path | None:
        if not self._image_tools_available():
            QMessageBox.warning(
                self,
                self._tr("Pillow not installed", "Brak Pillow"),
                self._tr(
                    "Image preparation is not available in this environment.",
                    "Moduł przygotowania obrazów nie jest dostępny.",
                ),
            )
            return None
        out_path = self._suggest_theme_asset_output(source_path, asset_kind)
        dlg = ImagePrepDialog(
            self,
            source_path,
            suggested_output_path=out_path,
            accept_button_text=button_text,
        )
        if dlg.exec() != QDialog.Accepted or dlg.output_path is None:
            return None
        return dlg.output_path

    def _copy_animation_frame_asset(self, source_path: Path, *, prefix: str = "frame") -> Path:
        assets_dir = self._theme_assets_dir() / "animation_frames"
        assets_dir.mkdir(parents=True, exist_ok=True)
        raw = self.theme_doc_path_edit.text().strip()
        theme_name = "theme"
        if raw:
            path = Path(raw).expanduser()
            theme_name = path.stem or "theme"
        stem = f"{theme_name}_{prefix}_{source_path.stem}"
        suffix = source_path.suffix.lower() or ".jpg"
        candidate = assets_dir / f"{stem}{suffix}"
        idx = 2
        while candidate.exists():
            candidate = assets_dir / f"{stem}_{idx}{suffix}"
            idx += 1
        shutil.copy2(source_path, candidate)
        return candidate

    @classmethod
    def _copy_animation_frame_asset_for_worker(
        cls,
        source_path: Path,
        *,
        target_dir: Path,
        theme_stem: str,
        base_dir: Path,
        prefix: str,
    ) -> str:
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{theme_stem}_{prefix}_{source_path.stem}"
        suffix = source_path.suffix.lower() or ".jpg"
        candidate = target_dir / f"{stem}{suffix}"
        idx = 2
        while candidate.exists():
            candidate = target_dir / f"{stem}_{idx}{suffix}"
            idx += 1
        shutil.copy2(source_path, candidate)
        return cls._display_path_for_base(candidate, base_dir)

    def _animation_controller(self) -> AnimationSequenceController | None:
        if self.theme_doc_model is None:
            return None
        return AnimationSequenceController(self.theme_doc_model)

    def _current_animation_effect(self) -> dict[str, object]:
        controller = self._animation_controller()
        if controller is None:
            return {}
        controller.normalize()
        return controller.animation()

    def _refresh_animation_controls(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        count = len(frame_paths)
        default_duration = max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
        if len(frame_durations) < count:
            frame_durations = frame_durations + [default_duration] * (count - len(frame_durations))
            animation["frame_durations_ms"] = frame_durations
        elif len(frame_durations) > count:
            frame_durations = frame_durations[:count]
            animation["frame_durations_ms"] = frame_durations
        current_frame = min(max(0, int(animation.get("current_frame", 0))), max(0, count - 1))
        self._designer_updating = True
        try:
            self.bg_animation_enabled_chk.setChecked(bool(animation.get("enabled", False)))
            self.bg_animation_use_bg_chk.setChecked(bool(animation.get("use_as_background", True)))
            self.bg_animation_fps_spin.setValue(float(animation.get("fps", 12.0)))
            self.bg_animation_frame_spin.setMaximum(max(0, count - 1))
            self.bg_animation_frame_spin.setValue(current_frame)
            self.bg_animation_duration_spin.setValue(frame_durations[current_frame] if count and current_frame < len(frame_durations) else default_duration)
            self.bg_animation_count_label.setText(self._format_animation_frame_count(count))
        finally:
            self._designer_updating = False
        has_frames = count > 0
        self.bg_animation_enabled_chk.setEnabled(has_frames)
        self.bg_animation_use_bg_chk.setEnabled(has_frames)
        self.bg_animation_fps_spin.setEnabled(has_frames)
        self.bg_animation_frame_spin.setEnabled(has_frames)
        self.bg_animation_prev_btn.setEnabled(has_frames)
        self.bg_animation_next_btn.setEnabled(has_frames)
        self.bg_animation_clear_btn.setEnabled(has_frames)
        self.bg_animation_duration_spin.setEnabled(has_frames)
        self._refresh_animation_frame_list()
        self._update_animation_preview_timer()

    def _current_animation_preview_path(self) -> str:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            return ""
        index = min(max(0, int(animation.get("current_frame", 0))), len(frame_paths) - 1)
        raw = str(frame_paths[index]).strip()
        return raw

    def _collect_animation_frame_paths(self, sources: list[Path]) -> list[str]:
        return self._collect_animation_frame_paths_for_worker(
            sources,
            target_dir=self._theme_assets_dir() / "animation_frames",
            theme_stem=Path(self.theme_doc_path_edit.text() or "theme").stem,
            base_dir=self._theme_base_dir(),
        )

    @staticmethod
    def _display_path_for_base(path: Path, base_dir: Path) -> str:
        try:
            return str(path.resolve().relative_to(base_dir.resolve()))
        except Exception:
            return str(path.resolve())

    @staticmethod
    def _raise_if_worker_cancelled(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Animation task cancelled.")

    @classmethod
    def _collect_animation_frame_paths_for_worker(
        cls,
        sources: list[Path],
        *,
        target_dir: Path,
        theme_stem: str,
        base_dir: Path,
        cancel_event: threading.Event | None = None,
        progress_callback: Any | None = None,
    ) -> list[str]:
        copied_paths: list[str] = []
        target_dir.mkdir(parents=True, exist_ok=True)
        if len(sources) == 1 and sources[0].suffix.lower() == ".zt":
            cls._raise_if_worker_cancelled(cancel_event)
            if extract_ttcr_zt_frames is None:
                return []
            frames = extract_ttcr_zt_frames(sources[0], target_dir, f"{theme_stem}_anim")
            for frame in frames:
                cls._raise_if_worker_cancelled(cancel_event)
                copied_paths.append(cls._display_path_for_base(frame, base_dir))
                if callable(progress_callback):
                    progress_callback(len(copied_paths), max(1, len(frames)), "Import TTCR frames")
            return copied_paths
        total = max(1, len(sources))
        for source_index, source in enumerate(sources):
            cls._raise_if_worker_cancelled(cancel_event)
            if not source.exists():
                continue
            stem = f"{theme_stem}_anim_{source.stem}"
            suffix = source.suffix.lower() or ".jpg"
            candidate = target_dir / f"{stem}{suffix}"
            idx = 2
            while candidate.exists():
                candidate = target_dir / f"{stem}_{idx}{suffix}"
                idx += 1
            shutil.copy2(source, candidate)
            copied_paths.append(cls._display_path_for_base(candidate, base_dir))
            if callable(progress_callback):
                progress_callback(source_index + 1, total, "Copy animation frames")
        return copied_paths

    def _render_current_animation_frame_image(self) -> "Image.Image | None":
        if render_theme_document is None or self.theme_doc_model is None:
            return None
        try:
            document = normalize_theme_document(self.theme_doc_model)
            return render_theme_document(
                ThemeDocument(document),
                base_dir=self._theme_base_dir(),
                stats_provider=self._preview_stats_provider,
            )
        except Exception:
            return None

    def _create_blank_animation_frame_asset(self, width: int = 1920, height: int = 462) -> Path | None:
        if render_theme_document is None:
            return None
        try:
            from PIL import Image
        except Exception:
            return None
        out_path = self._suggest_theme_asset_output(Path("blank_frame.png"), "animation_frames")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), (0, 0, 0)).save(out_path)
        return out_path

    def _set_current_animation_frame(self, index: int, *, persist: bool, render_preview: bool = True) -> None:
        controller = self._animation_controller()
        if controller is None:
            self._refresh_animation_controls()
            return
        seq = controller.set_current_frame(index)
        animation = controller.animation()
        frame_paths = seq.frame_paths
        if not frame_paths:
            self._refresh_animation_controls()
            return
        clamped = seq.current_frame
        self._designer_updating = True
        try:
            self.bg_animation_frame_spin.setValue(clamped)
            self.bg_animation_list.setCurrentRow(clamped)
        finally:
            self._designer_updating = False
        self._refresh_animation_controls()
        self._set_image_preview_label(
            self.background_preview_label,
            self._current_animation_preview_path() if bool(animation.get("use_as_background", True)) else self.bg_path_edit.text(),
            empty_text=self._empty_background_preview_caption(),
        )
        if persist:
            self.write_designer_to_json()
        if (
            render_preview
            and self._animation_edit_mode_enabled()
            and bool(animation.get("enabled", False))
            and bool(animation.get("use_as_background", True))
        ):
            self.preview_theme_doc()
        elif hasattr(self, "preview_info_label") and bool(animation.get("enabled", False)):
            self.preview_info_label.setText(
                self._tr(
                    f"Selected frame {clamped + 1}/{len(frame_paths)}. In normal mode run full render manually.",
                    f"Wybrano klatkę {clamped + 1}/{len(frame_paths)}. W trybie zwykłym pełny render uruchamiasz ręcznie.",
                )
            )
        self._refresh_animation_studio_preview()
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_playhead(clamped)
        self._scroll_animation_timeline_to_playhead()

    def _set_current_animation_frame_lightweight(self, index: int) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.set_current_frame(index)
        animation = controller.animation()
        if not seq.frame_paths:
            return
        clamped = seq.current_frame
        self._designer_updating = True
        try:
            if hasattr(self, "bg_animation_frame_spin"):
                self.bg_animation_frame_spin.setValue(clamped)
            if hasattr(self, "bg_animation_duration_spin") and clamped < len(seq.frame_durations_ms):
                self.bg_animation_duration_spin.setValue(seq.frame_durations_ms[clamped])
            if hasattr(self, "bg_animation_list"):
                self.bg_animation_list.blockSignals(True)
                self.bg_animation_list.setCurrentRow(clamped)
                self.bg_animation_list.blockSignals(False)
        finally:
            self._designer_updating = False
        self._set_image_preview_label(
            self.background_preview_label,
            self._current_animation_preview_path() if bool(animation.get("use_as_background", True)) else self.bg_path_edit.text(),
            empty_text=self._empty_background_preview_caption(),
        )
        self._refresh_animation_studio_preview()
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_playhead(clamped)
        self._scroll_animation_timeline_to_playhead()

    def _scroll_animation_timeline_to_playhead(self) -> None:
        scroll = getattr(self, "bg_animation_timeline_scroll", None)
        tw = getattr(self, "bg_animation_timeline", None)
        if scroll is None or tw is None:
            return
        cx = tw.playhead_center_x()
        if cx is None:
            return
        vp = max(1, scroll.viewport().width())
        hb = scroll.horizontalScrollBar()
        target = max(0, int(cx - vp // 2))
        target = min(hb.maximum(), target)
        hb.setValue(target)
        if hb.maximum() == 0 and tw.width() > vp:
            QTimer.singleShot(0, lambda: self._scroll_animation_timeline_to_playhead())

    def _maybe_warn_animation_frame_count(self, count: int) -> None:
        if count < ANIMATION_FRAMES_SOFT_WARN:
            return
        title = self._tr("Animation", "Animacja")
        if count >= ANIMATION_FRAMES_EXTREME_WARN:
            QMessageBox.warning(
                self,
                title,
                self._tr(
                    f"You have {count} frames. This is allowed, but the LCD path keeps RGB frames in memory and sends them over USB. "
                    "Check real playback, loop continuity, frame size, and live overlay cost.",
                    f"Masz {count} klatek. To jest dozwolone, ale tor LCD trzyma klatki RGB w pamięci i wysyła je po USB. "
                    "Sprawdź realne odtwarzanie, ciągłość pętli, rozmiar ramek i koszt nakładek live.",
                ),
            )
        elif count >= ANIMATION_FRAMES_STRONG_WARN:
            QMessageBox.information(
                self,
                title,
                self._tr(
                    f"{count} frames increases LCD memory and USB transfer cost. If playback stutters, lower FPS, slow timing, or simplify overlays.",
                    f"{count} klatek zwiększa koszt pamięci LCD i transferu USB. Jeśli odtwarzanie się przycina, obniż FPS, wydłuż czasy albo uprość nakładki.",
                ),
            )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        from PySide6.QtGui import QKeyEvent

        if event.type() == QEvent.Type.Wheel and (
            watched is getattr(self, "bg_animation_timeline", None)
            or watched is getattr(getattr(self, "bg_animation_timeline_scroll", None), "viewport", lambda: None)()
        ):
            wheel = event
            if wheel.modifiers() & Qt.ControlModifier:
                delta = wheel.angleDelta().y() or wheel.angleDelta().x()
                if delta > 0:
                    self.zoom_animation_timeline_in()
                elif delta < 0:
                    self.zoom_animation_timeline_out()
                return True
            scroll = getattr(self, "bg_animation_timeline_scroll", None)
            if scroll is not None:
                delta = wheel.angleDelta().x() or wheel.angleDelta().y()
                if delta:
                    hb = scroll.horizontalScrollBar()
                    hb.setValue(max(hb.minimum(), min(hb.maximum(), hb.value() - int(delta))))
                    return True

        if watched is getattr(self, "bg_animation_list", None) and event.type() == QEvent.Type.KeyPress:
            ke = event  # type: QKeyEvent
            if ke.key() == Qt.Key.Key_Left:
                row = self.bg_animation_list.currentRow()
                self.select_animation_frame(max(0, row - 1))
                return True
            if ke.key() == Qt.Key.Key_Right:
                row = self.bg_animation_list.currentRow()
                self.select_animation_frame(min(self.bg_animation_list.count() - 1, row + 1))
                return True
        if (
            watched is getattr(getattr(self, "theme_browser_scroll", None), "viewport", lambda: None)()
            and event.type() == QEvent.Type.Resize
        ):
            self._schedule_library_theme_browser_rebuild()
        return super().eventFilter(watched, event)

    def _refresh_animation_frame_list(self, *, preserve_selection: bool = True) -> None:
        if not hasattr(self, "bg_animation_list"):
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        current = min(max(0, int(animation.get("current_frame", 0))), max(0, len(frame_paths) - 1))
        prev_sel: set[int] = set()
        if preserve_selection:
            prev_sel = {idx.row() for idx in self.bg_animation_list.selectedIndexes()}
        self.bg_animation_list.blockSignals(True)
        self.bg_animation_list.clear()
        thumbnail_jobs: list[dict[str, Any]] = []
        thumbnail_job_keys: set[tuple[str, int]] = set()
        for idx, raw in enumerate(frame_paths):
            resolved = self._resolve_theme_asset_path(str(raw))
            duration_ms = frame_durations[idx] if idx < len(frame_durations) else max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
            item = QListWidgetItem(f"{idx + 1:03d}  {Path(str(raw)).name}  ·  {duration_ms} ms")
            item.setData(Qt.UserRole, str(raw))
            if resolved.exists():
                cache_key = self._animation_thumbnail_cache_key(resolved)
                cached = self._image_thumbnail_cache.get(cache_key)
                if len(frame_paths) <= ANIMATION_LIST_THUMB_MAX_FRAMES and cached is not None and not cached.isNull():
                    item.setIcon(QIcon(cached))
                if cached is None or cached.isNull():
                    should_build_for_list = len(frame_paths) <= ANIMATION_LIST_THUMB_MAX_FRAMES
                    should_build_for_timeline = len(frame_paths) <= ANIMATION_TIMELINE_THUMB_MAX_FRAMES
                    if (should_build_for_list or should_build_for_timeline) and cache_key not in thumbnail_job_keys:
                        thumbnail_job_keys.add(cache_key)
                        thumbnail_jobs.append(
                            {
                                "row": idx,
                                "raw": str(raw),
                                "path": str(resolved),
                                "mtime": cache_key[1],
                            }
                        )
            item.setToolTip(str(resolved))
            self.bg_animation_list.addItem(item)
        if frame_paths:
            valid_sel = {r for r in prev_sel if preserve_selection and 0 <= r < len(frame_paths)}
            if valid_sel:
                for r in sorted(valid_sel):
                    it = self.bg_animation_list.item(r)
                    if it is not None:
                        it.setSelected(True)
            self.bg_animation_list.setCurrentRow(current)
        self.bg_animation_list.blockSignals(False)
        if hasattr(self, "bg_animation_timeline"):
            sel_list = sorted({i.row() for i in self.bg_animation_list.selectedIndexes()})
            if not sel_list and frame_paths:
                sel_list = [current]
            timeline_thumbnails: dict[int, QPixmap] = {}
            for idx, raw in enumerate(frame_paths):
                resolved = self._resolve_theme_asset_path(str(raw))
                cache_key = self._animation_thumbnail_cache_key(resolved)
                cached = self._image_thumbnail_cache.get(cache_key)
                if cached is not None and not cached.isNull():
                    timeline_thumbnails[idx] = cached
                elif (
                    resolved.exists()
                    and len(frame_paths) <= ANIMATION_TIMELINE_THUMB_MAX_FRAMES
                    and cache_key not in thumbnail_job_keys
                ):
                    thumbnail_job_keys.add(cache_key)
                    thumbnail_jobs.append(
                        {
                            "row": idx,
                            "raw": str(raw),
                            "path": str(resolved),
                            "mtime": cache_key[1],
                        }
                    )
            self.bg_animation_timeline.set_timeline(
                frame_durations[: len(frame_paths)],
                current,
                selection=sel_list,
                playhead=current,
                loop_range=self._current_animation_loop_range(),
                thumbnails=timeline_thumbnails,
            )
        self._scroll_animation_timeline_to_playhead()
        has_selection = self.bg_animation_list.currentRow() >= 0
        duplicate_busy = bool(getattr(self, "_animation_duplicate_in_flight", False))
        stabilize_busy = bool(getattr(self, "_animation_stabilize_in_flight", False))
        self.bg_animation_remove_btn.setEnabled(has_selection)
        self.bg_animation_duplicate_btn.setEnabled(has_selection and not duplicate_busy)
        if hasattr(self, "bg_animation_hold_repeat_btn"):
            self.bg_animation_hold_repeat_btn.setEnabled(has_selection)
        has_frames = bool(frame_paths)
        export_busy = bool(getattr(self, "_animation_export_in_flight", False))
        if hasattr(self, "bg_animation_export_btn"):
            self.bg_animation_export_btn.setEnabled(has_frames and not export_busy)
        if hasattr(self, "animation_export_loop_btn"):
            self.animation_export_loop_btn.setEnabled(
                has_frames and self._current_animation_loop_range() is not None and not export_busy
            )
        if hasattr(self, "animation_export_selection_btn"):
            self.animation_export_selection_btn.setEnabled(has_selection and not export_busy)
        can_montage = len(frame_paths) > 1
        if hasattr(self, "bg_animation_reverse_btn"):
            self.bg_animation_reverse_btn.setEnabled(can_montage)
        if hasattr(self, "bg_animation_pingpong_btn"):
            self.bg_animation_pingpong_btn.setEnabled(can_montage)
        if hasattr(self, "bg_animation_normalize_duration_btn"):
            self.bg_animation_normalize_duration_btn.setEnabled(has_frames)
        if hasattr(self, "animation_stabilize_btn"):
            self.animation_stabilize_btn.setEnabled(len(frame_paths) > 1 and not stabilize_busy)
        if hasattr(self, "animation_stabilize_mode_combo"):
            self.animation_stabilize_mode_combo.setEnabled(len(frame_paths) > 1 and not stabilize_busy)
        if hasattr(self, "animation_select_range_btn"):
            self.animation_select_range_btn.setEnabled(has_frames)
        if hasattr(self, "animation_invert_selection_btn"):
            self.animation_invert_selection_btn.setEnabled(has_frames)
        if hasattr(self, "animation_clear_selection_btn"):
            self.animation_clear_selection_btn.setEnabled(has_frames)
        if hasattr(self, "animation_loop_in_btn"):
            self.animation_loop_in_btn.setEnabled(has_frames)
        if hasattr(self, "animation_loop_out_btn"):
            self.animation_loop_out_btn.setEnabled(has_frames)
        if hasattr(self, "animation_loop_clear_btn"):
            self.animation_loop_clear_btn.setEnabled(self._current_animation_loop_range() is not None)
        if hasattr(self, "animation_loop_close_seam_btn"):
            self.animation_loop_close_seam_btn.setEnabled(len(frame_paths) > 1)
        if hasattr(self, "animation_loop_label"):
            loop_range = self._current_animation_loop_range()
            if loop_range is None:
                self.animation_loop_label.setText(self._tr("Loop: full", "Pętla: całość"))
            else:
                self.animation_loop_label.setText(
                    self._tr(
                        f"Loop: {loop_range[0] + 1}-{loop_range[1] + 1}",
                        f"Pętla: {loop_range[0] + 1}-{loop_range[1] + 1}",
                    )
                )
        if hasattr(self, "bg_animation_repeat_all_btn"):
            self.bg_animation_repeat_all_btn.setEnabled(has_frames and not duplicate_busy)
        self.bg_animation_up_btn.setEnabled(has_selection and self.bg_animation_list.currentRow() > 0)
        self.bg_animation_down_btn.setEnabled(has_selection and self.bg_animation_list.currentRow() < len(frame_paths) - 1)
        self._start_animation_thumbnail_worker(thumbnail_jobs)
        self._refresh_animation_studio_preview()

    def _animation_thumbnail_cache_key(self, path: Path) -> tuple[str, int]:
        try:
            return str(path.resolve()), int(path.stat().st_mtime_ns)
        except Exception:
            return str(path.resolve()), 0

    def _start_animation_thumbnail_worker(self, jobs: list[dict[str, Any]]) -> None:
        if not jobs:
            if not getattr(self, "_animation_thumbnail_in_flight", False):
                self._set_animation_worker_state("thumbnails", None)
            return
        pending = getattr(self, "_animation_thumbnail_pending_jobs", {})
        if not isinstance(pending, dict):
            pending = {}
            self._animation_thumbnail_pending_jobs = pending
        for job in jobs:
            key = (str(job.get("path", "")), int(job.get("mtime", 0) or 0))
            if key[0]:
                pending[key] = job
        if getattr(self, "_animation_thumbnail_in_flight", False):
            self._set_animation_worker_state(
                "thumbnails",
                self._tr(
                    f"thumbnail queue: {len(pending)} pending",
                    f"kolejka miniaturek: {len(pending)}",
                ),
            )
            return
        self._drain_animation_thumbnail_queue()

    def _drain_animation_thumbnail_queue(self) -> None:
        pending = getattr(self, "_animation_thumbnail_pending_jobs", {})
        if not isinstance(pending, dict) or not pending:
            self._animation_thumbnail_in_flight = False
            self._set_animation_worker_state("thumbnails", None)
            return
        jobs = list(pending.values())
        pending.clear()
        self._animation_thumbnail_generation += 1
        generation = self._animation_thumbnail_generation
        self._animation_thumbnail_in_flight = True
        self._set_animation_worker_state(
            "thumbnails",
            self._tr(f"building {len(jobs)} thumbnails", f"miniatury: {len(jobs)}"),
        )

        def worker() -> None:
            results: list[dict[str, Any]] = []
            for job in jobs:
                path = Path(str(job.get("path", ""))).expanduser()
                image = QImage(str(path))
                if image.isNull():
                    continue
                scaled = image.scaled(96, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                results.append(
                    {
                        "row": int(job.get("row", -1)),
                        "raw": str(job.get("raw", "")),
                        "path": str(path.resolve()),
                        "mtime": int(job.get("mtime", 0)),
                        "image": scaled,
                    }
                )
            self.api_result.emit(f"animation-thumbnails::{generation}", True, {"result": {"items": results}})

        threading.Thread(target=worker, daemon=True).start()

    def _finish_animation_thumbnail_worker(self) -> None:
        self._animation_thumbnail_in_flight = False
        pending = getattr(self, "_animation_thumbnail_pending_jobs", {})
        if isinstance(pending, dict) and pending:
            QTimer.singleShot(0, self._drain_animation_thumbnail_queue)
        else:
            self._set_animation_worker_state("thumbnails", None)

    def _update_animation_preview_timer(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        should_run = (
            bool(self._animation_preview_active)
            and (
                self._animation_edit_mode_enabled()
                or (
                    hasattr(self, "main_tabs")
                    and hasattr(self, "studio_sections_tabs")
                    and self.main_tabs.currentIndex() == 1
                    and self.studio_sections_tabs.currentIndex() == 2
                )
            )
            and bool(animation.get("enabled", False))
            and bool(animation.get("use_as_background", True))
            and len(frame_paths) > 1
        )
        if should_run:
            current = min(max(0, int(animation.get("current_frame", 0))), len(frame_paths) - 1)
            default_interval = max(16, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
            interval_ms = default_interval
            if current < len(frame_durations):
                try:
                    interval_ms = max(16, int(frame_durations[current]))
                except Exception:
                    interval_ms = default_interval
            self.animation_preview_timer.start(interval_ms)
        else:
            self.animation_preview_timer.stop()
        if hasattr(self, "bg_animation_play_btn"):
            self.bg_animation_play_btn.setText(
                self._tr("⏸ Pause", "⏸ Pauza") if should_run else self._tr("▶ Play", "▶ Odtwórz")
            )

    def append_background_animation_frames(self) -> None:
        if getattr(self, "_animation_import_in_flight", False):
            return
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            self._tr("Add animation frames", "Dodaj klatki animacji"),
            str(Path.cwd()),
            self._tr(
                "Animation frames (*.zip *.zt *.jpg *.jpeg *.png *.webp *.bmp);;All files (*)",
                "Animacje/ramki (*.zip *.zt *.jpg *.jpeg *.png *.webp *.bmp);;All files (*)",
            ),
        )
        if not selected:
            return
        sources = [Path(item).expanduser() for item in selected]
        self._start_animation_frame_import(sources, mode="append")

    def duplicate_selected_animation_frames_bulk(self) -> None:
        if getattr(self, "_animation_duplicate_in_flight", False):
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        if not frame_paths:
            return
        times = max(1, int(self.animation_duplicate_repeat_spin.value()))
        rows = sorted({idx.row() for idx in self.bg_animation_list.selectedIndexes()})
        if not rows:
            row = self.bg_animation_list.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            QMessageBox.information(
                self,
                self._tr("Animation", "Animacja"),
                self._tr(
                    "Select frames in the list (Ctrl/Shift+click).",
                    "Zaznacz klatki na liście (Ctrl/Shift+klik).",
                ),
            )
            return
        default_ms = max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
        if len(frame_durations) < len(frame_paths):
            frame_durations.extend([default_ms] * (len(frame_paths) - len(frame_durations)))
        snapshot_paths = [str(frame_paths[r]) for r in rows]
        snapshot_durs = [int(frame_durations[r]) if r < len(frame_durations) else default_ms for r in rows]
        for sp in snapshot_paths:
            src = self._resolve_theme_asset_path(sp)
            if not src.exists():
                QMessageBox.warning(
                    self,
                    self._tr("Animation", "Animacja"),
                    self._tr("Frame file not found:\n{path}", "Nie znaleziono klatki:\n{path}").format(path=src),
                )
                return
        insert_at = rows[-1] + 1
        jobs = [
            {"source": str(self._resolve_theme_asset_path(sp)), "duration_ms": int(d)}
            for sp, d in zip(snapshot_paths, snapshot_durs, strict=True)
        ]
        self._start_animation_duplicate_worker(jobs, times=times, insert_at=insert_at, prefix="dup", mode="selection")

    def _start_animation_duplicate_worker(
        self,
        jobs: list[dict[str, Any]],
        *,
        times: int,
        insert_at: int,
        prefix: str,
        mode: str,
    ) -> None:
        if not jobs:
            return
        target_dir = self._theme_assets_dir() / "animation_frames"
        theme_stem = Path(self.theme_doc_path_edit.text() or "theme").stem or "theme"
        base_dir = self._theme_base_dir()
        self._set_animation_duplicate_busy(True)
        self.preview_info_label.setText(
            self._tr(
                f"Duplicating animation frames in background ({len(jobs)} ×{times}).",
                f"Duplikuję klatki animacji w tle ({len(jobs)} ×{times}).",
            )
        )

        def worker() -> None:
            try:
                copied: list[dict[str, Any]] = []
                for _ in range(max(1, int(times))):
                    for job in jobs:
                        source = Path(str(job.get("source", ""))).expanduser()
                        copied.append(
                            {
                                "path": self._copy_animation_frame_asset_for_worker(
                                    source,
                                    target_dir=target_dir,
                                    theme_stem=theme_stem,
                                    base_dir=base_dir,
                                    prefix=prefix,
                                ),
                                "duration_ms": int(job.get("duration_ms", 83)),
                            }
                        )
                self.api_result.emit(
                    "animation-duplicate",
                    True,
                    {
                        "result": {
                            "mode": mode,
                            "insert_at": int(insert_at),
                            "source_count": len(jobs),
                            "times": max(1, int(times)),
                            "frames": copied,
                        }
                    },
                )
            except Exception as exc:
                self.api_result.emit("animation-duplicate", False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_animation_duplicate(self, result: dict[str, Any]) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        frames = result.get("frames", [])
        if not isinstance(frames, list) or not frames:
            return
        insert_at = min(max(0, int(result.get("insert_at", len(frame_paths)))), len(frame_paths))
        self.push_designer_history()
        pos = insert_at
        for entry in frames:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path", "")).strip()
            if not path:
                continue
            frame_paths.insert(pos, path)
            frame_durations.insert(pos, max(1, int(entry.get("duration_ms", 83))))
            pos += 1
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations[: len(frame_paths)]
        animation["current_frame"] = min(max(insert_at, pos - 1), max(0, len(frame_paths) - 1))
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self.bg_animation_list.setCurrentRow(int(animation["current_frame"]))
        self._rebuild_theme_asset_gallery()
        self._maybe_warn_animation_frame_count(len(frame_paths))
        source_count = int(result.get("source_count", 0) or 0)
        times = int(result.get("times", 1) or 1)
        mode = str(result.get("mode", "selection"))
        if mode == "sequence":
            self.preview_info_label.setText(
                self._tr(
                    f"Appended full sequence ×{times} ({source_count} frames each).",
                    f"Dopisano całą sekwencję ×{times} ({source_count} klat.).",
                )
            )
        else:
            self.preview_info_label.setText(
                self._tr(
                    f"Duplicated {source_count} frame(s) ×{times}.",
                    f"Zduplikowano {source_count} klat. ×{times}.",
                )
            )
        self.schedule_preview_theme_doc()

    def _set_animation_duplicate_busy(self, busy: bool) -> None:
        self._animation_duplicate_in_flight = bool(busy)
        self._set_animation_worker_state(
            "duplicate",
            self._tr("duplicating frames", "duplikowanie klatek") if busy else None,
        )
        for button in (getattr(self, "bg_animation_duplicate_btn", None), getattr(self, "bg_animation_repeat_all_btn", None)):
            if button is not None:
                button.setEnabled(not busy)
        if hasattr(self, "bg_animation_duplicate_btn"):
            self.bg_animation_duplicate_btn.setText(
                self._tr("Duplicating…", "Duplikuję…") if busy else self._tr("Duplicate asset", "Duplikuj asset")
            )

    def stabilize_animation_frames(self) -> None:
        if getattr(self, "_animation_stabilize_in_flight", False):
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if len(frame_paths) < 2:
            QMessageBox.information(
                self,
                self._tr("Animation stabilization", "Stabilizacja animacji"),
                self._tr("At least two animation frames are required.", "Wymagane są co najmniej dwie klatki animacji."),
            )
            return
        rows = self._selected_animation_rows(fallback_current=False, fallback_all=False)
        if len(rows) < 2:
            rows = list(range(len(frame_paths)))
        current_row = self.bg_animation_list.currentRow() if hasattr(self, "bg_animation_list") else -1
        if current_row in rows:
            rows = [current_row] + [row for row in rows if row != current_row]
        jobs: list[dict[str, Any]] = []
        for row in rows:
            raw = str(frame_paths[row])
            resolved = self._resolve_theme_asset_path(raw)
            if not resolved.exists():
                QMessageBox.warning(
                    self,
                    self._tr("Animation stabilization", "Stabilizacja animacji"),
                    self._tr("Frame file not found:\n{path}", "Nie znaleziono klatki:\n{path}").format(path=resolved),
                )
                return
            jobs.append({"index": int(row), "raw": raw, "source": str(resolved)})
        target_dir = self._theme_assets_dir() / "animation_frames"
        theme_stem = Path(self.theme_doc_path_edit.text() or "theme").stem or "theme"
        base_dir = self._theme_base_dir()
        mode = "safe_translation"
        combo = getattr(self, "animation_stabilize_mode_combo", None)
        if combo is not None and isinstance(combo.currentData(), str):
            mode = str(combo.currentData())
        self._set_animation_stabilize_busy(True)
        self.preview_info_label.setText(
            self._tr(
                f"Stabilizing {len(jobs)} frame(s) in background with OpenCV ({mode}).",
                f"Stabilizuję {len(jobs)} klat. w tle przez OpenCV ({mode}).",
            )
        )

        def worker() -> None:
            try:
                result = self._stabilize_animation_frames_for_worker(
                    jobs,
                    target_dir=target_dir,
                    theme_stem=theme_stem,
                    base_dir=base_dir,
                    mode=mode,
                )
                self.api_result.emit("animation-stabilize", True, {"result": result})
            except Exception as exc:
                self.api_result.emit("animation-stabilize", False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    @classmethod
    def _stabilize_animation_frames_for_worker(
        cls,
        jobs: list[dict[str, Any]],
        *,
        target_dir: Path,
        theme_stem: str,
        base_dir: Path,
        mode: str = "auto_affine",
    ) -> dict[str, Any]:
        try:
            import cv2  # type: ignore[import-not-found]
            import numpy as np  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError(
                "OpenCV is required for stabilization. Install it in the GUI venv: "
                ".venv-gui/bin/pip install opencv-python-headless"
            ) from exc
        if len(jobs) < 2:
            raise ValueError("At least two frames are required for stabilization.")
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(ch.lower() if ch.isalnum() else "_" for ch in theme_stem).strip("_") or "theme"
        ref_job = jobs[0]
        ref_path = Path(str(ref_job.get("source", "")))
        ref = cv2.imread(str(ref_path), cv2.IMREAD_UNCHANGED)
        if ref is None:
            raise ValueError(f"Could not read reference frame: {ref_path}")
        ref_gray = cls._opencv_stabilize_gray(ref, cv2)
        replacements: list[dict[str, Any]] = []
        shifts: list[dict[str, Any]] = []
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 160, 1e-6)
        mode_order = cls._opencv_stabilize_mode_order(mode)
        failures = 0
        fallback_count = 0
        rejected_count = 0
        for job in jobs:
            idx = int(job.get("index", -1))
            source = Path(str(job.get("source", "")))
            frame = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
            if frame is None:
                raise ValueError(f"Could not read frame: {source}")
            warp = np.eye(2, 3, dtype=np.float32)
            used_mode = "reference"
            confidence = 1.0
            if idx != int(ref_job.get("index", -1)):
                gray = cls._opencv_stabilize_gray(frame, cv2)
                last_error: Exception | None = None
                for attempt, mode_name in enumerate(mode_order):
                    motion, initial_warp = cls._opencv_stabilize_motion(mode_name, np, cv2)
                    try:
                        cc, found = cv2.findTransformECC(
                            ref_gray,
                            gray,
                            initial_warp,
                            motion,
                            criteria,
                            None,
                            5,
                        )
                        if found.shape == (3, 3):
                            warp = found
                        else:
                            warp = found.astype(np.float32)
                        if not cls._opencv_stabilize_warp_is_safe(
                            mode,
                            mode_name,
                            warp,
                            ref_gray.shape[1],
                            ref_gray.shape[0],
                            float(cc),
                        ):
                            rejected_count += 1
                            last_error = RuntimeError(f"Rejected unsafe {mode_name} warp")
                            continue
                        used_mode = mode_name
                        confidence = float(cc)
                        if attempt > 0:
                            fallback_count += 1
                        break
                    except Exception as exc:
                        last_error = exc
                else:
                    failures += 1
                    used_mode = "identity"
                    confidence = 0.0
                    warp = np.eye(2, 3, dtype=np.float32)
                    if last_error is not None:
                        pass
            if warp.shape == (3, 3):
                stabilized = cv2.warpPerspective(
                    frame,
                    warp,
                    (ref_gray.shape[1], ref_gray.shape[0]),
                    flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                    borderMode=cv2.BORDER_REFLECT,
                )
            else:
                height, width = ref_gray.shape[:2]
                stabilized = cv2.warpAffine(
                    frame,
                    warp,
                    (width, height),
                    flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                    borderMode=cv2.BORDER_REFLECT,
                )
            if stabilized.shape[:2] != ref.shape[:2]:
                stabilized = cv2.resize(stabilized, (ref.shape[1], ref.shape[0]), interpolation=cv2.INTER_LINEAR)
            out = target_dir / f"{safe_stem}_stabilized_{idx:04d}.png"
            if not cv2.imwrite(str(out), stabilized):
                raise ValueError(f"Could not write stabilized frame: {out}")
            replacements.append({"index": idx, "path": cls._display_path_for_base(out, base_dir)})
            shifts.append(
                {
                    "index": idx,
                    "mode": used_mode,
                    "confidence": round(float(confidence), 5),
                    "dx": round(float(warp[0, 2]), 3),
                    "dy": round(float(warp[1, 2]), 3),
                }
            )
        return {
            "replacements": replacements,
            "count": len(replacements),
            "mode": mode,
            "fallback_count": fallback_count,
            "failure_count": failures,
            "rejected_count": rejected_count,
            "shifts": shifts,
        }

    @staticmethod
    def _opencv_stabilize_mode_order(mode: str) -> list[str]:
        normalized = str(mode or "auto_affine").strip().lower()
        if normalized == "safe_translation":
            return ["translation"]
        if normalized == "auto_safe":
            return ["euclidean", "translation"]
        if normalized == "translation":
            return ["translation"]
        if normalized == "euclidean":
            return ["euclidean", "translation"]
        if normalized == "affine":
            return ["affine", "euclidean", "translation"]
        return ["affine", "euclidean", "translation"]

    @staticmethod
    def _opencv_stabilize_motion(mode: str, np_module: Any, cv2_module: Any) -> tuple[int, Any]:
        normalized = str(mode).strip().lower()
        if normalized == "affine":
            return cv2_module.MOTION_AFFINE, np_module.eye(2, 3, dtype=np_module.float32)
        if normalized == "euclidean":
            return cv2_module.MOTION_EUCLIDEAN, np_module.eye(2, 3, dtype=np_module.float32)
        if normalized == "homography":
            return cv2_module.MOTION_HOMOGRAPHY, np_module.eye(3, 3, dtype=np_module.float32)
        return cv2_module.MOTION_TRANSLATION, np_module.eye(2, 3, dtype=np_module.float32)

    @staticmethod
    def _opencv_stabilize_warp_is_safe(
        requested_mode: str,
        used_mode: str,
        warp: Any,
        width: int,
        height: int,
        confidence: float,
    ) -> bool:
        requested = str(requested_mode or "").strip().lower()
        used = str(used_mode or "").strip().lower()
        safe_requested = requested.startswith("safe") or requested == "auto_safe"
        if not safe_requested:
            return True
        if confidence < 0.35:
            return False
        max_dx = max(12.0, float(width) * 0.18)
        max_dy = max(8.0, float(height) * 0.18)
        dx = abs(float(warp[0, 2]))
        dy = abs(float(warp[1, 2]))
        if dx > max_dx or dy > max_dy:
            return False
        if used == "translation":
            return True
        a = float(warp[0, 0])
        b = float(warp[0, 1])
        c = float(warp[1, 0])
        d = float(warp[1, 1])
        scale_x = (a * a + c * c) ** 0.5
        scale_y = (b * b + d * d) ** 0.5
        if not (0.94 <= scale_x <= 1.06 and 0.94 <= scale_y <= 1.06):
            return False
        shear = abs(a * b + c * d)
        if shear > 0.08:
            return False
        return True

    @staticmethod
    def _opencv_stabilize_gray(image: Any, cv2_module: Any) -> Any:
        if len(image.shape) == 2:
            gray = image
        elif image.shape[2] == 4:
            gray = cv2_module.cvtColor(image, cv2_module.COLOR_BGRA2GRAY)
        else:
            gray = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2GRAY)
        return cv2_module.GaussianBlur(gray, (5, 5), 0)

    def _finish_animation_stabilize(self, result: dict[str, Any]) -> None:
        replacements = result.get("replacements", [])
        if not isinstance(replacements, list) or not replacements:
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            return
        self.push_designer_history()
        changed = 0
        for entry in replacements:
            if not isinstance(entry, dict):
                continue
            try:
                idx = int(entry.get("index", -1))
            except Exception:
                continue
            path = str(entry.get("path", "")).strip()
            if 0 <= idx < len(frame_paths) and path:
                frame_paths[idx] = path
                changed += 1
        animation["frame_paths"] = frame_paths
        self.write_designer_to_json()
        self._image_thumbnail_cache.clear()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self._rebuild_theme_asset_gallery()
        mode = str(result.get("mode", "auto_affine"))
        fallback_count = int(result.get("fallback_count", 0) or 0)
        failure_count = int(result.get("failure_count", 0) or 0)
        rejected_count = int(result.get("rejected_count", 0) or 0)
        self.preview_info_label.setText(
            self._tr(
                f"Stabilized {changed} frame(s) ({mode}, fallbacks: {fallback_count}, rejected: {rejected_count}, failed: {failure_count}).",
                f"Ustabilizowano {changed} klat. ({mode}, fallbacki: {fallback_count}, odrzucone: {rejected_count}, błędy: {failure_count}).",
            )
        )
        self.schedule_preview_theme_doc()

    def _set_animation_stabilize_busy(self, busy: bool) -> None:
        self._animation_stabilize_in_flight = bool(busy)
        self._set_animation_worker_state(
            "stabilize",
            self._tr("stabilizing frames", "stabilizacja klatek") if busy else None,
        )
        if hasattr(self, "animation_stabilize_btn"):
            self.animation_stabilize_btn.setEnabled(not busy)
            self.animation_stabilize_btn.setText(
                self._tr("Stabilizing…", "Stabilizuję…") if busy else self._tr("Stabilize", "Stabilizuj")
            )
        if hasattr(self, "animation_stabilize_mode_combo"):
            self.animation_stabilize_mode_combo.setEnabled(not busy)

    def hold_selected_animation_frames_timing(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        times = max(1, int(self.animation_duplicate_repeat_spin.value()))
        rows = sorted({idx.row() for idx in self.bg_animation_list.selectedIndexes()})
        if not rows:
            row = self.bg_animation_list.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            QMessageBox.information(
                self,
                self._tr("Animation", "Animacja"),
                self._tr("Select one or more frames first.", "Najpierw zaznacz jedną lub więcej klatek."),
            )
            return
        self.push_designer_history()
        controller.repeat_timing(rows, times)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        for row in rows:
            item = self.bg_animation_list.item(row)
            if item is not None:
                item.setSelected(True)
        self.preview_info_label.setText(
            self._tr(
                f"Extended timing for {len(rows)} frame(s) ×{times} without copying files.",
                f"Wydłużono czas {len(rows)} klat. ×{times} bez kopiowania plików.",
            )
        )
        self.schedule_preview_theme_doc()

    def reverse_selected_animation_frames(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if seq.frame_count < 2:
            return
        rows = self._selected_animation_rows(fallback_current=False, fallback_all=True)
        self.push_designer_history()
        result = controller.reverse_indices(rows)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list(preserve_selection=False)
        affected = rows if len(rows) >= 2 else list(range(result.frame_count))
        for row in affected:
            item = self.bg_animation_list.item(row)
            if item is not None:
                item.setSelected(True)
        self.bg_animation_list.setCurrentRow(result.current_frame)
        self.preview_info_label.setText(
            self._tr(
                f"Reversed {len(affected)} animation frame(s).",
                f"Odwrócono {len(affected)} klat. animacji.",
            )
        )
        self.schedule_preview_theme_doc()

    def pingpong_selected_animation_frames(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if seq.frame_count < 2:
            return
        rows = self._selected_animation_rows(fallback_current=False, fallback_all=True)
        self.push_designer_history()
        before_count = seq.frame_count
        result = controller.ping_pong(rows)
        added = max(0, result.frame_count - before_count)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list(preserve_selection=False)
        if added:
            start = max(0, result.current_frame)
            for row in range(start, min(result.frame_count, start + added)):
                item = self.bg_animation_list.item(row)
                if item is not None:
                    item.setSelected(True)
            self.bg_animation_list.setCurrentRow(start)
        self._maybe_warn_animation_frame_count(result.frame_count)
        self.preview_info_label.setText(
            self._tr(
                f"Added ping-pong tail: {added} frame reference(s).",
                f"Dodano ogon ping-pong: {added} referencji klatek.",
            )
        )
        self.schedule_preview_theme_doc()

    def normalize_selected_animation_frame_durations(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        rows = self._selected_animation_rows(fallback_current=False, fallback_all=True)
        ms = max(1, int(self.animation_bulk_duration_spin.value()))
        self.push_designer_history()
        controller.apply_duration(rows, ms)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list(preserve_selection=False)
        for row in rows:
            item = self.bg_animation_list.item(row)
            if item is not None:
                item.setSelected(True)
        self.preview_info_label.setText(
            self._tr(
                f"Normalized {len(rows)} frame duration(s) to {ms} ms.",
                f"Wyrównano czas {len(rows)} klat. do {ms} ms.",
            )
        )
        self.schedule_preview_theme_doc()

    def duplicate_full_animation_sequence_bulk(self) -> None:
        if getattr(self, "_animation_duplicate_in_flight", False):
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        if not frame_paths:
            QMessageBox.information(
                self,
                self._tr("Animation", "Animacja"),
                self._tr("Add frames to the sequence first.", "Najpierw dodaj klatki do sekwencji."),
            )
            return
        times = max(1, int(self.animation_duplicate_repeat_spin.value()))
        default_ms = max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
        if len(frame_durations) < len(frame_paths):
            frame_durations.extend([default_ms] * (len(frame_paths) - len(frame_durations)))
        snapshot_paths = [str(p) for p in frame_paths]
        snapshot_durs = [int(frame_durations[i]) if i < len(frame_durations) else default_ms for i in range(len(frame_paths))]
        for sp in snapshot_paths:
            src = self._resolve_theme_asset_path(sp)
            if not src.exists():
                QMessageBox.warning(
                    self,
                    self._tr("Animation", "Animacja"),
                    self._tr("Frame file not found:\n{path}", "Nie znaleziono klatki:\n{path}").format(path=src),
                )
                return
        jobs = [
            {"source": str(self._resolve_theme_asset_path(sp)), "duration_ms": int(d)}
            for sp, d in zip(snapshot_paths, snapshot_durs, strict=True)
        ]
        self._start_animation_duplicate_worker(
            jobs,
            times=times,
            insert_at=len(frame_paths),
            prefix="seq",
            mode="sequence",
        )

    def insert_blank_animation_frame(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        blank = self._create_blank_animation_frame_asset()
        if blank is None:
            QMessageBox.warning(
                self,
                self._tr("Animation", "Animacja"),
                self._tr("Could not create a blank frame.", "Nie udało się utworzyć pustej klatki."),
            )
            return
        insert_at = self.bg_animation_list.currentRow()
        seq_before = controller.normalize()
        n_frames = seq_before.frame_count
        if insert_at < 0:
            insert_at = n_frames
        else:
            insert_at += 1
        self.push_designer_history()
        seq = controller.insert_frames(
            [self._theme_display_path(blank)],
            index=insert_at,
            duration_ms=max(1, int(self.bg_animation_duration_spin.value())),
        )
        animation = controller.animation()
        animation["enabled"] = True
        animation["use_as_background"] = True
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self.bg_animation_list.setCurrentRow(seq.current_frame)
        self._rebuild_theme_asset_gallery()
        self.preview_info_label.setText(self._tr("Added a blank animation frame.", "Dodano pustą klatkę animacji."))
        self.schedule_preview_theme_doc()

    def remove_selected_animation_frames(self) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        rows = sorted({idx.row() for idx in self.bg_animation_list.selectedIndexes()})
        if not rows:
            row = self.bg_animation_list.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            return
        self.push_designer_history()
        seq = controller.remove_indices(rows)
        animation = controller.animation()
        if not seq.frame_paths:
            animation["enabled"] = False
            animation["current_frame"] = 0
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self.schedule_preview_theme_doc()

    def move_selected_animation_frames(self, delta: int) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        rows = sorted({idx.row() for idx in self.bg_animation_list.selectedIndexes()})
        if len(rows) != 1:
            return
        row = rows[0]
        if row + int(delta) < 0 or row + int(delta) >= seq.frame_count:
            return
        self.push_designer_history()
        seq = controller.move_single(row, delta)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self.bg_animation_list.setCurrentRow(seq.current_frame)
        self.schedule_preview_theme_doc()

    def select_animation_frame(self, row: int) -> None:
        if self._designer_updating or row < 0:
            return
        self._set_current_animation_frame(row, persist=True)

    def on_animation_frames_reordered(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        if not frame_paths or self.bg_animation_list.count() != len(frame_paths):
            return
        path_to_duration: dict[str, int] = {}
        for idx, raw in enumerate(frame_paths):
            duration = frame_durations[idx] if idx < len(frame_durations) else max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
            path_to_duration[str(raw)] = duration
        new_paths: list[str] = []
        new_durations: list[int] = []
        for row in range(self.bg_animation_list.count()):
            item = self.bg_animation_list.item(row)
            raw_path = item.data(Qt.UserRole)
            if not isinstance(raw_path, str):
                continue
            new_paths.append(raw_path)
            new_durations.append(path_to_duration.get(raw_path, 83))
        if new_paths:
            self.push_designer_history()
            animation["frame_paths"] = new_paths
            animation["frame_durations_ms"] = new_durations
            current = self.bg_animation_list.currentRow()
            animation["current_frame"] = max(0, current)
            self.write_designer_to_json()
            self._refresh_animation_controls()
            self._sync_designer_preview_policy()
            self.schedule_preview_theme_doc()

    def export_animation_sequence(self) -> None:
        self._export_animation_sequence_for_indices(None, suffix="animation", scope_label=self._tr("full", "całość"))

    def export_animation_loop_range(self) -> None:
        loop_range = self._current_animation_loop_range()
        if loop_range is None:
            QMessageBox.information(
                self,
                self._tr("Animation export", "Eksport animacji"),
                self._tr("Set an animation loop range first.", "Najpierw ustaw zakres pętli animacji."),
            )
            return
        indices = list(range(loop_range[0], loop_range[1] + 1))
        self._export_animation_sequence_for_indices(indices, suffix="loop", scope_label=self._tr("loop", "pętla"))

    def export_animation_selection(self) -> None:
        indices = self._selected_animation_rows(fallback_current=True, fallback_all=False)
        if not indices:
            QMessageBox.information(
                self,
                self._tr("Animation export", "Eksport animacji"),
                self._tr("Select animation frames to export.", "Zaznacz klatki animacji do eksportu."),
            )
            return
        self._export_animation_sequence_for_indices(
            indices,
            suffix="selection",
            scope_label=self._tr("selection", "zaznaczenie"),
        )

    def _export_animation_sequence_for_indices(
        self,
        frame_indices: list[int] | None,
        *,
        suffix: str,
        scope_label: str,
    ) -> None:
        if getattr(self, "_animation_export_in_flight", False):
            return
        if self.theme_doc_model is None:
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            QMessageBox.information(
                self,
                self._tr("Animation export", "Eksport animacji"),
                self._tr("No animation frames to export.", "Brak klatek animacji do eksportu."),
            )
            return
        if frame_indices is None:
            export_indices = list(range(len(frame_paths)))
        else:
            export_indices = sorted({int(i) for i in frame_indices if 0 <= int(i) < len(frame_paths)})
        if not export_indices:
            QMessageBox.information(
                self,
                self._tr("Animation export", "Eksport animacji"),
                self._tr("No valid animation frames in this export range.", "Brak prawidłowych klatek w tym zakresie eksportu."),
            )
            return
        stem = Path(self.theme_doc_path_edit.text() or "motyw").stem
        safe_suffix = str(suffix or "animation").strip("_") or "animation"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Save animation export", "Zapisz eksport animacji"),
            str((Path.cwd() / "exports" / f"{stem}_{safe_suffix}.zip").resolve()),
            "ZIP (*.zip)",
        )
        if not selected:
            return
        target = Path(selected).expanduser()
        document = normalize_theme_document(deepcopy(self.theme_doc_model))
        base_dir = self._theme_base_dir()
        self._set_animation_export_busy(True)
        self.preview_info_label.setText(
            self._tr(
                f"Exporting animation {scope_label} in background: {target.name} ({len(export_indices)} frames)",
                f"Eksportuję animację ({scope_label}) w tle: {target.name} ({len(export_indices)} klatek)",
            )
        )
        self.append_log(
            f"[animation-export] start target={target} scope={scope_label} frames={len(export_indices)}/{len(frame_paths)}"
        )
        self._run_animation_export_worker(target, document, base_dir, export_indices, scope_label)

    def _run_animation_export_worker(
        self,
        target: Path,
        document: dict[str, Any],
        base_dir: Path,
        frame_indices: list[int],
        scope_label: str,
    ) -> None:
        cancel_event = self._animation_export_cancel_event
        def worker() -> None:
            try:
                result = self._export_animation_sequence_zip(
                    target,
                    document,
                    base_dir,
                    frame_indices,
                    scope_label,
                    cancel_event=cancel_event,
                )
                self.api_result.emit("animation-export", True, {"result": result})
            except Exception as exc:
                self.api_result.emit("animation-export", False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _export_animation_sequence_zip(
        self,
        target: Path,
        document: dict[str, Any],
        base_dir: Path,
        frame_indices: list[int],
        scope_label: str,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        if render_theme_document is None:
            raise RuntimeError("Theme renderer is not available.")
        self._raise_if_animation_task_cancelled(cancel_event)
        target.parent.mkdir(parents=True, exist_ok=True)
        animation = document.setdefault("effects", {}).setdefault("animation", {})
        if not isinstance(animation, dict):
            raise ValueError("Theme animation block is invalid.")
        frame_paths = animation.get("frame_paths", [])
        if not isinstance(frame_paths, list) or not frame_paths:
            raise ValueError("No animation frames to export.")
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        frame_count = len(frame_paths)
        export_indices = [int(i) for i in frame_indices if 0 <= int(i) < frame_count]
        if not export_indices:
            raise ValueError("No valid animation frames to export.")
        default_duration = max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
        export_durations = [
            int(frame_durations[idx]) if idx < len(frame_durations) else default_duration
            for idx in export_indices
        ]
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "type": "trofeo-animation-export",
                "theme_name": document.get("meta", {}).get("name", "Motyw"),
                "scope": scope_label,
                "fps": float(animation.get("fps", 12.0)),
                "loop": bool(animation.get("loop", True)),
                "loop_start": animation.get("loop_start"),
                "loop_end": animation.get("loop_end"),
                "frame_count": len(export_indices),
                "source_frame_count": frame_count,
                "source_indices": export_indices,
                "frame_durations_ms": export_durations,
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            self._emit_animation_progress("export", 0, len(export_indices), self._tr("Exporting animation", "Eksport animacji"))
            for out_idx, source_idx in enumerate(export_indices):
                self._raise_if_animation_task_cancelled(cancel_event)
                theme_frame = deepcopy(document)
                theme_frame.setdefault("effects", {}).setdefault("animation", {})
                theme_frame["effects"]["animation"]["current_frame"] = source_idx
                image = render_theme_document(
                    ThemeDocument(normalize_theme_document(theme_frame)),
                    base_dir=base_dir,
                    stats_provider=self._preview_stats_provider,
                )
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                zf.writestr(f"frames/frame_{out_idx:04d}.png", buffer.getvalue())
                if out_idx == len(export_indices) - 1 or out_idx % max(1, len(export_indices) // 20) == 0:
                    self._emit_animation_progress(
                        "export",
                        out_idx + 1,
                        len(export_indices),
                        self._tr("Exporting animation", "Eksport animacji"),
                    )
        return {
            "target": str(target),
            "name": target.name,
            "scope": scope_label,
            "frame_count": len(export_indices),
            "source_frame_count": frame_count,
            "bytes": target.stat().st_size if target.exists() else 0,
        }

    def _set_animation_export_busy(self, busy: bool) -> None:
        self._animation_export_in_flight = bool(busy)
        self._animation_export_cancel_event = threading.Event() if busy else None
        self._set_animation_worker_state(
            "export",
            self._tr("exporting ZIP", "eksport ZIP") if busy else None,
        )
        if not busy:
            self._set_animation_worker_state("cancel", None)
        if hasattr(self, "bg_animation_export_btn"):
            self.bg_animation_export_btn.setEnabled(not busy)
            self.bg_animation_export_btn.setText(
                self._tr("Exporting…", "Eksport…") if busy else self._tr("Export", "Eksportuj")
            )
        if hasattr(self, "animation_export_loop_btn"):
            self.animation_export_loop_btn.setEnabled(not busy and self._current_animation_loop_range() is not None)
            self.animation_export_loop_btn.setText(
                self._tr("Exporting…", "Eksport…") if busy else self._tr("Export Loop", "Eksport pętli")
            )
        if hasattr(self, "animation_export_selection_btn"):
            has_selection = hasattr(self, "bg_animation_list") and self.bg_animation_list.currentRow() >= 0
            self.animation_export_selection_btn.setEnabled(not busy and has_selection)
            self.animation_export_selection_btn.setText(
                self._tr("Exporting…", "Eksport…") if busy else self._tr("Export Sel", "Eksport zazn.")
            )

    def toggle_animation_preview_playback(self) -> None:
        if not self._animation_edit_mode_enabled():
            self.designer_animation_mode_btn.setChecked(True)
            self._on_animation_mode_toggled(True)
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if len(frame_paths) <= 1:
            self._animation_preview_active = False
            self._update_animation_preview_timer()
            return
        self._animation_preview_active = not self._animation_preview_active
        self._update_animation_preview_timer()

    def _advance_animation_preview(self) -> None:
        try:
            animation = self._current_animation_effect()
            frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
            if len(frame_paths) <= 1:
                self._animation_preview_active = False
                self._update_animation_preview_timer()
                return
            loop_range = self._current_animation_loop_range()
            loop_start = loop_range[0] if loop_range is not None else 0
            loop_end = loop_range[1] if loop_range is not None else len(frame_paths) - 1
            current = int(animation.get("current_frame", 0))
            if current < loop_start or current > loop_end:
                current = loop_start
            next_index = current + 1
            if next_index > loop_end or next_index >= len(frame_paths):
                if bool(animation.get("loop", True)):
                    next_index = loop_start
                else:
                    self._animation_preview_active = False
                    self._update_animation_preview_timer()
                    return
            self._set_current_animation_frame_lightweight(next_index)
            self._update_animation_preview_timer()
        except Exception as exc:
            self._animation_preview_active = False
            self._update_animation_preview_timer()
            self.append_log(f"[animation-preview] ERROR: {exc}")
            if hasattr(self, "preview_info_label"):
                self.preview_info_label.setText(
                    self._tr(
                        f"Animation preview stopped after an error: {exc}",
                        f"Podgląd animacji zatrzymany po błędzie: {exc}",
                    )
                )

    def import_background_animation(self) -> None:
        if getattr(self, "_animation_import_in_flight", False):
            return
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            self._tr("Choose animation frames, video, ZIP, or TTCR container", "Wybierz klatki animacji, wideo, ZIP lub kontener TTCR"),
            str(Path.cwd()),
            self._tr(
                "Animation media (*.zt *.zip *.jpg *.jpeg *.png *.webp *.bmp *.mp4 *.webm *.mov *.mkv *.avi *.m4v);;Video (*.mp4 *.webm *.mov *.mkv *.avi *.m4v);;Frames (*.jpg *.jpeg *.png *.webp *.bmp);;All files (*)",
                "Animacje/media (*.zt *.zip *.jpg *.jpeg *.png *.webp *.bmp *.mp4 *.webm *.mov *.mkv *.avi *.m4v);;Wideo (*.mp4 *.webm *.mov *.mkv *.avi *.m4v);;Klatki (*.jpg *.jpeg *.png *.webp *.bmp);;All files (*)",
            ),
        )
        if not selected:
            return
        sources = [Path(item).expanduser() for item in selected]
        self._start_animation_frame_import(sources, mode="replace")

    def _start_animation_frame_import(self, sources: list[Path], *, mode: str) -> None:
        if not sources:
            return
        target_dir = self._theme_assets_dir() / "animation_frames"
        theme_stem = Path(self.theme_doc_path_edit.text() or "theme").stem or "theme"
        base_dir = self._theme_base_dir()
        self._set_animation_import_busy(True)
        canvas = self.theme_doc_model.get("canvas", {}) if isinstance(self.theme_doc_model, dict) else {}
        canvas_size = (
            int(canvas.get("width", 1920) or 1920),
            int(canvas.get("height", 462) or 462),
        )
        fps = float(self.bg_animation_fps_spin.value()) if hasattr(self, "bg_animation_fps_spin") else 12.0
        cancel_event = self._animation_import_cancel_event
        self.preview_info_label.setText(
            self._tr(
                f"Preparing animation frames in background ({len(sources)} source file(s)).",
                f"Przygotowuję klatki animacji w tle ({len(sources)} plików źródłowych).",
            )
        )

        def worker() -> None:
            try:
                self._raise_if_animation_task_cancelled(cancel_event)
                self._emit_animation_progress("import", 0, len(sources), self._tr("Preparing frames", "Przygotowanie klatek"))
                import_payload = self._collect_animation_frame_import_payload_for_worker(
                    sources,
                    target_dir=target_dir,
                    theme_stem=theme_stem,
                    base_dir=base_dir,
                    fps=fps,
                    canvas_size=canvas_size,
                    cancel_event=cancel_event,
                    progress_callback=lambda current, total, label="": self._emit_animation_progress(
                        "import",
                        current,
                        total,
                        label or self._tr("Preparing frames", "Przygotowanie klatek"),
                    ),
                )
                self._raise_if_animation_task_cancelled(cancel_event)
                self.api_result.emit(
                    "animation-import",
                    True,
                    {"result": {"mode": mode, "source_count": len(sources), **import_payload}},
                )
            except Exception as exc:
                self.api_result.emit("animation-import", False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    @classmethod
    def _collect_animation_frame_import_payload_for_worker(
        cls,
        sources: list[Path],
        *,
        target_dir: Path,
        theme_stem: str,
        base_dir: Path,
        fps: float = 12.0,
        canvas_size: tuple[int, int] = (1920, 462),
        cancel_event: threading.Event | None = None,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        if len(sources) == 1 and sources[0].suffix.lower() == ".zip":
            return cls._collect_animation_zip_export_for_worker(
                sources[0],
                target_dir=target_dir,
                theme_stem=theme_stem,
                base_dir=base_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
        if any(source.suffix.lower() in VIDEO_BACKGROUND_EXTENSIONS for source in sources):
            return cls._collect_animation_video_frames_for_worker(
                sources,
                target_dir=target_dir,
                theme_stem=theme_stem,
                base_dir=base_dir,
                fps=fps,
                canvas_size=canvas_size,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
        copied_paths = cls._collect_animation_frame_paths_for_worker(
            sources,
            target_dir=target_dir,
            theme_stem=theme_stem,
            base_dir=base_dir,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        return {"frame_paths": copied_paths, "frame_durations_ms": []}

    @classmethod
    def _collect_animation_video_frames_for_worker(
        cls,
        sources: list[Path],
        *,
        target_dir: Path,
        theme_stem: str,
        base_dir: Path,
        fps: float,
        canvas_size: tuple[int, int],
        cancel_event: threading.Event | None = None,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found; video background import requires ffmpeg.")
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(ch.lower() if ch.isalnum() else "_" for ch in theme_stem).strip("_") or "theme"
        width = max(1, int(canvas_size[0]))
        height = max(1, int(canvas_size[1]))
        fps_value = max(1.0, min(30.0, float(fps or 12.0)))
        max_frames = int(max(24, min(VIDEO_IMPORT_MAX_FRAMES, fps_value * 20.0)))
        copied_paths: list[str] = []
        durations: list[int] = []
        truncated = False
        video_sources = [source for source in sources if source.suffix.lower() in VIDEO_BACKGROUND_EXTENSIONS and source.exists()]
        total_sources = max(1, len(video_sources))
        for source_index, source in enumerate(video_sources):
            cls._raise_if_worker_cancelled(cancel_event)
            prefix = target_dir / f"{safe_stem}_video_{source_index:02d}_%05d.png"
            vf = f"fps={fps_value:.3f},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
            cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vf",
                vf,
                "-frames:v",
                str(max_frames),
                str(prefix),
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            started_at = time.time()
            while proc.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2.0)
                    cls._raise_if_worker_cancelled(cancel_event)
                if time.time() - started_at > 180:
                    proc.kill()
                    proc.wait(timeout=2.0)
                    raise RuntimeError(f"ffmpeg timed out for {source}")
                time.sleep(0.1)
            stdout, stderr = proc.communicate()
            cls._raise_if_worker_cancelled(cancel_event)
            if proc.returncode != 0:
                raise RuntimeError((stderr or stdout or "").strip() or f"ffmpeg failed for {source}")
            frames = sorted(target_dir.glob(f"{safe_stem}_video_{source_index:02d}_*.png"))
            if len(frames) >= max_frames:
                truncated = True
            for frame in frames:
                cls._raise_if_worker_cancelled(cancel_event)
                copied_paths.append(cls._display_path_for_base(frame, base_dir))
                durations.append(max(1, int(round(1000.0 / fps_value))))
            if callable(progress_callback):
                progress_callback(source_index + 1, total_sources, "Import video frames")
        return {
            "frame_paths": copied_paths,
            "frame_durations_ms": durations[: len(copied_paths)],
            "source_kind": "video",
            "video_fps": fps_value,
            "video_max_frames": max_frames,
            "video_truncated": truncated,
        }

    @classmethod
    def _collect_animation_zip_export_for_worker(
        cls,
        source: Path,
        *,
        target_dir: Path,
        theme_stem: str,
        base_dir: Path,
        cancel_event: threading.Event | None = None,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        copied_paths: list[str] = []
        durations: list[int] = []
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(ch.lower() if ch.isalnum() else "_" for ch in theme_stem).strip("_") or "theme"
        with zipfile.ZipFile(source, "r") as zf:
            manifest: dict[str, Any] = {}
            try:
                raw_manifest = zf.read("manifest.json")
                loaded = json.loads(raw_manifest.decode("utf-8"))
                if isinstance(loaded, dict):
                    manifest = loaded
            except Exception:
                manifest = {}
            raw_durations = manifest.get("frame_durations_ms", [])
            if isinstance(raw_durations, list):
                for item in raw_durations:
                    try:
                        durations.append(max(1, int(float(item))))
                    except Exception:
                        continue
            names = [
                name
                for name in zf.namelist()
                if name.startswith("frames/")
                and not name.endswith("/")
                and Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            ]
            names.sort()
            total = max(1, len(names))
            for idx, name in enumerate(names):
                cls._raise_if_worker_cancelled(cancel_event)
                suffix = Path(name).suffix.lower() or ".png"
                out = target_dir / f"{safe_stem}_zip_{idx:04d}{suffix}"
                with zf.open(name, "r") as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                copied_paths.append(cls._display_path_for_base(out, base_dir))
                if callable(progress_callback):
                    progress_callback(idx + 1, total, "Import ZIP frames")
        return {"frame_paths": copied_paths, "frame_durations_ms": durations[: len(copied_paths)]}

    def _finish_animation_frame_import(
        self,
        mode: str,
        copied_paths: list[str],
        frame_durations: list[int] | None = None,
        import_info: dict[str, Any] | None = None,
    ) -> None:
        if not copied_paths:
            QMessageBox.warning(
                self,
                self._tr("Animation import", "Import animacji"),
                self._tr("Could not prepare animation frames.", "Nie udało się przygotować klatek animacji."),
            )
            return
        controller = self._animation_controller()
        if controller is None:
            return
        self.push_designer_history()
        seq = controller.normalize()
        animation = controller.animation()
        duration_ms = max(1, int(round(1000.0 / max(1.0, seq.fps))))
        imported_durations = [max(1, int(item)) for item in (frame_durations or [])[: len(copied_paths)]]
        before_count = seq.frame_count
        if mode == "append":
            controller.insert_frames(copied_paths, duration_ms=duration_ms)
            if imported_durations:
                existing = animation.get("frame_durations_ms", [])
                if isinstance(existing, list):
                    start = max(0, len(existing) - len(copied_paths))
                    for offset, value in enumerate(imported_durations):
                        idx = start + offset
                        if idx < len(existing):
                            existing[idx] = value
        else:
            controller.replace_frames(copied_paths, duration_ms=duration_ms)
            if imported_durations:
                padded = imported_durations + [duration_ms] * max(0, len(copied_paths) - len(imported_durations))
                animation["frame_durations_ms"] = padded[: len(copied_paths)]
        animation["enabled"] = True
        animation["use_as_background"] = True
        if mode == "replace" or before_count == 0:
            animation["current_frame"] = 0
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._animation_preview_active = False
        self._refresh_animation_frame_list()
        self._set_image_preview_label(self.background_preview_label, copied_paths[0], empty_text=self._empty_background_preview_caption())
        self._rebuild_theme_asset_gallery()
        self._maybe_warn_animation_frame_count(controller.normalize().frame_count)
        info = import_info if isinstance(import_info, dict) else {}
        source_kind = str(info.get("source_kind", "")).strip().lower()
        truncated = bool(info.get("video_truncated", False))
        if mode == "append":
            if source_kind == "video" and truncated:
                self.preview_info_label.setText(
                    self._tr(
                        f"Added {len(copied_paths)} video frame(s); import was capped for LCD performance.",
                        f"Dodano {len(copied_paths)} klatek wideo; import ograniczony dla wydajności LCD.",
                    )
                )
            else:
                self.preview_info_label.setText(self._tr(f"Added {len(copied_paths)} animation frame(s).", f"Dodano {len(copied_paths)} klat. animacji."))
        else:
            if source_kind == "video" and truncated:
                self.preview_info_label.setText(
                    self._tr(
                        f"Imported video background: {len(copied_paths)} frame(s); import was capped for LCD performance.",
                        f"Zaimportowano tło wideo: {len(copied_paths)} klat.; import ograniczony dla wydajności LCD.",
                    )
                )
            else:
                self.preview_info_label.setText(self._tr(f"Imported animation: {len(copied_paths)} frame(s).", f"Zaimportowano animację: {len(copied_paths)} klat."))
        self.schedule_preview_theme_doc()

    def _set_animation_import_busy(self, busy: bool) -> None:
        self._animation_import_in_flight = bool(busy)
        self._animation_import_cancel_event = threading.Event() if busy else None
        self._set_animation_worker_state(
            "import",
            self._tr("preparing frames", "przygotowanie klatek") if busy else None,
        )
        if not busy:
            self._set_animation_worker_state("cancel", None)
        for button in (getattr(self, "bg_animation_import_btn", None), getattr(self, "bg_animation_add_btn", None)):
            if button is not None:
                button.setEnabled(not busy)
        if hasattr(self, "bg_animation_import_btn"):
            self.bg_animation_import_btn.setText(
                self._tr("Importing…", "Import…") if busy else self._tr("Import", "Importuj")
            )

    def _apply_animation_thumbnail_payload(self, action: str, payload: object) -> None:
        try:
            generation = int(action.rsplit("::", 1)[1])
        except Exception:
            return
        if generation != getattr(self, "_animation_thumbnail_generation", 0):
            return
        self._finish_animation_thumbnail_worker()
        data = payload if isinstance(payload, dict) else {}
        result = data.get("result", {})
        items = result.get("items", []) if isinstance(result, dict) else []
        if not isinstance(items, list) or not hasattr(self, "bg_animation_list"):
            return
        timeline_updates: dict[int, QPixmap] = {}
        for entry in items:
            if not isinstance(entry, dict):
                continue
            row = int(entry.get("row", -1))
            if row < 0 or row >= self.bg_animation_list.count():
                continue
            item = self.bg_animation_list.item(row)
            if item is None or str(item.data(Qt.UserRole)) != str(entry.get("raw", "")):
                continue
            image = entry.get("image")
            if not isinstance(image, QImage) or image.isNull():
                continue
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                continue
            cache_key = (str(entry.get("path", "")), int(entry.get("mtime", 0) or 0))
            self._image_thumbnail_cache = {key: val for key, val in self._image_thumbnail_cache.items() if key[0] != cache_key[0]}
            self._image_thumbnail_cache[cache_key] = pixmap
            item.setIcon(QIcon(pixmap))
            timeline_updates[row] = pixmap
        self._trim_animation_thumbnail_cache()
        timeline = getattr(self, "bg_animation_timeline", None)
        if timeline is not None and hasattr(timeline, "update_thumbnails") and timeline_updates:
            timeline.update_thumbnails(timeline_updates)
        self._refresh_animation_controls()

    def _trim_animation_thumbnail_cache(self) -> None:
        max_items = 720
        cache = getattr(self, "_image_thumbnail_cache", {})
        if not isinstance(cache, dict) or len(cache) <= max_items:
            return
        keep = list(cache.items())[-max_items:]
        self._image_thumbnail_cache = dict(keep)

    def clear_background_animation(self) -> None:
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        controller = self._animation_controller()
        animation = controller.animation() if controller is not None else self._current_animation_effect()
        if controller is not None:
            controller.replace_frames([])
        else:
            animation["frame_paths"] = []
            animation["frame_durations_ms"] = []
        animation["enabled"] = False
        animation["current_frame"] = 0
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._animation_preview_active = False
        self._refresh_animation_frame_list()
        self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text=self._empty_background_preview_caption())
        self.schedule_preview_theme_doc()

    def nudge_animation_frame(self, delta: int) -> None:
        controller = self._animation_controller()
        if controller is None:
            return
        seq = controller.normalize()
        if not seq.frame_paths:
            return
        controller.set_current_frame(seq.current_frame + int(delta))
        self._refresh_animation_controls()
        self._set_current_animation_frame(controller.normalize().current_frame, persist=True)

    def _write_theme_autosave(self) -> None:
        if self.theme_doc_model is None:
            return
        payload = {
            "type": "theme-doc-autosave",
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "theme_path": self.theme_doc_path_edit.text().strip(),
            "document": self.theme_doc_model,
        }
        try:
            THEME_AUTOSAVE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            self.append_log(f"[autosave] ERROR: {exc}")

    def _restore_theme_autosave(self) -> bool:
        try:
            if not THEME_AUTOSAVE_PATH.exists():
                return False
            raw = json.loads(THEME_AUTOSAVE_PATH.read_text(encoding="utf-8"))
            if not (isinstance(raw, dict) and raw.get("type") == "theme-doc-autosave"):
                return False
            document = raw.get("document")
            if not isinstance(document, dict):
                return False
            normalized = normalize_theme_document(document)
            self.theme_doc_model = deepcopy(normalized)
            theme_path = str(raw.get("theme_path", "")).strip()
            if theme_path:
                self.theme_doc_path_edit.setText(theme_path)
            self._set_theme_doc_editor_document(normalized)
            self._load_background_fields()
            self.refresh_designer_element_list()
            self._update_preview_canvas_overlay()
            self._mark_theme_doc_dirty("autosave-restore")
            self.append_log(f"[autosave] restored {THEME_AUTOSAVE_PATH}")
            self.preview_theme_doc()
            return True
        except Exception as exc:
            self.append_log(f"[autosave] restore-skip: {exc}")
            return False

    def apply_url(self) -> None:
        new_url = self.url_edit.text().strip()
        if not new_url:
            return
        self.client.set_base_url(new_url)
        self.append_log(f"URL backend: {new_url}")
        self.refresh_status()
        self.refresh_theme_schema()

    def api_call(self, action: str, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 12.0) -> None:
        def worker() -> None:
            try:
                data = self.client.request(method=method, path=path, payload=payload, timeout=timeout)
                self.api_result.emit(action, True, data)
            except Exception as exc:
                self.api_result.emit(action, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def api_call_with_optional_stop(
        self,
        action: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        stop_first: bool = False,
        timeout: float = 12.0,
    ) -> None:
        def worker() -> None:
            try:
                if stop_first and bool(self.current_status.get("running", False)):
                    self.client.request(method="POST", path="/v1/stop", payload={}, timeout=20.0)
                    time.sleep(0.4)
                data = self.client.request(method=method, path=path, payload=payload, timeout=timeout)
                self.api_result.emit(action, True, data)
            except Exception as exc:
                self.api_result.emit(action, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_api_result(self, action: str, ok: bool, payload: object) -> None:
        is_designer_preview = action.startswith("theme-doc-preview")
        is_animation_thumbnails = action.startswith("animation-thumbnails::")
        if action == "animation-progress":
            if ok:
                self._apply_animation_progress_payload(payload)
            return
        if action == "status":
            self._status_in_flight = False
        if action == "animation-export":
            self._set_animation_export_busy(False)
        if action == "animation-import":
            self._set_animation_import_busy(False)
        if action == "animation-stabilize":
            self._set_animation_stabilize_busy(False)
        if is_designer_preview:
            self._preview_request_in_flight = False
        if (
            action
            in {"theme-doc-load", "theme-doc-apply", "studio-theme-save", "studio-theme-apply"}
            or is_designer_preview
        ):
            self._set_designer_toolbar_busy("theme-doc-preview" if is_designer_preview else action, False)
        is_template_preview = action.startswith("template-preview::")
        quiet_actions = {
            "theme-schema",
            "themes",
            "playlist",
            "theme-doc-preview",
        }

        if is_animation_thumbnails:
            if ok:
                self._apply_animation_thumbnail_payload(action, payload)
            else:
                self._finish_animation_thumbnail_worker()
            return

        if action == "animation-export" and not ok:
            self.append_log(f"[{action}] ERROR: {payload}")
            if "cancel" in str(payload).lower():
                self.preview_info_label.setText(self._tr("Animation export cancelled.", "Eksport animacji anulowany."))
                self._set_animation_worker_state("cancel", None)
                return
            self.preview_info_label.setText(
                self._tr(
                    f"Animation export failed: {str(payload)[:140]}",
                    f"Eksport animacji nie powiódł się: {str(payload)[:140]}",
                )
            )
            self._push_system_event("WARN", action, str(payload)[:120])
            QMessageBox.warning(
                self,
                self._tr("Animation Export", "Eksport animacji"),
                str(payload),
            )
            return
        if action == "animation-import" and not ok:
            self.append_log(f"[{action}] ERROR: {payload}")
            if "cancel" in str(payload).lower():
                self.preview_info_label.setText(self._tr("Animation import cancelled.", "Import animacji anulowany."))
                self._set_animation_worker_state("cancel", None)
                return
            self.preview_info_label.setText(
                self._tr(
                    f"Animation import failed: {str(payload)[:140]}",
                    f"Import animacji nie powiódł się: {str(payload)[:140]}",
                )
            )
            self._push_system_event("WARN", action, str(payload)[:120])
            QMessageBox.warning(
                self,
                self._tr("Animation Import", "Import animacji"),
                str(payload),
            )
            return
        if action == "animation-stabilize" and not ok:
            self.append_log(f"[{action}] ERROR: {payload}")
            self.preview_info_label.setText(
                self._tr(
                    f"Animation stabilization failed: {str(payload)[:140]}",
                    f"Stabilizacja animacji nie powiodła się: {str(payload)[:140]}",
                )
            )
            self._push_system_event("WARN", action, str(payload)[:120])
            QMessageBox.warning(
                self,
                self._tr("Animation stabilization", "Stabilizacja animacji"),
                str(payload),
            )
            return

        if not ok:
            self.append_log(f"[{action}] ERROR: {payload}")
            if (
                action
                in {"theme-doc-load", "theme-doc-apply", "studio-theme-save", "studio-theme-apply"}
                or is_designer_preview
            ):
                self._set_designer_toolbar_feedback(f"Błąd: {str(payload)[:120]}")
            self._push_system_event("WARN", action, str(payload)[:120])
            if is_designer_preview and self._preview_request_queued:
                self._preview_request_queued = False
                self.preview_debounce.start(self._designer_preview_delay_ms())
            if action != "status" and not is_template_preview and action not in quiet_actions:
                QMessageBox.warning(self, "API Error", str(payload))
            return

        data = payload if isinstance(payload, dict) else {}
        self.append_log(self._format_log_payload(action, data))
        if action == "animation-export":
            result = data.get("result", {})
            if isinstance(result, dict):
                name = str(result.get("name", "animation.zip"))
                scope = str(result.get("scope", "full"))
                frame_count = int(result.get("frame_count", 0) or 0)
                size_bytes = int(result.get("bytes", 0) or 0)
                self.preview_info_label.setText(
                    self._tr(
                        f"Animation exported: {name} ({scope}, {frame_count} frames, {size_bytes / 1024:.1f} KiB).",
                        f"Wyeksportowano animację: {name} ({scope}, {frame_count} klatek, {size_bytes / 1024:.1f} KiB).",
                    )
                )
            return
        if action == "animation-import":
            result = data.get("result", {})
            if isinstance(result, dict):
                mode = str(result.get("mode", "replace"))
                raw_paths = result.get("frame_paths", [])
                copied_paths = [str(item) for item in raw_paths] if isinstance(raw_paths, list) else []
                raw_durations = result.get("frame_durations_ms", [])
                frame_durations: list[int] = []
                if isinstance(raw_durations, list):
                    for item in raw_durations:
                        try:
                            frame_durations.append(max(1, int(float(item))))
                        except Exception:
                            continue
                self._finish_animation_frame_import(mode, copied_paths, frame_durations, result)
            return
        if action == "animation-stabilize":
            result = data.get("result", {})
            if isinstance(result, dict):
                self._finish_animation_stabilize(result)
            return
        if action != "status":
            status_payload = data.get("status", data)
            result_payload = data.get("result", {})
            summary = ""
            if isinstance(result_payload, dict) and result_payload:
                summary = ", ".join(f"{k}={result_payload[k]}" for k in list(result_payload.keys())[:3])
            elif isinstance(status_payload, dict):
                summary = self._summarize_status_payload(status_payload)
            self._push_system_event("INFO", action, summary[:120] if summary else "OK")
        if action in {
            "status",
            "start",
            "stop",
            "restart",
            "set-frame",
            "config",
            "scan",
            "send-image",
            "themes",
            "theme-add",
            "theme-remove",
            "theme-apply",
            "playlist",
            "playlist-add",
            "playlist-remove",
            "playlist-start",
            "playlist-stop",
            "bundle-save",
            "bundle-load",
            "theme-doc-load",
            "theme-doc-save",
            "theme-doc-apply",
            "studio-theme-save",
            "studio-theme-apply",
        }:
            status_payload = data.get("status", data)
            if isinstance(status_payload, dict):
                self._update_status(status_payload)
        if action in {"themes", "theme-add", "theme-remove", "bundle-load", "studio-theme-save", "studio-theme-apply"}:
            themes_payload = data.get("themes", data.get("result", {}))
            if isinstance(themes_payload, dict):
                self._update_themes(themes_payload)
        if action in {"playlist", "playlist-add", "playlist-remove", "playlist-start", "playlist-stop", "bundle-load"}:
            playlist_payload = data.get("playlist", data.get("result", {}))
            if isinstance(playlist_payload, dict):
                self._update_playlist(playlist_payload)
        if action == "theme-schema":
            result = data.get("result", {})
            if isinstance(result, dict):
                schema_version = result.get("schema_version", "?")
                stat_sources = result.get("stat_sources", [])
                if isinstance(stat_sources, list):
                    self.theme_stat_sources = [str(item) for item in stat_sources]
                    current_source = self.designer_source_combo.currentText()
                    current_source_data = str(self.designer_source_combo.currentData() or current_source).strip()
                    self._populate_designer_source_combo(current_source_data)
                    sources_preview = ", ".join(str(item) for item in stat_sources[:8])
                    if len(stat_sources) > 8:
                        sources_preview += f" ... (+{len(stat_sources) - 8})"
                else:
                    sources_preview = "-"
                self.theme_schema_label.setText(f"v{schema_version} | {sources_preview}")
        if action in {"theme-doc-load", "theme-doc-save"}:
            result = data.get("result", {})
            if isinstance(result, dict):
                document = result.get("document")
                if isinstance(document, dict):
                    try:
                        normalized = normalize_theme_document(document)
                    except Exception as exc:
                        QMessageBox.warning(self, self._tr("Theme error", "Błąd motywu"), str(exc))
                        normalized = None
                    if normalized is not None:
                        self.theme_doc_model = deepcopy(normalized)
                        self._set_theme_doc_editor_document(normalized)
                        self.refresh_designer_element_list()
                        self._load_background_fields()
                        self._sync_designer_preview_policy()
                        self.load_selected_designer_item()
                        self._update_preview_canvas_overlay()
                        self._mark_theme_doc_clean()
                resolved_path = result.get("resolved_path")
                if resolved_path:
                    self.theme_doc_path_edit.setText(str(resolved_path))
                self._rebuild_theme_asset_gallery()
                if action == "theme-doc-load":
                    self._set_designer_toolbar_feedback(f"Wczytano motyw: {Path(str(resolved_path or self.theme_doc_path_edit.text())).name}")
                    self.preview_theme_doc()
                elif action == "theme-doc-save":
                    self._mark_theme_doc_clean()
        if action in {"studio-theme-save", "studio-theme-apply"}:
            result = data.get("result", {})
            if isinstance(result, dict):
                resolved_path = result.get("resolved_path")
                if resolved_path:
                    self.theme_doc_path_edit.setText(str(resolved_path))
                theme_name = str(result.get("name", "")).strip()
                if theme_name:
                    self.theme_combo.setCurrentText(theme_name)
                    self.theme_name_edit.setText(theme_name)
                if resolved_path:
                    self.theme_path_edit.setText(str(resolved_path))
                self._rebuild_theme_asset_gallery()
                self._mark_theme_doc_clean()
                if action == "studio-theme-save":
                    self._set_designer_toolbar_feedback("Motyw zapisany. Możesz od razu zastosować go na LCD.")
                else:
                    self._set_designer_toolbar_feedback("Motyw zapisany i zastosowany na LCD.")
        if action == "theme-doc-apply":
            result = data.get("result", {})
            if isinstance(result, dict):
                rendered = result.get("rendered_theme", {})
                if isinstance(rendered, dict):
                    image_path = rendered.get("image_path")
                    if image_path:
                        self.append_log(f"[theme-doc-apply] rendered image: {image_path}")
                self._rebuild_theme_asset_gallery()
                self._set_designer_toolbar_feedback(
                    self._tr("Theme applied to LCD.", "Motyw zastosowany na LCD.")
                )
        if is_designer_preview:
            preview_seq = 0
            if "::" in action:
                try:
                    preview_seq = int(action.rsplit("::", 1)[1])
                except Exception:
                    preview_seq = 0
            if preview_seq and preview_seq != self._preview_request_active_seq:
                return
            result = data.get("result", {})
            if isinstance(result, dict):
                image_path = str(result.get("image_path", "")).strip()
                pixmap = QPixmap(image_path) if image_path else QPixmap()
                if pixmap.isNull():
                    encoded = str(result.get("image_base64", "")).strip()
                    if encoded:
                        try:
                            raw = base64.b64decode(encoded)
                            pixmap.loadFromData(raw)
                        except Exception:
                            pixmap = QPixmap()
                if not pixmap.isNull():
                    canvas_rotation = 0
                    if isinstance(self.theme_doc_model, dict):
                        canvas_rotation = int(self.theme_doc_model.get("canvas", {}).get("rotation", 0)) % 360
                    display_rotation = (-canvas_rotation) % 360
                    self.preview_label.set_preview_pixmap(pixmap, display_rotation=display_rotation)
                    self.animate_preview_flash()
                    self._set_designer_toolbar_feedback(
                        f"Podgląd gotowy {pixmap.width()}x{pixmap.height()} | kliknij, przeciągnij lub zaznacz prostokątem."
                    )
                    self._update_preview_canvas_overlay()
                else:
                    self._set_designer_toolbar_feedback(
                        self._tr(
                            f"Preview rendered, but GUI cannot load image: {image_path or 'no image path'}",
                            f"Podgląd wyrenderowany, ale GUI nie może załadować obrazu: {image_path or 'brak ścieżki'}",
                        ),
                        auto_clear_ms=None,
                    )
            if self._preview_request_queued:
                self._preview_request_queued = False
                self.preview_debounce.start(self._designer_preview_delay_ms())
        if is_template_preview:
            result = data.get("result", {})
            if isinstance(result, dict):
                image_path = str(result.get("image_path", "")).strip()
                template_path = action.split("::", 1)[1]
                thumb = self._template_thumb_map.get(template_path)
                if thumb and image_path:
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        pixmap = self._upright_template_pixmap(pixmap, template_path)
                        thumb.setText("")
                        thumb.setPixmap(
                            pixmap.scaled(
                                thumb.size(),
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation,
                            )
                        )

    def _update_status(self, status: dict[str, Any]) -> None:
        self.current_status = dict(status)
        
        if hasattr(self, "header_connection_label"):
            running = bool(status.get("running", False))
            self.header_connection_label.setText(self._tr("● Connected", "● Połączono") if running or bool(status.get("ok", False)) else self._tr("● Disconnected", "● Rozłączono"))
        if hasattr(self, "header_ready_label"):
            self.header_ready_label.setText(self._tr("Ready", "Gotowe") if bool(status.get("ok", False)) else self._tr("Error", "Błąd"))

        if hasattr(self, "cfg_ui_theme_combo"):
            self._sync_config_ui_controls_from_header()

        self.lbl_mode.setText(str(status.get("mode", "-")))
        
        if status.get("running"):
            self.lbl_running.setText("✅ Działa")
            self.lbl_running.setStyleSheet("color: #4ade80; font-weight: 700; background: #111827; border-radius: 6px; padding: 4px 8px;")
        else:
            self.lbl_running.setText("❌ Zatrzymany")
            self.lbl_running.setStyleSheet("color: #f87171; font-weight: 700; background: #111827; border-radius: 6px; padding: 4px 8px;")
            
        self.lbl_pid.setText(str(status.get("pid", "-")))
        self.lbl_uptime.setText(str(status.get("uptime_s", "-")))
        self.lbl_frame_count.setText(str(status.get("frame_count", "-")))
        playlist_running = bool(status.get("playlist_running", False))
        playlist_count = int(status.get("playlist_count", 0))
        playlist_index = int(status.get("playlist_index", 0))
        self.lbl_playlist.setText(f"{'ON' if playlist_running else 'OFF'} ({playlist_index}/{playlist_count})")
        self.lbl_playlist_uptime.setText(str(status.get("playlist_uptime_s", "-")))
        self.lbl_last_error.setText(str(status.get("last_error", "-")))

        cfg = status.get("config", {}) or {}
        self.lbl_pcap.setText(str(cfg.get("pcap_path", "-")))
        if "frame_index" in cfg:
            self.frame_spin.setValue(int(cfg.get("frame_index", 0)))
        if "pcap_path" in cfg:
            self.pcap_edit.setText(str(cfg.get("pcap_path")))
        if "ack_timeout_ms" in cfg:
            self.ack_timeout_spin.setValue(int(cfg.get("ack_timeout_ms", 500)))
        if "inter_packet_delay" in cfg:
            self.inter_delay_spin.setValue(float(cfg.get("inter_packet_delay", 0.01)))
        if "frame_delay" in cfg:
            self.frame_delay_spin.setValue(float(cfg.get("frame_delay", 0.02)))
        if hasattr(self, "cfg_api_port_spin") and "port" in cfg:
            self.cfg_api_port_spin.setValue(int(cfg.get("port", 18777)))
        if hasattr(self, "cfg_theme_dir_edit"):
            self.cfg_theme_dir_edit.setText(str((Path.cwd() / "themes").resolve()))
        weather_cfg = cfg.get("weather", {}) if isinstance(cfg, dict) else {}
        if isinstance(weather_cfg, dict) and hasattr(self, "cfg_weather_lat_edit"):
            if weather_cfg.get("lat") is not None:
                self.cfg_weather_lat_edit.setText(str(weather_cfg.get("lat")))
            if weather_cfg.get("lon") is not None:
                self.cfg_weather_lon_edit.setText(str(weather_cfg.get("lon")))
            if weather_cfg.get("location"):
                self.cfg_weather_location_edit.setText(str(weather_cfg.get("location")))
            if weather_cfg.get("refresh_s") is not None:
                try:
                    self.cfg_weather_refresh_spin.setValue(int(float(weather_cfg.get("refresh_s"))))
                except Exception:
                    pass
            if hasattr(self, "cfg_weather_status_label"):
                enabled = bool(weather_cfg.get("enabled", False))
                city = str(weather_cfg.get("location_label") or weather_cfg.get("location") or "N/A")
                temp = str(weather_cfg.get("temperature") or "N/A")
                condition = str(weather_cfg.get("condition") or "N/A")
                source = str(weather_cfg.get("last_source") or "none")
                cache_age = weather_cfg.get("cache_age_s")
                update_age = weather_cfg.get("last_update_age_s")
                error = str(weather_cfg.get("last_error") or "").strip()
                parts = [
                    self._tr("enabled", "włączona") if enabled else self._tr("not configured", "brak konfiguracji"),
                    f"{city}: {temp}, {condition}",
                    f"source: {source}",
                ]
                if update_age is not None:
                    parts.append(f"updated {update_age}s ago")
                if cache_age is not None:
                    parts.append(f"cache {cache_age}s")
                if error:
                    parts.append(f"error: {error[:100]}")
                self.cfg_weather_status_label.setText(" | ".join(parts))
        audio_eq_cfg = cfg.get("audio_eq", {}) if isinstance(cfg, dict) else {}
        if isinstance(audio_eq_cfg, dict) and hasattr(self, "cfg_audio_eq_status_label"):
            method = str(audio_eq_cfg.get("input_method") or "").strip()
            active_input = str(audio_eq_cfg.get("active_input") or "none").strip()
            profile = str(audio_eq_cfg.get("profile") or "balanced").strip()
            sensitivity = audio_eq_cfg.get("sensitivity", 1.0)
            if not bool(getattr(self, "_audio_eq_config_dirty", False)):
                idx = self.cfg_audio_eq_input_combo.findData(method)
                if idx >= 0 and self.cfg_audio_eq_input_combo.currentIndex() != idx:
                    self.cfg_audio_eq_input_combo.blockSignals(True)
                    try:
                        self.cfg_audio_eq_input_combo.setCurrentIndex(idx)
                    finally:
                        self.cfg_audio_eq_input_combo.blockSignals(False)
                if hasattr(self, "cfg_audio_eq_profile_combo"):
                    idx = self.cfg_audio_eq_profile_combo.findData(profile)
                    if idx >= 0 and self.cfg_audio_eq_profile_combo.currentIndex() != idx:
                        self.cfg_audio_eq_profile_combo.blockSignals(True)
                        try:
                            self.cfg_audio_eq_profile_combo.setCurrentIndex(idx)
                        finally:
                            self.cfg_audio_eq_profile_combo.blockSignals(False)
                if hasattr(self, "cfg_audio_eq_sensitivity_spin"):
                    try:
                        sensitivity_value = int(round(float(sensitivity or 1.0) * 100.0))
                        if self.cfg_audio_eq_sensitivity_spin.value() != sensitivity_value:
                            self.cfg_audio_eq_sensitivity_spin.blockSignals(True)
                            try:
                                self.cfg_audio_eq_sensitivity_spin.setValue(sensitivity_value)
                            finally:
                                self.cfg_audio_eq_sensitivity_spin.blockSignals(False)
                    except Exception:
                        pass
            status_text = str(audio_eq_cfg.get("status") or "unknown")
            source = str(audio_eq_cfg.get("source") or "none")
            age = str(audio_eq_cfg.get("age_ms") or "N/A")
            bar_count = str(audio_eq_cfg.get("bar_count") or 0)
            peak = str(audio_eq_cfg.get("peak") or 0.0)
            raw_peak = str(audio_eq_cfg.get("raw_peak") or 0.0)
            available = bool(audio_eq_cfg.get("cava_available", False))
            parts = [
                f"status: {status_text}",
                f"input: {method or 'auto'}",
                f"active: {active_input}",
                f"profile: {profile or 'balanced'}",
                f"sens: {int(round(float(sensitivity or 1.0) * 100.0))}%",
                f"source: {source}",
                f"bars: {bar_count}",
                f"peak: {peak}",
                f"raw: {raw_peak}",
                f"age: {age} ms",
            ]
            if not available:
                parts.append("cava not found")
            self.cfg_audio_eq_status_label.setText(" | ".join(parts))

        if hasattr(self, "system_api_status_value"):
            is_ok = bool(status.get("ok", False))
            running = bool(status.get("running", False))
            mode = str(status.get("mode", "idle"))
            self._set_dashboard_badge(self.system_api_status_value, "Online" if is_ok else "Offline", "ok" if is_ok else "error")
            self._set_dashboard_badge(self.system_ws_status_value, "Online" if is_ok else "Offline", "ok" if is_ok else "error")
            self._set_dashboard_badge(self.system_lcd_status_value, "Running" if running else mode.capitalize(), "ok" if running else "warn")
            self._set_dashboard_badge(self.system_queue_status_value, "Active" if running else "Idle", "ok" if running else "neutral")
            self._set_dashboard_badge(self.system_theme_engine_value, "Ready" if is_ok else "Offline", "ok" if is_ok else "error")
            self._set_dashboard_badge(self.system_backup_value, "Idle", "warn")

            self.system_uptime_value.setText(self._read_system_uptime())
            self.system_restart_value.setText(time.strftime("%H:%M:%S"))
            self.system_connection_value.setText(self._tr("Connected", "Połączono") if is_ok else self._tr("Disconnected", "Rozłączono"))
            self.system_device_value.setText(self.header_device_combo.currentText() if hasattr(self, "header_device_combo") else "Trofeo LCD")
            self.system_firmware_value.setText(str(status.get("firmware", "N/A")))
            self.system_ip_value.setText(str(cfg.get("host", "127.0.0.1")))
            self.system_port_value.setText(str(cfg.get("port", 18777)))
            self.system_serial_value.setText(str(status.get("serial", "USB")))

            cpu_value, cpu_detail = self._read_cpu_snapshot()
            mem_value, mem_detail = self._read_memory_snapshot()
            disk_value, disk_detail = self._read_disk_snapshot()
            temp_value, temp_detail = self._read_temperature_snapshot()
            self.system_cpu_value.setText(cpu_value)
            self.system_cpu_detail.setText(cpu_detail)
            self.system_mem_value.setText(mem_value)
            self.system_mem_detail.setText(mem_detail)
            self.system_disk_value.setText(disk_value)
            self.system_disk_detail.setText(disk_detail)
            self.system_temp_value.setText(temp_value)
            self.system_temp_detail.setText(temp_detail)

    def _update_themes(self, themes_payload: dict[str, Any]) -> None:
        items = themes_payload.get("items", [])
        if not isinstance(items, list):
            return

        current = self.theme_combo.currentText().strip()
        names = []
        self.theme_items = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
                self.theme_items[name] = item

        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems(names)
        if current in names:
            self.theme_combo.setCurrentText(current)
        self.theme_combo.blockSignals(False)
        if self._startup_theme_name and self._startup_theme_name not in names:
            self._startup_theme_name = ""
            self._save_ui_state()
        if hasattr(self, "library_summary_label"):
            self.library_summary_label.setText(
                f"Biblioteka: {len(names)} motywów. Edytuj, zastosuj, duplikuj lub usuń z poziomu kafelka."
                if names
                else "Biblioteka jest pusta. Utwórz nowy motyw albo zaimportuj katalog TTCR."
            )
        self._runtime_theme_cards_dirty = True
        self._library_theme_browser_dirty = True
        if getattr(self, "_initial_theme_data_loaded", False):
            self._maybe_rebuild_visible_theme_views()
        else:
            self._initial_theme_data_loaded = True
        self._apply_startup_theme_if_needed()

    def _maybe_rebuild_visible_theme_views(self) -> None:
        if hasattr(self, "main_tabs") and self.main_tabs.currentIndex() == 0 and getattr(self, "_runtime_theme_cards_dirty", False):
            self._runtime_theme_cards_dirty = False
            self._rebuild_runtime_theme_cards()
        if (
            hasattr(self, "main_tabs")
            and hasattr(self, "studio_sections_tabs")
            and self.main_tabs.currentIndex() == 1
            and self.studio_sections_tabs.currentIndex() == 0
            and getattr(self, "_library_theme_browser_dirty", False)
        ):
            self._library_theme_browser_dirty = False
            self._rebuild_library_theme_browser()

    def _update_playlist(self, playlist_payload: dict[str, Any]) -> None:
        items = playlist_payload.get("items", [])
        if not isinstance(items, list):
            return

        selected_row = self.playlist_list.currentRow()
        self.playlist_list.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            idx = item.get("index", "?")
            name = item.get("name", "?")
            duration = item.get("duration_s", "?")
            self.playlist_list.addItem(f"{idx}: {name} ({duration}s)")
        if selected_row >= 0 and selected_row < self.playlist_list.count():
            self.playlist_list.setCurrentRow(selected_row)

    def refresh_status(self) -> None:
        if self._status_in_flight:
            return
        self._status_in_flight = True
        self.api_call("status", "GET", "/v1/status", None, timeout=5.0)

    def refresh_themes(self) -> None:
        self.api_call("themes", "GET", "/v1/themes", None, timeout=5.0)

    def refresh_playlist(self) -> None:
        self.api_call("playlist", "GET", "/v1/playlist", None, timeout=5.0)

    def refresh_theme_schema(self) -> None:
        self.api_call("theme-schema", "GET", "/v1/theme-schema", None, timeout=5.0)

    def set_frame(self) -> None:
        payload = {"frame_index": int(self.frame_spin.value())}
        self.api_call("set-frame", "POST", "/v1/set-frame", payload)

    def apply_config(self) -> None:
        payload = {
            "pcap_path": self.pcap_edit.text().strip(),
            "frame_index": int(self.frame_spin.value()),
            "ack_timeout_ms": int(self.ack_timeout_spin.value()),
            "inter_packet_delay": float(self.inter_delay_spin.value()),
            "frame_delay": float(self.frame_delay_spin.value()),
        }
        if hasattr(self, "cfg_weather_lat_edit"):
            payload.update(self._weather_config_payload())
        if hasattr(self, "cfg_audio_eq_input_combo"):
            payload.update(self._audio_eq_config_payload())
        self.api_call("config", "POST", "/v1/config", payload)

    def browse_image(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Choose image", "Wybierz obraz"),
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All files (*)",
        )
        if selected:
            self.image_edit.setText(selected)

    def send_image(self) -> None:
        image_path = self.image_edit.text().strip()
        if not image_path:
            QMessageBox.information(
                self,
                self._tr("Information", "Informacja"),
                self._tr("Enter the path to an image file.", "Podaj ścieżkę do obrazu."),
            )
            return
        payload = {
            "path": image_path,
            "raw_jpeg_passthrough": bool(self.raw_passthrough_chk.isChecked()),
            "resume_loop": bool(self.resume_loop_chk.isChecked()),
        }
        self.api_call_with_optional_stop(
            "send-image",
            "POST",
            "/v1/send-image",
            payload,
            stop_first=bool(self.stop_before_send_chk.isChecked()),
            timeout=60.0,
        )

    def browse_theme_path(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Choose theme file", "Wybierz plik theme"),
            str(Path.cwd()),
            "Theme files (*.json *.png *.jpg *.jpeg *.bmp *.webp *.gif);;JSON (*.json);;Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All files (*)",
        )
        if selected:
            self.theme_path_edit.setText(selected)

    def add_or_update_theme(self) -> None:
        name = self.theme_name_edit.text().strip()
        path = self.theme_path_edit.text().strip()
        if not name or not path:
            QMessageBox.information(
                self,
                self._tr("Information", "Informacja"),
                self._tr("Enter a theme name and file path.", "Podaj nazwę i plik theme."),
            )
            return
        payload = {
            "name": name,
            "path": path,
            "raw_jpeg_passthrough": bool(self.theme_raw_chk.isChecked()),
        }
        self.api_call("theme-add", "POST", "/v1/themes/add", payload, timeout=10.0)

    def remove_theme(self) -> None:
        name = self.theme_combo.currentText().strip()
        if not name:
            QMessageBox.information(
                self,
                self._tr("Information", "Informacja"),
                self._tr("No theme selected.", "Brak wybranego theme."),
            )
            return
        payload = {"name": name}
        self.api_call("theme-remove", "POST", "/v1/themes/remove", payload, timeout=10.0)

    def apply_theme(self) -> None:
        name = self.theme_combo.currentText().strip()
        if not name:
            QMessageBox.information(
                self,
                self._tr("Information", "Informacja"),
                self._tr("No theme selected.", "Brak wybranego theme."),
            )
            return
        item = self.theme_items.get(name, {})
        path = str(item.get("path", "")).strip()
        theme_type = str(item.get("type", "")).strip()
        stop_first = bool(self.theme_stop_before_apply_chk.isChecked())
        resume_loop = bool(self.theme_resume_chk.isChecked())
        if theme_type == "theme-doc" and path:
            payload = {"path": path, "resume_loop": resume_loop}
            self.api_call_with_optional_stop(
                "theme-doc-apply",
                "POST",
                "/v1/theme-doc/apply",
                payload,
                stop_first=stop_first,
                timeout=90.0,
            )
            return
        if path:
            payload = {
                "path": path,
                "raw_jpeg_passthrough": bool(item.get("raw_jpeg_passthrough", False)),
                "resume_loop": resume_loop,
            }
            self.api_call_with_optional_stop(
                "send-image",
                "POST",
                "/v1/send-image",
                payload,
                stop_first=stop_first,
                timeout=90.0,
            )
            return
        payload = {"name": name, "resume_loop": resume_loop}
        self.api_call_with_optional_stop(
            "theme-apply",
            "POST",
            "/v1/themes/apply",
            payload,
            stop_first=stop_first,
            timeout=90.0,
        )

    def _render_template_thumbnail(self, template_path: str) -> QPixmap | None:
        if render_theme_file is None:
            return None
        try:
            image = render_theme_file(template_path, stats_provider=self._preview_stats_provider)
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

    def _upright_template_pixmap(self, pixmap: QPixmap, template_path: str) -> QPixmap:
        try:
            raw = json.loads(Path(template_path).read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                rotation = int(raw.get("canvas", {}).get("rotation", 0)) % 360
                if rotation:
                    return pixmap.transformed(QTransform().rotate((-rotation) % 360), Qt.SmoothTransformation)
        except Exception:
            pass
        return pixmap

    def _render_template_placeholder(self, title: str, accent: str, size: QSize) -> QPixmap:
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

    def _runtime_theme_card_pixmap(self, item: dict[str, Any], size: QSize) -> QPixmap:
        path = str(item.get("path", "")).strip()
        theme_type = str(item.get("type", "image")).strip()
        if theme_type == "theme-doc" and render_theme_file is not None and path:
            try:
                image = render_theme_file(path, stats_provider=self._preview_stats_provider)
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
            asset_path = self._theme_card_fast_preview_asset(path)
            if asset_path:
                pixmap = QPixmap(str(asset_path))
                if not pixmap.isNull():
                    return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if path:
            resolved = self._resolve_theme_asset_path(path)
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self._render_template_placeholder(str(item.get("name", "Theme")), "#5ec8ff", size)

    def _theme_card_fast_preview_asset(self, raw_path: str) -> Path | None:
        def _resolve_from_theme(theme_dir: Path, asset: str) -> Path:
            candidate = Path(asset).expanduser()
            if candidate.is_absolute():
                return candidate.resolve()
            theme_candidate = (theme_dir / candidate).resolve()
            if theme_candidate.exists():
                return theme_candidate
            return (Path.cwd() / candidate).resolve()

        try:
            path = self._resolve_theme_asset_path(str(raw_path))
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

    def _render_theme_preview_pixmap(self, item: dict[str, Any], size: QSize) -> QPixmap:
        path = str(item.get("path", "")).strip()
        theme_name = str(item.get("name", "Theme")).strip() or "Theme"
        theme_type = str(item.get("type", "image")).strip()
        if theme_type == "theme-doc" and render_theme_file is not None and path:
            try:
                image = render_theme_file(path, stats_provider=self._preview_stats_provider)
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
            resolved = self._resolve_theme_asset_path(path)
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self._render_template_placeholder(theme_name, "#5ec8ff", size)

    def _open_theme_preview_dialog(self, theme_name: str, theme_item: dict[str, Any]) -> None:
        pixmap = self._render_theme_preview_pixmap(theme_item, QSize(1180, 360))
        dialog = ThemePreviewDialog(theme_name, pixmap, self)
        dialog.exec()

    def _rebuild_runtime_theme_cards(self) -> None:
        if not hasattr(self, "runtime_theme_cards_layout"):
            return
        while self.runtime_theme_cards_layout.count():
            child = self.runtime_theme_cards_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        if not self.theme_items:
            empty = QLabel("Brak motywów. Dodaj pierwszy motyw z pliku albo wygeneruj go w Theme Studio.")
            empty.setObjectName("selectionSummaryLabel")
            empty.setWordWrap(True)
            self.runtime_theme_cards_layout.addWidget(empty)
            self.runtime_theme_cards_layout.addStretch(1)
            return
        current = self.theme_combo.currentText().strip()
        for name, item in self.theme_items.items():
            card = AnimatedCardFrame("templateCard")
            layout = QHBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(14)
            thumb = QLabel()
            thumb.setObjectName("templateCardThumb")
            thumb.setFixedSize(180, 72)
            thumb.setPixmap(self._runtime_theme_card_pixmap(item, thumb.size()))
            layout.addWidget(thumb)
            text_col = QVBoxLayout()
            title = QLabel(name)
            title.setObjectName("templateCardTitle")
            meta = QLabel(f"{item.get('type', 'image')} | {Path(str(item.get('path', ''))).name}")
            meta.setObjectName("templateCardMeta")
            meta.setWordWrap(True)
            text_col.addWidget(title)
            text_col.addWidget(meta)
            text_col.addStretch(1)
            layout.addLayout(text_col, 1)
            actions = QVBoxLayout()
            select_btn = QPushButton("Wybierz")
            apply_btn = QPushButton("Zastosuj")
            remove_btn = QPushButton("Usuń")
            if name == current:
                apply_btn.setObjectName("primaryButton")
            for btn in (select_btn, apply_btn, remove_btn):
                btn.setMinimumHeight(36)
            select_btn.clicked.connect(lambda _checked=False, theme_name=name: self.theme_combo.setCurrentText(theme_name))
            apply_btn.clicked.connect(lambda _checked=False, theme_name=name: self._apply_runtime_theme_card(theme_name))
            remove_btn.clicked.connect(lambda _checked=False, theme_name=name: self._remove_runtime_theme_card(theme_name))
            actions.addWidget(select_btn)
            actions.addWidget(apply_btn)
            actions.addWidget(remove_btn)
            actions.addStretch(1)
            layout.addLayout(actions)
            self.runtime_theme_cards_layout.addWidget(card)
        self.runtime_theme_cards_layout.addStretch(1)

    def _library_theme_browser_width(self) -> int:
        viewport_width = 0
        if hasattr(self, "theme_browser_scroll"):
            try:
                viewport_width = self.theme_browser_scroll.viewport().width()
            except Exception:
                viewport_width = 0
        if viewport_width <= 0 and hasattr(self, "library_theme_cards_container"):
            viewport_width = self.library_theme_cards_container.width()
        return max(260, int(viewport_width or 960))

    def _schedule_library_theme_browser_rebuild(self) -> None:
        if not hasattr(self, "library_theme_cards_layout"):
            return
        if not (
            hasattr(self, "main_tabs")
            and hasattr(self, "studio_sections_tabs")
            and self.main_tabs.currentIndex() == 1
            and self.studio_sections_tabs.currentIndex() == 0
        ):
            self._library_theme_browser_dirty = True
            return
        width = self._library_theme_browser_width()
        if width == getattr(self, "_library_theme_browser_last_width", 0):
            return
        self._library_theme_browser_last_width = width
        if getattr(self, "_library_theme_browser_rebuild_pending", False):
            return
        self._library_theme_browser_rebuild_pending = True

        def _run() -> None:
            self._library_theme_browser_rebuild_pending = False
            self._rebuild_library_theme_browser()

        QTimer.singleShot(0, _run)

    def _rebuild_library_theme_browser(self) -> None:
        if not hasattr(self, "library_theme_cards_layout"):
            return
        while self.library_theme_cards_layout.count():
            child = self.library_theme_cards_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        needle = self.library_theme_filter_edit.text().strip().lower() if hasattr(self, "library_theme_filter_edit") else ""
        type_filter = self.library_theme_type_combo.currentText().strip() if hasattr(self, "library_theme_type_combo") else "All"
        items: list[tuple[str, dict[str, Any]]] = []
        for name, item in self.theme_items.items():
            theme_type = str(item.get("type", "image"))
            hay = " ".join([name, theme_type, str(item.get("path", ""))]).lower()
            if needle and needle not in hay:
                continue
            category = self._theme_card_category(item)
            if type_filter == "Image" and theme_type != "image":
                continue
            if type_filter == "Theme" and theme_type != "theme-doc":
                continue
            if type_filter in {"Local", "TTCR", "Animated"} and category != type_filter:
                continue
            items.append((name, item))
        sort_mode = self.library_theme_sort_combo.currentText().strip() if hasattr(self, "library_theme_sort_combo") else "Name A-Z"
        if sort_mode in {"Newest", "Oldest"}:
            def _mtime(entry: tuple[str, dict[str, Any]]) -> float:
                try:
                    resolved = self._resolve_theme_asset_path(str(entry[1].get("path", "")))
                    return resolved.stat().st_mtime if resolved.exists() else 0.0
                except Exception:
                    return 0.0
            items.sort(key=_mtime, reverse=(sort_mode == "Newest"))
        else:
            items.sort(key=lambda entry: entry[0].lower(), reverse=(sort_mode == "Name Z-A"))
        current = self.theme_combo.currentText().strip() if hasattr(self, "theme_combo") else ""
        if hasattr(self, "library_current_theme_label"):
            self.library_current_theme_label.setText(
                self._tr(f"Currently selected: {current}", f"Aktualnie wybrany: {current}") if current else self._tr("No active theme.", "Brak aktywnego motywu.")
            )
        if not items:
            empty = QLabel(self._tr("No themes match the current filter.", "Brak motywów pasujących do filtra."))
            empty.setObjectName("selectionSummaryLabel")
            empty.setWordWrap(True)
            self.library_theme_cards_layout.addWidget(empty, 0, 0)
            if hasattr(self, "theme_browser_scroll"):
                self.theme_browser_scroll.setMinimumHeight(96)
                self.theme_browser_scroll.setMaximumHeight(96)
            if hasattr(self, "theme_browser_box"):
                self.theme_browser_box.setMinimumHeight(212)
                self.theme_browser_box.setMaximumHeight(212)
            return
        viewport_width = self._library_theme_browser_width()
        spacing = self.library_theme_cards_layout.horizontalSpacing()
        available_width = max(260, viewport_width - 4)
        min_card_width = 300
        columns = max(1, min(4, (available_width + spacing) // (min_card_width + spacing)))
        card_width = max(260, int((available_width - ((columns - 1) * spacing)) / columns))
        compact_cards = card_width < 430
        card_height_base = 268 if compact_cards else 228
        if hasattr(self, "library_theme_cards_container"):
            self.library_theme_cards_container.setMinimumWidth(0)
            self.library_theme_cards_container.setMaximumWidth(viewport_width)
        for idx, (name, item) in enumerate(items):
            asset_count, animation_count = self._theme_card_stats(item)
            category = self._theme_card_category(item)
            is_current = name == current
            card_height = card_height_base + (24 if compact_cards and is_current else 0)
            card = AnimatedCardFrame("libraryCard")
            card.setObjectName("libraryCard")
            card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            card.setFixedWidth(card_width)
            card.setMinimumHeight(card_height)
            card.setMaximumHeight(card_height)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(6)
            thumb = QLabel()
            thumb.setObjectName("templateCardThumb")
            thumb.setMinimumSize(0, 92)
            thumb.setMaximumHeight(92)
            thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            thumb.setAlignment(Qt.AlignCenter)
            thumb_size = QSize(max(1, card_width - 20), 92)
            thumb.setPixmap(
                self._runtime_theme_card_pixmap(item, thumb_size).scaled(
                    thumb_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            layout.addWidget(thumb)
            top_meta_row = QHBoxLayout()
            top_meta_row.setSpacing(8)
            badge = QLabel(self._theme_type_badge(item))
            badge.setObjectName("layerBadgeLabel")
            category_badge = QLabel(category)
            category_badge.setObjectName("layerBadgeLabel")
            modified = QLabel(self._theme_modified_label(item))
            modified.setObjectName("libraryCardMeta")
            modified.setMinimumWidth(0)
            menu_btn = QPushButton("...")
            menu_btn.setMinimumSize(34, 28)
            menu_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item, btn=menu_btn: self._show_library_theme_card_menu(theme_name, theme_item, btn))
            top_meta_row.addWidget(badge, 0)
            top_meta_row.addWidget(category_badge, 0)
            top_meta_row.addWidget(modified, 1)
            top_meta_row.addWidget(menu_btn, 0)
            layout.addLayout(top_meta_row)
            title = QLabel(name)
            title.setObjectName("libraryCardTitle")
            title.setWordWrap(True)
            meta = QLabel(Path(str(item.get('path', ''))).name)
            meta.setObjectName("libraryCardMeta")
            meta.setWordWrap(True)
            desc_parts = []
            if asset_count:
                desc_parts.append(f"Assety: {asset_count}")
            if animation_count:
                desc_parts.append(f"Klatki: {animation_count}")
            desc_text = " • ".join(desc_parts) if desc_parts else (
                "Gotowy do edycji." if str(item.get("type", "")) == "theme-doc"
                else "Gotowy do użycia."
            )
            desc = QLabel(desc_text)
            desc.setObjectName("libraryCardDesc")
            desc.setWordWrap(True)
            layout.addWidget(title)
            layout.addWidget(meta)
            layout.addWidget(desc)
            if is_current:
                active_label = QLabel(self._tr("Currently selected", "Aktualnie wybrany"))
                active_label.setObjectName("layerBadgeLabel")
                layout.addWidget(active_label)
            startup_row = QHBoxLayout()
            startup_chk = QCheckBox(self._tr("Apply on startup", "Zastosuj przy uruchomieniu"))
            startup_chk.setChecked(name == self._startup_theme_name)
            startup_chk.toggled.connect(
                lambda checked, theme_name=name: self._set_startup_theme_preference(theme_name, checked)
            )
            startup_row.addWidget(startup_chk)
            startup_row.addStretch(1)
            layout.addLayout(startup_row)
            select_btn = QPushButton(self._tr("Edit", "Edytuj") if str(item.get("type", "")) == "theme-doc" else self._tr("Select", "Wybierz"))
            preview_btn = QPushButton(self._tr("Preview", "Podgląd"))
            apply_btn = QPushButton(self._tr("Apply", "Zastosuj"))
            duplicate_btn = QPushButton(self._tr("Duplicate", "Duplikuj"))
            remove_btn = QPushButton(self._tr("Remove", "Usuń"))
            apply_btn.setObjectName("primaryButton" if is_current else "secondaryAccentButton")
            for btn in (select_btn, preview_btn, apply_btn, duplicate_btn, remove_btn):
                btn.setMinimumHeight(28)
                btn.setMinimumWidth(0)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            select_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item: self._library_select_theme(theme_name, theme_item))
            preview_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item: self._open_theme_preview_dialog(theme_name, theme_item))
            apply_btn.clicked.connect(lambda _checked=False, theme_name=name: self._apply_runtime_theme_card(theme_name))
            duplicate_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item: self._duplicate_theme_card(theme_name, theme_item))
            remove_btn.clicked.connect(lambda _checked=False, theme_name=name: self._remove_runtime_theme_card(theme_name))
            if compact_cards:
                compact_actions = QGridLayout()
                compact_actions.setHorizontalSpacing(6)
                compact_actions.setVerticalSpacing(6)
                compact_actions.addWidget(select_btn, 0, 0)
                compact_actions.addWidget(preview_btn, 0, 1)
                compact_actions.addWidget(apply_btn, 0, 2)
                compact_actions.addWidget(duplicate_btn, 1, 0, 1, 2)
                compact_actions.addWidget(remove_btn, 1, 2)
                for action_col in range(3):
                    compact_actions.setColumnStretch(action_col, 1)
                layout.addLayout(compact_actions)
            else:
                actions = QHBoxLayout()
                actions.setSpacing(6)
                actions.addWidget(select_btn, 2)
                actions.addWidget(preview_btn, 1)
                actions.addWidget(apply_btn, 2)
                actions.addWidget(duplicate_btn, 1)
                actions.addWidget(remove_btn, 1)
                layout.addLayout(actions)
            row = idx // columns
            col = idx % columns
            self.library_theme_cards_layout.addWidget(card, row, col)
        for col in range(4):
            self.library_theme_cards_layout.setColumnStretch(col, 0)
        for col in range(columns):
            self.library_theme_cards_layout.setColumnStretch(col, 1)
        row_count = max(1, (len(items) + columns - 1) // columns)
        visible_rows = min(row_count, 3)
        visible_heights = [
            card_height_base + (24 if compact_cards and name == current else 0)
            for name, _item in items[: visible_rows * columns]
        ]
        viewport_card_height = max(visible_heights or [card_height_base])
        row_gap = self.library_theme_cards_layout.verticalSpacing()
        viewport_height = 14 + (visible_rows * viewport_card_height) + (max(0, visible_rows - 1) * row_gap) + 10
        if hasattr(self, "theme_browser_scroll"):
            self.theme_browser_scroll.setMinimumHeight(viewport_height)
            self.theme_browser_scroll.setMaximumHeight(viewport_height if row_count <= 3 else 760)
        if hasattr(self, "theme_browser_box"):
            controls_height = 110
            box_height = controls_height + viewport_height
            self.theme_browser_box.setMinimumHeight(box_height)
            self.theme_browser_box.setMaximumHeight(box_height if row_count <= 3 else 900)

    def _library_select_theme(self, theme_name: str, theme_item: dict[str, Any]) -> None:
        self.theme_combo.setCurrentText(theme_name)
        theme_type = str(theme_item.get("type", ""))
        path = str(theme_item.get("path", "")).strip()
        if theme_type == "theme-doc" and path:
            self.theme_doc_path_edit.setText(path)
            self.load_theme_doc()
            self._go_designer()

    def _set_startup_theme_preference(self, theme_name: str, enabled: bool) -> None:
        if enabled:
            next_name = theme_name
        elif self._startup_theme_name == theme_name:
            next_name = ""
        else:
            return
        if self._startup_theme_name == next_name:
            return
        self._startup_theme_name = next_name
        self._startup_theme_applied = False
        self._save_ui_state()
        self._rebuild_library_theme_browser()
        if next_name:
            self.append_log(f"[theme-startup] Ustawiono motyw startowy: {next_name}")
        else:
            self.append_log("[theme-startup] Wyczyszczono motyw startowy.")

    def _apply_startup_theme_if_needed(self) -> None:
        if self._startup_theme_applied:
            return
        theme_name = self._startup_theme_name.strip()
        if not theme_name or theme_name not in self.theme_items:
            return
        self._startup_theme_applied = True
        self._apply_runtime_theme_card(theme_name)

    def _theme_type_badge(self, theme_item: dict[str, Any]) -> str:
        theme_type = str(theme_item.get("type", "image")).strip()
        if theme_type == "theme-doc":
            return self._tr("Theme", "Motyw")
        if theme_type == "image":
            return self._tr("Image", "Obraz")
        return theme_type or self._tr("Theme", "Motyw")

    def _read_theme_document_for_card(self, theme_item: dict[str, Any]) -> dict[str, Any] | None:
        theme_type = str(theme_item.get("type", "")).strip()
        path = str(theme_item.get("path", "")).strip()
        if theme_type != "theme-doc" or not path:
            return None
        try:
            resolved = self._resolve_theme_asset_path(path)
            raw = parse_theme_json_text(resolved.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else None
        except Exception:
            return None

    def _theme_card_category(self, theme_item: dict[str, Any]) -> str:
        document = self._read_theme_document_for_card(theme_item)
        if isinstance(document, dict):
            effects = document.get("effects", {})
            animation = effects.get("animation", {}) if isinstance(effects, dict) else {}
            frame_paths = animation.get("frame_paths", []) if isinstance(animation, dict) else []
            if bool(animation.get("enabled", False)) and isinstance(frame_paths, list) and len(frame_paths) > 1:
                return "Animated"
            meta = document.get("meta", {})
            tags = meta.get("tags", []) if isinstance(meta, dict) else []
            if isinstance(tags, list) and any(str(tag).strip().lower() == "ttcr-import" for tag in tags):
                return "TTCR"
            if isinstance(effects, dict) and isinstance(effects.get("import_report"), dict):
                source_path = str(effects["import_report"].get("source_path", "")).lower()
                if "ttcr" in source_path:
                    return "TTCR"
        path = str(theme_item.get("path", "")).lower()
        if "ttcr" in path:
            return "TTCR"
        return "Local"

    def _theme_card_stats(self, theme_item: dict[str, Any]) -> tuple[int, int]:
        document = self._read_theme_document_for_card(theme_item)
        if not isinstance(document, dict):
            return 0, 0
        asset_count = 0
        background = document.get("background", {})
        if isinstance(background, dict) and str(background.get("path", "")).strip():
            asset_count += 1
        images = document.get("images", [])
        if isinstance(images, list):
            asset_count += sum(1 for item in images if isinstance(item, dict) and str(item.get("path", "")).strip())
        effects = document.get("effects", {})
        animation = effects.get("animation", {}) if isinstance(effects, dict) else {}
        frame_paths = animation.get("frame_paths", []) if isinstance(animation, dict) else []
        animation_count = len(frame_paths) if isinstance(frame_paths, list) else 0
        return asset_count, animation_count

    def _theme_modified_label(self, theme_item: dict[str, Any]) -> str:
        path = str(theme_item.get("path", "")).strip()
        if not path:
            return "Brak pliku"
        try:
            resolved = self._resolve_theme_asset_path(path)
            if resolved.exists():
                stamp = datetime.fromtimestamp(resolved.stat().st_mtime)
                return f"Zmieniono: {stamp.strftime('%Y-%m-%d %H:%M')}"
        except Exception:
            pass
        return "Brak daty"

    def _show_library_theme_card_menu(self, theme_name: str, theme_item: dict[str, Any], anchor: QWidget) -> None:
        menu = QMenu(self)
        tr = self._tr
        edit_action = menu.addAction(tr("Edit", "Edytuj"))
        preview_action = menu.addAction(tr("Preview", "Podgląd"))
        apply_action = menu.addAction(tr("Apply", "Zastosuj"))
        duplicate_action = menu.addAction(tr("Duplicate", "Duplikuj"))
        remove_action = menu.addAction(tr("Remove", "Usuń"))
        chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        if chosen == edit_action:
            self._library_select_theme(theme_name, theme_item)
        elif chosen == preview_action:
            self._open_theme_preview_dialog(theme_name, theme_item)
        elif chosen == apply_action:
            self._apply_runtime_theme_card(theme_name)
        elif chosen == duplicate_action:
            self._duplicate_theme_card(theme_name, theme_item)
        elif chosen == remove_action:
            self._remove_runtime_theme_card(theme_name)

    def _duplicate_theme_card(self, theme_name: str, theme_item: dict[str, Any]) -> None:
        theme_type = str(theme_item.get("type", "")).strip()
        path = str(theme_item.get("path", "")).strip()
        if theme_type != "theme-doc" or not path:
            QMessageBox.information(
                self,
                self._tr("Duplicate theme", "Duplikowanie motywu"),
                self._tr(
                    "Duplication is only available for saved editable theme documents.",
                    "Duplikowanie jest dostępne tylko dla zapisanych motywów edytowalnych.",
                ),
            )
            return
        try:
            src_path = self._resolve_theme_asset_path(path)
            document = parse_theme_json_text(src_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("Plik motywu nie zawiera poprawnego dokumentu.")
            new_name = f"{theme_name} Kopia"
            document.setdefault("meta", {})
            document["meta"]["name"] = new_name
            out_path = src_path.with_name(f"{src_path.stem}_kopia{src_path.suffix}")
            idx = 2
            while out_path.exists():
                out_path = src_path.with_name(f"{src_path.stem}_kopia_{idx}{src_path.suffix}")
                idx += 1
            out_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.api_call(
                "theme-add",
                "POST",
                "/v1/themes/add",
                {"name": new_name, "path": str(out_path), "raw_jpeg_passthrough": False},
                timeout=10.0,
            )
        except Exception as exc:
            QMessageBox.warning(self, self._tr("Duplicate theme", "Duplikowanie motywu"), str(exc))

    def _rebuild_theme_asset_gallery(self) -> None:
        if not hasattr(self, "asset_gallery_layout"):
            return
        while self.asset_gallery_layout.count():
            child = self.asset_gallery_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        asset_root = self._theme_assets_dir().parent
        if not asset_root.exists():
            empty = QLabel("Brak assetów dla bieżącego motywu. Zaimportuj tło albo obraz do motywu, aby zbudować bibliotekę.")
            empty.setObjectName("selectionSummaryLabel")
            empty.setWordWrap(True)
            self.asset_gallery_layout.addWidget(empty, 0, 0)
            return
        files = sorted(
            [p for p in asset_root.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}],
            key=lambda p: str(p),
        )
        if not files:
            empty = QLabel("Brak obrazów w katalogu assetów tego motywu.")
            empty.setObjectName("selectionSummaryLabel")
            empty.setWordWrap(True)
            self.asset_gallery_layout.addWidget(empty, 0, 0)
            return
        container_width = max(720, self.asset_gallery_container.width() if hasattr(self, "asset_gallery_container") else 960)
        columns = max(1, min(4, container_width // 320))
        for idx, path in enumerate(files[:40]):
            card = AnimatedCardFrame("assetCard")
            card.setObjectName("assetCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            thumb = QLabel()
            thumb.setObjectName("templateCardThumb")
            thumb.setMinimumSize(240, 92)
            thumb.setMaximumHeight(92)
            thumb.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                thumb.setPixmap(pixmap.scaled(thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(thumb)
            title = QLabel(path.name)
            title.setObjectName("libraryCardTitle")
            title.setWordWrap(True)
            meta = QLabel(str(path.relative_to(asset_root)))
            meta.setObjectName("libraryCardMeta")
            meta.setWordWrap(True)
            desc = QLabel("Zasób gotowy do użycia jako tło albo warstwa obrazu.")
            desc.setObjectName("libraryCardDesc")
            desc.setWordWrap(True)
            layout.addWidget(title)
            layout.addWidget(meta)
            layout.addWidget(desc)
            layout.addStretch(1)
            actions = QHBoxLayout()
            actions.setSpacing(8)
            bg_btn = QPushButton("Ustaw jako tło")
            img_btn = QPushButton("Dodaj jako obraz")
            bg_btn.setObjectName("secondaryAccentButton")
            bg_btn.clicked.connect(lambda _checked=False, p=path: self._use_gallery_asset_as_background(p))
            img_btn.clicked.connect(lambda _checked=False, p=path: self._use_gallery_asset_as_image(p))
            actions.addWidget(bg_btn)
            actions.addWidget(img_btn)
            layout.addLayout(actions)
            row = idx // columns
            col = idx % columns
            self.asset_gallery_layout.addWidget(card, row, col)
        for col in range(columns):
            self.asset_gallery_layout.setColumnStretch(col, 1)

    def _use_gallery_asset_as_background(self, path: Path) -> None:
        self.bg_path_edit.setText(self._theme_display_path(path))
        self.bg_kind_combo.setCurrentText("image")
        animation = self._current_animation_effect()
        animation["enabled"] = False
        self._refresh_animation_controls()
        self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text=self._empty_background_preview_caption())
        self.on_background_field_changed()

    def _load_ttcr_stat_rules(self) -> dict[str, str]:
        try:
            if TTCR_STAT_RULES_PATH.exists():
                raw = json.loads(TTCR_STAT_RULES_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    out: dict[str, str] = {}
                    for key, value in raw.items():
                        key_text = str(key).strip().lower()
                        value_text = str(value).strip()
                        if key_text and value_text in self.theme_stat_sources:
                            out[key_text] = value_text
                    return out
        except Exception:
            pass
        return {}

    def _normalize_ttcr_rule_key(self, label: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(label).strip()).strip("_")

    def _save_ttcr_stat_rules(self, rules: dict[str, str]) -> None:
        try:
            TTCR_STAT_RULES_PATH.write_text(
                json.dumps(rules, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _apply_saved_ttcr_stat_rules(
        self,
        report: dict[str, Any],
        stats: list[dict[str, Any]],
    ) -> bool:
        rules = self._load_ttcr_stat_rules()
        if not rules:
            return False
        stat_entries = report.get("stat_entries", [])
        if not isinstance(stat_entries, list):
            return False
        changed = False
        for idx, entry in enumerate(stat_entries):
            if not isinstance(entry, dict) or not (0 <= idx < len(stats)) or not isinstance(stats[idx], dict):
                continue
            label_key = self._normalize_ttcr_rule_key(str(entry.get("label", "")).strip())
            if not label_key:
                continue
            target_source = rules.get(label_key)
            if target_source and stats[idx].get("source") != target_source:
                stats[idx]["source"] = target_source
                entry["source"] = target_source
                changed = True
        if changed:
            report["detected_stats"] = sorted(
                {str(item.get("source", "")).strip() for item in stats if isinstance(item, dict) and str(item.get("source", "")).strip()}
            )
        return changed

    def _review_single_ttcr_import_mappings(
        self,
        *,
        theme_name: str,
        theme_path: str,
        report: dict[str, Any],
    ) -> None:
        stat_entries = report.get("stat_entries", [])
        if not isinstance(stat_entries, list):
            stat_entries = []
        unmapped_stats = report.get("unmapped_stats", [])
        if not isinstance(unmapped_stats, list):
            unmapped_stats = []
        if not isinstance(self.theme_doc_model, dict):
            return
        stats = self.theme_doc_model.get("stats", [])
        if not isinstance(stats, list):
            return
        preset_changed = self._apply_saved_ttcr_stat_rules(report, stats)
        stat_entries = report.get("stat_entries", [])
        if not isinstance(stat_entries, list):
            stat_entries = []
        if not stat_entries and not unmapped_stats:
            return
        dialog = TTCRImportReviewDialog(
            self,
            theme_name=theme_name,
            stat_sources=self.theme_stat_sources,
            stat_entries=[entry for entry in stat_entries if isinstance(entry, dict)],
            unmapped_stats=[str(item) for item in unmapped_stats],
        )
        if dialog.exec() != QDialog.Accepted:
            return
        changed = False
        stat_entries_by_idx = [entry for entry in stat_entries if isinstance(entry, dict)]
        selected = dialog.selected_sources()
        for idx, source, label_text in selected:
            if 0 <= idx < len(stats) and isinstance(stats[idx], dict):
                if stats[idx].get("source") != source:
                    stats[idx]["source"] = source
                    changed = True
                continue
            unmapped_index = idx - len(stat_entries_by_idx)
            if 0 <= unmapped_index < len(unmapped_stats):
                raw_entry = unmapped_stats[unmapped_index]
                if isinstance(raw_entry, dict):
                    stats.append(
                        {
                            "id": f"stat_{len(stats)}",
                            "label": str(raw_entry.get("label", label_text)).strip() or label_text or source,
                            "source": source,
                            "format": "{value}",
                            "x": int(raw_entry.get("x", 0) or 0),
                            "y": int(raw_entry.get("y", 0) or 0),
                            "box_width": int(raw_entry.get("box_width", 220) or 220),
                            "box_height": int(raw_entry.get("box_height", 52) or 52),
                            "font_family": "DejaVu Sans",
                            "font_size": int(raw_entry.get("font_size", 28) or 28),
                            "label_color": [255, 255, 255],
                            "value_color": [220, 220, 220],
                            "align": "left",
                            "z_index": 240 + len(stats),
                            "visible": True,
                            "locked": False,
                        }
                    )
                    changed = True
        if dialog.remember_rules():
            rules = self._load_ttcr_stat_rules()
            for idx, source, label_text in selected:
                if source not in self.theme_stat_sources:
                    continue
                if 0 <= idx < len(stat_entries_by_idx) and isinstance(stat_entries_by_idx[idx], dict):
                    label_key = self._normalize_ttcr_rule_key(str(stat_entries_by_idx[idx].get("label", "")).strip())
                    if label_key:
                        rules[label_key] = source
                    continue
                label_key = self._normalize_ttcr_rule_key(label_text)
                if label_key:
                    rules[label_key] = source
            self._save_ttcr_stat_rules(rules)
        if not changed and not preset_changed:
            return
        try:
            normalized = normalize_theme_document(self.theme_doc_model)
            self.theme_doc_model = normalized
            self._set_theme_doc_editor_document(normalized)
            save_theme_document(theme_path, normalized)
            self.refresh_designer_element_list()
            self.load_selected_designer_item()
            self._update_preview_canvas_overlay()
            self._sync_designer_preview_policy()
            self.preview_theme_doc()
        except Exception as exc:
            QMessageBox.warning(
                self,
                self._tr("TTCR import", "Import TTCR"),
                self._tr(
                    "Could not save the corrected stat mapping:\n{err}",
                    "Nie udało się zapisać poprawionego mapowania statystyk:\n{err}",
                ).format(err=exc),
            )

    def import_ttcr_theme_bundle(self) -> None:
        if import_ttcr_theme is None:
            QMessageBox.warning(
                self,
                self._tr("TTCR import", "Import TTCR"),
                self._tr("The TTCR import module is not available.", "Moduł importu TTCR nie jest dostępny."),
            )
            return
        default_dir = Path.cwd()
        ttcr_root = Path.cwd() / "TTCR_Windows"
        if ttcr_root.exists():
            default_dir = ttcr_root
        directory = QFileDialog.getExistingDirectory(
            self,
            "Wybierz katalog motywu TTCR z kompletem zasobów",
            str(default_dir),
        )
        if not directory:
            return
        source_path = Path(directory).expanduser()

        output_path = self._suggest_ttcr_import_output_path(source_path)
        try:
            result = import_ttcr_theme(source_path, output_path)
        except Exception as exc:
            QMessageBox.warning(self, self._tr("TTCR import", "Import TTCR"), str(exc))
            return

        document = result.get("document")
        resolved_output = str(result.get("output_theme_path", output_path))
        theme_name = str(result.get("theme_name", "")).strip() or Path(resolved_output).stem
        report = result.get("report", {}) if isinstance(result.get("report"), dict) else {}
        generated_themes = result.get("generated_themes", [])

        if isinstance(document, dict):
            self.theme_doc_path_edit.setText(resolved_output)
            self.theme_doc_model = normalize_theme_document(document)
            self._set_theme_doc_editor_document(self.theme_doc_model)
            self.refresh_designer_element_list()
            self._load_background_fields()
            self.load_selected_designer_item()
            self._update_preview_canvas_overlay()
            self.preview_theme_doc()
            self._rebuild_theme_asset_gallery()

        theme_entries = []
        if isinstance(generated_themes, list) and generated_themes:
            for entry in generated_themes:
                if not isinstance(entry, dict):
                    continue
                entry_name = str(entry.get("theme_name", "")).strip()
                entry_path = str(entry.get("output_theme_path", "")).strip()
                if entry_name and entry_path:
                    theme_entries.append((entry_name, entry_path))
        if not theme_entries:
            theme_entries.append((theme_name, resolved_output))

        for entry_name, entry_path in theme_entries:
            self.api_call(
                "theme-add",
                "POST",
                "/v1/themes/add",
                {
                    "name": entry_name,
                    "path": entry_path,
                    "raw_jpeg_passthrough": False,
                },
                timeout=10.0,
            )
        self.refresh_themes()
        first_name, first_path = theme_entries[0]
        self.theme_combo.setCurrentText(first_name)
        if len(theme_entries) == 1 and isinstance(document, dict):
            self._go_designer()
            self._review_single_ttcr_import_mappings(
                theme_name=first_name,
                theme_path=resolved_output,
                report=report,
            )
        else:
            self._go_library()

        detected_stats = report.get("detected_stats", [])
        if not isinstance(detected_stats, list):
            detected_stats = []
        unmapped_stats = report.get("unmapped_stats", [])
        if not isinstance(unmapped_stats, list):
            unmapped_stats = []
        multi_detected_stats: list[str] = []
        multi_unmapped_stats: list[str] = []
        variant_lines: list[str] = []
        if isinstance(generated_themes, list) and generated_themes:
            for entry in generated_themes:
                if not isinstance(entry, dict):
                    continue
                entry_name = str(entry.get("theme_name", "")).strip()
                entry_report = entry.get("report", {})
                if not isinstance(entry_report, dict):
                    continue
                for source in entry_report.get("detected_stats", []) or []:
                    source_text = str(source).strip()
                    if source_text and source_text not in multi_detected_stats:
                        multi_detected_stats.append(source_text)
                for source in entry_report.get("unmapped_stats", []) or []:
                    source_text = str(source).strip()
                    if source_text and source_text not in multi_unmapped_stats:
                        multi_unmapped_stats.append(source_text)
                if entry_name:
                    mapped = ", ".join((entry_report.get("detected_stats", []) or [])[:4]) or "brak"
                    unmapped = ", ".join((entry_report.get("unmapped_stats", []) or [])[:3]) or "-"
                    variant_lines.append(f"- {entry_name}: mapowane [{mapped}], do sprawdzenia [{unmapped}]")

        animations = report.get("preserved_animations", [])
        extracted_frames = report.get("extracted_frames", [])
        background_source = str(report.get("background_source", "")).strip()
        anim_note = (
            f"\nZachowane animacje/assety: {len(animations)}."
            if isinstance(animations, list) and animations
            else ""
        )
        frames_note = (
            f"\nWyodrębnione klatki z kontenerów TTCR: {len(extracted_frames)}."
            if isinstance(extracted_frames, list) and extracted_frames
            else ""
        )
        variants_note = (
            f"\nZaimportowane warianty: {len(theme_entries)}."
            if len(theme_entries) > 1
            else ""
        )
        stats_sources = multi_detected_stats or detected_stats
        stats_note = (
            f"\nWykryte statystyki TTCR i zmapowane na Linux: {', '.join(stats_sources[:8])}."
            if stats_sources
            else "\nNie wykryto jednoznacznych statystyk TTCR do automatycznego mapowania."
        )
        if len(stats_sources) > 8:
            stats_note += f" (+{len(stats_sources) - 8} więcej)"
        unmapped_sources = multi_unmapped_stats or unmapped_stats
        unmapped_note = (
            f"\nDo ręcznej korekty po imporcie: {', '.join(unmapped_sources[:6])}."
            if unmapped_sources
            else ""
        )
        if len(unmapped_sources) > 6:
            unmapped_note += f" (+{len(unmapped_sources) - 6} więcej)"
        variants_detail_note = (
            "\n\nSkrót wariantów:\n" + "\n".join(variant_lines[:8])
            if variant_lines
            else ""
        )
        if len(variant_lines) > 8:
            variants_detail_note += f"\n... i jeszcze {len(variant_lines) - 8} wariantów."
        background_note = (
            f"\nŹródło tła po imporcie: {background_source}."
            if background_source
            else ""
        )
        QMessageBox.information(
            self,
            "Import TTCR",
            (
                f"Import zakończony.\n"
                f"Katalog: {source_path}\n"
                f"Zaimportowany motyw startowy: {first_name}\n"
                f"Aplikacja złożyła działający motyw Linux z całego katalogu TTCR, mapując układ, tła, obrazy, animacje i statystyki.{variants_note}{background_note}{stats_note}{unmapped_note}{frames_note}{anim_note}{variants_detail_note}"
            ),
        )

    def _use_gallery_asset_as_image(self, path: Path) -> None:
        combo_index = self.designer_kind_combo.findData("images")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        items = self._current_theme_items()
        self.push_designer_history()
        new_item = self._make_default_element("images")
        new_item["path"] = self._theme_display_path(path)
        new_item["fit"] = "cover"
        canvas = self.theme_doc_model.get("canvas", {}) if self.theme_doc_model is not None else {}
        new_item["rect"] = [0, 0, int(canvas.get("width", 1920)), int(canvas.get("height", 462))]
        items.append(new_item)
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.designer_element_list.setCurrentRow(len(items) - 1)
        self._set_image_preview_label(self.designer_image_preview_label, new_item["path"], empty_text=self._empty_image_preview_caption())
        self.schedule_preview_theme_doc()

    def _apply_runtime_theme_card(self, theme_name: str) -> None:
        self.theme_combo.setCurrentText(theme_name)
        self.apply_theme()

    def _remove_runtime_theme_card(self, theme_name: str) -> None:
        answer = QMessageBox.question(
            self,
            "Usuń motyw",
            f"Czy na pewno chcesz usunąć motyw:\n\n{theme_name}\n\nTej operacji nie można cofnąć.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.theme_combo.setCurrentText(theme_name)
        self.remove_theme()

    def _refresh_template_cards(self) -> None:
        for item in self._template_cards:
            thumb = item["thumb"]
            path = item["path"]
            pixmap = self._render_template_thumbnail(path)
            if pixmap is None or pixmap.isNull():
                thumb.setText("")
                thumb.setPixmap(self._render_template_placeholder(item["title"], item["accent"], thumb.size()))
            else:
                thumb.setText("")
                thumb.setPixmap(
                    pixmap.scaled(
                        thumb.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
        if render_theme_file is None:
            self._request_template_previews()

    def _request_template_previews(self) -> None:
        for item in self._template_cards:
            path = str(Path(item["path"]).resolve())
            try:
                document = parse_theme_json_text(Path(path).read_text(encoding="utf-8"))
                if not isinstance(document, dict):
                    continue
            except Exception:
                continue
            self.api_call(
                f"template-preview::{path}",
                "POST",
                "/v1/theme-doc/preview",
                {"path": path, "document": document},
                timeout=20.0,
            )

    def browse_new_theme_path(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Save new theme", "Zapisz nowy motyw"),
            self.new_theme_path_edit.text().strip() or str(self._default_new_theme_path()),
            "JSON (*.json);;All files (*)",
        )
        if selected:
            self._new_theme_path_user_edited = True
            self.new_theme_path_edit.setText(selected)

    def _default_new_theme_dir(self) -> Path:
        path = (Path.cwd() / "themes").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _sanitize_theme_name_for_filename(self, name: str) -> str:
        sanitized = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
        return sanitized or "nowy_motyw"

    def _default_new_theme_path(self) -> Path:
        base_name = self._sanitize_theme_name_for_filename(self.new_theme_name_edit.text().strip())
        template_path = str(self.new_theme_template_combo.currentData() or "themes/nowy_motyw.json")
        template_stem = Path(template_path).stem.replace("_monitor", "")
        suffix = template_stem if template_stem and template_stem not in {"nowy_motyw", base_name} else ""
        filename = f"{base_name}.json" if not suffix else f"{base_name}_{suffix}.json"
        return self._default_new_theme_dir() / filename

    def _mark_new_theme_path_customized(self, _text: str) -> None:
        self._new_theme_path_user_edited = True

    def _toggle_new_theme_advanced(self, checked: bool) -> None:
        self.new_theme_path_row.setVisible(bool(checked))
        self.new_theme_advanced_btn.setText("Ukryj ustawienia pliku" if checked else "Ustawienia pliku")

    def suggest_new_theme_path_from_template(self) -> None:
        if getattr(self, "_new_theme_path_user_edited", False):
            return
        self.new_theme_path_edit.setText(str(self._default_new_theme_path()))

    def create_new_theme_from_template(self) -> None:
        template_path = str(self.new_theme_template_combo.currentData() or "").strip()
        output_path = self.new_theme_path_edit.text().strip()
        theme_name = self.new_theme_name_edit.text().strip()
        if not template_path or not output_path or not theme_name:
            QMessageBox.information(self, "Info", "Podaj nazwę, plik i wybierz styl startowy.")
            return
        try:
            src_path = Path(template_path)
            if not src_path.is_absolute():
                src_path = Path.cwd() / src_path
            document = parse_theme_json_text(src_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("Szablon nie jest poprawnym obiektem JSON.")
            document.setdefault("meta", {})
            document["meta"]["name"] = theme_name
            document["meta"]["description"] = f"Motyw utworzony na bazie {Path(template_path).stem}."
            resolved_out = Path(output_path)
            if not resolved_out.is_absolute():
                resolved_out = Path.cwd() / resolved_out
            resolved_out.parent.mkdir(parents=True, exist_ok=True)
            resolved_out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "Template Error", str(exc))
            return

        self.load_theme_template(str(resolved_out), preview_after=True)
        QMessageBox.information(self, "Nowy motyw", f"Utworzono nowy motyw:\n{resolved_out}")

    def load_theme_template(self, template_path: str, *, preview_after: bool = True) -> None:
        resolved = Path(template_path)
        if not resolved.is_absolute():
            resolved = Path.cwd() / resolved
        if not resolved.exists():
            QMessageBox.warning(self, "Template Error", f"Nie znaleziono szablonu:\n{resolved}")
            return
        try:
            raw = parse_theme_json_text(resolved.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Template musi być obiektem JSON.")
            normalized = normalize_theme_document(raw)
        except Exception as exc:
            QMessageBox.warning(self, "Template Error", str(exc))
            return

        self.theme_doc_path_edit.setText(str(resolved))
        self.theme_doc_model = deepcopy(normalized)
        self._set_theme_doc_editor_document(normalized)
        self.refresh_designer_element_list()
        self._load_background_fields()
        self._sync_designer_preview_policy()
        self.load_selected_designer_item()
        self._mark_theme_doc_clean()
        if preview_after:
            self.preview_theme_doc()

    def browse_theme_doc_path(self) -> None:
        if not self._confirm_discard_unsaved_theme_changes(self._tr("browse another theme", "wybór innego motywu")):
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik motywu",
            str(Path.cwd() / "themes"),
            "JSON (*.json);;All files (*)",
        )
        if selected:
            self.theme_doc_path_edit.setText(selected)

    def use_selected_theme_doc(self) -> None:
        if not self._confirm_discard_unsaved_theme_changes(self._tr("use selected theme", "użycie wybranego motywu")):
            return
        name = self.theme_combo.currentText().strip()
        if not name:
            QMessageBox.information(self, "Info", "Najpierw wybierz motyw z listy.")
            return
        item = self.theme_items.get(name, {})
        path = str(item.get("path", "")).strip()
        theme_type = str(item.get("type", "")).strip()
        if not path:
            QMessageBox.information(self, "Info", "Wybrany motyw nie ma ścieżki.")
            return
        if theme_type != "theme-doc" and not path.lower().endswith(".json"):
            QMessageBox.information(self, "Info", "Wybrany motyw nie jest edytowalnym motywem.")
            return
        self.theme_doc_path_edit.setText(path)

    def _parse_theme_doc_editor(self) -> dict[str, Any] | None:
        raw = self.theme_doc_editor.toPlainText().strip()
        if not raw:
            QMessageBox.information(self, "Info", "Motyw jest pusty.")
            return None
        try:
            document = parse_theme_json_text(raw)
        except json.JSONDecodeError as exc:
            QMessageBox.warning(
                self,
                self._tr("Theme error", "Błąd motywu"),
                self._tr("Could not read theme data: {err}", "Nie udało się odczytać danych motywu: {err}").format(err=exc),
            )
            return None
        if not isinstance(document, dict):
            QMessageBox.warning(
                self,
                self._tr("Theme error", "Błąd motywu"),
                self._tr("The theme file format is invalid.", "Plik motywu ma niepoprawny format."),
            )
            return None
        return document

    def _set_theme_doc_editor_document(self, document: dict[str, Any]) -> None:
        self._theme_doc_editor_syncing = True
        try:
            self.theme_doc_editor.setPlainText(json.dumps(document, ensure_ascii=False, indent=2))
        finally:
            self._theme_doc_editor_syncing = False

    def open_current_theme_json_externally(self, *, from_animation_studio: bool = False) -> None:
        if self.theme_doc_model is None:
            QMessageBox.information(
                self,
                self._tr("Theme JSON", "JSON motywu"),
                self._tr("Load or create a theme first.", "Najpierw wczytaj lub utwórz motyw."),
            )
            return
        path = self.theme_doc_path_edit.text().strip()
        if not path:
            QMessageBox.information(
                self,
                self._tr("Theme JSON", "JSON motywu"),
                self._tr(
                    "Set the theme file path first (JSON tab — theme file field).",
                    "Najpierw ustaw ścieżkę pliku motywu (zakładka JSON — pole pliku).",
                ),
            )
            return
        resolved = Path(path).expanduser()
        if not resolved.is_absolute():
            resolved = (Path.cwd() / resolved).resolve()
        try:
            normalized = normalize_theme_document(deepcopy(self.theme_doc_model))
            self.theme_doc_model = normalized
            save_theme_document(resolved, normalized, include_doc_header=True)
            self._set_theme_doc_editor_document(normalized)
            self._mark_theme_doc_clean()
        except Exception as exc:
            QMessageBox.warning(
                self,
                self._tr("Theme JSON", "JSON motywu"),
                self._tr(f"Could not write theme file:\n{exc}", f"Nie można zapisać pliku motywu:\n{exc}"),
            )
            return
        url = QUrl.fromLocalFile(str(resolved.resolve()))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                self._tr("Theme JSON", "JSON motywu"),
                self._tr(
                    f"No application opened this file:\n{resolved}",
                    f"Nie otwarto pliku w domyślnej aplikacji:\n{resolved}",
                ),
            )
            return
        extra = ""
        if from_animation_studio:
            extra = " " + self._tr(
                "Background animation: effects.animation.",
                "Animacja tła: effects.animation.",
            )
        self._set_designer_toolbar_feedback(
            self._tr(
                "Theme JSON opened in external editor. After saving there, use Load theme to refresh." + extra,
                "Otwarto plik JSON motywu w zewnętrznym edytorze. Po zapisie tam użyj „Wczytaj motyw”, by odświeżyć."
                + extra,
            ),
            auto_clear_ms=9000,
        )

    def insert_theme_json_field_guide_in_editor(self) -> None:
        guide = theme_json_documentation_preamble()
        cur = self.theme_doc_editor.toPlainText()
        if "Open Trofeo LCD — theme JSON" in cur[:2048]:
            QMessageBox.information(
                self,
                self._tr("Field guide", "Opis pól"),
                self._tr("The guide is already at the beginning of the editor.", "Opis jest już na początku edytora."),
            )
            return
        self.theme_doc_editor.setPlainText(guide + cur)

    def _theme_doc_editor_differs_from_model(self) -> bool:
        if not isinstance(self.theme_doc_model, dict):
            return bool(self.theme_doc_editor.toPlainText().strip())
        try:
            model_text = json.dumps(self.theme_doc_model, ensure_ascii=False, indent=2).strip()
        except Exception:
            return True
        editor_text = self.theme_doc_editor.toPlainText().strip()
        return editor_text != model_text

    def _current_theme_document(self, *, allow_editor_fallback: bool = True) -> dict[str, Any] | None:
        if isinstance(self.theme_doc_model, dict) and not self._theme_doc_editor_differs_from_model():
            return deepcopy(self.theme_doc_model)
        if not allow_editor_fallback:
            QMessageBox.information(self, "Info", "Najpierw wczytaj albo utwórz motyw.")
            return None
        document = self._parse_theme_doc_editor()
        if document is None:
            return None
        try:
            normalized = normalize_theme_document(document)
        except Exception as exc:
            QMessageBox.warning(self, self._tr("Theme error", "Błąd motywu"), str(exc))
            return None
        self.theme_doc_model = deepcopy(normalized)
        self._set_theme_doc_editor_document(normalized)
        self._sync_designer_preview_policy()
        self._load_background_fields()
        self.refresh_designer_element_list()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()
        return deepcopy(normalized)

    def load_theme_doc(self) -> None:
        if not self._confirm_discard_unsaved_theme_changes(self._tr("load theme", "wczytanie motywu")):
            self._set_designer_toolbar_busy("theme-doc-load", False)
            return
        theme_path = self.theme_doc_path_edit.text().strip()
        if not theme_path:
            self._set_designer_toolbar_busy("theme-doc-load", False)
            QMessageBox.information(self, "Info", "Podaj ścieżkę do pliku motywu.")
            return
        self.api_call("theme-doc-load", "POST", "/v1/theme-doc/load", {"path": theme_path}, timeout=15.0)

    def save_theme_doc(self) -> None:
        theme_path = self.theme_doc_path_edit.text().strip()
        if not theme_path:
            QMessageBox.information(self, "Info", "Podaj ścieżkę do pliku motywu.")
            return
        document = self._current_theme_document()
        if document is None:
            return
        payload = {"path": theme_path, "document": document}
        self.api_call("theme-doc-save", "POST", "/v1/theme-doc/save", payload, timeout=20.0)

    def _suggest_theme_save_as_path(self) -> Path:
        raw = self.theme_doc_path_edit.text().strip()
        if raw:
            current = Path(raw).expanduser()
            if not current.is_absolute():
                current = (Path.cwd() / current).resolve()
            parent = current.parent if current.parent else (Path.cwd() / "themes").resolve()
            stem = current.stem or "theme"
            candidate = parent / f"{stem}_copy.json"
        else:
            parent = (Path.cwd() / "themes").resolve()
            candidate = parent / "theme_copy.json"
        index = 2
        while candidate.exists():
            candidate = candidate.with_name(f"{candidate.stem.rsplit('_', 1)[0] if candidate.stem.endswith(f'_{index - 1}') else candidate.stem}_{index}.json")
            index += 1
        return candidate

    def save_theme_doc_as(self, *, from_animation_studio: bool = False) -> None:
        document = self._current_theme_document()
        if document is None:
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Save Theme As", "Zapisz motyw jako"),
            str(self._suggest_theme_save_as_path()),
            "JSON (*.json);;All files (*)",
        )
        if not selected:
            return
        target = Path(selected).expanduser()
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()

        normalized = normalize_theme_document(deepcopy(document))
        self.theme_doc_path_edit.setText(str(target))
        self.theme_doc_model = deepcopy(normalized)
        self._set_theme_doc_editor_document(normalized)
        self._load_background_fields()
        self.refresh_designer_element_list()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()
        self._sync_designer_preview_policy()
        self._schedule_theme_autosave()
        self._run_theme_library_workflow(
            action="studio-theme-save",
            theme_path=str(target),
            document=normalized,
            apply_after=False,
        )
        origin = self._tr("Animation Studio", "Studio animacji") if from_animation_studio else self._tr("Theme Designer", "Projektant")
        self._set_designer_toolbar_feedback(
            self._tr(
                f"{origin}: saving theme copy {target.name}.",
                f"{origin}: zapisuję kopię motywu {target.name}.",
            )
        )

    def _current_theme_library_name(self, document: dict[str, Any] | None = None) -> str:
        if isinstance(document, dict):
            meta = document.get("meta", {})
            if isinstance(meta, dict):
                name = str(meta.get("name", "")).strip()
                if name:
                    return name
        theme_path = self.theme_doc_path_edit.text().strip()
        if theme_path:
            return Path(theme_path).stem.replace("_", " ").strip() or "Nowy motyw"
        return "Nowy motyw"

    def _run_theme_library_workflow(
        self,
        *,
        action: str,
        theme_path: str,
        document: dict[str, Any],
        apply_after: bool,
    ) -> None:
        theme_name = self._current_theme_library_name(document)
        stop_first = bool(self.theme_doc_stop_before_apply_chk.isChecked()) if apply_after else False
        resume_loop = bool(self.theme_doc_resume_chk.isChecked()) if apply_after else False

        def worker() -> None:
            try:
                if stop_first and bool(self.current_status.get("running", False)):
                    self.client.request(method="POST", path="/v1/stop", payload={}, timeout=20.0)
                    time.sleep(0.4)

                save_data = self.client.request(
                    method="POST",
                    path="/v1/theme-doc/save",
                    payload={"path": theme_path, "document": document},
                    timeout=20.0,
                )
                save_result = save_data.get("result", {}) if isinstance(save_data, dict) else {}
                resolved_path = str(save_result.get("resolved_path", theme_path)).strip() or theme_path

                add_data = self.client.request(
                    method="POST",
                    path="/v1/themes/add",
                    payload={
                        "name": theme_name,
                        "path": resolved_path,
                        "raw_jpeg_passthrough": False,
                    },
                    timeout=12.0,
                )
                themes_payload = add_data.get("themes", add_data.get("result", {})) if isinstance(add_data, dict) else {}

                if apply_after:
                    apply_data = self.client.request(
                        method="POST",
                        path="/v1/themes/apply",
                        payload={"name": theme_name, "resume_loop": resume_loop},
                        timeout=90.0,
                    )
                    payload = {
                        "result": {
                            "name": theme_name,
                            "resolved_path": resolved_path,
                            "saved": True,
                            "applied": True,
                        },
                        "themes": themes_payload,
                        "status": apply_data.get("status", apply_data) if isinstance(apply_data, dict) else {},
                    }
                    self.api_result.emit(action, True, payload)
                    return

                payload = {
                    "result": {
                        "name": theme_name,
                        "resolved_path": resolved_path,
                        "saved": True,
                    },
                    "themes": themes_payload,
                    "status": save_data.get("status", save_data) if isinstance(save_data, dict) else {},
                }
                self.api_result.emit(action, True, payload)
            except Exception as exc:
                self.api_result.emit(action, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def save_current_theme_to_library(self) -> None:
        theme_path = self.theme_doc_path_edit.text().strip()
        if not theme_path:
            self._set_designer_toolbar_busy("studio-theme-save", False)
            QMessageBox.information(self, "Info", "Najpierw wybierz lub utwórz motyw.")
            return
        document = self._current_theme_document()
        if document is None:
            self._set_designer_toolbar_busy("studio-theme-save", False)
            return
        self._run_theme_library_workflow(
            action="studio-theme-save",
            theme_path=theme_path,
            document=document,
            apply_after=False,
        )

    def apply_current_theme_to_lcd(self) -> None:
        self.apply_theme_doc()

    def apply_theme_doc(self) -> None:
        theme_path = self.theme_doc_path_edit.text().strip()
        if not theme_path:
            QMessageBox.information(self, "Info", "Podaj ścieżkę do pliku motywu.")
            return
        document = self._current_theme_document()
        if document is None:
            return
        payload = {
            "path": theme_path,
            "document": document,
            "resume_loop": bool(self.theme_doc_resume_chk.isChecked()),
        }
        self.api_call_with_optional_stop(
            "theme-doc-apply",
            "POST",
            "/v1/theme-doc/apply",
            payload,
            stop_first=bool(self.theme_doc_stop_before_apply_chk.isChecked()),
            timeout=90.0,
        )

    def preview_theme_doc(self) -> None:
        document = self._current_theme_document()
        if document is None:
            return
        if self._preview_request_in_flight:
            self._preview_request_queued = True
            if self._designer_is_heavy_preview() and hasattr(self, "preview_info_label"):
                self.preview_info_label.setText("Szybki podgląd aktywny. Pełny render czeka na zakończenie poprzedniego.")
            return
        # Keep the normal preview path lightweight. Backend writes previews into
        # the app runtime directory now, so GUI can load the PNG directly.
        payload = {"path": self.theme_doc_path_edit.text().strip(), "document": document}
        self._preview_request_in_flight = True
        self._preview_request_queued = False
        self._preview_request_seq += 1
        self._preview_request_active_seq = self._preview_request_seq
        self.api_call(
            f"theme-doc-preview::{self._preview_request_active_seq}",
            "POST",
            "/v1/theme-doc/preview",
            payload,
            timeout=self._designer_preview_timeout_s(),
        )

    def schedule_preview_theme_doc(self) -> None:
        if getattr(self, "_designer_drag_active", False):
            return
        if self.designer_auto_preview_chk.isChecked():
            if self._designer_is_heavy_preview() and hasattr(self, "preview_info_label"):
                self.preview_info_label.setText("Szybki podgląd aktywny. Pełny render pojawi się po krótkiej pauzie.")
            self.preview_debounce.start(self._designer_preview_delay_ms())
        elif self._designer_is_heavy_preview() and hasattr(self, "preview_info_label"):
            self.preview_info_label.setText(
                "Ciężka animacja: pełny render tylko po kliknięciu Podgląd albo Zastosuj motyw."
            )

    def _designer_animation_frame_count(self) -> int:
        if self.theme_doc_model is None:
            return 0
        effects = self.theme_doc_model.get("effects", {})
        if not isinstance(effects, dict):
            return 0
        animation = effects.get("animation", {})
        if not isinstance(animation, dict):
            return 0
        frame_paths = animation.get("frame_paths", [])
        if not isinstance(frame_paths, list):
            return 0
        return len(frame_paths)

    def _designer_is_heavy_preview(self) -> bool:
        return self._designer_animation_frame_count() >= ANIMATION_FRAMES_SOFT_WARN

    def _animation_edit_mode_enabled(self) -> bool:
        return bool(hasattr(self, "designer_animation_mode_btn") and self.designer_animation_mode_btn.isChecked())

    def _sync_designer_preview_policy(self) -> None:
        if not hasattr(self, "designer_auto_preview_chk"):
            return
        if self._designer_is_heavy_preview():
            if self.designer_auto_preview_chk.isChecked():
                self.designer_auto_preview_chk.blockSignals(True)
                self.designer_auto_preview_chk.setChecked(False)
                self.designer_auto_preview_chk.blockSignals(False)
            if hasattr(self, "preview_info_label"):
                self.preview_info_label.setText(
                    "Ciężka animacja: auto-preview wyłączony. Edytuj lekko na canvasie i używaj ręcznie przycisku Podgląd."
                )

    def _on_animation_mode_toggled(self, checked: bool) -> None:
        self._animation_preview_active = False
        self._update_animation_preview_timer()
        self._apply_designer_aux_visibility()
        if hasattr(self, "preview_info_label"):
            if checked:
                self.preview_info_label.setText(
                    "Edycja animacji: możesz pracować na timeline, klatkach i podglądzie ruchu."
                )
            elif self._designer_animation_frame_count() > 0:
                self.preview_info_label.setText(
                    "Tryb zwykły: pracujesz na wybranej klatce roboczej. Pełną animację uruchamiaj ręcznie."
                )

    def _designer_preview_delay_ms(self) -> int:
        frame_count = self._designer_animation_frame_count()
        if frame_count >= ANIMATION_FRAMES_EXTREME_WARN:
            return 2200
        if frame_count >= ANIMATION_FRAMES_STRONG_WARN:
            return 1600
        if frame_count >= ANIMATION_FRAMES_SOFT_WARN:
            return 1000
        return 300

    def _designer_preview_timeout_s(self) -> float:
        frame_count = self._designer_animation_frame_count()
        if frame_count >= ANIMATION_FRAMES_EXTREME_WARN:
            return 180.0
        if frame_count >= ANIMATION_FRAMES_STRONG_WARN:
            return 120.0
        if frame_count >= ANIMATION_FRAMES_SOFT_WARN:
            return 75.0
        return 45.0

    def _snap_value(self, value: int) -> int:
        if not self.designer_snap_chk.isChecked():
            return int(value)
        step = max(1, int(self.designer_snap_spin.value()))
        return int(round(value / step) * step)

    def _make_default_element(self, collection: str) -> dict[str, Any]:
        index = 0
        if self.theme_doc_model is not None:
            if collection == "panels":
                index = len(self.theme_doc_model.get("background", {}).get("panels", []))
            else:
                index = len(self.theme_doc_model.get(collection, []))
        if collection == "texts":
            return {
                "id": f"text_{index}",
                "text": "NEW TEXT",
                "x": 100,
                "y": 100,
                "box_width": 320,
                "box_height": 48,
                "font_size": 24,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "color": [255, 255, 255],
                "align": "left",
                "z_index": 200,
            }
        if collection == "stats":
            return {
                "id": f"stat_{index}",
                "label": "Label",
                "source": self.theme_stat_sources[0] if self.theme_stat_sources else "hostname",
                "format": "{value}",
                "display": "text",
                "min_value": 0.0,
                "max_value": 100.0,
                "x": 100,
                "y": 100,
                "box_width": 320,
                "box_height": 40,
                "font_size": 22,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "label_color": [220, 220, 220],
                "value_color": [220, 220, 220],
                "track_color": [34, 44, 58, 210],
                "fill_color": [220, 220, 220],
                "stroke_width": 12,
                "show_value_text": True,
                "sparkline_points": 42,
                "sparkline_fill_opacity": 0.18,
                "sparkline_show_points": True,
                "align": "left",
                "z_index": 220,
            }
        if collection == "panels":
            return {
                "rect": [100, 100, 240, 100],
                "radius": 16,
                "fill": [0, 0, 0],
                "opacity": 1.0,
                "z_index": 50,
            }
        if collection == "widgets":
            return self._make_weather_widget("weather_current", "compact")
        return {
            "id": f"image_{index}",
            "path": "reference_frame_trcc.jpg",
            "rect": [100, 100, 240, 120],
            "fit": "contain",
            "opacity": 1.0,
            "rotation": 0,
            "z_index": 100,
        }

    def _make_weather_widget(self, kind: str, style: str = "compact") -> dict[str, Any]:
        style_key = str(style or "compact").strip().lower()
        if kind == "weather_forecast_7d":
            rect = [246, 316, 1088, 112]
            prefix = "widget_weather_forecast"
        else:
            prefix = "widget_weather_current"
            rect = {
                "compact": [1360, 270, 500, 152],
                "wide": [980, 300, 820, 112],
                "hero": [1160, 42, 650, 170],
            }.get(style_key, [1360, 270, 500, 152])
        return {
            "id": self._next_item_id("widgets", prefix),
            "kind": kind,
            "style": style_key,
            "rect": rect,
            "settings": {
                "panel_enabled": True,
                "animate_icons": True,
            },
            "opacity": 1.0,
            "z_index": 210,
            "visible": True,
            "locked": False,
        }

    def _make_media_widget(self, style: str = "standard") -> dict[str, Any]:
        style_key = str(style or "standard").strip().lower()
        rect = {
            "standard": [40, 320, 760, 128],
            "hero": [36, 250, 932, 176],
            "mini": [1520, 24, 360, 96],
        }.get(style_key, [40, 320, 760, 128])
        return {
            "id": self._next_item_id("widgets", "widget_media_now_playing"),
            "kind": "media_now_playing",
            "style": style_key,
            "rect": rect,
            "settings": {
                "panel_enabled": True,
                "backdrop_enabled": True,
                "backdrop_opacity": 0.30,
                "cover_enabled": True,
                "cover_placeholder_enabled": True,
                "title_marquee": True,
                "title_marquee_speed": 55.0,
                "equalizer_enabled": True,
                "equalizer_bars": 20,
                "equalizer_gap": 4,
                "equalizer_mirror": False,
                "equalizer_color": [102, 226, 120, 255],
                "equalizer_accent_color": [246, 231, 152, 255],
                "equalizer_track_color": [0, 0, 0, 0],
            },
            "opacity": 1.0,
            "z_index": 210,
            "visible": True,
            "locked": False,
        }

    def _next_item_id(self, collection: str, prefix: str) -> str:
        if self.theme_doc_model is None:
            return f"{prefix}_0"
        if collection == "panels":
            items = self.theme_doc_model.get("background", {}).get("panels", [])
        else:
            items = self.theme_doc_model.get(collection, [])
        used = {str(item.get("id", "")).strip() for item in items if isinstance(item, dict)}
        idx = 0
        while True:
            candidate = f"{prefix}_{idx}"
            if candidate not in used:
                return candidate
            idx += 1

    def add_now_playing_widget(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        widgets = self.theme_doc_model.setdefault("widgets", [])
        widgets.append(self._make_media_widget("standard"))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        combo_index = self.designer_kind_combo.findData("widgets")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
            self.designer_element_list.setCurrentRow(len(widgets) - 1)
        self.preview_info_label.setText("Dodano kompletny widget Now Playing.")
        self.schedule_preview_theme_doc()

    def add_now_playing_widget_hero(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        widgets = self.theme_doc_model.setdefault("widgets", [])
        widgets.append(self._make_media_widget("hero"))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        combo_index = self.designer_kind_combo.findData("widgets")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
            self.designer_element_list.setCurrentRow(len(widgets) - 1)
        self.preview_info_label.setText("Dodano kompletny widget Now Playing Hero.")
        self.schedule_preview_theme_doc()

    def add_now_playing_widget_mini(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        widgets = self.theme_doc_model.setdefault("widgets", [])
        widgets.append(self._make_media_widget("mini"))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        combo_index = self.designer_kind_combo.findData("widgets")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
            self.designer_element_list.setCurrentRow(len(widgets) - 1)
        self.preview_info_label.setText("Dodano kompletny widget Now Playing Mini.")
        self.schedule_preview_theme_doc()

    def add_volume_widget(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        background = self.theme_doc_model.setdefault("background", {})
        panels = background.setdefault("panels", [])
        panels.append(
            {
                "id": self._next_item_id("panels", "panel_volume"),
                "rect": [1492, 132, 300, 82],
                "radius": 16,
                "fill": [8, 14, 24, 200],
                "opacity": 1.0,
                "z_index": 96,
                "visible": True,
                "locked": False,
            }
        )
        stats = self.theme_doc_model.setdefault("stats", [])
        stats.append(
            {
                "id": self._next_item_id("stats", "stat_volume_percent"),
                "label": "VOL",
                "source": "volume_percent",
                "format": "{value}",
                "x": 1516,
                "y": 150,
                "box_width": 160,
                "box_height": 28,
                "font_family": "DejaVu Sans",
                "font_size": 24,
                "font_bold": True,
                "font_italic": False,
                "font_underline": False,
                "marquee": False,
                "marquee_speed": 55.0,
                "label_color": [160, 196, 232],
                "value_color": [235, 246, 255],
                "align": "left",
                "z_index": 211,
                "visible": True,
                "locked": False,
            }
        )
        stats.append(
            {
                "id": self._next_item_id("stats", "stat_volume_state"),
                "label": "",
                "source": "volume_state",
                "format": "{value}",
                "x": 1516,
                "y": 181,
                "box_width": 220,
                "box_height": 22,
                "font_family": "DejaVu Sans",
                "font_size": 16,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "marquee": False,
                "marquee_speed": 55.0,
                "label_color": [160, 196, 232],
                "value_color": [210, 224, 240],
                "align": "left",
                "z_index": 210,
                "visible": True,
                "locked": False,
            }
        )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText("Dodano widget Volume: poziom głośności i stan wyciszenia.")
        self.schedule_preview_theme_doc()

    def add_graphic_equalizer_widget(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        stats = self.theme_doc_model.setdefault("stats", [])
        stats.append(
            {
                "id": self._next_item_id("stats", "stat_music_equalizer"),
                "label": "",
                "source": "volume_percent",
                "format": "{value}",
                "x": 1560,
                "y": 356,
                "box_width": 320,
                "box_height": 72,
                "font_family": "DejaVu Sans",
                "font_size": 22,
                "font_bold": True,
                "font_italic": False,
                "font_underline": False,
                "marquee": False,
                "marquee_speed": 55.0,
                "label_color": [149, 206, 152],
                "value_color": [246, 231, 152],
                "display": "equalizer",
                "min_value": 0.0,
                "max_value": 100.0,
                "track_color": [0, 0, 0, 0],
                "fill_color": [102, 226, 120, 255],
                "stroke_width": 0,
                "show_value_text": False,
                "equalizer_bars": 20,
                "equalizer_gap": 4,
                "equalizer_mirror": False,
                "align": "left",
                "z_index": 214,
                "visible": True,
                "locked": False,
            }
        )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText(
            "Dodano widget Graphic EQ: animowany pasek muzyczny sterowany głośnością i stanem odtwarzania."
        )
        self.schedule_preview_theme_doc()

    def _weather_stat_item(
        self,
        source: str,
        label: str,
        fmt: str,
        x: int,
        y: int,
        w: int,
        h: int,
        size: int,
        bold: bool,
        value_color: list[int] | None = None,
        align: str = "left",
    ) -> dict[str, Any]:
        return {
            "id": self._next_item_id("stats", f"stat_{source}"),
            "label": label,
            "source": source,
            "format": fmt,
            "x": x,
            "y": y,
            "box_width": w,
            "box_height": h,
            "font_family": "DejaVu Sans",
            "font_size": size,
            "font_bold": bold,
            "font_italic": False,
            "font_underline": False,
            "label_color": [160, 196, 232],
            "value_color": value_color or [235, 246, 255],
            "align": align,
            "z_index": 211,
            "visible": True,
            "locked": False,
        }

    def add_weather_current_widget(self, style: str = "compact") -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        widgets = self.theme_doc_model.setdefault("widgets", [])
        widgets.append(self._make_weather_widget("weather_current", style))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        combo_index = self.designer_kind_combo.findData("widgets")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
            self.designer_element_list.setCurrentRow(len(widgets) - 1)
        self.preview_info_label.setText(f"Dodano kompletny widget Weather Current ({style}).")
        self.schedule_preview_theme_doc()

    def add_weather_forecast_widget(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        widgets = self.theme_doc_model.setdefault("widgets", [])
        widgets.append(self._make_weather_widget("weather_forecast_7d", "forecast"))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        combo_index = self.designer_kind_combo.findData("widgets")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
            self.designer_element_list.setCurrentRow(len(widgets) - 1)
        self.preview_info_label.setText("Dodano kompletny widget Weather 7D Forecast.")
        self.schedule_preview_theme_doc()

    @staticmethod
    def _item_rect_bounds(item: dict[str, Any], collection: str) -> tuple[int, int, int, int] | None:
        try:
            if collection in {"images", "widgets"}:
                x, y, w, h = [int(v) for v in item.get("rect", [])]
                return x, y, x + w, y + h
            if collection == "panels":
                x, y, w, h = [int(v) for v in item.get("rect", [])]
                return x, y, x + w, y + h
            if collection == "stats":
                x = int(item.get("x", 0))
                y = int(item.get("y", 0))
                w = max(1, int(item.get("box_width", 0) or 180))
                h = max(1, int(item.get("box_height", 0) or int(item.get("font_size", 18)) + 8))
                return x, y, x + w, y + h
        except Exception:
            return None
        return None

    @staticmethod
    def _union_bounds(bounds: list[tuple[int, int, int, int]]) -> list[int]:
        x1 = min(b[0] for b in bounds)
        y1 = min(b[1] for b in bounds)
        x2 = max(b[2] for b in bounds)
        y2 = max(b[3] for b in bounds)
        pad = 16
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        return [x1, y1, max(120, x2 - x1 + pad), max(60, y2 - y1 + pad)]

    def _legacy_weather_groups(self) -> tuple[list[tuple[str, int, dict[str, Any]]], list[tuple[str, int, dict[str, Any]]]]:
        current: list[tuple[str, int, dict[str, Any]]] = []
        forecast: list[tuple[str, int, dict[str, Any]]] = []
        if self.theme_doc_model is None:
            return current, forecast
        panels = self.theme_doc_model.get("background", {}).get("panels", [])
        for idx, item in enumerate(panels if isinstance(panels, list) else []):
            if not isinstance(item, dict):
                continue
            ident = str(item.get("id", "")).strip().lower()
            if any(ident.startswith(prefix) for prefix in WEATHER_RELATED_PANEL_ID_PREFIXES):
                current.append(("panels", idx, item))
        for collection in ("images", "stats"):
            items = self.theme_doc_model.get(collection, [])
            for idx, item in enumerate(items if isinstance(items, list) else []):
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", "")).strip()
                ident = str(item.get("id", "")).strip().lower()
                label = str(item.get("label", "")).strip().lower()
                if source.startswith("weather_day_"):
                    forecast.append((collection, idx, item))
                elif source in WEATHER_STAT_SOURCES or source in WEATHER_RELATED_IMAGE_SOURCES or "weather" in ident or "pogoda" in label:
                    current.append((collection, idx, item))
        return current, forecast

    def convert_legacy_weather_widgets(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        current, forecast = self._legacy_weather_groups()
        if not current and not forecast:
            QMessageBox.information(
                self,
                self._tr("Weather", "Pogoda"),
                self._tr("No split weather elements found in this theme.", "Nie znaleziono rozbitych elementów pogody w tym motywie."),
            )
            return
        self.push_designer_history()
        widgets = self.theme_doc_model.setdefault("widgets", [])

        def first_panel_fill(items: list[tuple[str, int, dict[str, Any]]], fallback: list[int]) -> list[int]:
            for collection, _idx, item in items:
                if collection == "panels" and isinstance(item.get("fill"), list):
                    return list(item.get("fill", fallback))
            return fallback

        if current:
            bounds = [b for collection, _idx, item in current if (b := self._item_rect_bounds(item, collection)) is not None]
            widget = self._make_weather_widget("weather_current", "wide")
            if bounds:
                widget["rect"] = self._union_bounds(bounds)
            widget.setdefault("settings", {})["panel_fill"] = first_panel_fill(current, [8, 14, 24, 205])
            widget["id"] = self._next_item_id("widgets", "widget_weather_current_migrated")
            widgets.append(widget)
        if forecast:
            bounds = [b for collection, _idx, item in forecast if (b := self._item_rect_bounds(item, collection)) is not None]
            widget = self._make_weather_widget("weather_forecast_7d", "forecast")
            if bounds:
                widget["rect"] = self._union_bounds(bounds)
            widget.setdefault("settings", {})["panel_fill"] = first_panel_fill(forecast, [8, 14, 24, 190])
            widget["id"] = self._next_item_id("widgets", "widget_weather_forecast_migrated")
            widgets.append(widget)

        remove_by_collection: dict[str, set[int]] = {"images": set(), "stats": set(), "panels": set()}
        for collection, idx, _item in current + forecast:
            remove_by_collection.setdefault(collection, set()).add(idx)
        for collection in ("images", "stats"):
            items = self.theme_doc_model.get(collection, [])
            if isinstance(items, list) and remove_by_collection.get(collection):
                self.theme_doc_model[collection] = [item for idx, item in enumerate(items) if idx not in remove_by_collection[collection]]
        panels = self.theme_doc_model.get("background", {}).get("panels", [])
        if isinstance(panels, list) and remove_by_collection.get("panels"):
            self.theme_doc_model.setdefault("background", {})["panels"] = [item for idx, item in enumerate(panels) if idx not in remove_by_collection["panels"]]

        self.write_designer_to_json()
        self.refresh_designer_element_list()
        combo_index = self.designer_kind_combo.findData("widgets")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
            self.designer_element_list.setCurrentRow(max(0, len(widgets) - 1))
        self.preview_info_label.setText(
            self._tr(
                f"Converted split weather elements into {int(bool(current)) + int(bool(forecast))} composite widget(s).",
                f"Przekonwertowano rozbite elementy pogody na {int(bool(current)) + int(bool(forecast))} kompletne widgety.",
            )
        )
        self.schedule_preview_theme_doc()

    def add_analog_clock_widget(self, style: str = "classic") -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        style_key = str(style).strip().lower()
        presets = {
            "classic": {
                "rect": [1508, 22, 180, 180],
                "face": [18, 24, 36, 230],
                "tick": [224, 232, 244, 220],
                "hand": [245, 248, 252, 255],
                "second": [255, 96, 96, 255],
                "center": [250, 250, 252, 255],
                "border": [235, 246, 255, 155],
                "glow_radius": 14,
                "glow_opacity": 0.16,
            },
            "modern": {
                "rect": [1508, 22, 180, 180],
                "face": [8, 16, 28, 210],
                "tick": [86, 214, 255, 235],
                "hand": [235, 245, 255, 255],
                "second": [103, 255, 211, 255],
                "center": [240, 248, 255, 255],
                "border": [0, 186, 255, 165],
                "glow_radius": 18,
                "glow_opacity": 0.24,
            },
            "nordic": {
                "rect": [1508, 22, 180, 180],
                "face": [20, 24, 30, 222],
                "tick": [215, 225, 232, 215],
                "hand": [244, 240, 232, 255],
                "second": [196, 162, 108, 255],
                "center": [252, 248, 242, 255],
                "border": [208, 186, 152, 160],
                "glow_radius": 10,
                "glow_opacity": 0.10,
            },
        }
        preset = presets.get(style_key, presets["classic"])
        self.push_designer_history()
        images = self.theme_doc_model.setdefault("images", [])
        images.append(
            {
                "id": self._next_item_id("images", f"img_analog_clock_{style_key}"),
                "path": "",
                "source": "analog_clock",
                "clock_style": style_key,
                "clock_show_second_hand": True,
                "clock_face_color": preset["face"],
                "clock_tick_color": preset["tick"],
                "clock_hand_color": preset["hand"],
                "clock_second_color": preset["second"],
                "clock_center_color": preset["center"],
                "rect": preset["rect"],
                "fit": "contain",
                "opacity": 1.0,
                "radius": 0,
                "border_width": 2,
                "border_color": preset["border"],
                "glow_radius": preset["glow_radius"],
                "glow_opacity": preset["glow_opacity"],
                "rotation": 0,
                "z_index": 212,
                "visible": True,
                "locked": False,
            }
        )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText(f"Dodano zegar analogowy: {style_key.title()}.")
        self.schedule_preview_theme_doc()

    def _gauge_bundle_stat_item(
        self,
        *,
        item_id_prefix: str,
        label: str,
        source: str,
        fmt: str,
        x: int,
        y: int,
        size: int,
        preset: str,
        font_family: str = "DejaVu Sans",
        font_size: int = 22,
        label_color: list[int] | None = None,
        value_color: list[int] | None = None,
        min_value: float = 0.0,
        max_value: float = 100.0,
    ) -> dict[str, Any]:
        return {
            "id": self._next_item_id("stats", item_id_prefix),
            "label": label,
            "source": source,
            "format": fmt,
            "x": x,
            "y": y,
            "box_width": size,
            "box_height": size,
            "font_family": font_family,
            "font_size": font_size,
            "font_bold": True,
            "font_italic": False,
            "font_underline": False,
            "marquee": False,
            "marquee_speed": 55.0,
            "label_color": label_color or [214, 224, 238],
            "value_color": value_color or [244, 248, 252],
            "display": "gauge",
            "gauge_preset": preset,
            "gauge_smooth": 0.26,
            "gauge_match_value_color": True,
            "gauge_ring_size": max(96, size - 12),
            "gauge_value_layout": "center",
            "gauge_inner_alpha": 0.82,
            "stroke_width": 0,
            "min_value": min_value,
            "max_value": max_value,
            "show_value_text": True,
            "align": "center",
            "z_index": 216,
            "visible": True,
            "locked": False,
        }

    def add_gauge_ring_bundle(self, style: str = "system") -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        style_key = str(style).strip().lower()
        bundles: dict[str, dict[str, Any]] = {
            "system": {
                "title": "System Trio",
                "items": [
                    dict(item_id_prefix="stat_cpu_ring", label="CPU", source="cpu_usage_percent", fmt="{value}%", x=120, y=126, size=170, preset="usage"),
                    dict(item_id_prefix="stat_ram_ring", label="RAM", source="mem_percent", fmt="{value}%", x=324, y=126, size=170, preset="usage"),
                    dict(item_id_prefix="stat_gpu_ring", label="GPU", source="gpu_load", fmt="{value}%", x=528, y=126, size=170, preset="usage"),
                ],
            },
            "nordic": {
                "title": "Nordic Trio",
                "items": [
                    dict(item_id_prefix="stat_cpu_ring_nordic", label="CPU", source="cpu_usage_percent", fmt="{value}%", x=96, y=118, size=184, preset="nordic", font_family="DejaVu Serif", label_color=[223, 230, 238], value_color=[252, 248, 240]),
                    dict(item_id_prefix="stat_ram_ring_nordic", label="RAM", source="mem_percent", fmt="{value}%", x=314, y=118, size=184, preset="runic_gold", font_family="DejaVu Serif", label_color=[229, 210, 170], value_color=[255, 248, 232]),
                    dict(item_id_prefix="stat_gpu_ring_nordic", label="GPU", source="gpu_load", fmt="{value}%", x=532, y=118, size=184, preset="nordic", font_family="DejaVu Serif", label_color=[223, 230, 238], value_color=[252, 248, 240]),
                ],
            },
            "cyber": {
                "title": "Cyber Trio",
                "items": [
                    dict(item_id_prefix="stat_cpu_ring_cyber", label="CPU LOAD", source="cpu_usage_percent", fmt="{value}%", x=96, y=124, size=204, preset="cyber", font_size=24),
                    dict(item_id_prefix="stat_ram_ring_cyber", label="RAM", source="mem_percent", fmt="{value}%", x=340, y=124, size=204, preset="plasma_blue", font_size=24),
                    dict(item_id_prefix="stat_gpu_ring_cyber", label="GPU", source="gpu_load", fmt="{value}%", x=584, y=124, size=204, preset="cyber", font_size=24),
                ],
            },
            "thermal": {
                "title": "Thermal Trio",
                "items": [
                    dict(item_id_prefix="stat_cpu_temp_ring", label="CPU TEMP", source="cpu_temp_c", fmt="{value}°C", x=96, y=118, size=184, preset="thermal", min_value=35.0, max_value=92.0),
                    dict(item_id_prefix="stat_gpu_temp_ring", label="GPU TEMP", source="gpu_temp", fmt="{value}°C", x=314, y=118, size=184, preset="thermal", min_value=35.0, max_value=95.0),
                    dict(item_id_prefix="stat_cpu_freq_ring", label="CPU GHz", source="cpu_freq_ghz", fmt="{value}", x=532, y=118, size=184, preset="freq", min_value=0.8, max_value=5.5),
                ],
            },
        }
        spec = bundles.get(style_key, bundles["system"])
        self.push_designer_history()
        stats = self.theme_doc_model.setdefault("stats", [])
        for item_spec in spec["items"]:
            stats.append(self._gauge_bundle_stat_item(**item_spec))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText(f"Dodano zestaw gauge: {spec['title']}.")
        self.schedule_preview_theme_doc()

    def quick_add_designer_element(self, collection: str) -> None:
        combo_index = self.designer_kind_combo.findData(collection)
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
        self.add_designer_element()
        collection_name = {
            "texts": "tekst",
            "stats": "statystykę",
            "images": "obraz",
            "panels": "panel",
        }.get(collection, "element")
        self.designer_selection_label.setText(
            f"Dodano nowy element: {collection_name}. Lista po lewej pokazuje wszystkie elementy tej kategorii."
        )

    def add_stat_visual_widget(self, display: str = "progress") -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        mode = str(display or "progress").strip().lower()
        if mode not in {"progress", "sparkline"}:
            mode = "progress"
        self.push_designer_history()
        stats = self.theme_doc_model.setdefault("stats", [])
        is_sparkline = mode == "sparkline"
        stats.append(
            {
                "id": self._next_item_id("stats", f"stat_{mode}"),
                "label": "CPU" if not is_sparkline else "CPU HISTORY",
                "source": "cpu_core_avg_percent",
                "format": "{value}%",
                "display": mode,
                "min_value": 0.0,
                "max_value": 100.0,
                "x": 100,
                "y": 330 if not is_sparkline else 290,
                "box_width": 360 if not is_sparkline else 420,
                "box_height": 48 if not is_sparkline else 92,
                "font_family": "DejaVu Sans",
                "font_size": 22,
                "font_bold": True,
                "font_italic": False,
                "font_underline": False,
                "label_color": [235, 246, 255],
                "value_color": [255, 206, 88],
                "track_color": [15, 24, 36, 190],
                "fill_color": [90, 220, 132, 255],
                "stroke_width": 4 if is_sparkline else 12,
                "show_value_text": True,
                "sparkline_points": 42,
                "sparkline_fill_opacity": 0.18,
                "sparkline_show_points": True,
                "align": "left",
                "z_index": 220,
                "visible": True,
                "locked": False,
            }
        )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText(
            "Dodano Sparkline z zakresem 0-100%." if is_sparkline else "Dodano pasek postępu z zakresem 0-100%."
        )
        self.schedule_preview_theme_doc()

    def clear_designer_selection(self) -> None:
        self.designer_cross_selection = []
        self._designer_selection_group_label = ""
        self.designer_element_list.clearSelection()
        self.designer_element_list.setCurrentRow(-1)
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def toggle_selected_visible(self) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        self.push_designer_history()
        new_value = not all(bool(item.get("visible", True)) for _collection, _row, item in selected)
        for _collection, _row, item in selected:
            item["visible"] = new_value
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.schedule_preview_theme_doc()

    def toggle_selected_locked(self) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        self.push_designer_history()
        new_value = not all(bool(item.get("locked", False)) for _collection, _row, item in selected)
        for _collection, _row, item in selected:
            item["locked"] = new_value
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.schedule_preview_theme_doc()

    def _selected_collection(self) -> str:
        return str(self.designer_kind_combo.currentData())

    def _theme_items_for_collection(self, collection: str) -> list[dict[str, Any]]:
        if self.theme_doc_model is None:
            return []
        if collection == "panels":
            items = self.theme_doc_model.get("background", {}).get("panels", [])
        else:
            items = self.theme_doc_model.get(collection, [])
        return items if isinstance(items, list) else []

    def _current_theme_items(self) -> list[dict[str, Any]]:
        return self._theme_items_for_collection(self._selected_collection())

    def _selected_item(self) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
        items = self._current_theme_items()
        row = self.designer_element_list.currentRow()
        if row < 0 or row >= len(items):
            return items, row, None
        return items, row, items[row]

    def _selected_rows(self) -> list[int]:
        rows = sorted({idx.row() for idx in self.designer_element_list.selectedIndexes()})
        if rows:
            return rows
        row = self.designer_element_list.currentRow()
        return [row] if row >= 0 else []

    def _normalize_designer_selection(self, entries: list[tuple[str, int]] | None) -> list[tuple[str, int]]:
        if self.theme_doc_model is None or not entries:
            return []
        normalized: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for collection, row in entries:
            key = (str(collection), int(row))
            if key in seen:
                continue
            items = self._theme_items_for_collection(key[0])
            if 0 <= key[1] < len(items):
                normalized.append(key)
                seen.add(key)
        return normalized

    def _set_designer_selection_group(self, entries: list[tuple[str, int]], *, group_label: str = "") -> None:
        self.designer_cross_selection = self._normalize_designer_selection(entries)
        self._designer_selection_group_label = group_label if len(self.designer_cross_selection) > 1 else ""

    def _selected_entries_any(self) -> list[tuple[str, int]]:
        selected = self._normalize_designer_selection(self.designer_cross_selection)
        if selected:
            if selected != self.designer_cross_selection:
                self.designer_cross_selection = list(selected)
            return selected
        current = self._selected_collection()
        return self._normalize_designer_selection([(current, row) for row in self._selected_rows()])

    def _selected_items_multi_any(self) -> list[tuple[str, int, dict[str, Any]]]:
        out: list[tuple[str, int, dict[str, Any]]] = []
        for collection, row in self._selected_entries_any():
            items = self._theme_items_for_collection(collection)
            if 0 <= row < len(items):
                out.append((collection, row, items[row]))
        return out

    def _selected_items_multi(self) -> list[tuple[int, dict[str, Any]]]:
        items = self._current_theme_items()
        out: list[tuple[int, dict[str, Any]]] = []
        for row in self._selected_rows():
            if 0 <= row < len(items):
                out.append((row, items[row]))
        return out

    def _selection_group_label_for_entries(self, entries: list[tuple[str, int]]) -> str:
        normalized = self._normalize_designer_selection(entries)
        if len(normalized) <= 1:
            return ""
        if all(
            self._is_media_related_item(self._theme_items_for_collection(collection)[row], collection)
            for collection, row in normalized
        ):
            return "Media Player"
        return "Grupa warstw" if len({collection for collection, _row in normalized}) > 1 else ""

    def _all_canvas_elements(self) -> list[dict[str, Any]]:
        if self.theme_doc_model is None:
            return []
        out: list[dict[str, Any]] = []
        for collection in ("panels", "images", "texts", "stats", "widgets"):
            if collection == "panels":
                items = self.theme_doc_model.get("background", {}).get("panels", [])
            else:
                items = self.theme_doc_model.get(collection, [])
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                if collection in {"images", "panels", "widgets"}:
                    rect = item.get("rect", [0, 0, 1, 1])
                    if not isinstance(rect, list) or len(rect) != 4:
                        continue
                    rect_tuple = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
                    label = str(item.get("id", f"{collection}_{idx}"))
                else:
                    x = int(item.get("x", 0))
                    y = int(item.get("y", 0))
                    width = max(1, int(item.get("box_width", 320)))
                    height = max(1, int(item.get("box_height", 48)))
                    rect_tuple = (x, y, width, height)
                    label = str(item.get("id", f"{collection}_{idx}"))
                out.append(
                    {
                        "collection": collection,
                        "index": idx,
                        "rect": rect_tuple,
                        "label": label,
                        "z_index": int(item.get("z_index", 0)),
                        "visible": bool(item.get("visible", True)),
                        "locked": bool(item.get("locked", False)),
                    }
                )
        return sorted(out, key=lambda item: int(item.get("z_index", 0)))

    def _update_preview_canvas_overlay(self) -> None:
        if self.theme_doc_model is None:
            self.preview_label.set_canvas_metadata(canvas_width=1920, canvas_height=462, elements=[], selected=[])
            return
        canvas = self.theme_doc_model.get("canvas", {})
        width = int(canvas.get("width", 1920))
        height = int(canvas.get("height", 462))
        selected_entries = self._selected_entries_any()
        elements = self._all_canvas_elements()
        if not self.preview_guides_chk.isChecked():
            if not selected_entries:
                elements = []
            else:
                selected_set = set(selected_entries)
                elements = [
                    item for item in elements
                    if (str(item.get("collection")), int(item.get("index", -1))) in selected_set
                ]
        self.preview_label.set_canvas_metadata(
            canvas_width=width,
            canvas_height=height,
            elements=elements,
            selected=selected_entries,
        )

    def _ensure_theme_doc_model(self) -> bool:
        if self.theme_doc_model is not None:
            return True
        self.reload_designer_from_json()
        return self.theme_doc_model is not None

    def prepare_image_asset(self, source_edit: QLineEdit) -> None:
        if not self._image_tools_available():
            QMessageBox.warning(
                self,
                self._tr("Pillow not installed", "Brak Pillow"),
                self._tr(
                    "Image preparation is not available in this environment.",
                    "Moduł przygotowania obrazów nie jest dostępny.",
                ),
            )
            return
        source = source_edit.text().strip()
        if not source:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "Wybierz obraz źródłowy",
                str(Path.cwd()),
                "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
            )
            if not chosen:
                return
            source = chosen
        resolved = Path(source).expanduser()
        if not resolved.is_absolute():
            resolved = (Path.cwd() / resolved).resolve()
        if not resolved.exists():
            QMessageBox.warning(
                self,
                self._tr("Missing file", "Brak pliku"),
                self._tr("Image not found:\n{path}", "Nie znaleziono obrazu:\n{path}").format(path=resolved),
            )
            return
        dlg = ImagePrepDialog(self, resolved)
        if dlg.exec() != QDialog.Accepted or dlg.output_path is None:
            return
        source_edit.setText(str(dlg.output_path))
        self.append_log(f"[image-prep] {resolved} -> {dlg.output_path}")

    def import_background_image(self) -> None:
        if not self._image_tools_available():
            QMessageBox.warning(
                self,
                self._tr("Pillow not installed", "Brak Pillow"),
                self._tr(
                    "Image preparation is not available in this environment.",
                    "Moduł przygotowania obrazów nie jest dostępny.",
                ),
            )
            return
        if not self._ensure_theme_doc_model():
            QMessageBox.warning(
                self,
                self._tr("Theme error", "Błąd motywu"),
                self._tr("Load a valid theme in the designer first.", "Najpierw wczytaj poprawny motyw w projektancie."),
            )
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz obraz tła",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not chosen:
            return
        source = Path(chosen).expanduser()
        if not source.is_absolute():
            source = (Path.cwd() / source).resolve()
        if not source.exists():
            QMessageBox.warning(
                self,
                self._tr("Missing file", "Brak pliku"),
                self._tr("Image not found:\n{path}", "Nie znaleziono obrazu:\n{path}").format(path=source),
            )
            return
        out = self._run_theme_image_import(source, asset_kind="background", button_text="Importuj tło")
        if out is None:
            return
        self.bg_kind_combo.setCurrentText("image")
        self.bg_fit_combo.setCurrentText("cover")
        self.bg_opacity_spin.setValue(1.0)
        animation = self._current_animation_effect()
        animation["enabled"] = False
        self.bg_path_edit.setText(self._theme_display_path(out))
        self.preview_info_label.setText(
            "Tło zaimportowane. Możesz jeszcze zmienić Fit, Opacity albo przełączyć z generated/color na image."
        )
        self.append_log(f"[background-import] {source} -> {out}")
        self._refresh_animation_controls()
        self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text=self._empty_background_preview_caption())

    def clear_background_image(self) -> None:
        if not self._ensure_theme_doc_model():
            return
        self.bg_kind_combo.setCurrentText("generated")
        self.bg_path_edit.clear()
        self.bg_fit_combo.setCurrentText("cover")
        self.bg_opacity_spin.setValue(1.0)
        animation = self._current_animation_effect()
        animation["enabled"] = False
        self.preview_info_label.setText("Tło wyczyszczone. Możesz wrócić do generated/color albo zaimportować nowe tło.")
        self._refresh_animation_controls()
        self._set_image_preview_label(self.background_preview_label, "", empty_text=self._empty_background_preview_caption())

    def _load_background_fields(self) -> None:
        if self.theme_doc_model is None:
            return
        background = self.theme_doc_model.get("background", {})
        canvas = self.theme_doc_model.get("canvas", {})
        effects = self.theme_doc_model.get("effects", {})
        animation = effects.get("animation", {}) if isinstance(effects.get("animation", {}), dict) else {}
        self._designer_updating = True
        try:
            self.bg_kind_combo.setCurrentText(str(background.get("kind", "generated")))
            self.bg_base_color_edit.setText(json.dumps(background.get("base_color", [9, 14, 22]), ensure_ascii=False))
            self.bg_accent_color_edit.setText(json.dumps(background.get("accent_color", [20, 34, 48]), ensure_ascii=False))
            self.bg_texture_alpha_spin.setValue(float(background.get("texture_alpha", 0.4)))
            self.bg_rotation_spin.setValue(int(canvas.get("rotation", 180)))
            self.bg_path_edit.setText(str(background.get("path", "")))
            self.bg_fit_combo.setCurrentText(str(background.get("fit", "cover")))
            self.bg_opacity_spin.setValue(float(background.get("opacity", 1.0)))
            self.bg_show_grid_chk.setChecked(bool(effects.get("show_grid", False)))
            self.bg_show_safe_chk.setChecked(bool(effects.get("show_safe_area", False)))
            self.bg_animation_enabled_chk.setChecked(bool(animation.get("enabled", False)))
            self.bg_animation_use_bg_chk.setChecked(bool(animation.get("use_as_background", True)))
            self.bg_animation_fps_spin.setValue(float(animation.get("fps", 12.0)))
            frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
            current_frame = min(max(0, int(animation.get("current_frame", 0))), max(0, len(frame_paths) - 1))
            self.bg_animation_frame_spin.setMaximum(max(0, len(frame_paths) - 1))
            self.bg_animation_frame_spin.setValue(current_frame)
            self.bg_animation_count_label.setText(self._format_animation_frame_count(len(frame_paths)))
        finally:
            self._designer_updating = False
        self._refresh_all_color_previews()
        self._refresh_animation_controls()
        preview_path = ""
        if not preview_path and bool(animation.get("enabled", False)) and bool(animation.get("use_as_background", True)):
            preview_path = self._current_animation_preview_path()
        if not preview_path:
            preview_path = str(background.get("path", ""))
        self._set_image_preview_label(
            self.background_preview_label,
            preview_path,
            empty_text=self._empty_background_preview_caption(),
        )

    def reload_designer_from_json(self) -> None:
        document = self._parse_theme_doc_editor()
        if document is None:
            return
        try:
            self.push_designer_history()
            self.theme_doc_model = normalize_theme_document(document)
        except Exception as exc:
            QMessageBox.warning(self, self._tr("Theme error", "Błąd motywu"), str(exc))
            return
        self._sync_designer_preview_policy()
        self._load_background_fields()
        self._sync_designer_theme_gauge_from_model()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self._mark_theme_doc_dirty("json-to-designer")
        self.preview_theme_doc()

    def write_designer_to_json(self) -> None:
        if self.theme_doc_model is None:
            QMessageBox.information(self, "Info", "Designer nie ma jeszcze wczytanego theme.")
            return
        self._set_theme_doc_editor_document(self.theme_doc_model)
        self._mark_theme_doc_dirty("designer-change")

    def _display_name_for_item(self, item: dict[str, Any], collection: str, idx: int) -> str:
        ident = str(item.get("id", f"{collection}_{idx}")).strip() or f"{collection}_{idx}"
        flags = []
        if not bool(item.get("visible", True)):
            flags.append("H")
        if bool(item.get("locked", False)):
            flags.append("L")
        type_tag = {
            "texts": "TXT",
            "stats": "STA",
            "images": "IMG",
            "panels": "PNL",
            "widgets": "WID",
        }.get(collection, collection[:3].upper())
        prefix = f"[{type_tag}{':' + ''.join(flags) if flags else ''}] "
        if collection == "texts":
            text = str(item.get("text", "")).strip() or "Tekst"
            return f"{prefix}{text[:30]}"
        if collection == "stats":
            label = str(item.get("label", "")).strip()
            source = str(item.get("source", "")).strip() or "stat"
            display = str(item.get("display", "text")).strip().lower()
            if display == "equalizer":
                return f"{prefix}{(label or 'Graphic EQ')[:40]}"
            title = label or self._humanize_stat_source(source)
            return f"{prefix}{title[:40]}"
        if collection == "panels":
            rect = item.get("rect", [0, 0, 0, 0])
            size = f"{rect[2]}x{rect[3]}" if isinstance(rect, list) and len(rect) == 4 else "panel"
            return f"{prefix}Panel {idx + 1} [{size}]"
        if collection == "widgets":
            kind = str(item.get("kind", "widget")).strip()
            label = {
                "weather_current": "Pogoda teraz",
                "weather_forecast_7d": "Prognoza 7 dni",
                "media_now_playing": "Now Playing",
            }.get(kind, kind or "Widget")
            return f"{prefix}{label[:40]}"
        source = str(item.get("source", "")).strip()
        if source == "media_cover":
            return f"{prefix}Okładka Now Playing"
        if source == "media_video_frame":
            return f"{prefix}Kadr Media / Video"
        if source == "analog_clock":
            style = str(item.get("clock_style", "classic")).strip().title() or "Classic"
            return f"{prefix}Zegar analogowy {style}"
        name = Path(str(item.get("path", ""))).name or ident
        return f"{prefix}{name[:34]}"

    def _icon_for_collection(self, collection: str):
        style = self.style()
        if collection == "texts":
            return style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        if collection == "stats":
            return style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        if collection == "images":
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        if collection == "panels":
            return style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)

    def _thumbnail_for_item(self, item: dict[str, Any], collection: str) -> QPixmap | None:
        if collection != "images":
            return None
        raw_path = str(item.get("path", "")).strip()
        source = str(item.get("source", "")).strip()
        if source in {"media_cover", "media_video_frame"}:
            raw_path = self._current_media_dynamic_path(source)
        if not raw_path:
            return None
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            return None
        try:
            cache_key = (str(path), int(path.stat().st_mtime_ns))
        except Exception:
            cache_key = (str(path), 0)
        cached = self._image_thumbnail_cache.get(cache_key)
        if cached is not None and not cached.isNull():
            return cached
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._image_thumbnail_cache = {key: val for key, val in self._image_thumbnail_cache.items() if key[0] != str(path)}
        self._image_thumbnail_cache[cache_key] = pixmap
        return pixmap

    def refresh_designer_element_list(self) -> None:
        if self.theme_doc_model is None:
            self.designer_element_list.clear()
            self.designer_element_list.setEnabled(False)
            self._update_designer_element_list_height()
            self.load_selected_designer_item()
            self._update_preview_canvas_overlay()
            return
        items = self._current_theme_items()
        self.designer_element_list.setEnabled(True)
        current_id = None
        _items, _row, selected = self._selected_item()
        if selected is not None:
            current_id = str(selected.get("id", "")).strip()

        self.designer_element_list.blockSignals(True)
        self.designer_element_list.clear()
        collection = self._selected_collection()
        selected_rows_for_collection = [
            row for selected_collection, row in self._normalize_designer_selection(self.designer_cross_selection)
            if selected_collection == collection
        ]
        selected_row = -1
        for idx, item in enumerate(items):
            display = self._display_name_for_item(item, collection, idx)
            subtitle = self._subtitle_for_item(item, collection)
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, str(item.get("id", "")))
            list_item.setData(Qt.UserRole + 1, idx)
            list_item.setFlags(
                list_item.flags()
                | Qt.ItemIsDragEnabled
                | Qt.ItemIsDropEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsEnabled
            )
            list_item.setToolTip(json.dumps(item, ensure_ascii=False, indent=2)[:1200])
            self.designer_element_list.addItem(list_item)
            row_widget = LayerRowWidget(
                title=display,
                subtitle=subtitle,
                icon=self._icon_for_collection(collection),
                visible=bool(item.get("visible", True)),
                locked=bool(item.get("locked", False)),
                thumbnail=self._thumbnail_for_item(item, collection),
            )
            row_widget.activated.connect(lambda modifiers, idx=idx: self._activate_designer_list_row(idx, modifiers))
            row_widget.visibility_toggled.connect(lambda idx=idx: self.toggle_layer_visibility_at(idx))
            row_widget.lock_toggled.connect(lambda idx=idx: self.toggle_layer_lock_at(idx))
            list_item.setSizeHint(row_widget.sizeHint())
            self.designer_element_list.setItemWidget(list_item, row_widget)
            if current_id and str(item.get("id", "")) == current_id:
                selected_row = idx
        if selected_rows_for_collection:
            first_row = min(selected_rows_for_collection)
            for row in selected_rows_for_collection:
                if 0 <= row < self.designer_element_list.count():
                    list_item = self.designer_element_list.item(row)
                    if list_item is not None and not list_item.isHidden():
                        list_item.setSelected(True)
            self.designer_element_list.setCurrentRow(first_row)
        elif selected_row < 0 and items and not self.designer_cross_selection:
            selected_row = 0
        if selected_row >= 0 and not selected_rows_for_collection:
            self.designer_element_list.setCurrentRow(selected_row)
        self.designer_element_list.blockSignals(False)
        self.filter_designer_element_list()
        self.update_layer_row_visuals()
        self.load_selected_designer_item()
        self._update_designer_element_list_height()

    def _refresh_designer_list_row(self, row: int) -> None:
        if self.theme_doc_model is None:
            return
        collection = self._selected_collection()
        items = self._current_theme_items()
        if row < 0 or row >= len(items) or row >= self.designer_element_list.count():
            return
        item = items[row]
        list_item = self.designer_element_list.item(row)
        widget = self.designer_element_list.itemWidget(list_item)
        if not isinstance(widget, LayerRowWidget):
            return
        widget.set_title(self._display_name_for_item(item, collection, row))
        widget.set_subtitle(self._subtitle_for_item(item, collection))
        widget.set_visible_state(bool(item.get("visible", True)))
        widget.set_locked(bool(item.get("locked", False)))
        widget.set_thumbnail(self._thumbnail_for_item(item, collection))
        list_item.setData(Qt.UserRole, str(item.get("id", "")))
        list_item.setToolTip(json.dumps(item, ensure_ascii=False, indent=2)[:1200])
        list_item.setSizeHint(widget.sizeHint())
        self.filter_designer_element_list()
        self.update_layer_row_visuals()

    def _subtitle_for_item(self, item: dict[str, Any], collection: str) -> str:
        if collection == "stats":
            source = str(item.get("source", "")).strip()
            label = str(item.get("label", "")).strip()
            display = str(item.get("display", "text")).strip().lower()
            if display == "equalizer":
                return f"music equalizer • {int(item.get('equalizer_bars', 18))} bars"
            source_text = label or source or "Statystyka"
            return f"{source_text} • {int(item.get('font_size', 22))} px"
        if collection == "images":
            rect = item.get("rect", [0, 0, 0, 0])
            fit = str(item.get("fit", "contain")).strip()
            source = str(item.get("source", "")).strip()
            if source == "media_cover":
                if isinstance(rect, list) and len(rect) == 4:
                    return f"dynamiczna okładka • {rect[2]}×{rect[3]}"
                return "dynamiczna okładka"
            if source == "media_video_frame":
                if isinstance(rect, list) and len(rect) == 4:
                    return f"dynamiczny media-backdrop • {rect[2]}×{rect[3]}"
                return "dynamiczny media-backdrop"
            if isinstance(rect, list) and len(rect) == 4:
                return f"{rect[2]}×{rect[3]} • {fit}"
            return fit
        if collection == "panels":
            rect = item.get("rect", [0, 0, 0, 0])
            if isinstance(rect, list) and len(rect) == 4:
                return f"{rect[2]}×{rect[3]} • radius {int(item.get('radius', 0))}"
        if collection == "widgets":
            rect = item.get("rect", [0, 0, 0, 0])
            style = str(item.get("style", "compact")).strip()
            if isinstance(rect, list) and len(rect) == 4:
                return f"{rect[2]}×{rect[3]} • {style}"
            return style
        if collection == "texts":
            text = str(item.get("text", "")).strip()
            return f"{int(item.get('font_size', 24))} px • {str(item.get('align', 'left'))} • {text[:24]}"
        return ""

    def update_layer_row_visuals(self) -> None:
        current = self.designer_element_list.currentRow()
        for row in range(self.designer_element_list.count()):
            item = self.designer_element_list.item(row)
            widget = self.designer_element_list.itemWidget(item)
            if isinstance(widget, LayerRowWidget):
                widget.set_selected(row == current or item.isSelected())

    def _select_designer_rows(self, rows: list[int]) -> None:
        rows = sorted(set(rows))
        self.designer_element_list.blockSignals(True)
        self.designer_element_list.clearSelection()
        first_row = min(rows) if rows else -1
        for row in rows:
            item = self.designer_element_list.item(row)
            if item is not None and not item.isHidden():
                item.setSelected(True)
        self.designer_element_list.setCurrentRow(first_row)
        self.designer_element_list.blockSignals(False)
        collection = self._selected_collection()
        self._set_designer_selection_group([(collection, row) for row in rows], group_label="")
        self.update_layer_row_visuals()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def _activate_designer_list_row(self, row: int, modifiers: object) -> None:
        if not (0 <= row < self.designer_element_list.count()):
            return
        item = self.designer_element_list.item(row)
        if item is None:
            return
        mods = modifiers if isinstance(modifiers, Qt.KeyboardModifiers) else Qt.NoModifier
        self.designer_element_list.blockSignals(True)
        if mods & (Qt.ControlModifier | Qt.MetaModifier):
            item.setSelected(not item.isSelected())
            self.designer_element_list.setCurrentRow(row)
        elif mods & Qt.ShiftModifier and self.designer_element_list.currentRow() >= 0:
            anchor = self.designer_element_list.currentRow()
            self.designer_element_list.clearSelection()
            for current_row in range(min(anchor, row), max(anchor, row) + 1):
                current_item = self.designer_element_list.item(current_row)
                if current_item is not None:
                    current_item.setSelected(True)
            self.designer_element_list.setCurrentRow(row)
        else:
            self.designer_element_list.clearSelection()
            item.setSelected(True)
            self.designer_element_list.setCurrentRow(row)
        self.designer_element_list.blockSignals(False)
        rows = self._selected_rows()
        self._set_designer_selection_group(
            [(self._selected_collection(), current_row) for current_row in rows],
            group_label="",
        )
        self.update_layer_row_visuals()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def _is_media_related_item(self, item: dict[str, Any], collection: str) -> bool:
        ident = str(item.get("id", "")).strip().lower()
        source = str(item.get("source", "")).strip().lower()
        label = str(item.get("label", "")).strip().lower()
        display = str(item.get("display", "")).strip().lower()
        if source.startswith("media_") or source == "media_cover" or self._is_music_stat_source(source):
            return True
        if collection == "widgets" and str(item.get("kind", "")).strip().lower().startswith("media_"):
            return True
        if display in MUSIC_VISUAL_STAT_DISPLAYS:
            return True
        if ident.startswith("panel_media") or ident.startswith("stat_media") or ident.startswith("img_media"):
            return True
        if ident.startswith("panel_volume") or ident.startswith("stat_volume") or ident.startswith("panel_music_eq"):
            return True
        return "media" in ident or "now playing" in label or "equalizer" in ident or "graphic eq" in label

    def _is_weather_related_item(self, item: dict[str, Any], collection: str) -> bool:
        ident = str(item.get("id", "")).strip().lower()
        source = str(item.get("source", "")).strip().lower()
        label = str(item.get("label", "")).strip().lower()
        if collection == "stats" and self._is_weather_stat_source(source):
            return True
        if collection == "images" and (
            source in WEATHER_RELATED_IMAGE_SOURCES
            or (source.startswith("weather_day_") and source.endswith("_icon"))
        ):
            return True
        if collection == "panels" and any(ident.startswith(prefix) for prefix in WEATHER_RELATED_PANEL_ID_PREFIXES):
            return True
        if collection == "widgets" and str(item.get("kind", "")).strip().lower().startswith("weather_"):
            return True
        return "weather" in ident or "pogoda" in label or "weather" in label

    def _item_matches_designer_domain(self, item: dict[str, Any], collection: str, domain: str) -> bool:
        domain_key = str(domain).strip().lower() or "all"
        if domain_key == "all":
            return True
        is_music = self._is_media_related_item(item, collection)
        is_weather = self._is_weather_related_item(item, collection)
        if domain_key == "music":
            return is_music
        if domain_key == "weather":
            return is_weather
        if domain_key == "system":
            return not is_music and not is_weather
        return True

    def select_all_designer_elements(self) -> None:
        rows = [row for row in range(self.designer_element_list.count()) if not self.designer_element_list.item(row).isHidden()]
        self._select_designer_rows(rows)

    def invert_designer_selection(self) -> None:
        current = set(self._selected_rows())
        rows: list[int] = []
        for row in range(self.designer_element_list.count()):
            item = self.designer_element_list.item(row)
            if item is None or item.isHidden():
                continue
            if row not in current:
                rows.append(row)
        self._select_designer_rows(rows)

    def select_media_designer_group(self) -> None:
        entries: list[tuple[str, int]] = []
        first_collection = ""
        for collection in ("panels", "images", "stats", "texts"):
            items = self._theme_items_for_collection(collection)
            for row, item in enumerate(items):
                if self._is_media_related_item(item, collection):
                    if not first_collection:
                        first_collection = collection
                    entries.append((collection, row))
        if not entries:
            return
        current_collection = self._selected_collection()
        target_collection = current_collection
        current_rows = [row for collection, row in entries if collection == current_collection]
        if not current_rows and first_collection:
            combo_index = self.designer_kind_combo.findData(first_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
            target_collection = first_collection
            current_rows = [row for collection, row in entries if collection == target_collection]
        self._set_designer_selection_group(entries, group_label="Media Player")
        self.designer_element_list.blockSignals(True)
        self.designer_element_list.clearSelection()
        first_row = min(current_rows) if current_rows else -1
        for row in current_rows:
            item = self.designer_element_list.item(row)
            if item is not None and not item.isHidden():
                item.setSelected(True)
        self.designer_element_list.setCurrentRow(first_row)
        self.designer_element_list.blockSignals(False)
        self.update_layer_row_visuals()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def filter_designer_element_list(self) -> None:
        needle = self.designer_component_search.text().strip().lower() if hasattr(self, "designer_component_search") else ""
        domain = self._designer_domain_mode()
        collection = self._selected_collection()
        items = self._current_theme_items() if self.theme_doc_model is not None else []
        for row in range(self.designer_element_list.count()):
            item = self.designer_element_list.item(row)
            widget = self.designer_element_list.itemWidget(item)
            hay = ""
            if isinstance(widget, LayerRowWidget):
                hay = " ".join(
                    [
                        widget.title_label.text(),
                        widget.subtitle_label.text(),
                        widget.badge_label.text(),
                    ]
                ).lower()
            else:
                hay = (item.text() or "").lower()
            model_item = items[row] if 0 <= row < len(items) else {}
            domain_hidden = not self._item_matches_designer_domain(model_item, collection, domain)
            text_hidden = bool(needle) and needle not in hay
            item.setHidden(domain_hidden or text_hidden)
        current_row = self.designer_element_list.currentRow()
        if 0 <= current_row < self.designer_element_list.count():
            current_item = self.designer_element_list.item(current_row)
            if current_item is not None and current_item.isHidden():
                replacement = -1
                for row in range(self.designer_element_list.count()):
                    candidate = self.designer_element_list.item(row)
                    if candidate is not None and not candidate.isHidden():
                        replacement = row
                        break
                self.designer_element_list.setCurrentRow(replacement)
        self._update_designer_element_list_height()

    def _update_designer_element_list_height(self) -> None:
        if not hasattr(self, "designer_element_list"):
            return
        # Keep the left panel stable. The list is the only vertically expanding
        # child; recalculating max height from visible rows makes the Designer
        # jump while filtering or changing selection.
        self.designer_element_list.setMinimumHeight(260)
        self.designer_element_list.setMaximumHeight(16777215)

    def apply_studio_layout_preset(self, preset_name: str) -> None:
        splitter = getattr(self, "studio_splitter", None)
        if splitter is None:
            return
        if preset_name == "compact":
            splitter.setSizes([720, 860])
        elif preset_name == "canvas":
            splitter.setSizes([560, 1220])
        else:
            splitter.setSizes([760, 1040])
        top_splitter = getattr(self, "designer_top_splitter", None)
        if top_splitter is not None:
            if preset_name == "canvas":
                top_splitter.setSizes([1040, 240])
            elif preset_name == "compact":
                top_splitter.setSizes([900, 220])
            else:
                top_splitter.setSizes([980, 260])
            self._clamp_designer_splitter_later()

    def apply_designer_mode(self, mode: str) -> None:
        simple = str(mode).lower() == "simple"
        if hasattr(self, "designer_lower_controls"):
            self.designer_lower_controls.setVisible(not simple)
        if hasattr(self, "designer_controls_splitter"):
            if simple:
                self.designer_controls_splitter.setSizes([760, 0])
            else:
                self.designer_controls_splitter.setSizes([520, 260])
        if hasattr(self, "designer_main_splitter"):
            if simple:
                self.designer_main_splitter.setSizes([500, 1380])
            else:
                self.designer_main_splitter.setSizes([520, 1360])
        for widget in getattr(self, "designer_advanced_buttons", []):
            widget.setVisible(not simple)
        if hasattr(self, "preview_guides_chk"):
            self.preview_guides_chk.setChecked(False if simple else self.preview_guides_chk.isChecked())
        if hasattr(self, "inspector_tabs"):
            general_idx = self.inspector_tabs.indexOf(self.inspector_general)
            content_idx = self.inspector_tabs.indexOf(self.inspector_content)
            appearance_idx = self.inspector_tabs.indexOf(self.inspector_appearance)
            gauge_idx = self.inspector_tabs.indexOf(getattr(self, "inspector_gauge", None))
            geometry_idx = self.inspector_tabs.indexOf(self.inspector_geometry)
            image_idx = self.inspector_tabs.indexOf(self.inspector_image)
            if general_idx >= 0:
                self.inspector_tabs.setTabVisible(general_idx, True)
            if content_idx >= 0:
                self.inspector_tabs.setTabVisible(content_idx, True)
            if appearance_idx >= 0:
                self.inspector_tabs.setTabVisible(appearance_idx, True)
            if gauge_idx >= 0:
                self.inspector_tabs.setTabVisible(gauge_idx, not simple)
            if geometry_idx >= 0:
                self.inspector_tabs.setTabVisible(geometry_idx, not simple)
            if image_idx >= 0:
                current_collection = self._selected_collection() if hasattr(self, "designer_kind_combo") else ""
                self.inspector_tabs.setTabVisible(image_idx, (not simple) or current_collection == "images")
        self._refresh_inspector_music_layout()
        self._refresh_inspector_weather_layout()
        self._clamp_designer_splitter_later()

    def _designer_splitter_limits(self) -> tuple[int, int]:
        height = max(760, int(self.height() or 0))
        compact_height = height < 1040
        min_canvas = 280 if compact_height else 320
        max_inspector = 380 if compact_height else 460
        return min_canvas, max_inspector

    def _clamp_designer_splitter_later(self) -> None:
        QTimer.singleShot(0, self._clamp_designer_splitter)

    def _clamp_designer_splitter(self) -> None:
        splitter = getattr(self, "designer_top_splitter", None)
        inspector = getattr(self, "designer_inspector_container", None)
        canvas = getattr(self, "designer_canvas_workbench", None)
        if splitter is None or inspector is None or canvas is None or splitter.count() < 2:
            return
        min_canvas, max_inspector = self._designer_splitter_limits()
        max_canvas = 430 if (self.height() or 0) < 1040 else 500
        canvas.setMinimumHeight(min_canvas)
        canvas.setMaximumHeight(max_canvas)
        inspector.setMaximumHeight(max_inspector)
        sizes = splitter.sizes()
        if len(sizes) < 2:
            return
        total = max(sum(sizes), min_canvas + 180)
        target_inspector = min(max_inspector, max(180, sizes[1]))
        target_canvas = max(min_canvas, min(max_canvas, total - target_inspector))
        target_inspector = max(180, min(max_inspector, total - target_canvas))
        if target_canvas + target_inspector < total and target_inspector < max_inspector:
            target_inspector = min(max_inspector, target_inspector + (total - target_canvas - target_inspector))
        next_sizes = [target_canvas, target_inspector]
        if any(abs(sizes[idx] - next_sizes[idx]) > 8 for idx in range(2)):
            splitter.blockSignals(True)
            try:
                splitter.setSizes(next_sizes)
            finally:
                splitter.blockSignals(False)

    def _set_designer_inspector_docked_bottom(self, dock_bottom: bool) -> None:
        container = getattr(self, "designer_inspector_container", None)
        top_splitter = getattr(self, "designer_top_splitter", None)
        lower_splitter = getattr(self, "designer_controls_splitter", None)
        if container is None or top_splitter is None or lower_splitter is None:
            return
        dock_bottom = bool(dock_bottom)
        if getattr(self, "designer_inspector_docked_bottom", False) == dock_bottom:
            return
        container.hide()
        container.setParent(None)
        if dock_bottom:
            lower_splitter.insertWidget(0, container)
            lower_splitter.setStretchFactor(0, 1)
        else:
            top_splitter.addWidget(container)
            top_splitter.setStretchFactor(top_splitter.indexOf(container), 0)
        container.show()
        self.designer_inspector_docked_bottom = dock_bottom

    def _history_snapshot(self) -> dict[str, Any] | None:
        if self.theme_doc_model is None:
            return None
        return deepcopy(self.theme_doc_model)

    def push_designer_history(self) -> None:
        if self._history_suspended:
            return
        snapshot = self._history_snapshot()
        if snapshot is None:
            return
        if self._history_undo and self._history_undo[-1] == snapshot:
            return
        self._history_undo.append(snapshot)
        self._history_undo = self._history_undo[-80:]
        self._history_redo.clear()

    def begin_designer_drag(self) -> None:
        self._designer_drag_active = True
        if hasattr(self, "preview_debounce"):
            self.preview_debounce.stop()
        self.push_designer_history()

    def _restore_history_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._history_suspended = True
        try:
            self.theme_doc_model = normalize_theme_document(deepcopy(snapshot))
            self._load_background_fields()
            self.write_designer_to_json()
            self.refresh_designer_element_list()
            self._update_preview_canvas_overlay()
            self.schedule_preview_theme_doc()
        finally:
            self._history_suspended = False

    def undo_designer_change(self) -> None:
        current = self._history_snapshot()
        if not self._history_undo or current is None:
            return
        previous = self._history_undo.pop()
        self._history_redo.append(current)
        self._restore_history_snapshot(previous)

    def redo_designer_change(self) -> None:
        current = self._history_snapshot()
        if not self._history_redo or current is None:
            return
        upcoming = self._history_redo.pop()
        self._history_undo.append(current)
        self._restore_history_snapshot(upcoming)

    def update_preview_coords(self, point: object) -> None:
        if isinstance(point, QPoint):
            self.preview_coords_label.setText(f"x: {point.x()}, y: {point.y()}")
        else:
            self.preview_coords_label.setText("x: -, y: -")

    def _designer_keyboard_capture_enabled(self) -> bool:
        if not hasattr(self, "main_tabs") or self.main_tabs.currentIndex() != 1:
            return False
        focus = QApplication.focusWidget()
        blocked_types = (QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox)
        if isinstance(focus, blocked_types):
            return False
        return True

    def _selected_item_rect(self, item: dict[str, Any], collection: str) -> tuple[int, int, int, int]:
        if collection in {"images", "panels", "widgets"}:
            rect = item.get("rect", [0, 0, 1, 1])
            if isinstance(rect, list) and len(rect) == 4:
                return int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
            return 0, 0, 1, 1
        return (
            int(item.get("x", 0)),
            int(item.get("y", 0)),
            max(1, int(item.get("box_width", 320))),
            max(1, int(item.get("box_height", 48))),
        )

    def _selected_group_bounds(self, selected: list[tuple[str, int, dict[str, Any]]]) -> tuple[int, int, int, int] | None:
        rects = [self._selected_item_rect(item, collection) for collection, _row, item in selected]
        if not rects:
            return None
        left = min(rect[0] for rect in rects)
        top = min(rect[1] for rect in rects)
        right = max(rect[0] + rect[2] for rect in rects)
        bottom = max(rect[1] + rect[3] for rect in rects)
        return int(left), int(top), max(1, int(right - left)), max(1, int(bottom - top))

    def _apply_item_rect(self, collection: str, item: dict[str, Any], rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        x = self._snap_value(int(x))
        y = self._snap_value(int(y))
        width = max(1, self._snap_value(int(width)))
        height = max(1, self._snap_value(int(height)))
        if collection in {"images", "panels", "widgets"}:
            item["rect"] = [x, y, width, height]
        else:
            item["x"] = x
            item["y"] = y
            item["box_width"] = width
            item["box_height"] = height

    def _selected_nudge_step(self) -> int:
        combo = getattr(self, "designer_nudge_step_combo", None)
        if combo is None:
            return 1
        try:
            return max(1, int(combo.currentData() or 1))
        except Exception:
            return 1

    def nudge_selected_elements(
        self,
        dx: int,
        dy: int,
        *,
        big_step: bool = False,
        step_override: int | None = None,
        require_keyboard_focus: bool = True,
    ) -> None:
        if require_keyboard_focus and not self._designer_keyboard_capture_enabled():
            return
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        step = int(step_override) if step_override is not None else (10 if big_step else 1)
        step = max(1, step)
        dx *= step
        dy *= step
        self.push_designer_history()
        first_collection, first_row, first_item = selected[0]
        first_before = self._selected_item_rect(first_item, first_collection)
        for selected_collection, _row, item in selected:
            if bool(item.get("locked", False)):
                continue
            if selected_collection in {"images", "panels", "widgets"}:
                rect = item.get("rect", [0, 0, 1, 1])
                if isinstance(rect, list) and len(rect) == 4:
                    item["rect"] = [
                        self._snap_value(int(rect[0]) + dx),
                        self._snap_value(int(rect[1]) + dy),
                        int(rect[2]),
                        int(rect[3]),
                    ]
            else:
                item["x"] = self._snap_value(int(item.get("x", 0)) + dx)
                item["y"] = self._snap_value(int(item.get("y", 0)) + dy)
        first_after = self._selected_item_rect(first_item, first_collection)
        actual_dx = int(first_after[0] - first_before[0])
        actual_dy = int(first_after[1] - first_before[1])
        self.preview_delta_label.setText(f"Δx: {actual_dx:+d}, Δy: {actual_dy:+d}")
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        if first_collection != self._selected_collection():
            combo_index = self.designer_kind_combo.findData(first_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
        if 0 <= first_row < self.designer_element_list.count():
            self.designer_element_list.setCurrentRow(first_row)
        self._update_preview_canvas_overlay()
        guides = self.preview_label._compute_snap_guides(
            first_after[0],
            first_after[1],
            first_after[2],
            first_after[3],
            first_collection,
            first_row,
        )
        self.preview_label.set_temporary_guides(guides, f"Δx {actual_dx:+d}  Δy {actual_dy:+d}")
        self.schedule_preview_theme_doc()

    def toggle_layer_visibility_at(self, row: int) -> None:
        if self.theme_doc_model is None:
            return
        items = self._current_theme_items()
        if not (0 <= row < len(items)):
            return
        items[row]["visible"] = not bool(items[row].get("visible", True))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.designer_element_list.setCurrentRow(row)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def toggle_layer_lock_at(self, row: int) -> None:
        if self.theme_doc_model is None:
            return
        items = self._current_theme_items()
        if not (0 <= row < len(items)):
            return
        items[row]["locked"] = not bool(items[row].get("locked", False))
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.designer_element_list.setCurrentRow(row)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def on_designer_rows_reordered(self) -> None:
        if self.theme_doc_model is None or self._designer_updating:
            return
        items = self._current_theme_items()
        if not items:
            return
        self.push_designer_history()
        by_id = {str(item.get("id", "")): item for item in items}
        reordered: list[dict[str, Any]] = []
        for row in range(self.designer_element_list.count()):
            list_item = self.designer_element_list.item(row)
            ident = str(list_item.data(Qt.UserRole) or "")
            target = by_id.get(ident)
            if target is not None:
                reordered.append(target)
        if len(reordered) != len(items):
            return
        collection = self._selected_collection()
        if collection == "panels":
            self.theme_doc_model.setdefault("background", {})["panels"] = reordered
        else:
            self.theme_doc_model[collection] = reordered
        for idx, item in enumerate(reordered):
            item["z_index"] = idx
        current = self.designer_element_list.currentRow()
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        if 0 <= current < self.designer_element_list.count():
            self.designer_element_list.setCurrentRow(current)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def show_designer_layer_menu(self, pos: QPoint) -> None:
        item = self.designer_element_list.itemAt(pos)
        if item is not None:
            item.setSelected(True)
            self.designer_element_list.setCurrentItem(item)
        menu = QMenu(self)
        tr = self._tr
        visible_action = menu.addAction(tr("Show / hide", "Pokaż / Ukryj"))
        lock_action = menu.addAction(tr("Lock / unlock", "Blokuj / Odblokuj"))
        menu.addSeparator()
        up_action = menu.addAction(tr("Layer +", "Warstwa +"))
        down_action = menu.addAction(tr("Layer −", "Warstwa -"))
        menu.addSeparator()
        dup_action = menu.addAction(tr("Duplicate", "Duplikuj"))
        del_action = menu.addAction(tr("Delete", "Usuń"))
        chosen = menu.exec(self.designer_element_list.mapToGlobal(pos))
        if chosen == visible_action:
            self.toggle_selected_visible()
        elif chosen == lock_action:
            self.toggle_selected_locked()
        elif chosen == up_action:
            self.raise_designer_layer()
        elif chosen == down_action:
            self.lower_designer_layer()
        elif chosen == dup_action:
            self.clone_designer_element()
        elif chosen == del_action:
            self.remove_designer_element()

    def _set_tab_enabled_if_present(self, widget: QWidget, enabled: bool) -> None:
        idx = self.inspector_tabs.indexOf(widget)
        if idx >= 0:
            self.inspector_tabs.setTabVisible(idx, enabled)

    def _set_form_row_visible(self, layout: QFormLayout, label_widget: QWidget, field_widget: QWidget, visible: bool) -> None:
        if label_widget is not None:
            label_widget.setVisible(visible)
        if field_widget is not None:
            field_widget.setVisible(visible)
        if layout is not None:
            layout.invalidate()

    def _set_field_enabled(self, widget: QWidget, enabled: bool) -> None:
        widget.setEnabled(enabled)

    def _stat_binding_row_pairs(self) -> list[tuple[QLabel, QWidget]]:
        return [
            (self.row_content_source, self.designer_source_combo),
            (self.row_content_format, self.designer_format_edit),
            (self.row_content_stat_display, self.designer_stat_display_combo),
            (self.row_content_stat_range, self.designer_stat_range_row),
            (self.row_content_stat_show_value, self.designer_stat_show_value_chk),
        ]

    def _move_stat_binding_rows_to_music(self) -> None:
        if not hasattr(self, "inspector_music_layout"):
            return
        if getattr(self, "_stat_binding_rows_layout", None) is self.inspector_music_layout:
            return
        content = self.inspector_content_layout
        music = self.inspector_music_layout
        pairs = self._stat_binding_row_pairs()
        for _lbl, field in pairs:
            try:
                content.removeRow(field)
            except Exception:
                pass
        for lbl, fld in reversed(pairs):
            music.insertRow(0, lbl, fld)
        self._stat_binding_rows_layout = self.inspector_music_layout

    def _move_stat_binding_rows_to_content(self) -> None:
        if not hasattr(self, "inspector_content_layout"):
            return
        if getattr(self, "_stat_binding_rows_layout", None) is self.inspector_content_layout:
            return
        content = self.inspector_content_layout
        music = self.inspector_music_layout
        pairs = self._stat_binding_row_pairs()
        for _lbl, field in pairs:
            try:
                music.removeRow(field)
            except Exception:
                pass
        insert_at = 2
        for lbl, fld in pairs:
            content.insertRow(insert_at, lbl, fld)
            insert_at += 1
        self._stat_binding_rows_layout = self.inspector_content_layout

    def _sync_stat_binding_row_visibility(self, collection: str) -> None:
        is_stat = collection == "stats"
        on_music = getattr(self, "_stat_binding_rows_layout", None) is getattr(self, "inspector_music_layout", None)
        lay = self.inspector_music_layout if on_music else self.inspector_content_layout
        for lbl, field in self._stat_binding_row_pairs():
            self._set_form_row_visible(lay, lbl, field, is_stat)

    def _refresh_inspector_music_layout(self) -> None:
        if not hasattr(self, "inspector_music"):
            return
        music_idx = self.inspector_tabs.indexOf(self.inspector_music)
        multi = self._selected_items_multi_any()
        coll = self._selected_collection()

        simple_mode = bool(
            hasattr(self, "designer_mode_combo")
            and str(self.designer_mode_combo.currentText()).strip().lower() == "simple"
        )

        if len(multi) != 1:
            self._move_stat_binding_rows_to_content()
            if music_idx >= 0:
                self.inspector_tabs.setTabVisible(music_idx, False)
            if hasattr(self, "inspector_music_spectrum_placeholder"):
                self.inspector_music_spectrum_placeholder.setVisible(False)
            if hasattr(self, "inspector_music_hint"):
                self.inspector_music_hint.setVisible(False)
            self._sync_stat_binding_row_visibility(coll)
            return

        _c, _r, item = multi[0]
        src = str(self.designer_source_combo.currentData() or "").strip() if coll == "stats" else ""
        want_music_tab = False
        show_music_stat_rows = False

        if coll == "stats":
            display_mode = str(item.get("display", "text")).strip().lower() if item is not None else ""
            show_music_stat_rows = src in MUSIC_AUDIO_STAT_SOURCES or display_mode in MUSIC_VISUAL_STAT_DISPLAYS
            want_music_tab = show_music_stat_rows
        elif coll == "panels" and item is not None:
            pid = str(item.get("id", "")).strip()
            want_music_tab = any(pid.startswith(p) for p in MUSIC_RELATED_PANEL_ID_PREFIXES)
        elif coll == "images" and item is not None:
            want_music_tab = str(item.get("source", "")).strip() in MUSIC_RELATED_IMAGE_SOURCES
        elif coll == "widgets" and item is not None:
            want_music_tab = str(item.get("kind", "")).strip().lower().startswith("media_")

        if coll == "stats" and show_music_stat_rows and not simple_mode:
            self._move_stat_binding_rows_to_music()
        else:
            self._move_stat_binding_rows_to_content()

        tab_shown = bool(want_music_tab) and not simple_mode
        if music_idx >= 0:
            self.inspector_tabs.setTabVisible(music_idx, tab_shown)

        hint_panel = (
            coll == "panels"
            and item is not None
            and any(str(item.get("id", "")).strip().startswith(p) for p in MUSIC_RELATED_PANEL_ID_PREFIXES)
        )
        hint_image = (
            coll == "images"
            and item is not None
            and str(item.get("source", "")).strip() in MUSIC_RELATED_IMAGE_SOURCES
        )
        hint_widget = (
            coll == "widgets"
            and item is not None
            and str(item.get("kind", "")).strip().lower().startswith("media_")
        )
        if hasattr(self, "inspector_music_hint"):
            if hint_panel:
                self.inspector_music_hint.setText(
                    self._tr(
                        "This panel is used by Music / Now Playing bundles (appearance is edited under Style).",
                        "Ten panel jest używany w zestawach Muzyka / Now Playing (wygląd ustawisz w zakładce Styl).",
                    )
                )
            elif hint_image:
                self.inspector_music_hint.setText(
                    self._tr(
                        "Album art / media backdrop: crop and opacity under Image; synchronized spectrum EQ will appear here later.",
                        "Okładka / tło mediów: kadrowanie i przezroczystość w zakładce Obraz; zsynchronizowany korektor widma pojawi się tu później.",
                    )
                )
            elif hint_widget:
                self.inspector_music_hint.setText(
                    self._tr(
                        "Composite Now Playing widget: move and scale it as one element; tune title, artist, details and panel styling here.",
                        "Złożony widget Now Playing: przesuwasz i skalujesz go jako jeden element; tutaj ustawiasz tytuł, wykonawcę, detale i panel.",
                    )
                )
            elif coll == "stats" and item is not None and str(item.get("display", "")).strip().lower() == "equalizer":
                self.inspector_music_hint.setText(
                    self._tr(
                        "Graphic EQ is a music-only animated display. It reacts to volume and playback state; use bars / gap / mirror below.",
                        "Graphic EQ to animowany widok tylko dla muzyki. Reaguje na głośność i stan odtwarzania; niżej ustawisz liczbę słupków, odstęp i tryb mirror.",
                    )
                )
            else:
                self.inspector_music_hint.clear()
            show_music_hint = bool(tab_shown and (hint_panel or hint_image or hint_widget))
            if coll == "stats" and item is not None and str(item.get("display", "")).strip().lower() == "equalizer":
                show_music_hint = bool(tab_shown)
            self.inspector_music_hint.setVisible(show_music_hint)

        if hasattr(self, "inspector_music_spectrum_placeholder"):
            pl = self._tr(
                "Animated spectrum / EQ visualizer: reserved for a future update.",
                "Animowany korektor / wizualizacja widma: zarezerwowane na przyszłą aktualizację.",
            )
            self.inspector_music_spectrum_placeholder.setText(pl)
            show_eq_placeholder = (
                coll == "stats"
                and item is not None
                and str(item.get("display", "")).strip().lower() == "equalizer"
            )
            self.inspector_music_spectrum_placeholder.setVisible(bool(tab_shown and not show_eq_placeholder))

        show_media_widget_fields = bool(tab_shown and coll == "widgets" and item is not None and str(item.get("kind", "")).strip().lower().startswith("media_"))
        music_layout = self.inspector_music_layout
        for row_label, widget in (
            (self.row_music_widget_options, self.music_widget_options_row),
            (self.row_music_widget_title_font, self.widget_title_font_spin),
            (self.row_music_widget_artist_font, self.widget_body_font_spin),
            (self.row_music_widget_detail_font, self.widget_detail_font_spin),
            (self.row_music_widget_title_color, self.widget_title_color_row),
            (self.row_music_widget_artist_color, self.widget_body_color_row),
            (self.row_music_widget_detail_color, self.widget_detail_color_row),
            (self.row_music_widget_panel_color, self.widget_panel_color_row),
        ):
            self._set_form_row_visible(music_layout, row_label, widget, show_media_widget_fields)

        self._sync_stat_binding_row_visibility(coll)

    def _refresh_inspector_weather_layout(self) -> None:
        if not hasattr(self, "inspector_weather"):
            return
        weather_idx = self.inspector_tabs.indexOf(self.inspector_weather)
        multi = self._selected_items_multi_any()
        coll = self._selected_collection()
        want_weather_tab = False
        weather_source = ""
        weather_format = "{value}"
        if len(multi) == 1:
            _c, _r, item = multi[0]
            if coll == "stats":
                src = str(item.get("source", "")).strip()
                want_weather_tab = src in WEATHER_STAT_SOURCES
                weather_source = src
                weather_format = str(item.get("format", "{value}") or "{value}")
            elif coll == "images":
                src = str(item.get("source", "")).strip()
                want_weather_tab = src in WEATHER_RELATED_IMAGE_SOURCES or (src.startswith("weather_day_") and src.endswith("_icon"))
            elif coll == "panels":
                pid = str(item.get("id", "")).strip()
                want_weather_tab = any(pid.startswith(prefix) for prefix in WEATHER_RELATED_PANEL_ID_PREFIXES)
            elif coll == "widgets":
                want_weather_tab = str(item.get("kind", "")).strip().lower().startswith("weather_")
        if weather_idx >= 0:
            self.inspector_tabs.setTabVisible(weather_idx, bool(want_weather_tab))
        show_stat_fields = bool(want_weather_tab and coll == "stats")
        show_city_fields = bool(want_weather_tab and coll == "widgets")
        show_weather_widget_fields = show_city_fields
        for row_widget in (
            getattr(self, "row_weather_city", None),
            getattr(self, "weather_city_row", None),
        ):
            if row_widget is not None:
                row_widget.setVisible(show_city_fields)
        weather_layout = getattr(self, "inspector_weather_layout", None)
        self._set_form_row_visible(
            weather_layout,
            getattr(self, "row_weather_source", None),
            getattr(self, "weather_binding_row", None),
            show_stat_fields,
        )
        self._set_form_row_visible(
            weather_layout,
            getattr(self, "row_weather_tools", None),
            getattr(self, "weather_tools_row", None),
            bool(want_weather_tab and not show_weather_widget_fields),
        )
        for row_label, widget in (
            (self.row_weather_widget_fonts, self.weather_widget_fonts_row),
            (self.row_weather_widget_colors, self.weather_widget_colors_row),
            (self.row_weather_widget_transparent_bg, self.weather_widget_transparent_bg_chk),
            (self.row_weather_widget_animate_icons, self.weather_widget_animate_icons_chk),
        ):
            self._set_form_row_visible(weather_layout, row_label, widget, show_weather_widget_fields)
        if show_stat_fields and hasattr(self, "weather_source_combo"):
            self._designer_updating = True
            try:
                self._populate_weather_source_combo(weather_source)
                idx = self.weather_format_combo.findData(weather_format)
                if idx < 0 and weather_format:
                    self.weather_format_combo.addItem(weather_format, weather_format)
                    idx = self.weather_format_combo.findData(weather_format)
                self.weather_format_combo.setCurrentIndex(idx if idx >= 0 else 0)
            finally:
                self._designer_updating = False

    def preview_zoom_fit(self) -> None:
        self.preview_label.set_zoom_mode("fit")

    def preview_zoom_set(self, percent: int) -> None:
        self.preview_label.set_zoom_percent(percent)

    def _apply_visibility_for_collection(self, collection: str) -> None:
        is_text = collection == "texts"
        is_stat = collection == "stats"
        is_image = collection == "images"
        is_panel = collection == "panels"
        is_widget = collection == "widgets"
        supports_motion = collection in {"texts", "stats", "images", "panels", "widgets"}

        self._set_tab_enabled_if_present(self.inspector_general, True)
        self._set_tab_enabled_if_present(self.inspector_content, is_text or is_stat)
        self._set_tab_enabled_if_present(self.inspector_appearance, is_text or is_stat or is_image or is_panel or is_widget)
        self._set_tab_enabled_if_present(self.inspector_gauge, is_stat)
        self._set_tab_enabled_if_present(self.inspector_geometry, True)
        self._set_tab_enabled_if_present(self.inspector_image, is_image)
        self._set_tab_enabled_if_present(self.inspector_weather, is_widget)

        self._set_form_row_visible(inspector_content_layout := self.inspector_content_layout, self.row_content_text, self.designer_text_edit, is_text)
        self._set_form_row_visible(inspector_content_layout, self.row_content_label, self.designer_label_edit, is_stat)
        # Stat binding rows (source, format, …) live on Content or Music tab — visibility via _refresh_inspector_music_layout().
        self.designer_source_combo.setToolTip("Źródło danych dla tej statystyki.")
        self.designer_format_edit.setPlaceholderText("{value}")
        self.designer_label_edit.setPlaceholderText("Np. CPU, RAM, Temp")

        appearance_layout = self.inspector_appearance_layout
        self._set_form_row_visible(appearance_layout, self.row_appearance_font, self.font_row, is_text or is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_font_style, self.font_style_row, is_text or is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_align, self.designer_align_combo, is_text or is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_color, self.designer_color_row, is_text)
        self._set_form_row_visible(appearance_layout, self.row_appearance_label_color, self.designer_label_color_row, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_value_color, self.designer_value_color_row, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_track_color, self.designer_track_color_row, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_fill_color, self.designer_fill_color_row, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_sparkline_points, self.designer_sparkline_points_spin, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_sparkline_fill_opacity, self.designer_sparkline_fill_opacity_spin, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_sparkline_show_points, self.designer_sparkline_show_points_chk, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_panel_fill, self.panel_style_row, is_panel or is_widget)
        if hasattr(self, "panel_fill_compact_label"):
            self.panel_fill_compact_label.setVisible(is_panel)
        if hasattr(self, "panel_fill_row"):
            self.panel_fill_row.setVisible(is_panel)
        if hasattr(self, "panel_radius_compact_label"):
            self.panel_radius_compact_label.setVisible(is_panel)
        if hasattr(self, "panel_radius_spin"):
            self.panel_radius_spin.setVisible(is_panel)

        geometry_layout = self.inspector_geometry_layout
        self._set_form_row_visible(geometry_layout, self.row_geometry_x, self.designer_x_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_geometry_y, self.designer_y_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_geometry_w, self.designer_w_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_geometry_h, self.designer_h_spin, True)
        self._set_form_row_visible(
            geometry_layout,
            getattr(self, "row_geometry_group_bounds", None),
            getattr(self, "geometry_group_bounds_label", None),
            False,
        )
        self._set_form_row_visible(geometry_layout, self.row_motion_enabled, self.motion_enabled_chk, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_range, self.motion_range_row, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_target_x, self.motion_target_x_spin, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_target_y, self.motion_target_y_spin, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_target_opacity, self.motion_target_opacity_spin, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_actions, self.motion_actions_row, supports_motion)
        image_layout = self.inspector_image_layout
        self._set_form_row_visible(image_layout, self.row_image_path, self.designer_path_row, is_image)
        self._set_form_row_visible(image_layout, self.row_image_fit, self.image_transform_row, is_image)
        self._set_form_row_visible(image_layout, self.row_image_import, self.designer_import_image_btn, is_image)
        self._set_form_row_visible(image_layout, self.row_image_actions, self.designer_image_actions_row, is_image)
        self._set_form_row_visible(image_layout, self.row_image_preview, self.designer_image_preview_label, is_image)

        self.designer_import_image_btn.setVisible(collection == "images")
        self.designer_path_prepare_btn.setVisible(collection == "images")
        self.designer_path_browse_btn.setVisible(collection == "images")

        if collection == "texts":
            self.preview_info_label.setText("Tekst: kliknij na podglądzie, aby ustawić pozycję napisu.")
            self.inspector_tabs.setCurrentWidget(self.inspector_content)
        elif collection == "stats":
            self.preview_info_label.setText("Statystyka: wybierz źródło danych i ustaw pozycję klikając na podglądzie.")
            self.inspector_tabs.setCurrentWidget(self.inspector_content)
        elif collection == "panels":
            self.preview_info_label.setText("Panel: przeciągnij, aby przesunąć. Uchwyt w rogu zmienia rozmiar.")
            self.inspector_tabs.setCurrentWidget(self.inspector_appearance)
        elif collection == "widgets":
            self.preview_info_label.setText("Widget: przesuwasz i skalujesz całość, szczegóły ustawiasz w zakładce Weather.")
            self.inspector_tabs.setCurrentWidget(self.inspector_weather)
        else:
            self.preview_info_label.setText("Obraz: kliknij na podglądzie, aby ustawić pozycję albo zmień parametry w zakładce Obraz.")
            self.inspector_tabs.setCurrentWidget(self.inspector_image)

        if collection == "stats":
            self._update_gauge_stat_inspector_visibility()
        self._clamp_designer_splitter_later()

    def load_selected_designer_item(self) -> None:
        collection = self._selected_collection()
        self._apply_visibility_for_collection(collection)
        self.preview_delta_label.setText("Δx: 0, Δy: 0")
        self.preview_label.clear_temporary_guides()
        selected_multi_any = self._selected_items_multi_any()
        items, row, item = self._selected_item()
        active_item = item
        active_collection = collection
        active_row = row
        if len(selected_multi_any) == 1:
            active_collection, active_row, active_item = selected_multi_any[0]
        self._designer_updating = True
        try:
            if len(selected_multi_any) > 1:
                selected_entries = [(selected_collection, selected_row) for selected_collection, selected_row, _selected_item in selected_multi_any]
                group_label = self._designer_selection_group_label or self._selection_group_label_for_entries(selected_entries)
                collections = sorted({selected_collection for selected_collection, _selected_row in selected_entries})
                meta = ", ".join(collections)
                self.designer_selection_label.setText(
                    f"Grupa: {group_label or 'Multi'} • {len(selected_multi_any)} • {meta}"
                )
                self.designer_selection_label.setToolTip(
                    f"Grupa: {group_label or 'Multi'} • {len(selected_multi_any)} • {meta}"
                )
                self.inspector_selection_summary.setText(
                    "Dostępne są wspólne ustawienia: widoczność, blokada, warstwa i przesuwanie całej grupy."
                )
                bounds = self._selected_group_bounds(selected_multi_any)
                if bounds is not None and hasattr(self, "geometry_group_bounds_label"):
                    bx, by, bw, bh = bounds
                    self.geometry_group_bounds_label.setText(f"x: {bx}, y: {by}, w: {bw}, h: {bh}")
                    self._set_form_row_visible(
                        self.inspector_geometry_layout,
                        self.row_geometry_group_bounds,
                        self.geometry_group_bounds_label,
                        True,
                    )
                common_z = {int(sel_item.get('z_index', 0)) for _sel_collection, _sel_row, sel_item in selected_multi_any}
                self.designer_id_edit.clear()
                self.designer_text_edit.clear()
                self.designer_label_edit.clear()
                self.designer_format_edit.clear()
                self.designer_path_edit.clear()
                self.designer_visible_chk.setChecked(all(bool(sel_item.get("visible", True)) for _sel_collection, _sel_row, sel_item in selected_multi_any))
                self.designer_locked_chk.setChecked(all(bool(sel_item.get("locked", False)) for _sel_collection, _sel_row, sel_item in selected_multi_any))
                self.designer_z_spin.setValue(next(iter(common_z)) if len(common_z) == 1 else 0)
                self.panel_fill_edit.clear()
                self.panel_radius_spin.setValue(0)
                self._clear_stat_gauge_fields()
                self._clear_stat_sparkline_fields()
                self._clear_stat_equalizer_fields()
                self._load_motion_track_fields(None, collection)
                self.inspector_tabs.setCurrentWidget(self.inspector_general)
                self._update_designer_mouse_tools_availability()
                return

            if active_item is None:
                self.designer_selection_label.setText(
                    "Brak zaznaczenia • kliknij warstwę lub element na podglądzie"
                )
                self.designer_selection_label.setToolTip(
                    "Brak zaznaczenia • kliknij warstwę lub element na podglądzie"
                )
                self.inspector_selection_summary.setText("Wybierz element z listy warstw albo kliknij go na podglądzie.")
                self.designer_id_edit.clear()
                self.designer_x_spin.setValue(0)
                self.designer_y_spin.setValue(0)
                self.designer_text_edit.clear()
                self.designer_font_family_combo.setCurrentText(available_font_families()[0])
                self.designer_font_size_spin.setValue(24)
                self.designer_font_bold_chk.setChecked(False)
                self.designer_font_italic_chk.setChecked(False)
                self.designer_font_underline_chk.setChecked(False)
                self.designer_align_combo.setCurrentText("left")
                self.designer_color_edit.clear()
                self.designer_label_edit.clear()
                default_source = self.theme_stat_sources[0] if self.theme_stat_sources else ""
                self._populate_designer_source_combo(default_source)
                self.designer_format_edit.clear()
                self.designer_stat_display_combo.setCurrentText("text")
                self.designer_stat_min_spin.setValue(0.0)
                self.designer_stat_max_spin.setValue(100.0)
                self.designer_stat_show_value_chk.setChecked(True)
                self.designer_label_color_edit.clear()
                self.designer_value_color_edit.clear()
                self.designer_track_color_edit.clear()
                self.designer_fill_color_edit.clear()
                self._clear_stat_gauge_fields()
                self._clear_stat_sparkline_fields()
                self._clear_stat_equalizer_fields()
                self.designer_stat_stroke_width_spin.setValue(12)
                self.designer_path_edit.clear()
                self.designer_w_spin.setValue(1)
                self.designer_h_spin.setValue(1)
                self.designer_fit_combo.setCurrentText("contain")
                self.designer_opacity_spin.setValue(1.0)
                self.designer_rotation_spin.setValue(0)
                self.designer_z_spin.setValue(0)
                self.designer_visible_chk.setChecked(True)
                self.designer_locked_chk.setChecked(False)
                self.panel_fill_edit.clear()
                self.panel_opacity_spin.setValue(1.0)
                self.panel_radius_spin.setValue(0)
                self._load_motion_track_fields(None, collection)
                self._update_designer_mouse_tools_availability()
                return

            self.designer_selection_label.setText(
                self._display_name_for_item(active_item, active_collection, active_row)
            )
            self.designer_selection_label.setToolTip(
                self._display_name_for_item(active_item, active_collection, active_row)
            )
            self.inspector_selection_summary.setText(
                f"Edytujesz element: {str(active_item.get('id', f'item_{active_row}'))}"
            )
            self.designer_id_edit.setText(str(active_item.get("id", "")))
            self.designer_x_spin.setValue(int(active_item.get("x", active_item.get("rect", [0, 0, 1, 1])[0])))
            self.designer_y_spin.setValue(int(active_item.get("y", active_item.get("rect", [0, 0, 1, 1])[1])))
            self.designer_text_edit.setText(str(active_item.get("text", "")))
            font_family = str(active_item.get("font_family", available_font_families()[0]))
            self.designer_font_family_combo.setCurrentText(font_family)
            self.designer_font_size_spin.setValue(int(active_item.get("font_size", 24)))
            self.designer_font_bold_chk.setChecked(bool(active_item.get("font_bold", False)))
            self.designer_font_italic_chk.setChecked(bool(active_item.get("font_italic", False)))
            self.designer_font_underline_chk.setChecked(bool(active_item.get("font_underline", False)))
            self.designer_align_combo.setCurrentText(str(active_item.get("align", "left")))
            self.designer_color_edit.setText(json.dumps(active_item.get("color", [255, 255, 255]), ensure_ascii=False))
            self.designer_label_edit.setText(str(active_item.get("label", "")))
            source = str(active_item.get("source", self.theme_stat_sources[0] if self.theme_stat_sources else ""))
            if source:
                idx = self.designer_source_combo.findData(source)
                if idx >= 0:
                    self.designer_source_combo.setCurrentIndex(idx)
            self.designer_format_edit.setText(str(active_item.get("format", "{value}")))
            self.designer_stat_display_combo.setCurrentText(str(active_item.get("display", "text")))
            if active_collection == "stats" and str(active_item.get("display", "")).strip().lower() == "gauge":
                if self._repair_gauge_stat_dimensions(active_item):
                    self.write_designer_to_json()
            self.designer_stat_min_spin.setValue(float(active_item.get("min_value", 0.0)))
            self.designer_stat_max_spin.setValue(float(active_item.get("max_value", 100.0)))
            self.designer_stat_show_value_chk.setChecked(bool(active_item.get("show_value_text", True)))
            self.designer_label_color_edit.setText(json.dumps(active_item.get("label_color", [220, 220, 220]), ensure_ascii=False))
            self.designer_value_color_edit.setText(json.dumps(active_item.get("value_color", [220, 220, 220]), ensure_ascii=False))
            self.designer_track_color_edit.setText(json.dumps(active_item.get("track_color", [34, 44, 58, 210]), ensure_ascii=False))
            self.designer_fill_color_edit.setText(json.dumps(active_item.get("fill_color", active_item.get("value_color", [220, 220, 220])), ensure_ascii=False))
            if active_collection == "stats":
                sw = int(active_item.get("stroke_width", 12))
                self.designer_stat_stroke_width_spin.setValue(0 if sw <= 0 else sw)
                preset = str(active_item.get("gauge_preset", "")).strip().lower()
                pr_idx = self.designer_stat_gauge_preset_combo.findData(preset)
                self.designer_stat_gauge_preset_combo.setCurrentIndex(pr_idx if pr_idx >= 0 else 0)
                for gkey, gedit in (
                    ("gauge_color_low", self.designer_gauge_low_edit),
                    ("gauge_color_mid", self.designer_gauge_mid_edit),
                    ("gauge_color_high", self.designer_gauge_high_edit),
                ):
                    gval = active_item.get(gkey)
                    if gval is not None:
                        gedit.setText(json.dumps(gval, ensure_ascii=False))
                    else:
                        gedit.clear()
                self.designer_gauge_smooth_spin.setValue(float(active_item.get("gauge_smooth", 0.32)))
                self.designer_gauge_match_value_chk.setChecked(bool(active_item.get("gauge_match_value_color", True)))
                grs = active_item.get("gauge_ring_size")
                if grs is not None:
                    self.designer_gauge_ring_spin.setValue(max(40, min(900, int(grs))))
                else:
                    bw0 = int(active_item.get("box_width", 160))
                    bh0 = int(active_item.get("box_height", 160))
                    self.designer_gauge_ring_spin.setValue(max(40, min(bw0, bh0)))
                gvl = str(active_item.get("gauge_value_layout", "center")).strip().lower()
                gvl_idx = self.designer_gauge_value_layout_combo.findData(gvl)
                if gvl_idx < 0:
                    _map = {"inside": "center", "middle": "center", "bottom": "below", "dol": "below", "pod": "below", "side": "beside", "bok": "beside"}
                    gvl_idx = self.designer_gauge_value_layout_combo.findData(_map.get(gvl, "center"))
                self.designer_gauge_value_layout_combo.setCurrentIndex(gvl_idx if gvl_idx >= 0 else 0)
                self.designer_gauge_inner_alpha_spin.setValue(float(active_item.get("gauge_inner_alpha", 1.0)))
                self.designer_sparkline_points_spin.setValue(int(active_item.get("sparkline_points", 42)))
                self.designer_sparkline_fill_opacity_spin.setValue(float(active_item.get("sparkline_fill_opacity", 0.18)))
                self.designer_sparkline_show_points_chk.setChecked(bool(active_item.get("sparkline_show_points", True)))
                self.designer_equalizer_bars_spin.setValue(int(active_item.get("equalizer_bars", 18)))
                self.designer_equalizer_gap_spin.setValue(int(active_item.get("equalizer_gap", 4)))
                self.designer_equalizer_mirror_chk.setChecked(bool(active_item.get("equalizer_mirror", False)))
            else:
                self.designer_stat_stroke_width_spin.setValue(12)
                self._clear_stat_gauge_fields()
                self._clear_stat_sparkline_fields()
                self._clear_stat_equalizer_fields()
            self.designer_path_edit.setText(str(active_item.get("path", "")))
            if active_collection in {"texts", "stats"}:
                self.designer_w_spin.setValue(int(active_item.get("box_width", 320 if active_collection == "texts" else 160)))
                self.designer_h_spin.setValue(int(active_item.get("box_height", 48 if active_collection == "texts" else 160)))
            else:
                rect = active_item.get("rect", [0, 0, 1, 1])
                self.designer_w_spin.setValue(int(rect[2] if len(rect) >= 4 else 1))
                self.designer_h_spin.setValue(int(rect[3] if len(rect) >= 4 else 1))
            self.designer_fit_combo.setCurrentText(str(active_item.get("fit", "contain")))
            self.designer_opacity_spin.setValue(float(active_item.get("opacity", 1.0)))
            self.designer_rotation_spin.setValue(int(active_item.get("rotation", 0)))
            self.designer_z_spin.setValue(int(active_item.get("z_index", 0)))
            self.designer_visible_chk.setChecked(bool(active_item.get("visible", True)))
            self.designer_locked_chk.setChecked(bool(active_item.get("locked", False)))
            if active_collection == "panels":
                self.panel_fill_edit.setText(json.dumps(active_item.get("fill", [0, 0, 0]), ensure_ascii=False))
                self.panel_opacity_spin.setValue(float(active_item.get("opacity", 1.0)))
                self.panel_radius_spin.setValue(int(active_item.get("radius", 0)))
            elif active_collection == "widgets":
                self.panel_fill_edit.clear()
                self.panel_opacity_spin.setValue(float(active_item.get("opacity", 1.0)))
                self.panel_radius_spin.setValue(0)
            else:
                self.panel_fill_edit.clear()
                self.panel_opacity_spin.setValue(1.0)
                self.panel_radius_spin.setValue(0)
            self._load_widget_style_fields(active_item if active_collection == "widgets" else None)
            self._load_motion_track_fields(active_item, active_collection)
        finally:
            self._designer_updating = False
        self._refresh_inspector_music_layout()
        self._refresh_inspector_weather_layout()
        self._refresh_all_color_previews()
        preview_image_path = ""
        if active_item is not None:
            preview_image_path = str(active_item.get("path", ""))
            if active_collection == "images" and str(active_item.get("source", "")).strip() in {"media_cover", "media_video_frame"}:
                preview_image_path = self._current_media_dynamic_path(str(active_item.get("source", "")).strip())
        self._set_image_preview_label(
            self.designer_image_preview_label,
            preview_image_path,
            empty_text=self._empty_image_preview_caption(),
        )
        self._update_preview_canvas_overlay()
        self._update_gauge_stat_inspector_visibility()
        self._update_designer_mouse_tools_availability()

    def _populate_designer_stat_gauge_preset_combo(self) -> None:
        self.designer_stat_gauge_preset_combo.clear()
        self.designer_stat_gauge_preset_combo.addItem("(z motywu / auto)", "")
        ordered = [pid for pid in GAUGE_PRESET_ORDER if pid in GAUGE_PRESETS]
        ordered.extend(pid for pid in sorted(GAUGE_PRESETS.keys()) if pid not in ordered)
        for pid in ordered:
            label = GAUGE_PRESET_LABELS.get(pid, pid)
            self.designer_stat_gauge_preset_combo.addItem(f"{label} ({pid})", pid)

    def _populate_designer_theme_gauge_style_combo(self) -> None:
        self.designer_theme_gauge_style_combo.clear()
        self.designer_theme_gauge_style_combo.addItem("(default from theme name)", "")
        style_keys = sorted(set(GAUGE_PRESETS.keys()) | set(THEME_STYLE_PRESET.keys()))
        for sk in style_keys:
            if sk in GAUGE_PRESETS:
                label = GAUGE_PRESET_LABELS.get(sk, sk)
                text = f"{label} ({sk})"
            else:
                preset_id = THEME_STYLE_PRESET.get(sk, "")
                preset_label = GAUGE_PRESET_LABELS.get(preset_id, preset_id) if preset_id else ""
                text = f"{sk} -> {preset_label}" if preset_label else sk
            self.designer_theme_gauge_style_combo.addItem(text, sk)

    def _sync_designer_theme_gauge_from_model(self) -> None:
        if self.theme_doc_model is None:
            return
        meta = self.theme_doc_model.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        style = str(meta.get("gauge_style", "")).strip().lower()
        self._designer_updating = True
        try:
            idx = self.designer_theme_gauge_style_combo.findData(style)
            self.designer_theme_gauge_style_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._designer_updating = False

    def _on_designer_theme_gauge_style_changed(self, _idx: int) -> None:
        if self._designer_updating or self.theme_doc_model is None:
            return
        data = self.designer_theme_gauge_style_combo.currentData()
        style = str(data).strip() if data is not None else ""
        meta = self.theme_doc_model.setdefault("meta", {})
        if not isinstance(meta, dict):
            meta = {}
            self.theme_doc_model["meta"] = meta
        if style:
            meta["gauge_style"] = style
        else:
            meta.pop("gauge_style", None)
        self.write_designer_to_json()
        self.schedule_preview_theme_doc()

    def _repair_gauge_stat_dimensions(self, item: dict[str, Any]) -> bool:
        bw = int(item.get("box_width", 1))
        bh = int(item.get("box_height", 1))
        changed = False
        if min(bw, bh) < 48:
            item["box_width"] = max(160, bw)
            item["box_height"] = max(160, bh)
            changed = True
        cap = min(int(item.get("box_width", 160)), int(item.get("box_height", 160)))
        if item.get("gauge_ring_size") is None:
            item["gauge_ring_size"] = max(48, cap - 12)
            changed = True
        else:
            grs = int(item["gauge_ring_size"])
            if grs > cap:
                item["gauge_ring_size"] = max(40, cap)
                changed = True
        return changed

    def _clear_stat_gauge_fields(self) -> None:
        self.designer_stat_gauge_preset_combo.setCurrentIndex(0)
        self.designer_gauge_low_edit.clear()
        self.designer_gauge_mid_edit.clear()
        self.designer_gauge_high_edit.clear()
        self.designer_gauge_smooth_spin.setValue(0.32)
        self.designer_gauge_match_value_chk.setChecked(True)
        self.designer_gauge_ring_spin.setValue(160)
        self.designer_gauge_value_layout_combo.setCurrentIndex(0)
        self.designer_gauge_inner_alpha_spin.setValue(1.0)

    def _clear_stat_sparkline_fields(self) -> None:
        self.designer_sparkline_points_spin.setValue(42)
        self.designer_sparkline_fill_opacity_spin.setValue(0.18)
        self.designer_sparkline_show_points_chk.setChecked(True)

    def _clear_stat_equalizer_fields(self) -> None:
        self.designer_equalizer_bars_spin.setValue(18)
        self.designer_equalizer_gap_spin.setValue(4)
        self.designer_equalizer_mirror_chk.setChecked(False)

    def _load_widget_style_fields(self, item: dict[str, Any] | None) -> None:
        if item is None or str(item.get("kind", "")).strip().lower() not in {"weather_current", "weather_forecast_7d", "media_now_playing"}:
            return
        settings = item.get("settings", {}) if isinstance(item.get("settings", {}), dict) else {}
        kind = str(item.get("kind", "")).strip().lower()
        self._designer_updating = True
        try:
            if kind.startswith("weather_"):
                self.weather_widget_title_font_spin.setValue(int(settings.get("location_font_size", settings.get("day_font_size", 18))))
                self.weather_widget_body_font_spin.setValue(int(settings.get("temp_font_size", settings.get("temp_max_font_size", 38))))
                self.weather_widget_detail_font_spin.setValue(int(settings.get("detail_font_size", settings.get("condition_font_size", 18))))
                self.weather_widget_title_color_edit.setText(json.dumps(settings.get("location_color", settings.get("day_color", [235, 246, 255])), ensure_ascii=False))
                self.weather_widget_body_color_edit.setText(json.dumps(settings.get("temp_color", settings.get("temp_max_color", [246, 231, 152])), ensure_ascii=False))
                self.weather_widget_detail_color_edit.setText(json.dumps(settings.get("detail_color", settings.get("condition_color", [210, 224, 240])), ensure_ascii=False))
                self.weather_widget_panel_color_edit.setText(json.dumps(settings.get("panel_fill", [8, 14, 24, 205]), ensure_ascii=False))
                panel_fill = settings.get("panel_fill", [8, 14, 24, 205])
                panel_alpha = panel_fill[3] if isinstance(panel_fill, list) and len(panel_fill) > 3 else 255
                self.weather_widget_transparent_bg_chk.setChecked(not bool(settings.get("panel_enabled", panel_alpha > 0)))
                self.weather_widget_animate_icons_chk.setChecked(bool(settings.get("animate_icons", True)))
            elif kind == "media_now_playing":
                style = str(item.get("style", "standard")).strip().lower()
                self.widget_title_font_spin.setValue(int(settings.get("title_font_size", 32 if style == "hero" else 20 if style == "mini" else 28)))
                self.widget_body_font_spin.setValue(int(settings.get("artist_font_size", 24 if style == "hero" else 16 if style == "mini" else 22)))
                self.widget_detail_font_spin.setValue(int(settings.get("detail_font_size", 18)))
                self.widget_title_color_edit.setText(json.dumps(settings.get("title_color", [244, 248, 255]), ensure_ascii=False))
                self.widget_body_color_edit.setText(json.dumps(settings.get("artist_color", [210, 224, 240]), ensure_ascii=False))
                self.widget_detail_color_edit.setText(json.dumps(settings.get("detail_color", [160, 196, 232]), ensure_ascii=False))
                self.widget_panel_color_edit.setText(json.dumps(settings.get("panel_fill", [8, 14, 24, 210]), ensure_ascii=False))
                self.widget_cover_enabled_chk.setChecked(bool(settings.get("cover_enabled", True)))
                self.widget_backdrop_enabled_chk.setChecked(bool(settings.get("backdrop_enabled", True)))
                self.widget_title_marquee_chk.setChecked(bool(settings.get("title_marquee", True)))
                self.widget_equalizer_enabled_chk.setChecked(bool(settings.get("equalizer_enabled", True)))
        finally:
            self._designer_updating = False

    def _apply_widget_style_fields(self, item: dict[str, Any]) -> None:
        kind = str(item.get("kind", "")).strip().lower()
        settings = item.setdefault("settings", {})
        if not isinstance(settings, dict):
            settings = {}
            item["settings"] = settings
        if kind.startswith("weather_"):
            settings["panel_fill"] = self._parse_color_line(self.weather_widget_panel_color_edit.text(), settings.get("panel_fill", [8, 14, 24, 205]))
            settings["panel_enabled"] = not bool(self.weather_widget_transparent_bg_chk.isChecked())
            settings["animate_icons"] = bool(self.weather_widget_animate_icons_chk.isChecked())
            if kind == "weather_forecast_7d":
                settings["location_font_size"] = int(self.weather_widget_title_font_spin.value())
                settings["day_font_size"] = int(self.weather_widget_title_font_spin.value())
                settings["temp_max_font_size"] = int(self.weather_widget_body_font_spin.value())
                settings["temp_min_font_size"] = max(6, int(self.weather_widget_body_font_spin.value() * 0.76))
                settings["condition_font_size"] = int(self.weather_widget_detail_font_spin.value())
                settings["location_color"] = self._parse_color_line(self.weather_widget_title_color_edit.text(), settings.get("location_color", [235, 246, 255]))
                settings["day_color"] = self._parse_color_line(self.weather_widget_title_color_edit.text(), settings.get("day_color", [160, 196, 232]))
                settings["temp_max_color"] = self._parse_color_line(self.weather_widget_body_color_edit.text(), settings.get("temp_max_color", [246, 231, 152]))
                settings["temp_min_color"] = self._parse_color_line(self.weather_widget_detail_color_edit.text(), settings.get("temp_min_color", [180, 206, 232]))
                settings["condition_color"] = self._parse_color_line(self.weather_widget_detail_color_edit.text(), settings.get("condition_color", [210, 224, 240]))
            else:
                settings["location_font_size"] = int(self.weather_widget_title_font_spin.value())
                settings["temp_font_size"] = int(self.weather_widget_body_font_spin.value())
                settings["condition_font_size"] = int(self.weather_widget_detail_font_spin.value())
                settings["detail_font_size"] = int(self.weather_widget_detail_font_spin.value())
                settings["location_color"] = self._parse_color_line(self.weather_widget_title_color_edit.text(), settings.get("location_color", [235, 246, 255]))
                settings["temp_color"] = self._parse_color_line(self.weather_widget_body_color_edit.text(), settings.get("temp_color", [246, 231, 152]))
                settings["condition_color"] = self._parse_color_line(self.weather_widget_detail_color_edit.text(), settings.get("condition_color", [210, 224, 240]))
                settings["detail_color"] = self._parse_color_line(self.weather_widget_detail_color_edit.text(), settings.get("detail_color", [210, 224, 240]))
        elif kind == "media_now_playing":
            settings["title_font_size"] = int(self.widget_title_font_spin.value())
            settings["artist_font_size"] = int(self.widget_body_font_spin.value())
            settings["detail_font_size"] = int(self.widget_detail_font_spin.value())
            settings["title_color"] = self._parse_color_line(self.widget_title_color_edit.text(), settings.get("title_color", [244, 248, 255]))
            settings["artist_color"] = self._parse_color_line(self.widget_body_color_edit.text(), settings.get("artist_color", [210, 224, 240]))
            settings["detail_color"] = self._parse_color_line(self.widget_detail_color_edit.text(), settings.get("detail_color", [160, 196, 232]))
            settings["panel_fill"] = self._parse_color_line(self.widget_panel_color_edit.text(), settings.get("panel_fill", [8, 14, 24, 210]))
            settings["cover_enabled"] = bool(self.widget_cover_enabled_chk.isChecked())
            settings["backdrop_enabled"] = bool(self.widget_backdrop_enabled_chk.isChecked())
            settings["title_marquee"] = bool(self.widget_title_marquee_chk.isChecked())
            settings["equalizer_enabled"] = bool(self.widget_equalizer_enabled_chk.isChecked())
            settings["cover_placeholder_enabled"] = True

    def _update_gauge_stat_inspector_visibility(self) -> None:
        gauge_layout = self.inspector_gauge_layout
        gauge_tab_idx = self.inspector_tabs.indexOf(getattr(self, "inspector_gauge", None))
        selected_multi = self._selected_items_multi_any()
        show_gauge = False
        show_sparkline = False
        show_equalizer = False
        if len(selected_multi) == 1:
            coll, _row, sel_item = selected_multi[0]
            if coll == "stats" and sel_item is not None:
                display = str(sel_item.get("display", "text")).strip().lower()
                show_gauge = display == "gauge"
                show_sparkline = display == "sparkline"
                show_equalizer = display == "equalizer"
        if gauge_tab_idx >= 0:
            self.inspector_tabs.setTabVisible(gauge_tab_idx, show_gauge)
        gauge_rows = (
            (self.row_appearance_stroke_width, self.designer_stat_stroke_width_spin),
            (self.row_gauge_ring, self.designer_gauge_ring_spin),
            (self.row_gauge_value_layout, self.designer_gauge_value_layout_combo),
            (self.row_gauge_inner_alpha, self.designer_gauge_inner_alpha_spin),
            (self.row_gauge_preset, self.designer_stat_gauge_preset_combo),
            (self.row_gauge_grad_low, self.designer_gauge_low_row),
            (self.row_gauge_grad_mid, self.designer_gauge_mid_row),
            (self.row_gauge_grad_high, self.designer_gauge_high_row),
            (self.row_gauge_smooth, self.designer_gauge_smooth_spin),
            (self.row_gauge_match_value, self.designer_gauge_match_value_chk),
        )
        for row_label, widget in gauge_rows:
            self._set_form_row_visible(gauge_layout, row_label, widget, show_gauge)
        appearance_layout = self.inspector_appearance_layout
        sparkline_rows = (
            (self.row_sparkline_points, self.designer_sparkline_points_spin),
            (self.row_sparkline_fill_opacity, self.designer_sparkline_fill_opacity_spin),
            (self.row_sparkline_show_points, self.designer_sparkline_show_points_chk),
        )
        for row_label, widget in sparkline_rows:
            self._set_form_row_visible(appearance_layout, row_label, widget, show_sparkline)
        music_layout = self.inspector_music_layout
        equalizer_rows = (
            (self.row_music_equalizer_bars, self.designer_equalizer_bars_spin),
            (self.row_music_equalizer_gap, self.designer_equalizer_gap_spin),
            (self.row_music_equalizer_mirror, self.designer_equalizer_mirror_chk),
        )
        for row_label, widget in equalizer_rows:
            self._set_form_row_visible(music_layout, row_label, widget, show_equalizer)
        self._clamp_designer_splitter_later()

    def _parse_color_line(self, value: str, fallback: list[int]) -> list[int]:
        raw = value.strip()
        if not raw:
            return fallback
        try:
            parsed = json.loads(raw)
        except Exception:
            return fallback
        if isinstance(parsed, list) and len(parsed) in (3, 4):
            out: list[int] = []
            for item in parsed:
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    return fallback
                out.append(max(0, min(255, int(item))))
            return out
        return fallback

    def _motion_tracks(self) -> list[dict[str, Any]]:
        if self.theme_doc_model is None:
            return []
        effects = self.theme_doc_model.setdefault("effects", {})
        tracks = effects.setdefault("motion_tracks", [])
        if not isinstance(tracks, list):
            tracks = []
            effects["motion_tracks"] = tracks
        return tracks

    def _motion_track_for_item(self, item_id: str) -> dict[str, Any] | None:
        for track in self._motion_tracks():
            if isinstance(track, dict) and str(track.get("item_id", "")).strip() == item_id:
                return track
        return None

    def _remove_motion_track_by_id(self, item_id: str) -> None:
        tracks = self._motion_tracks()
        tracks[:] = [track for track in tracks if not (isinstance(track, dict) and str(track.get("item_id", "")).strip() == item_id)]

    def _load_motion_track_fields(self, item: dict[str, Any] | None, collection: str) -> None:
        enabled_types = {"texts", "stats", "images", "panels", "widgets"}
        item_id = "" if item is None else str(item.get("id", "")).strip()
        track = self._motion_track_for_item(item_id) if item_id else None
        base_x = 0 if item is None else int(item.get("x", item.get("rect", [0, 0, 1, 1])[0]))
        base_y = 0 if item is None else int(item.get("y", item.get("rect", [0, 0, 1, 1])[1]))
        base_opacity = 1.0 if item is None else float(item.get("opacity", 1.0))
        self._designer_updating = True
        try:
            self.motion_enabled_chk.setChecked(track is not None)
            self.motion_start_spin.setValue(int(track.get("frame_start", 0)) if track else 0)
            self.motion_end_spin.setValue(int(track.get("frame_end", 30)) if track else 30)
            self.motion_target_x_spin.setValue(int(track.get("x_to", base_x)) if track else base_x)
            self.motion_target_y_spin.setValue(int(track.get("y_to", base_y)) if track else base_y)
            self.motion_target_opacity_spin.setValue(float(track.get("opacity_to", base_opacity)) if track else base_opacity)
        finally:
            self._designer_updating = False
        enabled = item is not None and collection in enabled_types
        for widget in (
            self.motion_enabled_chk,
            self.motion_start_spin,
            self.motion_end_spin,
            self.motion_target_x_spin,
            self.motion_target_y_spin,
            self.motion_target_opacity_spin,
            self.motion_capture_current_btn,
            self.motion_remove_btn,
        ):
            widget.setEnabled(enabled)
        self.motion_remove_btn.setEnabled(enabled and track is not None)

    def on_motion_track_changed(self, *_args: object) -> None:
        if self._designer_updating or self.theme_doc_model is None:
            return
        items, row, item = self._selected_item()
        if item is None:
            return
        collection = self._selected_collection()
        if collection not in {"texts", "stats", "images", "panels", "widgets"}:
            return
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            return
        self.push_designer_history()
        self._remove_motion_track_by_id(item_id)
        if self.motion_enabled_chk.isChecked():
            frame_start = int(self.motion_start_spin.value())
            frame_end = max(frame_start, int(self.motion_end_spin.value()))
            track = {
                "item_id": item_id,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "x_to": int(self.motion_target_x_spin.value()),
                "y_to": int(self.motion_target_y_spin.value()),
                "opacity_to": float(self.motion_target_opacity_spin.value()),
            }
            self._motion_tracks().append(track)
            self.motion_end_spin.setValue(frame_end)
        self.write_designer_to_json()
        self.schedule_preview_theme_doc()

    def capture_motion_target_from_current(self) -> None:
        items, row, item = self._selected_item()
        if item is None:
            return
        current_x = int(item.get("x", item.get("rect", [0, 0, 1, 1])[0]))
        current_y = int(item.get("y", item.get("rect", [0, 0, 1, 1])[1]))
        current_opacity = float(item.get("opacity", 1.0))
        self.motion_target_x_spin.setValue(current_x)
        self.motion_target_y_spin.setValue(current_y)
        self.motion_target_opacity_spin.setValue(current_opacity)
        if not self.motion_enabled_chk.isChecked():
            self.motion_enabled_chk.setChecked(True)

    def remove_motion_track_for_selected(self) -> None:
        items, row, item = self._selected_item()
        if item is None:
            return
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            return
        self.push_designer_history()
        self._remove_motion_track_by_id(item_id)
        self.motion_enabled_chk.setChecked(False)
        self.write_designer_to_json()
        self.schedule_preview_theme_doc()

    def on_designer_field_changed(self, *_args: object) -> None:
        if self._designer_updating or self.theme_doc_model is None:
            return
        selected_multi = self._selected_items_multi_any()
        if len(selected_multi) > 1:
            self.push_designer_history()
            new_visible = bool(self.designer_visible_chk.isChecked())
            new_locked = bool(self.designer_locked_chk.isChecked())
            new_z = int(self.designer_z_spin.value())
            for _collection, _row, selected_item in selected_multi:
                selected_item["visible"] = new_visible
                selected_item["locked"] = new_locked
                selected_item["z_index"] = new_z
            first_collection, first_row, _first_item = selected_multi[0]
            self.write_designer_to_json()
            if first_collection != self._selected_collection():
                combo_index = self.designer_kind_combo.findData(first_collection)
                if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                    self.designer_kind_combo.setCurrentIndex(combo_index)
            for selected_collection, selected_row, _selected_item in selected_multi:
                if selected_collection == self._selected_collection():
                    self._refresh_designer_list_row(selected_row)
            if 0 <= first_row < self.designer_element_list.count() and self.designer_element_list.currentRow() != first_row:
                self.designer_element_list.setCurrentRow(first_row)
            self._update_preview_canvas_overlay()
            self.schedule_preview_theme_doc()
            return
        items, row, item = self._selected_item()
        if item is None:
            return

        self.push_designer_history()
        collection = self._selected_collection()
        item["id"] = self.designer_id_edit.text().strip() or item.get("id", "")
        item["z_index"] = int(self.designer_z_spin.value())
        item["visible"] = bool(self.designer_visible_chk.isChecked())
        item["locked"] = bool(self.designer_locked_chk.isChecked())
        if collection in {"texts", "stats"}:
            item["x"] = self._snap_value(int(self.designer_x_spin.value()))
            item["y"] = self._snap_value(int(self.designer_y_spin.value()))
            item["box_width"] = self._snap_value(int(self.designer_w_spin.value()))
            item["box_height"] = self._snap_value(int(self.designer_h_spin.value()))
            item["font_family"] = self.designer_font_family_combo.currentText()
            item["font_size"] = int(self.designer_font_size_spin.value())
            item["font_bold"] = bool(self.designer_font_bold_chk.isChecked())
            item["font_italic"] = bool(self.designer_font_italic_chk.isChecked())
            item["font_underline"] = bool(self.designer_font_underline_chk.isChecked())
            item["align"] = self.designer_align_combo.currentText()
        if collection == "texts":
            item["text"] = self.designer_text_edit.text()
            item["color"] = self._parse_color_line(self.designer_color_edit.text(), item.get("color", [255, 255, 255]))
        elif collection == "stats":
            min_value = float(self.designer_stat_min_spin.value())
            max_value = float(self.designer_stat_max_spin.value())
            if max_value <= min_value:
                max_value = min_value + 1.0
                self._designer_updating = True
                try:
                    self.designer_stat_max_spin.setValue(max_value)
                finally:
                    self._designer_updating = False
            item["label"] = self.designer_label_edit.text()
            item["source"] = str(self.designer_source_combo.currentData() or self.designer_source_combo.currentText()).strip()
            item["format"] = self.designer_format_edit.text().strip() or "{value}"
            item["display"] = self.designer_stat_display_combo.currentText().strip().lower() or "text"
            if item["display"] == "gauge":
                desired_ring = int(self.designer_gauge_ring_spin.value())
                gw = max(120, self._snap_value(int(self.designer_w_spin.value())))
                gh = max(120, self._snap_value(int(self.designer_h_spin.value())))
                margin = max(12, int(round(min(gw, gh) * 0.06)))
                max_fit = max(40, min(gw, gh) - margin)
                if desired_ring > max_fit:
                    side = desired_ring + margin
                    gw = max(gw, side)
                    gh = max(gh, side)
                item["box_width"] = gw
                item["box_height"] = gh
                item["gauge_ring_size"] = max(40, min(desired_ring, min(gw, gh) - margin))
                item["gauge_value_layout"] = str(self.designer_gauge_value_layout_combo.currentData() or "center")
                item["gauge_inner_alpha"] = float(self.designer_gauge_inner_alpha_spin.value())
                self._designer_updating = True
                try:
                    self.designer_w_spin.setValue(gw)
                    self.designer_h_spin.setValue(gh)
                    self.designer_gauge_ring_spin.setValue(int(item["gauge_ring_size"]))
                finally:
                    self._designer_updating = False
            elif item["display"] == "sparkline":
                sw = max(140, self._snap_value(int(self.designer_w_spin.value())))
                sh = max(54, self._snap_value(int(self.designer_h_spin.value())))
                item["box_width"] = sw
                item["box_height"] = sh
                item["sparkline_points"] = int(self.designer_sparkline_points_spin.value())
                item["sparkline_fill_opacity"] = float(self.designer_sparkline_fill_opacity_spin.value())
                item["sparkline_show_points"] = bool(self.designer_sparkline_show_points_chk.isChecked())
                self._designer_updating = True
                try:
                    self.designer_w_spin.setValue(sw)
                    self.designer_h_spin.setValue(sh)
                finally:
                    self._designer_updating = False
            elif item["display"] == "equalizer":
                ew = max(180, self._snap_value(int(self.designer_w_spin.value())))
                eh = max(52, self._snap_value(int(self.designer_h_spin.value())))
                item["box_width"] = ew
                item["box_height"] = eh
                item["equalizer_bars"] = int(self.designer_equalizer_bars_spin.value())
                item["equalizer_gap"] = int(self.designer_equalizer_gap_spin.value())
                item["equalizer_mirror"] = bool(self.designer_equalizer_mirror_chk.isChecked())
                self._designer_updating = True
                try:
                    self.designer_w_spin.setValue(ew)
                    self.designer_h_spin.setValue(eh)
                finally:
                    self._designer_updating = False
            item["min_value"] = min_value
            item["max_value"] = max_value
            item["show_value_text"] = bool(self.designer_stat_show_value_chk.isChecked())
            item["label_color"] = self._parse_color_line(
                self.designer_label_color_edit.text(),
                item.get("label_color", [220, 220, 220]),
            )
            item["value_color"] = self._parse_color_line(
                self.designer_value_color_edit.text(),
                item.get("value_color", [220, 220, 220]),
            )
            item["track_color"] = self._parse_color_line(
                self.designer_track_color_edit.text(),
                item.get("track_color", [34, 44, 58, 210]),
            )
            item["fill_color"] = self._parse_color_line(
                self.designer_fill_color_edit.text(),
                item.get("fill_color", item.get("value_color", [220, 220, 220])),
            )
            item["stroke_width"] = int(self.designer_stat_stroke_width_spin.value())
            pid = str(self.designer_stat_gauge_preset_combo.currentData() or "").strip()
            if pid:
                item["gauge_preset"] = pid
            else:
                item.pop("gauge_preset", None)
            for gkey, gedit in (
                ("gauge_color_low", self.designer_gauge_low_edit),
                ("gauge_color_mid", self.designer_gauge_mid_edit),
                ("gauge_color_high", self.designer_gauge_high_edit),
            ):
                graw = gedit.text().strip()
                if not graw:
                    item.pop(gkey, None)
                else:
                    item[gkey] = self._parse_color_line(graw, item.get(gkey) or [128, 128, 128])
            item["gauge_smooth"] = float(self.designer_gauge_smooth_spin.value())
            item["gauge_match_value_color"] = bool(self.designer_gauge_match_value_chk.isChecked())
        elif collection == "images":
            item["path"] = self.designer_path_edit.text().strip()
            item["rect"] = [
                self._snap_value(int(self.designer_x_spin.value())),
                self._snap_value(int(self.designer_y_spin.value())),
                self._snap_value(int(self.designer_w_spin.value())),
                self._snap_value(int(self.designer_h_spin.value())),
            ]
            item["fit"] = self.designer_fit_combo.currentText()
            item["opacity"] = float(self.designer_opacity_spin.value())
            item["rotation"] = int(self.designer_rotation_spin.value())
            source = str(item.get("source", "")).strip()
            preview_path = self._current_media_dynamic_path(source) if source in {"media_cover", "media_video_frame"} else item["path"]
            self._set_image_preview_label(self.designer_image_preview_label, preview_path, empty_text=self._empty_image_preview_caption())
        elif collection == "panels":
            item["rect"] = [
                self._snap_value(int(self.designer_x_spin.value())),
                self._snap_value(int(self.designer_y_spin.value())),
                self._snap_value(int(self.designer_w_spin.value())),
                self._snap_value(int(self.designer_h_spin.value())),
            ]
            item["fill"] = self._parse_color_line(self.panel_fill_edit.text(), item.get("fill", [0, 0, 0]))
            item["opacity"] = float(self.panel_opacity_spin.value())
            item["radius"] = int(self.panel_radius_spin.value())
        elif collection == "widgets":
            item["rect"] = [
                self._snap_value(int(self.designer_x_spin.value())),
                self._snap_value(int(self.designer_y_spin.value())),
                self._snap_value(int(self.designer_w_spin.value())),
                self._snap_value(int(self.designer_h_spin.value())),
            ]
            item["opacity"] = float(self.panel_opacity_spin.value())
            self._apply_widget_style_fields(item)

        self._refresh_inspector_music_layout()
        self._refresh_inspector_weather_layout()
        self.write_designer_to_json()
        self._refresh_designer_list_row(row)
        if 0 <= row < self.designer_element_list.count() and self.designer_element_list.currentRow() != row:
            self.designer_element_list.setCurrentRow(row)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def add_designer_element(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        collection = self._selected_collection()
        items = self._current_theme_items()
        self.push_designer_history()
        new_item = self._make_default_element(collection)
        items.append(new_item)
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.designer_element_list.setCurrentRow(len(items) - 1)
        self.schedule_preview_theme_doc()

    def import_image_as_designer_element(self) -> None:
        if not self._image_tools_available():
            QMessageBox.warning(
                self,
                self._tr("Pillow not installed", "Brak Pillow"),
                self._tr(
                    "Image preparation is not available in this environment.",
                    "Moduł przygotowania obrazów nie jest dostępny.",
                ),
            )
            return
        if not self._ensure_theme_doc_model():
            QMessageBox.warning(
                self,
                self._tr("Theme error", "Błąd motywu"),
                self._tr("Load a valid theme in the designer first.", "Najpierw wczytaj poprawny motyw w projektancie."),
            )
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz obraz do motywu",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not chosen:
            return
        source = Path(chosen).expanduser()
        if not source.is_absolute():
            source = (Path.cwd() / source).resolve()
        if not source.exists():
            QMessageBox.warning(
                self,
                self._tr("Missing file", "Brak pliku"),
                self._tr("Image not found:\n{path}", "Nie znaleziono obrazu:\n{path}").format(path=source),
            )
            return
        prepared_path = self._run_theme_image_import(source, asset_kind="image", button_text="Importuj obraz")
        if prepared_path is None:
            return
        prepared = self._theme_display_path(prepared_path)
        combo_index = self.designer_kind_combo.findData("images")
        if combo_index >= 0:
            self.designer_kind_combo.setCurrentIndex(combo_index)
        self.designer_path_edit.setText(prepared)
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        items = self._current_theme_items()
        self.push_designer_history()
        new_item = self._make_default_element("images")
        new_item["path"] = prepared
        new_item["fit"] = "cover"
        canvas = self.theme_doc_model.get("canvas", {}) if self.theme_doc_model is not None else {}
        new_item["rect"] = [
            0,
            0,
            int(canvas.get("width", 1920)),
            int(canvas.get("height", 462)),
        ]
        items.append(new_item)
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.designer_element_list.setCurrentRow(len(items) - 1)
        self.inspector_tabs.setCurrentWidget(self.inspector_image)
        self.preview_info_label.setText(
            "Obraz zaimportowany. Przeciągnij go na preview albo zmień kadr, fit i przezroczystość w zakładce Obraz."
        )
        self.append_log(f"[designer-image-import] {source} -> {prepared_path}")
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def apply_image_rect_preset(self, preset: str) -> None:
        if self.theme_doc_model is None:
            return
        collection = self._selected_collection()
        items, row, item = self._selected_item()
        if item is None or collection != "images":
            QMessageBox.information(self, "Info", "Najpierw wybierz element obrazu.")
            return
        canvas = self.theme_doc_model.get("canvas", {}) if isinstance(self.theme_doc_model, dict) else {}
        canvas_width = int(canvas.get("width", 1920))
        canvas_height = int(canvas.get("height", 462))
        if preset == "fullscreen":
            rect = [0, 0, canvas_width, canvas_height]
            fit = "cover"
        elif preset == "left-half":
            rect = [0, 0, canvas_width // 2, canvas_height]
            fit = "cover"
        elif preset == "right-half":
            rect = [canvas_width // 2, 0, canvas_width - (canvas_width // 2), canvas_height]
            fit = "cover"
        else:
            rect = [0, 0, canvas_width, canvas_height]
            fit = "contain"
        self.push_designer_history()
        item["rect"] = [self._snap_value(int(v)) for v in rect]
        item["fit"] = fit
        self._designer_updating = True
        try:
            self.designer_x_spin.setValue(int(item["rect"][0]))
            self.designer_y_spin.setValue(int(item["rect"][1]))
            self.designer_w_spin.setValue(int(item["rect"][2]))
            self.designer_h_spin.setValue(int(item["rect"][3]))
            self.designer_fit_combo.setCurrentText(fit)
        finally:
            self._designer_updating = False
        self.write_designer_to_json()
        self._refresh_designer_list_row(row)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def clone_designer_element(self) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            QMessageBox.information(self, "Info", "Zaznacz element do duplikacji.")
            return
        self.push_designer_history()
        cloned_entries: list[tuple[str, int]] = []
        by_collection: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for collection, row, item in selected:
            by_collection.setdefault(collection, []).append((row, item))
        for collection, entries in by_collection.items():
            items = self._theme_items_for_collection(collection)
            insert_at = max(row for row, _item in entries) + 1
            clones: list[dict[str, Any]] = []
            for _row, item in entries:
                cloned = deepcopy(item)
                cloned["id"] = f"{str(item.get('id', 'item'))}_copy"
                if "x" in cloned:
                    cloned["x"] = int(cloned["x"]) + 20
                if "y" in cloned:
                    cloned["y"] = int(cloned["y"]) + 20
                if "rect" in cloned and isinstance(cloned["rect"], list) and len(cloned["rect"]) == 4:
                    cloned["rect"][0] = int(cloned["rect"][0]) + 20
                    cloned["rect"][1] = int(cloned["rect"][1]) + 20
                clones.append(cloned)
            for offset, cloned in enumerate(clones):
                items.insert(insert_at + offset, cloned)
                cloned_entries.append((collection, insert_at + offset))
        self._set_designer_selection_group(
            cloned_entries,
            group_label=self._selection_group_label_for_entries(cloned_entries),
        )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.schedule_preview_theme_doc()

    def remove_designer_element(self) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            QMessageBox.information(self, "Info", "Zaznacz element do usunięcia.")
            return
        self.push_designer_history()
        by_collection: dict[str, list[int]] = {}
        for collection, row, _item in selected:
            by_collection.setdefault(collection, []).append(row)
        for collection, rows in by_collection.items():
            items = self._theme_items_for_collection(collection)
            for row in sorted(set(rows), reverse=True):
                if 0 <= row < len(items):
                    items.pop(row)
        self.designer_cross_selection = []
        self._designer_selection_group_label = ""
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def copy_designer_elements(self) -> None:
        selected = self._selected_items_multi_any()
        if not selected:
            QMessageBox.information(self, "Info", "Zaznacz elementy do skopiowania.")
            return
        self.designer_clipboard = [(collection, deepcopy(item)) for collection, _row, item in selected]

    def paste_designer_elements(self) -> None:
        if self.theme_doc_model is None or not self.designer_clipboard:
            QMessageBox.information(self, "Info", "Schowek designera jest pusty.")
            return
        self.push_designer_history()
        pasted_entries: list[tuple[str, int]] = []
        for collection, item in self.designer_clipboard:
            items = self._theme_items_for_collection(collection)
            cloned = deepcopy(item)
            cloned["id"] = f"{str(item.get('id', 'item'))}_paste"
            if "x" in cloned:
                cloned["x"] = int(cloned["x"]) + 24
            if "y" in cloned:
                cloned["y"] = int(cloned["y"]) + 24
            if "rect" in cloned and isinstance(cloned["rect"], list) and len(cloned["rect"]) == 4:
                cloned["rect"][0] = int(cloned["rect"][0]) + 24
                cloned["rect"][1] = int(cloned["rect"][1]) + 24
            items.append(cloned)
            pasted_entries.append((collection, len(items) - 1))
        self._set_designer_selection_group(
            pasted_entries,
            group_label=self._selection_group_label_for_entries(pasted_entries),
        )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.schedule_preview_theme_doc()

    def browse_designer_image_path(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz obraz elementu",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All files (*)",
        )
        if selected:
            source = Path(selected).expanduser()
            if not source.is_absolute():
                source = (Path.cwd() / source).resolve()
            if not self._ensure_theme_doc_model():
                QMessageBox.warning(
                    self,
                    self._tr("Theme error", "Błąd motywu"),
                    self._tr("Load a valid theme in the designer first.", "Najpierw wczytaj poprawny motyw w projektancie."),
                )
                return
            if source.exists() and self._image_tools_available():
                prepared_path = self._run_theme_image_import(source, asset_kind="image", button_text="Importuj obraz")
                if prepared_path is not None:
                    self.designer_path_edit.setText(self._theme_display_path(prepared_path))
            else:
                self.designer_path_edit.setText(self._theme_display_path(source))
            self._set_image_preview_label(self.designer_image_preview_label, self.designer_path_edit.text(), empty_text=self._empty_image_preview_caption())

    def browse_background_path(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz obraz lub wideo tła",
            str(Path.cwd()),
            "Background media (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.webm *.mov *.mkv *.avi *.m4v);;Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;Video (*.mp4 *.webm *.mov *.mkv *.avi *.m4v);;All files (*)",
        )
        if selected:
            source = Path(selected).expanduser()
            if not source.is_absolute():
                source = (Path.cwd() / source).resolve()
            if not self._ensure_theme_doc_model():
                QMessageBox.warning(
                    self,
                    self._tr("Theme error", "Błąd motywu"),
                    self._tr("Load a valid theme in the designer first.", "Najpierw wczytaj poprawny motyw w projektancie."),
                )
                return
            if source.suffix.lower() in VIDEO_BACKGROUND_EXTENSIONS:
                self._start_animation_frame_import([source], mode="replace")
                self.bg_animation_enabled_chk.setChecked(True)
                self.bg_animation_use_bg_chk.setChecked(True)
                self.preview_info_label.setText(self._tr("Importing video background frames...", "Importuję klatki tła wideo..."))
                return
            if source.exists() and self._image_tools_available():
                prepared_path = self._run_theme_image_import(source, asset_kind="background", button_text="Importuj tło")
                if prepared_path is not None:
                    self.bg_path_edit.setText(self._theme_display_path(prepared_path))
                else:
                    return
            else:
                self.bg_path_edit.setText(self._theme_display_path(source))
            self.bg_kind_combo.setCurrentText("image")
            self.bg_fit_combo.setCurrentText("cover")
            self.bg_opacity_spin.setValue(1.0)
            animation = self._current_animation_effect()
            animation["enabled"] = False
            self._refresh_animation_controls()
            self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text=self._empty_background_preview_caption())

    def on_background_field_changed(self, *_args: object) -> None:
        if self._designer_updating or self.theme_doc_model is None:
            return
        self.push_designer_history()
        background = self.theme_doc_model.setdefault("background", {})
        canvas = self.theme_doc_model.setdefault("canvas", {})
        effects = self.theme_doc_model.setdefault("effects", {})
        background["kind"] = self.bg_kind_combo.currentText()
        background["base_color"] = self._parse_color_line(self.bg_base_color_edit.text(), background.get("base_color", [9, 14, 22]))
        background["accent_color"] = self._parse_color_line(self.bg_accent_color_edit.text(), background.get("accent_color", [20, 34, 48]))
        background["texture_alpha"] = float(self.bg_texture_alpha_spin.value())
        canvas["rotation"] = int(self.bg_rotation_spin.value())
        background["path"] = self.bg_path_edit.text().strip()
        background["fit"] = self.bg_fit_combo.currentText()
        background["opacity"] = float(self.bg_opacity_spin.value())
        effects["show_grid"] = bool(self.bg_show_grid_chk.isChecked())
        effects["show_safe_area"] = bool(self.bg_show_safe_chk.isChecked())
        animation = effects.setdefault("animation", {})
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        if len(frame_durations) < len(frame_paths):
            frame_durations.extend([max(1, int(round(1000.0 / max(1.0, float(self.bg_animation_fps_spin.value())))))] * (len(frame_paths) - len(frame_durations)))
        animation["enabled"] = bool(self.bg_animation_enabled_chk.isChecked()) and bool(frame_paths)
        animation["use_as_background"] = bool(self.bg_animation_use_bg_chk.isChecked())
        animation["fps"] = float(self.bg_animation_fps_spin.value())
        animation["current_frame"] = min(max(0, int(self.bg_animation_frame_spin.value())), max(0, len(frame_paths) - 1))
        if frame_paths and 0 <= int(animation["current_frame"]) < len(frame_durations):
            frame_durations[int(animation["current_frame"])] = int(self.bg_animation_duration_spin.value())
        animation["loop"] = bool(animation.get("loop", True))
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations[: len(frame_paths)]
        items, _row, item = self._selected_item()
        if self._selected_collection() == "panels" and item is not None:
            item["fill"] = self._parse_color_line(self.panel_fill_edit.text(), item.get("fill", [0, 0, 0]))
            item["opacity"] = float(self.panel_opacity_spin.value())
            item["radius"] = int(self.panel_radius_spin.value())
        self.write_designer_to_json()
        self._refresh_animation_frame_list()
        self._update_animation_preview_timer()
        self._update_preview_canvas_overlay()
        preview_path = ""
        if not preview_path and bool(animation.get("enabled", False)) and bool(animation.get("use_as_background", True)):
            preview_path = self._current_animation_preview_path()
        if not preview_path:
            preview_path = background.get("path", "")
        self._set_image_preview_label(self.background_preview_label, str(preview_path), empty_text=self._empty_background_preview_caption())
        self.schedule_preview_theme_doc()

    def select_designer_element_from_canvas(self, collection: str, index: int) -> None:
        self._set_designer_selection_group([(collection, index)], group_label="")
        combo_index = self.designer_kind_combo.findData(collection)
        if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
            self.designer_kind_combo.setCurrentIndex(combo_index)
        if 0 <= index < self.designer_element_list.count():
            self.designer_element_list.blockSignals(True)
            self.designer_element_list.clearSelection()
            self.designer_element_list.setCurrentRow(index)
            item = self.designer_element_list.item(index)
            if item is not None:
                item.setSelected(True)
            self.designer_element_list.blockSignals(False)
        self.update_layer_row_visuals()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def select_multiple_designer_elements_from_canvas(self, elements: object) -> None:
        if not isinstance(elements, list) or not elements:
            return
        normalized = self._normalize_designer_selection(
            [
                (str(collection), int(index))
                for collection, index in elements
                if isinstance(collection, str) and isinstance(index, int)
            ]
        )
        if not normalized:
            first = elements[0]
            if (
                isinstance(first, tuple)
                and len(first) == 2
                and isinstance(first[0], str)
                and isinstance(first[1], int)
            ):
                self.select_designer_element_from_canvas(str(first[0]), int(first[1]))
            return
        self._set_designer_selection_group(
            normalized,
            group_label=self._selection_group_label_for_entries(normalized),
        )
        current_collection = self._selected_collection()
        filtered = [index for collection, index in normalized if collection == current_collection]
        if not filtered:
            target_collection, _target_row = normalized[0]
            combo_index = self.designer_kind_combo.findData(target_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
            current_collection = target_collection
            filtered = [index for collection, index in normalized if collection == current_collection]
        self.designer_element_list.blockSignals(True)
        self.designer_element_list.clearSelection()
        first_row = filtered[0]
        for row in filtered:
            item = self.designer_element_list.item(row)
            if item is not None:
                item.setSelected(True)
        self.designer_element_list.setCurrentRow(first_row)
        self.designer_element_list.blockSignals(False)
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()

    def move_designer_element(self, collection: str, index: int, x: int, y: int) -> None:
        if self.theme_doc_model is None:
            return
        items = self._theme_items_for_collection(collection)
        if not isinstance(items, list) or index < 0 or index >= len(items):
            return
        item = items[index]
        if bool(item.get("locked", False)):
            return
        selected = self._selected_items_multi_any()
        selected_keys = {(selected_collection, selected_row) for selected_collection, selected_row, _selected_item in selected}
        if len(selected) > 1 and (collection, index) in selected_keys:
            current_rect = self._selected_item_rect(item, collection)
            snapped_x, snapped_y, guides = self._apply_canvas_element_snap(
                int(x),
                int(y),
                int(current_rect[2]),
                int(current_rect[3]),
                collection,
                index,
            )
            delta_x = int(snapped_x) - int(current_rect[0])
            delta_y = int(snapped_y) - int(current_rect[1])
            if delta_x or delta_y:
                for selected_collection, _row, selected_item in selected:
                    if bool(selected_item.get("locked", False)):
                        continue
                    if selected_collection in {"images", "panels", "widgets"}:
                        rect = selected_item.get("rect", [0, 0, 1, 1])
                        if isinstance(rect, list) and len(rect) == 4:
                            selected_item["rect"] = [
                                self._snap_value(int(rect[0]) + delta_x),
                                self._snap_value(int(rect[1]) + delta_y),
                                int(rect[2]),
                                int(rect[3]),
                            ]
                    else:
                        selected_item["x"] = self._snap_value(int(selected_item.get("x", 0)) + delta_x)
                        selected_item["y"] = self._snap_value(int(selected_item.get("y", 0)) + delta_y)
            self.preview_label.set_temporary_guides(guides, f"Δx {delta_x:+d}  Δy {delta_y:+d}")
            self._sync_drag_editor_state(collection, index)
            return
        if collection in {"images", "panels", "widgets"}:
            rect = item.get("rect", [0, 0, 1, 1])
            if isinstance(rect, list) and len(rect) == 4:
                snapped_x, snapped_y, guides = self._apply_canvas_element_snap(
                    int(x),
                    int(y),
                    int(rect[2]),
                    int(rect[3]),
                    collection,
                    index,
                )
                item["rect"] = [self._snap_value(int(snapped_x)), self._snap_value(int(snapped_y)), int(rect[2]), int(rect[3])]
                self.preview_label.set_temporary_guides(
                    guides,
                    f"Δx {int(item['rect'][0]) - int(rect[0]):+d}  Δy {int(item['rect'][1]) - int(rect[1]):+d}",
                )
        else:
            current_rect = self._selected_item_rect(item, collection)
            snapped_x, snapped_y, guides = self._apply_canvas_element_snap(
                int(x),
                int(y),
                int(current_rect[2]),
                int(current_rect[3]),
                collection,
                index,
            )
            item["x"] = self._snap_value(int(snapped_x))
            item["y"] = self._snap_value(int(snapped_y))
            self.preview_label.set_temporary_guides(
                guides,
                f"Δx {int(item['x']) - int(current_rect[0]):+d}  Δy {int(item['y']) - int(current_rect[1]):+d}",
            )
        self._sync_drag_editor_state(collection, index)

    def apply_geometry_rect_preset(self, preset: str) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            QMessageBox.information(self, "Info", self._tr("Select one or more elements first.", "Najpierw zaznacz jeden lub więcej elementów."))
            return
        editable = [(collection, row, item) for collection, row, item in selected if not bool(item.get("locked", False))]
        if not editable:
            return
        canvas = self.theme_doc_model.get("canvas", {}) if isinstance(self.theme_doc_model, dict) else {}
        canvas_width = max(1, int(canvas.get("width", 1920)))
        canvas_height = max(1, int(canvas.get("height", 462)))
        margin_x = 48
        margin_y = 24
        gap_y = 18
        current_bounds = self._selected_group_bounds(editable)
        if current_bounds is None:
            return
        current_x, current_y, current_w, current_h = current_bounds
        if preset == "top":
            next_rect = [margin_x, margin_y, max(1, canvas_width - margin_x * 2), max(1, min(current_h, 82))]
        elif preset == "bottom":
            height = max(1, min(current_h, 92))
            next_rect = [margin_x, max(0, canvas_height - margin_y - height), max(1, canvas_width - margin_x * 2), height]
        elif preset == "left":
            width = max(1, min(max(current_w, 360), (canvas_width // 2) - margin_x - 16))
            next_rect = [margin_x, margin_y + gap_y, width, max(1, canvas_height - (margin_y + gap_y) * 2)]
        elif preset == "right":
            width = max(1, min(max(current_w, 360), (canvas_width // 2) - margin_x - 16))
            next_rect = [max(0, canvas_width - margin_x - width), margin_y + gap_y, width, max(1, canvas_height - (margin_y + gap_y) * 2)]
        else:
            width = max(1, min(max(current_w, 520), canvas_width - margin_x * 2))
            height = max(1, min(max(current_h, 150), canvas_height - margin_y * 2))
            next_rect = [(canvas_width - width) // 2, (canvas_height - height) // 2, width, height]
        self.push_designer_history()
        x, y, width, height = [self._snap_value(int(v)) for v in next_rect]
        width = max(1, width)
        height = max(1, height)
        scale_x = width / max(1, current_w)
        scale_y = height / max(1, current_h)
        for collection, _row, item in editable:
            item_x, item_y, item_w, item_h = self._selected_item_rect(item, collection)
            rel_x = item_x - current_x
            rel_y = item_y - current_y
            next_item_rect = (
                x + int(round(rel_x * scale_x)),
                y + int(round(rel_y * scale_y)),
                max(1, int(round(item_w * scale_x))),
                max(1, int(round(item_h * scale_y))),
            )
            self._apply_item_rect(collection, item, next_item_rect)
        first_collection, first_row, _first_item = selected[0]
        self._designer_updating = True
        try:
            self.designer_x_spin.setValue(x)
            self.designer_y_spin.setValue(y)
            self.designer_w_spin.setValue(width)
            self.designer_h_spin.setValue(height)
        finally:
            self._designer_updating = False
        self.write_designer_to_json()
        if len(selected) == 1:
            self._refresh_designer_list_row(first_row)
        else:
            self.refresh_designer_element_list()
            self._set_designer_selection_group(
                [(collection, row) for collection, row, _item in selected],
                group_label=self._selection_group_label_for_entries([(collection, row) for collection, row, _item in selected]),
            )
        if first_collection != self._selected_collection():
            combo_index = self.designer_kind_combo.findData(first_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
        if 0 <= first_row < self.designer_element_list.count():
            self.designer_element_list.setCurrentRow(first_row)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def resize_designer_element(self, collection: str, index: int, x: int, y: int, width: int, height: int) -> None:
        if self.theme_doc_model is None:
            return
        if collection == "panels":
            items = self.theme_doc_model.get("background", {}).get("panels", [])
        else:
            items = self.theme_doc_model.get(collection, [])
        if not isinstance(items, list) or index < 0 or index >= len(items):
            return
        item = items[index]
        if bool(item.get("locked", False)):
            return
        if collection in {"images", "panels", "widgets"}:
            item["rect"] = [
                self._snap_value(int(x)),
                self._snap_value(int(y)),
                max(1, self._snap_value(int(width))),
                max(1, self._snap_value(int(height))),
            ]
        else:
            item["x"] = self._snap_value(int(x))
            item["y"] = self._snap_value(int(y))
            item["box_width"] = max(1, self._snap_value(int(width)))
            item["box_height"] = max(1, self._snap_value(int(height)))
        self._sync_drag_editor_state(collection, index)

    def _sync_drag_editor_state(self, collection: str, index: int) -> None:
        combo_index = self.designer_kind_combo.findData(collection)
        if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
            self.designer_kind_combo.setCurrentIndex(combo_index)
        if 0 <= index < self.designer_element_list.count() and self.designer_element_list.currentRow() != index:
            self.designer_element_list.setCurrentRow(index)
        items = self._current_theme_items()
        if not (0 <= index < len(items)):
            return
        item = items[index]
        rect = self._selected_item_rect(item, collection)
        self._designer_updating = True
        try:
            self.designer_x_spin.setValue(int(rect[0]))
            self.designer_y_spin.setValue(int(rect[1]))
            self.designer_w_spin.setValue(int(rect[2]))
            self.designer_h_spin.setValue(int(rect[3]))
            if collection == "images":
                self.designer_opacity_spin.setValue(float(item.get("opacity", 1.0)))
                self.designer_rotation_spin.setValue(int(item.get("rotation", 0)))
            elif collection == "texts":
                self.designer_text_edit.setText(str(item.get("text", "")))
            elif collection == "stats":
                self.designer_label_edit.setText(str(item.get("label", "")))
        finally:
            self._designer_updating = False
        self._update_preview_canvas_overlay()

    def finish_designer_drag(self) -> None:
        if self.theme_doc_model is None:
            self._designer_drag_active = False
            return
        self._designer_drag_active = False
        self.write_designer_to_json()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def raise_designer_layer(self) -> None:
        self._adjust_designer_layer(1)

    def lower_designer_layer(self) -> None:
        self._adjust_designer_layer(-1)

    def move_designer_layer_to_edge(self, edge: str) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        all_items = self._all_canvas_elements()
        if not all_items:
            return
        self.push_designer_history()
        first_collection, first_row, _first_item = selected[0]
        z_values = [int(entry.get("z_index", 0)) for entry in all_items]
        if str(edge).strip().lower() == "back":
            next_z = min(z_values) - len(selected)
            for collection, row, item in selected:
                item["z_index"] = next_z
                next_z += 1
        else:
            next_z = max(z_values) + 1
            for collection, row, item in selected:
                item["z_index"] = next_z
                next_z += 1
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        if first_collection != self._selected_collection():
            combo_index = self.designer_kind_combo.findData(first_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
        self._set_designer_selection_group(
            [(collection, row) for collection, row, _item in selected],
            group_label=self._selection_group_label_for_entries([(collection, row) for collection, row, _item in selected]),
        )
        if 0 <= first_row < self.designer_element_list.count():
            self.designer_element_list.setCurrentRow(first_row)
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def _adjust_designer_layer(self, delta: int) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        self.push_designer_history()
        first_collection, first_row, _first_item = selected[0]
        for _collection, _row, item in selected:
            item["z_index"] = int(item.get("z_index", 0)) + int(delta)
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        if first_collection != self._selected_collection():
            combo_index = self.designer_kind_combo.findData(first_collection)
            if combo_index >= 0 and combo_index != self.designer_kind_combo.currentIndex():
                self.designer_kind_combo.setCurrentIndex(combo_index)
        if 0 <= first_row < self.designer_element_list.count():
            self.designer_element_list.setCurrentRow(first_row)
        self.schedule_preview_theme_doc()

    def move_selected_element_to_preview_point(self, x: int, y: int) -> None:
        if self.theme_doc_model is None:
            return
        selected = self._selected_items_multi_any()
        if not selected:
            return
        self.push_designer_history()
        first_collection, _first_row, first_item = selected[0]
        if bool(first_item.get("locked", False)):
            return
        first_rect = self._selected_item_rect(first_item, first_collection)
        delta_x = self._snap_value(x) - int(first_rect[0])
        delta_y = self._snap_value(y) - int(first_rect[1])
        for selected_collection, _row, item in selected:
            if bool(item.get("locked", False)):
                continue
            if selected_collection in {"images", "panels", "widgets"}:
                rect = item.get("rect", [0, 0, 1, 1])
                item["rect"] = [
                    self._snap_value(int(rect[0]) + delta_x),
                    self._snap_value(int(rect[1]) + delta_y),
                    int(rect[2]),
                    int(rect[3]),
                ]
            else:
                item["x"] = self._snap_value(int(item.get("x", 0)) + delta_x)
                item["y"] = self._snap_value(int(item.get("y", 0)) + delta_y)
        self.write_designer_to_json()
        self.load_selected_designer_item()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def _current_layout_snapshot(self) -> dict[str, Any]:
        if self.theme_doc_model is None:
            return {}
        data = self.theme_doc_model
        return {
            "canvas": {"rotation": int(data.get("canvas", {}).get("rotation", 180))},
            "background": {
                "kind": str(data.get("background", {}).get("kind", "generated")),
                "base_color": deepcopy(data.get("background", {}).get("base_color", [9, 14, 22])),
                "accent_color": deepcopy(data.get("background", {}).get("accent_color", [20, 34, 48])),
                "texture_alpha": float(data.get("background", {}).get("texture_alpha", 0.4)),
                "path": str(data.get("background", {}).get("path", "")),
                "fit": str(data.get("background", {}).get("fit", "cover")),
                "opacity": float(data.get("background", {}).get("opacity", 1.0)),
                "panels": deepcopy(data.get("background", {}).get("panels", [])),
            },
            "effects": deepcopy(data.get("effects", {})),
            "texts": [
                {
                    "id": item.get("id"),
                    "x": item.get("x"),
                    "y": item.get("y"),
                    "box_width": item.get("box_width"),
                    "box_height": item.get("box_height"),
                    "z_index": item.get("z_index"),
                }
                for item in data.get("texts", [])
            ],
            "stats": [
                {
                    "id": item.get("id"),
                    "x": item.get("x"),
                    "y": item.get("y"),
                    "box_width": item.get("box_width"),
                    "box_height": item.get("box_height"),
                    "z_index": item.get("z_index"),
                }
                for item in data.get("stats", [])
            ],
            "images": [
                {
                    "id": item.get("id"),
                    "rect": deepcopy(item.get("rect")),
                    "z_index": item.get("z_index"),
                }
                for item in data.get("images", [])
            ],
            "widgets": [
                {
                    "id": item.get("id"),
                    "rect": deepcopy(item.get("rect")),
                    "z_index": item.get("z_index"),
                }
                for item in data.get("widgets", [])
            ],
        }

    def _apply_layout_snapshot(self, snapshot: dict[str, Any]) -> None:
        if self.theme_doc_model is None:
            return
        data = self.theme_doc_model
        if "canvas" in snapshot and isinstance(snapshot["canvas"], dict):
            data.setdefault("canvas", {}).update(snapshot["canvas"])
        if "background" in snapshot and isinstance(snapshot["background"], dict):
            bg = data.setdefault("background", {})
            for key in ("kind", "base_color", "accent_color", "texture_alpha", "path", "fit", "opacity", "panels"):
                if key in snapshot["background"]:
                    bg[key] = deepcopy(snapshot["background"][key])
        if "effects" in snapshot and isinstance(snapshot["effects"], dict):
            data.setdefault("effects", {}).update(snapshot["effects"])
        for collection in ("texts", "stats", "images", "widgets"):
            items = data.get(collection, [])
            by_id = {str(item.get("id", "")): item for item in items if isinstance(item, dict)}
            for snap_item in snapshot.get(collection, []):
                if not isinstance(snap_item, dict):
                    continue
                target = by_id.get(str(snap_item.get("id", "")))
                if target is None:
                    continue
                for key, value in snap_item.items():
                    if key != "id":
                        target[key] = deepcopy(value)
        self._load_background_fields()
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self.schedule_preview_theme_doc()

    def _load_layout_presets(self) -> None:
        self.layout_presets = {}
        try:
            if LAYOUT_PRESETS_PATH.exists():
                raw = json.loads(LAYOUT_PRESETS_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.layout_presets = raw
        except Exception:
            self.layout_presets = {}
        self.layout_preset_combo.clear()
        self.layout_preset_combo.addItems(sorted(self.layout_presets.keys()))

    def _save_layout_presets_file(self) -> None:
        LAYOUT_PRESETS_PATH.write_text(json.dumps(self.layout_presets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.layout_preset_combo.clear()
        self.layout_preset_combo.addItems(sorted(self.layout_presets.keys()))

    def save_layout_preset(self) -> None:
        if self.theme_doc_model is None:
            return
        name = self.layout_preset_name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Info", "Podaj nazwę presetu.")
            return
        self.layout_presets[name] = self._current_layout_snapshot()
        self._save_layout_presets_file()
        self.layout_preset_combo.setCurrentText(name)

    def load_layout_preset(self) -> None:
        name = self.layout_preset_combo.currentText().strip()
        if not name:
            QMessageBox.information(self, "Info", "Wybierz preset.")
            return
        snapshot = self.layout_presets.get(name)
        if not isinstance(snapshot, dict):
            QMessageBox.information(self, "Info", "Preset nie istnieje.")
            return
        self._apply_layout_snapshot(snapshot)

    def delete_layout_preset(self) -> None:
        name = self.layout_preset_combo.currentText().strip()
        if not name:
            return
        self.layout_presets.pop(name, None)
        self._save_layout_presets_file()

    def apply_builtin_layout_preset(self, preset_name: str) -> None:
        if self.theme_doc_model is None:
            document = self._parse_theme_doc_editor()
            if document is None:
                return
            try:
                self.theme_doc_model = normalize_theme_document(document)
            except Exception as exc:
                QMessageBox.warning(self, self._tr("Theme error", "Błąd motywu"), str(exc))
                return

        model = deepcopy(self.theme_doc_model)
        panels = model.setdefault("background", {}).setdefault("panels", [])
        texts = model.setdefault("texts", [])
        stats = model.setdefault("stats", [])
        images = model.setdefault("images", [])

        def set_box(item: dict[str, Any], x: int, y: int, w: int, h: int, align: str = "left") -> None:
            item["x"] = x
            item["y"] = y
            item["box_width"] = w
            item["box_height"] = h
            item["align"] = align

        if preset_name == "dashboard":
            model["background"]["base_color"] = [9, 14, 22]
            model["background"]["accent_color"] = [20, 34, 48]
            for idx, panel in enumerate(panels[:5]):
                if idx == 0:
                    panel["rect"] = [24, 18, 1872, 56]
                elif idx == 1:
                    panel["rect"] = [24, 90, 540, 210]
                elif idx == 2:
                    panel["rect"] = [584, 90, 540, 210]
                elif idx == 3:
                    panel["rect"] = [1144, 90, 360, 210]
                elif idx == 4:
                    panel["rect"] = [24, 384, 680, 52]
            for idx, item in enumerate(texts[:5]):
                if idx == 0:
                    set_box(item, 42, 22, 480, 42)
                elif idx == 1:
                    set_box(item, 42, 100, 180, 30)
                elif idx == 2:
                    set_box(item, 602, 100, 220, 30)
                elif idx == 3:
                    set_box(item, 1162, 100, 220, 30)
                elif idx == 4:
                    set_box(item, 42, 394, 620, 30)
            stat_positions = [
                (190, 22, 360, 42),
                (1608, 22, 240, 42),
                (42, 140, 230, 34),
                (42, 174, 230, 34),
                (42, 208, 230, 34),
                (602, 140, 250, 34),
                (602, 174, 250, 34),
                (1162, 140, 250, 34),
            ]
            for item, (x, y, w, h) in zip(stats, stat_positions):
                set_box(item, x, y, w, h)
        elif preset_name == "minimal":
            model["background"]["base_color"] = [13, 16, 21]
            model["background"]["accent_color"] = [28, 36, 44]
            for panel in panels:
                panel["visible"] = False
            if panels:
                panels[0]["visible"] = True
                panels[0]["rect"] = [28, 28, 1860, 74]
                panels[0]["fill"] = [0, 0, 0]
            for idx, item in enumerate(texts):
                item["visible"] = idx in {0, 4}
            for idx, item in enumerate(stats):
                item["visible"] = idx < 4
            if texts:
                set_box(texts[0], 42, 40, 520, 40)
            if len(texts) > 4:
                set_box(texts[4], 42, 408, 760, 26)
            minimal_positions = [
                (210, 40, 460, 40),
                (1550, 40, 260, 40),
                (42, 158, 420, 42),
                (42, 208, 420, 42),
            ]
            for item, (x, y, w, h) in zip(stats, minimal_positions):
                set_box(item, x, y, w, h)
        elif preset_name == "focus":
            model["background"]["base_color"] = [8, 12, 18]
            model["background"]["accent_color"] = [38, 84, 104]
            for idx, panel in enumerate(panels[:5]):
                panel["visible"] = True
                if idx == 0:
                    panel["rect"] = [24, 18, 1872, 56]
                elif idx == 1:
                    panel["rect"] = [24, 90, 920, 292]
                elif idx == 2:
                    panel["rect"] = [966, 90, 930, 292]
                else:
                    panel["visible"] = False
            for idx, item in enumerate(texts):
                item["visible"] = idx in {0, 1, 2, 4}
            for idx, item in enumerate(stats):
                item["visible"] = idx < 6
            if texts:
                set_box(texts[0], 42, 22, 420, 42)
            if len(texts) > 1:
                set_box(texts[1], 42, 104, 240, 30)
            if len(texts) > 2:
                set_box(texts[2], 986, 104, 240, 30)
            if len(texts) > 4:
                set_box(texts[4], 42, 418, 760, 26)
            focus_positions = [
                (190, 22, 420, 42),
                (1610, 22, 240, 42),
                (42, 152, 300, 36),
                (42, 196, 300, 36),
                (42, 240, 300, 36),
                (986, 152, 320, 36),
            ]
            for item, (x, y, w, h) in zip(stats, focus_positions):
                set_box(item, x, y, w, h)
            if images:
                images[0]["visible"] = True
                images[0]["rect"] = [1310, 116, 540, 210]
                images[0]["fit"] = "cover"
                images[0]["opacity"] = 0.9

        self.theme_doc_model = normalize_theme_document(model)
        self._load_background_fields()
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self.preview_theme_doc()

    def add_playlist_item(self) -> None:
        name = self.theme_combo.currentText().strip()
        if not name:
            QMessageBox.information(self, "Info", "Wybierz theme do dodania.")
            return
        payload = {
            "name": name,
            "duration_s": float(self.playlist_duration_spin.value()),
        }
        self.api_call("playlist-add", "POST", "/v1/playlist/add", payload, timeout=10.0)

    def remove_playlist_item(self) -> None:
        row = self.playlist_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Zaznacz element playlisty do usunięcia.")
            return
        payload = {"index": int(row)}
        self.api_call("playlist-remove", "POST", "/v1/playlist/remove", payload, timeout=10.0)

    def start_playlist(self) -> None:
        if self.playlist_list.count() == 0:
            QMessageBox.information(self, "Info", "Playlist jest pusta. Dodaj najpierw pozycje.")
            return
        self.api_call("playlist-start", "POST", "/v1/playlist/start", {}, timeout=10.0)

    def stop_playlist(self) -> None:
        self.api_call("playlist-stop", "POST", "/v1/playlist/stop", {}, timeout=10.0)

    def browse_bundle_path(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Wybierz plik bundle",
            str(Path.cwd() / ".trofeo-bundle.json"),
            "JSON (*.json);;All files (*)",
        )
        if selected:
            self.bundle_path_edit.setText(selected)

    def _collect_theme_asset_paths(self, document: dict[str, Any]) -> dict[str, Path]:
        assets: dict[str, Path] = {}
        bg_path = str(document.get("background", {}).get("path", "")).strip()
        if bg_path:
            path = Path(bg_path).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            if path.exists():
                assets["background"] = path
        for idx, item in enumerate(document.get("images", [])):
            if not isinstance(item, dict):
                continue
            raw = str(item.get("path", "")).strip()
            if not raw:
                continue
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            if path.exists():
                assets[f"images/{idx}"] = path
        return assets

    def save_bundle(self) -> None:
        path = self.bundle_path_edit.text().strip()
        if not path:
            QMessageBox.information(self, "Info", "Podaj ścieżkę do pliku bundle.")
            return
        if self.theme_doc_model is None:
            payload = {"path": path}
            self.api_call("bundle-save", "POST", "/v1/bundle/save", payload, timeout=10.0)
            return
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
        document = deepcopy(self.theme_doc_model)
        remapped = deepcopy(document)
        assets_payload: dict[str, dict[str, str]] = {}
        preview_payload: dict[str, str] | None = None
        for key, asset_path in self._collect_theme_asset_paths(document).items():
            assets_payload[key] = {
                "filename": asset_path.name,
                "data_b64": base64.b64encode(asset_path.read_bytes()).decode("ascii"),
            }
            if key == "background":
                remapped.setdefault("background", {})["path"] = f"assets/{asset_path.name}"
            elif key.startswith("images/"):
                index = int(key.split("/", 1)[1])
                if index < len(remapped.get("images", [])):
                    remapped["images"][index]["path"] = f"assets/{asset_path.name}"
        if render_theme_document is not None:
            try:
                preview_image = render_theme_document(
                    ThemeDocument(normalize_theme_document(deepcopy(remapped))),
                    base_dir=Path.cwd(),
                    stats_provider=self._preview_stats_provider,
                )
                preview_image.thumbnail((920, 240))
                buffer = io.BytesIO()
                preview_image.save(buffer, format="PNG")
                preview_payload = {
                    "filename": "preview.png",
                    "data_b64": base64.b64encode(buffer.getvalue()).decode("ascii"),
                }
            except Exception as exc:
                self.append_log(f"[bundle-save] preview-skip: {exc}")
        bundle = {
            "bundle_version": 1,
            "type": "theme-doc-bundle",
            "document": remapped,
            "assets": assets_payload,
            "preview": preview_payload,
            "theme_path": self.theme_doc_path_edit.text().strip(),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(f"[bundle-save] {target}")

    def load_bundle(self) -> None:
        path = self.bundle_path_edit.text().strip()
        if not path:
            QMessageBox.information(self, "Info", "Podaj ścieżkę do pliku bundle.")
            return
        source = Path(path).expanduser()
        if not source.is_absolute():
            source = (Path.cwd() / source).resolve()
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except Exception:
            payload = {"path": path, "merge": bool(self.bundle_merge_chk.isChecked())}
            self.api_call("bundle-load", "POST", "/v1/bundle/load", payload, timeout=10.0)
            return
        if not (isinstance(raw, dict) and raw.get("type") == "theme-doc-bundle" and isinstance(raw.get("document"), dict)):
            payload = {"path": path, "merge": bool(self.bundle_merge_chk.isChecked())}
            self.api_call("bundle-load", "POST", "/v1/bundle/load", payload, timeout=10.0)
            return
        assets_dir = source.parent / f"{source.stem}_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        document = deepcopy(raw["document"])
        for key, asset in raw.get("assets", {}).items():
            if not isinstance(asset, dict):
                continue
            filename = str(asset.get("filename", "asset.bin"))
            data_b64 = str(asset.get("data_b64", ""))
            if not data_b64:
                continue
            out_path = assets_dir / filename
            out_path.write_bytes(base64.b64decode(data_b64.encode("ascii")))
            if key == "background":
                document.setdefault("background", {})["path"] = str(out_path)
            elif key.startswith("images/"):
                index = int(key.split("/", 1)[1])
                if index < len(document.get("images", [])):
                    document["images"][index]["path"] = str(out_path)
        self.theme_doc_model = normalize_theme_document(document)
        self.theme_doc_path_edit.setText(str(source))
        self._load_background_fields()
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self.preview_theme_doc()
        preview_asset = raw.get("preview")
        if isinstance(preview_asset, dict) and preview_asset.get("data_b64"):
            self.append_log("[bundle-load] preview found in bundle")
        self.append_log(f"[bundle-load] {source}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Qt GUI client for Trofeo backend")
    parser.add_argument("--url", default="http://127.0.0.1:18777", help="Backend base URL")
    args = parser.parse_args()

    app = QApplication([])
    app.setApplicationName("Open Trofeo LCD")
    win = TrofeoGui(base_url=args.url)
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
