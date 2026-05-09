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
from urllib.parse import unquote, urlparse

try:
    from PySide6.QtCore import QEasingCurve, QPoint, QRect, QSize, Qt, QTimer, Signal, QPropertyAnimation, QUrl
    from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPen, QPixmap, QTransform
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

from theme_schema import KNOWN_STAT_SOURCES, ThemeDocument, normalize_theme_document, save_theme_document
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
        "title": "Dashboard",
        "description": "Pelny dashboard z sekcjami CPU, pamięci, uptime i wyraźnym podziałem paneli.",
        "path": "themes/dashboard_monitor.json",
        "accent": "#59b7ff",
    },
    {
        "title": "Minimal",
        "description": "Lekki układ z ograniczoną liczbą sekcji i większym naciskiem na czytelność.",
        "path": "themes/minimal_monitor.json",
        "accent": "#8fd878",
    },
    {
        "title": "Focus",
        "description": "Układ z większymi kartami i mocniejszym akcentem na najważniejsze statystyki.",
        "path": "themes/focus_monitor.json",
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
        self._guide_lines: list[tuple[str, int]] = []
        self._movement_badge: str = ""

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

    def set_temporary_guides(self, guides: list[tuple[str, int]], badge: str = "") -> None:
        self._guide_lines = list(guides)
        self._movement_badge = badge
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
        hit = self._hit_test(event.position().toPoint())
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
                self._drag_mode = mode
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
            if self._selection_origin_widget is not None:
                self._selection_current_widget = event.position().toPoint()
                self.update()
            self.cursor_changed.emit(img_pos if (img_pos := self._widget_to_image_point(event.position().toPoint())) is not None else None)
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
        elif self._drag_mode == "resize":
            self._guide_lines = self._compute_snap_guides(start_x, start_y, max(1, start_w + dx), max(1, start_h + dy), collection, index)
            self.element_resized.emit(
                collection,
                index,
                start_x,
                start_y,
                max(1, start_w + dx),
                max(1, start_h + dy),
            )

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
                if self._selected == key:
                    painter.fillRect(self._resize_handle_rect(rect), QColor("#5ec8ff"))
            if self._selection_origin_widget is not None and self._selection_current_widget is not None:
                select_rect = QRect(self._selection_origin_widget, self._selection_current_widget).normalized()
                painter.setPen(QPen(QColor("#89ddff"), 1, Qt.DashLine))
                painter.fillRect(select_rect, QColor(94, 200, 255, 36))
                painter.drawRect(select_rect)
            if self._guide_lines:
                guide_pen = QPen(QColor("#45d0ff"), 1, Qt.DashLine)
                painter.setPen(guide_pen)
                for axis, value in self._guide_lines:
                    if axis == "x":
                        x = self._draw_offset_x + int(round(value * self._draw_width / max(1, self._canvas_size.width())))
                        painter.drawLine(x, self._draw_offset_y, x, self._draw_offset_y + self._draw_height)
                    else:
                        y = self._draw_offset_y + int(round(value * self._draw_height / max(1, self._canvas_size.height())))
                        painter.drawLine(self._draw_offset_x, y, self._draw_offset_x + self._draw_width, y)
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

    def _resize_handle_rect(self, rect: QRect) -> QRect:
        return QRect(rect.right() - 10, rect.bottom() - 10, 16, 16)

    def _hit_test(self, pos: QPoint) -> tuple[str, int, str] | None:
        for item in reversed(self._elements):
            if not bool(item.get("visible", True)):
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            if self._resize_handle_rect(rect).contains(pos):
                return item["collection"], item["index"], "resize"
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
    ) -> list[tuple[str, int]]:
        guides: list[tuple[str, int]] = []
        current_x = {x, x + w // 2, x + w}
        current_y = {y, y + h // 2, y + h}
        safe_left = 24
        safe_right = max(0, self._canvas_size.width() - 24)
        safe_top = 18
        safe_bottom = max(0, self._canvas_size.height() - 18)
        canvas_guides_x = {self._canvas_size.width() // 2, safe_left, safe_right}
        canvas_guides_y = {self._canvas_size.height() // 2, safe_top, safe_bottom}
        for cx in current_x:
            for ox in canvas_guides_x:
                if abs(cx - ox) <= 6:
                    guides.append(("x", ox))
        for cy in current_y:
            for oy in canvas_guides_y:
                if abs(cy - oy) <= 6:
                    guides.append(("y", oy))
        for item in self._elements:
            if item["collection"] == collection and int(item["index"]) == index:
                continue
            if not bool(item.get("visible", True)):
                continue
            rx, ry, rw, rh = item["rect"]
            other_x = {rx, rx + rw // 2, rx + rw}
            other_y = {ry, ry + rh // 2, ry + rh}
            for cx in current_x:
                for ox in other_x:
                    if abs(cx - ox) <= 6:
                        guides.append(("x", ox))
                        break
            for cy in current_y:
                for oy in other_y:
                    if abs(cy - oy) <= 6:
                        guides.append(("y", oy))
                        break
        unique: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for item in guides:
            if item not in seen:
                unique.append(item)
                seen.add(item)
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


class LayerListWidget(QListWidget):
    rows_reordered = Signal()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        super().dropEvent(event)
        self.rows_reordered.emit()


class AnimationTimelineWidget(QWidget):
    frame_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._durations: list[int] = []
        self._current_index = 0
        self.setMinimumHeight(72)

    def set_timeline(self, durations: list[int], current_index: int) -> None:
        self._durations = [max(1, int(item)) for item in durations]
        self._current_index = max(0, min(int(current_index), len(self._durations) - 1)) if self._durations else 0
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not self._durations:
            return
        total = sum(self._durations)
        if total <= 0:
            return
        x = int(event.position().x())
        usable_width = max(1, self.width() - 16)
        cursor = 8
        for idx, duration in enumerate(self._durations):
            width = max(18, int(round(usable_width * duration / total)))
            if cursor <= x <= cursor + width:
                self.frame_selected.emit(idx)
                break
            cursor += width + 4

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.fillRect(self.rect(), QColor("#151b24"))
            if not self._durations:
                painter.setPen(QColor("#7a8797"))
                painter.drawText(self.rect().adjusted(12, 0, -12, 0), Qt.AlignVCenter | Qt.AlignLeft, "Timeline animacji pojawi się po imporcie klatek.")
                return
            total = sum(self._durations)
            usable_width = max(1, self.width() - 16)
            x = 8
            for idx, duration in enumerate(self._durations):
                width = max(18, int(round(usable_width * duration / total)))
                rect = QRect(x, 14, width, 34)
                is_current = idx == self._current_index
                fill = QColor("#2d6df6" if is_current else "#253244")
                border = QColor("#7dd3fc" if is_current else "#42516a")
                painter.setPen(QPen(border, 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 7, 7)
                painter.setPen(QColor("#eef6ff" if is_current else "#c7d2e0"))
                label = f"{idx + 1}"
                if width >= 64:
                    label = f"{idx + 1} · {duration} ms"
                painter.drawText(rect.adjusted(8, 0, -8, 0), Qt.AlignCenter, label)
                x += width + 4
            painter.setPen(QColor("#8fa4bf"))
            painter.drawText(QRect(10, 50, self.width() - 20, 18), Qt.AlignLeft | Qt.AlignVCenter, f"Klatki: {len(self._durations)}  |  Łączny czas: {sum(self._durations)} ms")
        finally:
            painter.end()


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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(18, 18))
        layout.addWidget(icon_label)
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(58, 36)
        self.thumb_label.setStyleSheet("background: #0f1319; border: 1px solid #314055; border-radius: 8px;")
        if thumbnail is not None and not thumbnail.isNull():
            self.thumb_label.setPixmap(thumbnail.scaled(58, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
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
        self.lock_btn = QToolButton()
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(bool(locked))
        self.lock_btn.setText("L" if locked else "E")
        self.lock_btn.setToolTip("Blokuj / Odblokuj")
        layout.addWidget(self.eye_btn)
        layout.addWidget(self.lock_btn)
        self.eye_btn.clicked.connect(self._emit_visibility)
        self.lock_btn.clicked.connect(self._emit_lock)
        self.setMinimumHeight(58)
        self.set_title(title)
        self.set_subtitle(subtitle)
        self.set_thumbnail(thumbnail)
        self.set_locked(bool(locked))
        self.set_selected(False)

    def set_title(self, title: str) -> None:
        badge = ""
        rest = title
        if title.startswith("[") and "]" in title:
            badge, rest = title.split("]", 1)
            badge = badge.lstrip("[")
            rest = rest.strip()
        self.badge_label.setText(badge)
        self._collection = badge
        title_text = rest or title
        self.title_label.setText(self.title_label.fontMetrics().elidedText(title_text, Qt.ElideRight, 220))

    def set_visible_state(self, visible: bool) -> None:
        self.eye_btn.setChecked(bool(visible))
        self.eye_btn.setIcon(self._visible_icon if visible else self._hidden_icon)
        self.eye_btn.setText("")

    def set_subtitle(self, subtitle: str) -> None:
        text = subtitle.strip()
        self.subtitle_label.setVisible(bool(text))
        self.subtitle_label.setText(self.subtitle_label.fontMetrics().elidedText(text, Qt.ElideRight, 220))

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
            self.thumb_label.setPixmap(thumbnail.scaled(58, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
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

    def _emit_visibility(self) -> None:
        self.set_visible_state(self.eye_btn.isChecked())
        self.visibility_toggled.emit()

    def _emit_lock(self) -> None:
        self.set_locked(self.lock_btn.isChecked())
        self.lock_toggled.emit()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.activated.emit(event.modifiers())
        super().mousePressEvent(event)


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

    def __init__(self, base_url: str):
        super().__init__()
        self.setWindowTitle("Open Trofeo LCD")
        self.resize(1680, 1040)
        self.setMinimumSize(1480, 920)
        self._status_in_flight = False
        self.theme_items: dict[str, dict[str, Any]] = {}
        self.theme_doc_model: dict[str, Any] | None = None
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
        self._image_thumbnail_cache: dict[tuple[str, int], QPixmap] = {}
        self._preview_request_in_flight = False
        self._preview_request_queued = False
        self._preview_request_seq = 0
        self._preview_request_active_seq = 0
        self.preview_debounce = QTimer(self)
        self.preview_debounce.setSingleShot(True)
        self.preview_debounce.timeout.connect(self.preview_theme_doc)
        self.autosave_debounce = QTimer(self)
        self.autosave_debounce.setSingleShot(True)
        self.autosave_debounce.timeout.connect(self._write_theme_autosave)
        self.animation_preview_timer = QTimer(self)
        self.animation_preview_timer.timeout.connect(self._advance_animation_preview)
        self._animation_preview_active = False

        self.client = BackendClient(base_url=base_url)
        self._build_ui(base_url)
        self._restore_ui_state()
        self._setup_shortcuts()
        self._setup_tray()
        self.apply_ui_chrome()
        self.api_result.connect(self._on_api_result)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(1500)

        self.refresh_status()
        self.refresh_themes()
        self.refresh_playlist()
        self.refresh_theme_schema()
        self._load_layout_presets()
        self._refresh_template_cards()
        self._rebuild_theme_asset_gallery()
        self.suggest_new_theme_path_from_template()
        restored_autosave = self._restore_theme_autosave()
        if not restored_autosave and Path(self.theme_doc_path_edit.text().strip()).exists():
            self.load_theme_doc()
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
        groups = {
            "🖥️ System": ["hostname", "ip_local", "time_hms", "date_ymd", "uptime_human"],
            "⚙️ CPU": ["cpu_usage_percent", "cpu_core_avg_percent", "cpu_core_max_percent", "cpu_freq_ghz", "cpu_temp_c", "load_average"],
            "🎮 GPU": ["gpu_name", "gpu_temp", "gpu_load", "vram_percent", "vram_used_mb", "vram_total_mb"],
            "🌐 Sieć": ["net_dl_kbps", "net_ul_kbps"],
            "💽 Dysk": ["disk_percent", "disk_used_gb", "disk_total_gb"],
            "🧠 RAM": ["mem_percent", "mem_used_mb", "mem_total_mb"],
            "🎵 Media": ["media_title", "media_artist", "media_app", "media_state"],
        }
        
        for group_name, stats in groups.items():
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
            "media_title": "Now Playing: Title",
            "media_artist": "Now Playing: Artist",
            "media_app": "Now Playing: App",
            "media_state": "Now Playing: State",
        }
        if source in custom:
            return custom[source]
        return source.replace("_", " ").title()

    def _populate_designer_source_combo(self, selected_source: str = "") -> None:
        if not hasattr(self, "designer_source_combo"):
            return
        self.designer_source_combo.blockSignals(True)
        self.designer_source_combo.clear()
        for source in self.theme_stat_sources:
            self.designer_source_combo.addItem(self._humanize_stat_source(source), source)
        if selected_source:
            idx = self.designer_source_combo.findData(selected_source)
            if idx >= 0:
                self.designer_source_combo.setCurrentIndex(idx)
        self.designer_source_combo.blockSignals(False)

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

    def _create_dashboard_status_row(self, label: str, value: str = "-") -> tuple[QWidget, QLabel]:
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
        return frame, current

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

    def _create_system_metric_card(self, title: str, value: str = "-", detail: str = "-") -> tuple[QFrame, QLabel, QLabel]:
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
        return card, value_lbl, detail_lbl

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
        self._save_ui_state()
        self.append_log("[config] Zastosowano ustawienia interfejsu.")

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
        self.nav_system_btn = QPushButton("◉  System")
        self.nav_logs_btn = QPushButton("☰  Logs")
        self.nav_config_btn = QPushButton("⚙  Configuration")
        self._nav_button_meta = {
            self.nav_library_btn: ("🗂", "Theme Gallery"),
            self.nav_designer_btn: ("✎", "Theme Designer"),
            self.nav_system_btn: ("◉", "System"),
            self.nav_logs_btn: ("☰", "Logs"),
            self.nav_config_btn: ("⚙", "Configuration"),
        }
        self._shell_nav_buttons = [
            self.nav_library_btn,
            self.nav_designer_btn,
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
        self.header_donate_btn = QPushButton("Donate / Support")
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
        endpoint_layout = QHBoxLayout(endpoint_box)
        self.url_edit = QLineEdit(base_url)
        self.apply_url_btn = QPushButton("Ustaw URL")
        self.apply_url_btn.clicked.connect(self.apply_url)
        self.refresh_btn = QPushButton("Odśwież status")
        self.refresh_btn.clicked.connect(self.refresh_status)
        endpoint_layout.addWidget(QLabel("URL:"))
        endpoint_layout.addWidget(self.url_edit, 1)
        endpoint_layout.addWidget(self.apply_url_btn)
        endpoint_layout.addWidget(self.refresh_btn)
        runtime_layout.addWidget(endpoint_box)

        control_box = QGroupBox("Kontrola Urządzenia")
        control_layout = QHBoxLayout(control_box)
        control_layout.setContentsMargins(16, 20, 16, 16)
        control_layout.setSpacing(12)
        
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setObjectName("primaryButton")
        self.stop_btn = QPushButton("⏹ Stop")
        self.restart_btn = QPushButton("🔄 Restart")
        self.scan_btn = QPushButton("🔍 Scan")
        self.hide_to_tray_btn = QPushButton("📥 Do Tray")
        
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
            "Steruj wyświetlaczem jak natywną aplikacją Plasma: uruchamiaj runtime, wysyłaj pojedyncze obrazy "
            "i zarządzaj motywami z czytelnych kart zamiast surowych pól."
        )
        runtime_hero_text.setObjectName("studioHeroText")
        runtime_hero_text.setWordWrap(True)
        runtime_hero_layout.addWidget(runtime_hero_text, 1)
        runtime_layout.addWidget(runtime_hero)

        runtime_sections_tabs = QTabWidget()
        runtime_sections_tabs.setDocumentMode(True)
        runtime_layout.addWidget(runtime_sections_tabs, 1)
        runtime_sections_tabs.currentChanged.connect(lambda _idx: self._animate_widget_fade(runtime_sections_tabs.currentWidget()))

        runtime_device_tab = QWidget()
        runtime_device_layout = QVBoxLayout(runtime_device_tab)
        runtime_device_layout.setContentsMargins(0, 0, 0, 0)
        runtime_device_layout.setSpacing(10)
        runtime_sections_tabs.addTab(runtime_device_tab, "Urządzenie")

        runtime_image_tab = QWidget()
        runtime_image_layout = QVBoxLayout(runtime_image_tab)
        runtime_image_layout.setContentsMargins(0, 0, 0, 0)
        runtime_image_layout.setSpacing(10)
        runtime_sections_tabs.addTab(runtime_image_tab, "Obraz")

        runtime_theme_tab = QWidget()
        runtime_theme_layout = QVBoxLayout(runtime_theme_tab)
        runtime_theme_layout.setContentsMargins(0, 0, 0, 0)
        runtime_theme_layout.setSpacing(10)
        runtime_sections_tabs.addTab(runtime_theme_tab, "Motywy")

        work_box = QGroupBox("Obraz Jednorazowy")
        work_layout = QVBoxLayout(work_box)
        work_layout.setSpacing(8)
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(0, 1_000_000)
        self.set_frame_btn = QPushButton("Ustaw klatkę")
        self.set_frame_btn.clicked.connect(self.set_frame)
        frame_row = QHBoxLayout()
        frame_row.addWidget(QLabel("Frame index:"))
        frame_row.addWidget(self.frame_spin)
        frame_row.addWidget(self.set_frame_btn)
        frame_row.addStretch(1)
        work_layout.addLayout(frame_row)

        self.image_edit = QLineEdit(str(Path("reference_frame_trcc.jpg")))
        self.browse_btn = QPushButton("Wybierz obraz")
        self.prepare_image_btn = QPushButton("Przygotuj obraz")
        self.send_image_btn = QPushButton("Wyślij obraz")
        self.raw_passthrough_chk = QCheckBox("Raw JPEG passthrough")
        self.raw_passthrough_chk.setChecked(False)
        self.stop_before_send_chk = QCheckBox("Zatrzymaj runtime przed wysyłką")
        self.stop_before_send_chk.setChecked(True)
        self.resume_loop_chk = QCheckBox("Wznów loop po wysyłce")
        self.resume_loop_chk.setChecked(False)
        self.browse_btn.clicked.connect(self.browse_image)
        self.prepare_image_btn.clicked.connect(lambda: self.prepare_image_asset(self.image_edit))
        self.send_image_btn.clicked.connect(self.send_image)
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Plik obrazu:"))
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

        cfg_box = QGroupBox("Ustawienia Odtwarzania")
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
        self.apply_cfg_btn = QPushButton("Zastosuj Config")
        self.apply_cfg_btn.clicked.connect(self.apply_config)
        cfg_form.addRow("PCAP file:", self.pcap_edit)
        cfg_form.addRow("ACK timeout (ms):", self.ack_timeout_spin)
        cfg_form.addRow("Inter packet delay (s):", self.inter_delay_spin)
        cfg_form.addRow("Frame delay (s):", self.frame_delay_spin)
        cfg_form.addRow("", self.apply_cfg_btn)
        cfg_status_row.addWidget(cfg_box, 1)

        status_box = QGroupBox("Monitor Systemowy")
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

        status_grid.addWidget(make_status_label("📟 Tryb:"), 0, 0)
        status_grid.addWidget(self.lbl_mode, 0, 1)
        status_grid.addWidget(make_status_label("🚦 Status:"), 0, 2)
        status_grid.addWidget(self.lbl_running, 0, 3)
        status_grid.addWidget(make_status_label("🆔 PID:"), 1, 0)
        status_grid.addWidget(self.lbl_pid, 1, 1)
        status_grid.addWidget(make_status_label("⏱ Uptime:"), 1, 2)
        status_grid.addWidget(self.lbl_uptime, 1, 3)
        status_grid.addWidget(make_status_label("🖼 Ramki:"), 2, 0)
        status_grid.addWidget(self.lbl_frame_count, 2, 1)
        status_grid.addWidget(make_status_label("📂 PCAP:"), 2, 2)
        status_grid.addWidget(self.lbl_pcap, 2, 3)
        status_grid.addWidget(make_status_label("🎵 Playlista:"), 3, 0)
        status_grid.addWidget(self.lbl_playlist, 3, 1)
        status_grid.addWidget(make_status_label("⏳ Czas PL:"), 3, 2)
        status_grid.addWidget(self.lbl_playlist_uptime, 3, 3)
        status_grid.addWidget(make_status_label("⚠️ Błąd:"), 4, 0)
        status_grid.addWidget(self.lbl_last_error, 4, 1, 1, 3)
        cfg_status_row.addWidget(status_box, 1)
        runtime_device_layout.addLayout(cfg_status_row)
        runtime_device_layout.addStretch(1)

        theme_box = QGroupBox("Biblioteka motywów")
        theme_layout = QVBoxLayout(theme_box)
        theme_layout.setSpacing(8)
        self.theme_combo = QComboBox()
        self.theme_refresh_btn = QPushButton("Odśwież listę")
        self.theme_apply_btn = QPushButton("Zastosuj motyw")
        self.theme_remove_btn = QPushButton("Usuń Theme")
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
        self.theme_browse_btn = QPushButton("Wybierz plik")
        self.theme_prepare_btn = QPushButton("Przygotuj obraz")
        self.theme_add_btn = QPushButton("Dodaj / Aktualizuj Theme")
        self.theme_raw_chk = QCheckBox("Raw JPEG passthrough (theme)")
        self.theme_stop_before_apply_chk = QCheckBox("Zatrzymaj runtime przed apply")
        self.theme_stop_before_apply_chk.setChecked(True)
        self.theme_resume_chk = QCheckBox("Wznów loop po apply")
        self.theme_raw_chk.setChecked(False)
        self.theme_resume_chk.setChecked(False)
        self.theme_browse_btn.clicked.connect(self.browse_theme_path)
        self.theme_prepare_btn.clicked.connect(lambda: self.prepare_image_asset(self.theme_path_edit))
        self.theme_add_btn.clicked.connect(self.add_or_update_theme)
        theme_row_2 = QHBoxLayout()
        theme_row_2.addWidget(QLabel("Nazwa:"))
        theme_row_2.addWidget(self.theme_name_edit, 1)
        theme_layout.addLayout(theme_row_2)
        theme_row_3 = QHBoxLayout()
        theme_row_3.addWidget(QLabel("Plik:"))
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
        runtime_theme_cards_box = QGroupBox("Karty Motywów")
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
            "System pokazuje stan backendu, urządzenia i podstawowe metryki hosta. "
            "Szybkie akcje po prawej używają tych samych, działających endpointów co dotychczas."
        )
        system_intro_text.setObjectName("studioHeroText")
        system_intro_text.setWordWrap(True)
        system_intro_layout.addWidget(system_intro_text)
        runtime_layout.addWidget(system_intro)

        system_top_row = QHBoxLayout()
        system_top_row.setSpacing(14)

        backend_status_box = QGroupBox("Status Backendu")
        backend_status_box.setObjectName("dashboardCardBox")
        backend_status_layout = QVBoxLayout(backend_status_box)
        backend_status_layout.setSpacing(10)
        self.system_api_status_row, self.system_api_status_value = self._create_dashboard_status_row("API Server", "Offline")
        self.system_ws_status_row, self.system_ws_status_value = self._create_dashboard_status_row("WebSocket", "Offline")
        self.system_lcd_status_row, self.system_lcd_status_value = self._create_dashboard_status_row("LCD Daemon", "Idle")
        self.system_queue_status_row, self.system_queue_status_value = self._create_dashboard_status_row("Queue Worker", "Idle")
        self.system_theme_engine_row, self.system_theme_engine_value = self._create_dashboard_status_row("Theme Engine", "Ready")
        self.system_backup_row, self.system_backup_value = self._create_dashboard_status_row("Auto Backup", "Idle")
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

        system_info_box = QGroupBox("Informacje o Systemie")
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
            ("System operacyjny:", self.system_os_value),
            ("Framework:", self.system_framework_value),
            ("Wersja aplikacji:", self.system_app_version_value),
            ("Uptime:", self.system_uptime_value),
            ("Hostname:", self.system_hostname_value),
            ("Ostatni restart:", self.system_restart_value),
        ]
        for idx, (label_text, value_lbl) in enumerate(info_rows):
            system_info_grid.addWidget(QLabel(label_text), idx, 0)
            system_info_grid.addWidget(value_lbl, idx, 1)
        system_top_row.addWidget(system_info_box, 1)

        resources_box = QGroupBox("Zasoby Systemowe")
        resources_box.setObjectName("dashboardCardBox")
        resources_layout = QHBoxLayout(resources_box)
        resources_layout.setSpacing(10)
        cpu_card, self.system_cpu_value, self.system_cpu_detail = self._create_system_metric_card("CPU")
        mem_card, self.system_mem_value, self.system_mem_detail = self._create_system_metric_card("RAM")
        disk_card, self.system_disk_value, self.system_disk_detail = self._create_system_metric_card("DYSK")
        temp_card, self.system_temp_value, self.system_temp_detail = self._create_system_metric_card("TEMPERATURA")
        for card in (cpu_card, mem_card, disk_card, temp_card):
            resources_layout.addWidget(card, 1)
        system_top_row.addWidget(resources_box, 1)
        runtime_layout.addLayout(system_top_row)

        system_bottom_row = QHBoxLayout()
        system_bottom_row.setSpacing(14)

        device_box = QGroupBox("Sieć i Urządzenie")
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
            ("Połączenie:", self.system_connection_value),
            ("Urządzenie:", self.system_device_value),
            ("Firmware:", self.system_firmware_value),
            ("Rozdzielczość:", self.system_resolution_value),
            ("Adres IP:", self.system_ip_value),
            ("Port API:", self.system_port_value),
            ("USB/Serial:", self.system_serial_value),
        ]
        for idx, (label_text, value_lbl) in enumerate(device_rows):
            device_grid.addWidget(QLabel(label_text), idx, 0)
            device_grid.addWidget(value_lbl, idx, 1)
        system_bottom_row.addWidget(device_box, 1)

        events_box = QGroupBox("Zdarzenia Systemowe")
        events_box.setObjectName("dashboardCardBox")
        events_layout = QVBoxLayout(events_box)
        events_header = QHBoxLayout()
        for title, stretch in (("Czas", 1), ("Poziom", 1), ("Źródło", 2), ("Wiadomość", 4)):
            lbl = QLabel(title)
            lbl.setObjectName("eventHeaderLabel")
            events_header.addWidget(lbl, stretch)
        events_layout.addLayout(events_header)
        self.system_events_list = QListWidget()
        self.system_events_list.setMinimumHeight(260)
        self.system_events_list.setObjectName("systemEventsList")
        events_layout.addWidget(self.system_events_list)
        system_bottom_row.addWidget(events_box, 2)

        quick_actions_box = QGroupBox("Szybkie Akcje")
        quick_actions_box.setObjectName("dashboardCardBox")
        quick_actions_layout = QVBoxLayout(quick_actions_box)
        self.system_restart_backend_btn = QPushButton("Restart backend")
        self.system_restart_service_btn = QPushButton("Restart usługi")
        self.system_refresh_status_btn = QPushButton("Odśwież status")
        self.system_export_logs_btn = QPushButton("Eksportuj logi")
        self.system_diagnostic_btn = QPushButton("Diagnostyka")
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
        self.nav_library_btn.clicked.connect(lambda: self._go_library())
        self.nav_designer_btn.clicked.connect(lambda: self._go_designer())
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar_collapsed)

        studio_toolbar_box = QGroupBox("")
        studio_toolbar_box.setObjectName("designerToolbarBox")
        studio_toolbar_box.setFlat(True)
        studio_toolbar_layout = QHBoxLayout(studio_toolbar_box)
        self.studio_toolbar_load_btn = QPushButton("📂 Otwórz motyw")
        self.studio_toolbar_save_btn = QPushButton("💾 Zapisz motyw")
        self.studio_toolbar_preview_btn = QPushButton("Podgląd")
        self.studio_toolbar_apply_btn = QPushButton("▶ Zastosuj motyw")
        self.studio_toolbar_reload_btn = QPushButton("↻ JSON -> Designer")
        self.studio_toolbar_export_btn = QPushButton("⇄ Designer -> JSON")
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
        self.studio_toolbar_load_btn.setText("Wczytaj motyw")
        self.studio_toolbar_save_btn.setText("Zapisz motyw")
        self.studio_toolbar_apply_btn.setText("Zastosuj motyw")
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
        designer_tab_layout.setSpacing(10)
        studio_left_tabs.addTab(designer_tab, "Designer")
        studio_left_tabs.addTab(json_tab, "JSON")

        theme_doc_box = QGroupBox("Motyw")
        theme_doc_grid = QGridLayout(theme_doc_box)
        theme_doc_grid.setColumnStretch(1, 1)
        self.theme_doc_path_edit = QLineEdit(str(Path("themes/default_monitor.json")))
        self.theme_doc_browse_btn = QPushButton("Wybierz motyw")
        self.theme_doc_use_selected_btn = QPushButton("Z aktywnego motywu")
        self.theme_doc_load_btn = QPushButton("Wczytaj")
        self.theme_doc_save_btn = QPushButton("Zapisz")
        self.theme_doc_apply_btn = QPushButton("Zastosuj")
        self.theme_doc_apply_btn.setObjectName("primaryButton")
        self.theme_doc_stop_before_apply_chk = QCheckBox("Zatrzymaj runtime przed apply")
        self.theme_doc_stop_before_apply_chk.setChecked(True)
        self.theme_doc_resume_chk = QCheckBox("Wznów loop po apply")
        self.theme_doc_resume_chk.setChecked(False)
        self.theme_schema_label = QLabel("-")
        self.theme_doc_editor = QTextEdit()
        self.theme_doc_editor.setPlaceholderText("{\n  \"schema_version\": 1,\n  ...\n}")
        self.theme_doc_editor.setMinimumHeight(460)
        self.theme_doc_editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.theme_doc_browse_btn.clicked.connect(self.browse_theme_doc_path)
        self.theme_doc_use_selected_btn.clicked.connect(self.use_selected_theme_doc)
        self.theme_doc_load_btn.clicked.connect(self.load_theme_doc)
        self.theme_doc_save_btn.clicked.connect(self.save_theme_doc)
        self.theme_doc_apply_btn.clicked.connect(self.apply_theme_doc)
        theme_doc_grid.addWidget(QLabel("Plik motywu:"), 0, 0)
        theme_doc_grid.addWidget(self.theme_doc_path_edit, 0, 1, 1, 3)
        theme_doc_grid.addWidget(self.theme_doc_browse_btn, 0, 4)
        theme_doc_grid.addWidget(self.theme_doc_use_selected_btn, 0, 5)
        theme_doc_grid.addWidget(self.theme_doc_stop_before_apply_chk, 1, 1, 1, 2)
        theme_doc_grid.addWidget(self.theme_doc_resume_chk, 1, 3)
        theme_doc_grid.addWidget(self.theme_doc_load_btn, 1, 4)
        theme_doc_grid.addWidget(self.theme_doc_save_btn, 1, 5)
        theme_doc_grid.addWidget(self.theme_doc_apply_btn, 2, 5)
        theme_doc_grid.addWidget(QLabel("Źródła danych:"), 2, 0)
        theme_doc_grid.addWidget(self.theme_schema_label, 2, 1, 1, 4)
        theme_doc_grid.addWidget(self.theme_doc_editor, 3, 0, 1, 6)
        json_tab_layout.addWidget(theme_doc_box, 1)
        theme_doc_box.hide()

        designer_box = QGroupBox("")
        designer_box.setObjectName("designerWorkspaceBox")
        designer_box.setFlat(True)
        designer_outer = QVBoxLayout(designer_box)
        designer_outer.setContentsMargins(0, 0, 0, 0)
        designer_outer.setSpacing(10)

        # 1. INICJALIZACJA WSZYSTKICH WIDŻETÓW (BEZPIECZNIE NA POCZĄTKU)
        self.preview_label = PreviewLabel(self)
        self.designer_element_list = LayerListWidget()
        self.designer_element_list.setObjectName("designerLayerList")
        self.designer_kind_combo = QComboBox()
        self.designer_kind_combo.addItem("Teksty", "texts"); self.designer_kind_combo.addItem("Statystyki", "stats")
        self.designer_kind_combo.addItem("Obrazy", "images"); self.designer_kind_combo.addItem("Panele", "panels")
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
        self.designer_color_edit = QLineEdit(); self.designer_label_color_edit = QLineEdit(); self.designer_value_color_edit = QLineEdit()
        self.designer_align_combo = QComboBox(); self.designer_align_combo.addItems(["left", "center", "right"])
        self.designer_font_family_combo = QComboBox(); self.designer_font_family_combo.addItems(available_font_families())
        self.designer_font_size_spin = QSpinBox(); self.designer_font_size_spin.setRange(6, 200)
        self.designer_font_bold_chk = QCheckBox("B")
        self.designer_font_italic_chk = QCheckBox("I")
        self.designer_font_underline_chk = QCheckBox("U")

        self.designer_path_edit = QLineEdit()
        self.designer_fit_combo = QComboBox(); self.designer_fit_combo.addItems(["contain", "cover", "stretch"])
        self.designer_visible_chk = QCheckBox("Widoczny"); self.designer_locked_chk = QCheckBox("Zablokowany")

        # Inicjalizacja brakujących widżetów paska narzędzi i opcji
        self.designer_mode_combo = QComboBox(); self.designer_mode_combo.addItems(["Simple", "Advanced"])
        self.designer_auto_preview_chk = QCheckBox("Auto-preview"); self.designer_auto_preview_chk.setChecked(True)
        self.designer_snap_chk = QCheckBox("Snap"); self.designer_snap_chk.setChecked(True)
        self.designer_snap_spin = QSpinBox(); self.designer_snap_spin.setRange(1, 128); self.designer_snap_spin.setValue(8)
        self.designer_undo_btn = QPushButton("Cofnij")
        self.designer_redo_btn = QPushButton("Ponów")
        self.designer_animation_mode_btn = QPushButton("Animacja"); self.designer_animation_mode_btn.setCheckable(True)
        self.designer_assets_toggle_btn = QPushButton("Multimedia"); self.designer_assets_toggle_btn.setCheckable(True)
        self.designer_details_toggle_btn = QPushButton("Pokaż dół"); self.designer_details_toggle_btn.setCheckable(True)

        # Inicjalizacja widżetów animacji (ruchu)
        self.motion_enabled_chk = QCheckBox("Animuj element")
        self.motion_start_spin = QSpinBox(); self.motion_start_spin.setRange(0, 99999)
        self.motion_end_spin = QSpinBox(); self.motion_end_spin.setRange(0, 99999)
        self.motion_target_x_spin = QSpinBox(); self.motion_target_x_spin.setRange(-5000, 5000)
        self.motion_target_y_spin = QSpinBox(); self.motion_target_y_spin.setRange(-5000, 5000)
        self.motion_target_opacity_spin = QDoubleSpinBox(); self.motion_target_opacity_spin.setRange(0.0, 1.0); self.motion_target_opacity_spin.setSingleStep(0.05)
        self.motion_capture_current_btn = QPushButton("Ustaw koniec z bieżącej")
        self.motion_remove_btn = QPushButton("Usuń ruch")

        # Widżety Tła / Presetów / Logów
        self.bg_kind_combo = QComboBox(); self.bg_kind_combo.addItems(["generated", "image", "color"])
        self.bg_rotation_spin = QSpinBox(); self.bg_rotation_spin.setRange(0, 270); self.bg_rotation_spin.setSingleStep(90)
        self.bg_base_color_edit = QLineEdit(); self.bg_base_color_btn = QPushButton("🎨")
        self.bg_accent_color_edit = QLineEdit(); self.bg_accent_color_btn = QPushButton("🎨")
        self.bg_texture_alpha_spin = QDoubleSpinBox(); self.bg_texture_alpha_spin.setRange(0.0, 1.0); self.bg_texture_alpha_spin.setSingleStep(0.05)
        self.bg_path_edit = QLineEdit(); self.bg_path_browse_btn = QPushButton("...")
        self.bg_prepare_btn = QPushButton("Importuj tło")
        self.bg_fit_combo = QComboBox(); self.bg_fit_combo.addItems(["cover", "contain", "stretch"])
        self.bg_opacity_spin = QDoubleSpinBox(); self.bg_opacity_spin.setRange(0.0, 1.0); self.bg_opacity_spin.setSingleStep(0.05)
        self.bg_clear_btn = QPushButton("Wyczyść"); self.bg_cover_btn = QPushButton("Cover"); self.bg_contain_btn = QPushButton("Contain")
        self.bg_preset_ocean_btn = QPushButton("Ocean"); self.bg_preset_amber_btn = QPushButton("Amber")
        self.bg_preset_mono_btn = QPushButton("Mono"); self.bg_preset_neon_btn = QPushButton("Neon")
        self.bg_show_grid_chk = QCheckBox("Siatka"); self.bg_show_safe_chk = QCheckBox("Safe Area")
        self.panel_fill_edit = QLineEdit(); self.panel_fill_btn = QPushButton("🎨")
        self.panel_radius_spin = QSpinBox(); self.panel_radius_spin.setRange(0, 500)
        self.panel_opacity_spin = QDoubleSpinBox(); self.panel_opacity_spin.setRange(0.0, 1.0); self.panel_opacity_spin.setSingleStep(0.05)
        self.background_preview_label = QLabel("Podgląd tła")
        
        # Inicjalizacja widżetów animacji tła
        self.bg_animation_enabled_chk = QCheckBox("Animacja aktywna")
        self.bg_animation_use_bg_chk = QCheckBox("Użyj jako tła")
        self.bg_animation_fps_spin = QDoubleSpinBox(); self.bg_animation_fps_spin.setRange(1.0, 60.0); self.bg_animation_fps_spin.setValue(12.0)
        self.bg_animation_frame_spin = QSpinBox(); self.bg_animation_frame_spin.setRange(0, 99999)
        self.bg_animation_duration_spin = QSpinBox(); self.bg_animation_duration_spin.setRange(1, 60000); self.bg_animation_duration_spin.setValue(83)
        self.bg_animation_prev_btn = QPushButton("◀")
        self.bg_animation_next_btn = QPushButton("▶")
        self.bg_animation_clear_btn = QPushButton("Wyczyść animację")
        self.bg_animation_timeline = AnimationTimelineWidget()
        self.bg_animation_remove_btn = QPushButton("Usuń")
        self.bg_animation_duplicate_btn = QPushButton("Duplikuj")
        self.bg_animation_up_btn = QPushButton("▲")
        self.bg_animation_down_btn = QPushButton("▼")
        self.bg_animation_play_btn = QPushButton("▶ Odtwórz")
        self.bg_animation_count_label = QLabel("0 klatek")
        self.bg_animation_list = LayerListWidget()
        self.bg_animation_add_btn = QPushButton("Dodaj")
        self.bg_animation_blank_btn = QPushButton("Pusta")
        self.bg_animation_export_btn = QPushButton("Eksportuj")
        self.bg_animation_import_btn = QPushButton("Importuj")

        self.layout_preset_name_edit = QLineEdit(); self.layout_preset_combo = QComboBox()
        self.layout_preset_save_btn = QPushButton("Zapisz preset"); self.layout_preset_load_btn = QPushButton("Wczytaj preset")
        self.layout_preset_delete_btn = QPushButton("Usuń preset")
        self.designer_toolbar_feedback_label = QLabel("Projektant gotowy.")
        self.designer_toolbar_feedback_label.setObjectName("previewHintLabel")
        self.designer_toolbar_feedback_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.designer_toolbar_feedback_label.setMinimumWidth(0)
        self.designer_toolbar_feedback_label.setMaximumWidth(210)
        self.designer_toolbar_feedback_label.hide()
        self.designer_toolbar_feedback_timer = QTimer(self)
        self.designer_toolbar_feedback_timer.setSingleShot(True)
        self.designer_toolbar_feedback_timer.timeout.connect(lambda: self._set_designer_toolbar_feedback("", auto_clear_ms=None))

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
        studio_layout.setSpacing(10)
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
        toolbar_layout.setSpacing(8)

        self.designer_reload_btn = AnimatedToolbarButton("Wczytaj motyw")
        self.designer_reload_btn.setObjectName("secondaryAccentButton")
        self.designer_write_btn = AnimatedToolbarButton("Zapisz motyw")
        self.designer_write_btn.setObjectName("secondaryAccentButton")
        self.designer_animation_mode_btn = AnimatedToolbarButton("Animacja")
        self.designer_animation_mode_btn.setCheckable(True)
        self.designer_animation_mode_btn.setObjectName("modeToggleButton")
        self.designer_assets_toggle_btn = AnimatedToolbarButton("Multimedia")
        self.designer_assets_toggle_btn.setCheckable(True)
        self.designer_assets_toggle_btn.setObjectName("modeToggleButton")
        self.designer_preview_btn = AnimatedToolbarButton("Podgląd")
        self.designer_preview_btn.setObjectName("secondaryAccentButton")
        self.designer_apply_btn = AnimatedToolbarButton("Zastosuj motyw")
        self.designer_apply_btn.setObjectName("primaryButton")

        for btn in [self.designer_reload_btn, self.designer_write_btn, self.designer_animation_mode_btn, self.designer_assets_toggle_btn, self.designer_preview_btn, self.designer_apply_btn]:
            btn.setMinimumHeight(36)
            btn.setMaximumHeight(40)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            font = btn.font()
            font.setPointSize(max(10, font.pointSize()))
            font.setBold(True)
            btn.setFont(font)

        toolbar_layout.addWidget(self.designer_reload_btn)
        toolbar_layout.addWidget(self.designer_write_btn)
        toolbar_layout.addWidget(self.designer_animation_mode_btn)
        toolbar_layout.addWidget(self.designer_assets_toggle_btn)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.designer_toolbar_feedback_label, 0, Qt.AlignVCenter)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.designer_preview_btn)
        toolbar_layout.addWidget(self.designer_apply_btn)
        studio_layout.addWidget(toolbar_frame)

        # PIONOWY SPLITTER DLA LCD I INSPECTORA
        self.designer_top_splitter = QSplitter(Qt.Vertical)
        self.designer_top_splitter.setChildrenCollapsible(False)
        studio_layout.addWidget(self.designer_top_splitter, 1)

        # LCD PREVIEW (Góra prawego panelu)
        self.designer_canvas_workbench = QFrame()
        self.designer_canvas_workbench.setObjectName("designerSectionBox")
        canvas_vbox = QVBoxLayout(self.designer_canvas_workbench)
        canvas_vbox.setContentsMargins(0, 0, 0, 0) # Przejmujemy niewykorzystaną część
        
        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True); preview_scroll.setAlignment(Qt.AlignCenter)
        preview_scroll.setFrameShape(QFrame.NoFrame); preview_scroll.setWidget(self.preview_label)
        canvas_vbox.addWidget(preview_scroll, 1)
        
        info_row = QHBoxLayout()
        info_row.setContentsMargins(10, 0, 10, 10)
        self.preview_info_label = QLabel("💡 Wskazówka: Możesz przesuwać elementy bezpośrednio na podglądzie.")
        self.preview_info_label.setObjectName("previewHintLabel")
        self.preview_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.preview_coords_label = QLabel("x: -, y: -")
        self.preview_coords_label.setObjectName("previewHintLabel")
        self.preview_delta_label = QLabel("Δx: 0, Δy: 0")
        self.preview_delta_label.setObjectName("previewHintLabel")
        self.preview_guides_chk = QCheckBox("Pokaż ramki")
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
        self._setup_inspector_tabs(QVBoxLayout(self.designer_inspector_container))
        self.designer_top_splitter.addWidget(self.designer_inspector_container)
        
        # Ograniczamy wysokość Inspectora, dajemy więcej miejsca dla LCD
        self.designer_top_splitter.setStretchFactor(0, 5) # Canvas
        self.designer_top_splitter.setStretchFactor(1, 1) # Inspector
        self.designer_top_splitter.setSizes([900, 200])

        designer_tab_layout.addWidget(designer_box, 1)

        # LOGI API (Przeniesione na osobny layout, by nie przeszkadzały w Designerze)
        log_box = QGroupBox("Logi API i aplikacji")
        log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(14, 14, 14, 14)
        log_layout.setSpacing(10)
        
        log_toolbar = QHBoxLayout()
        self.log_filter_edit = QLineEdit(); self.log_filter_edit.setPlaceholderText("Filtr logów...")
        self.log_filter_edit.textChanged.connect(lambda: self._refresh_log_view(force=True))
        self.log_only_errors_chk = QCheckBox("Tylko błędy")
        self.log_only_errors_chk.toggled.connect(lambda: self._refresh_log_view(force=True))
        self.log_hide_status_chk = QCheckBox("Ukryj status"); self.log_hide_status_chk.setChecked(True)
        self.log_hide_status_chk.toggled.connect(lambda: self._refresh_log_view(force=True))
        self.log_copy_btn = QPushButton("Kopiuj widok"); self.log_copy_btn.clicked.connect(self.copy_filtered_logs)
        self.log_copy_selection_btn = QPushButton("Kopiuj zaznaczenie"); self.log_copy_selection_btn.clicked.connect(self.copy_selected_logs)
        self.log_clear_btn = QPushButton("Wyczyść"); self.log_clear_btn.clicked.connect(self.clear_logs)
        
        log_toolbar.addWidget(QLabel("Szukaj:")); log_toolbar.addWidget(self.log_filter_edit, 1)
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
        self.designer_preview_btn.clicked.connect(self._trigger_designer_preview)
        self.designer_apply_btn.clicked.connect(self._trigger_designer_apply)
        self.designer_undo_btn.clicked.connect(self.undo_designer_change)
        self.designer_redo_btn.clicked.connect(self.redo_designer_change)
        self.designer_mode_combo.currentTextChanged.connect(self.apply_designer_mode)
        self.designer_animation_mode_btn.toggled.connect(self._sync_designer_preview_policy)
        self.designer_assets_toggle_btn.toggled.connect(self._sync_designer_preview_policy)
        self.designer_details_toggle_btn.toggled.connect(self._sync_designer_preview_policy)

        
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
            (self.designer_font_family_combo, "currentTextChanged"), (self.designer_font_size_spin, "valueChanged"),
            (self.designer_font_bold_chk, "toggled"), (self.designer_font_italic_chk, "toggled"),
            (self.designer_font_underline_chk, "toggled"),
            (self.designer_color_edit, "textChanged"), (self.designer_label_color_edit, "textChanged"),
            (self.designer_value_color_edit, "textChanged"),
            (self.bg_kind_combo, "currentTextChanged"), (self.bg_path_edit, "textChanged")
        ]:
            try: getattr(widget, signal).connect(self.on_designer_field_changed)
            except: pass
        self.bg_animation_timeline.frame_selected.connect(self.select_animation_frame)
        self.layout_preset_save_btn.clicked.connect(self.save_layout_preset)
        self.layout_preset_load_btn.clicked.connect(self.load_layout_preset)
        self.layout_preset_delete_btn.clicked.connect(self.delete_layout_preset)
        self.bg_animation_import_btn.clicked.connect(self.import_background_animation)
        self.bg_animation_add_btn.clicked.connect(self.import_background_animation)
        self.bg_animation_blank_btn.clicked.connect(self.insert_blank_animation_frame)
        self.bg_animation_duplicate_btn.clicked.connect(self.duplicate_selected_animation_frame)
        self.bg_animation_remove_btn.clicked.connect(self.remove_selected_animation_frames)
        self.bg_animation_clear_btn.clicked.connect(self.clear_background_animation)
        self.bg_animation_up_btn.clicked.connect(lambda: self.move_selected_animation_frames(-1))
        self.bg_animation_down_btn.clicked.connect(lambda: self.move_selected_animation_frames(1))
        self.bg_animation_export_btn.clicked.connect(self.export_animation_sequence)
        self.bg_animation_play_btn.clicked.connect(self.toggle_animation_preview_playback)
        self.bg_animation_prev_btn.clicked.connect(lambda: self.select_animation_frame(max(0, self.bg_animation_list.currentRow() - 1)))
        self.bg_animation_next_btn.clicked.connect(lambda: self.select_animation_frame(min(self.bg_animation_list.count() - 1, self.bg_animation_list.currentRow() + 1)))
        self.bg_animation_list.currentRowChanged.connect(self.select_animation_frame)
        self.bg_animation_list.rows_reordered.connect(self.on_animation_frames_reordered)
        
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
            QMessageBox.information(self, "Logi", "Brak logów do skopiowania.")
            return
        QApplication.clipboard().setText(text)
        self._refresh_log_view(force=True)
        self.append_log("[logs] Skopiowano przefiltrowane logi do schowka.")

    def copy_selected_logs(self) -> None:
        if not hasattr(self, "log_view"):
            return
        selected = self.log_view.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not selected:
            QMessageBox.information(self, "Logi", "Brak zaznaczonego fragmentu logów.")
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
            QMessageBox.warning(self, "Niepoprawny link", f"Nie udało się przygotować adresu do {label}:\n{url}")
            return
        if QDesktopServices.openUrl(target):
            self.append_log(f"[link] Otwarto {label}: {url}")
            return
        QMessageBox.warning(
            self,
            "Nie udało się otworzyć linku",
            f"System nie otworzył {label}.\nSkopiuj adres ręcznie:\n{url}",
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
        if action == "theme-doc-preview":
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

    def _image_tools_available(self) -> bool:
        return prepare_image_for_canvas is not None and render_prepared_image is not None

    def _update_image_tools_availability(self) -> None:
        available = self._image_tools_available()
        message = "" if available else "Funkcja niedostępna: brak Pillow w środowisku GUI."
        for button in (
            getattr(self, "designer_import_image_btn", None),
            getattr(self, "designer_path_prepare_btn", None),
            getattr(self, "bg_prepare_btn", None),
        ):
            if button is None:
                continue
            button.setEnabled(available)
            button.setToolTip(message)

    def _setup_designer_layers_panel(self, parent_layout: QVBoxLayout) -> None:
        """Konfiguruje lewy panel z listą warstw."""
        box = QGroupBox("Warstwy i komponenty")
        self.designer_elements_box = box
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.designer_component_search = QLineEdit()
        self.designer_component_search.setPlaceholderText("Szukaj warstwy lub tekstu...")
        self.designer_component_search.setClearButtonEnabled(True)
        search_row.addWidget(self.designer_component_search, 1)
        self.designer_quick_add_toggle_btn = QPushButton("+ komponent")
        self.designer_quick_add_toggle_btn.setCheckable(True)
        self.designer_quick_add_toggle_btn.setChecked(False)
        self.designer_quick_add_toggle_btn.setMinimumHeight(28)
        search_row.addWidget(self.designer_quick_add_toggle_btn)
        layout.addLayout(search_row)

        self.designer_collection_hint = QLabel("Wybierz kategorię i dodaj nowy element jednym kliknięciem.")
        self.designer_collection_hint.setObjectName("selectionSummaryLabel")
        self.designer_collection_hint.setWordWrap(True)
        layout.addWidget(self.designer_collection_hint)
        collection_row = QHBoxLayout()
        collection_row.setSpacing(6)
        collection_label = QLabel("Kategoria")
        collection_label.setObjectName("headerFieldLabel")
        collection_row.addWidget(collection_label)
        collection_row.addWidget(self.designer_kind_combo, 1)
        layout.addLayout(collection_row)
        self.designer_selection_label.setObjectName("selectionSummaryLabel")
        self.designer_selection_label.setWordWrap(True)
        self.designer_selection_label.setMaximumHeight(34)
        layout.addWidget(self.designer_selection_label)
        self.designer_kind_combo.currentIndexChanged.connect(self.refresh_designer_element_list)
        
        # Szybkie dodawanie
        self.designer_quick_add_container = QWidget()
        quick_container_layout = QVBoxLayout(self.designer_quick_add_container)
        quick_container_layout.setContentsMargins(0, 0, 0, 0)
        quick_container_layout.setSpacing(4)
        quick_grid = QGridLayout()
        self.quick_add_text_btn = QPushButton("Tekst")
        self.quick_add_stat_btn = QPushButton("Statystyka")
        self.quick_add_image_btn = QPushButton("Obraz")
        self.quick_add_panel_btn = QPushButton("Panel")
        quick_grid.setHorizontalSpacing(4)
        quick_grid.setVerticalSpacing(4)
        for btn in (self.quick_add_text_btn, self.quick_add_stat_btn, self.quick_add_image_btn, self.quick_add_panel_btn):
            btn.setObjectName("quickAddButton")
            btn.setMinimumHeight(30)
        self.quick_add_now_playing_btn = QPushButton("Now Playing")
        self.quick_add_now_playing_btn.setObjectName("quickAddButton")
        self.quick_add_now_playing_btn.setMinimumHeight(30)
        self.quick_add_now_playing_hero_btn = QPushButton("Now Playing Hero")
        self.quick_add_now_playing_hero_btn.setObjectName("quickAddButton")
        self.quick_add_now_playing_hero_btn.setMinimumHeight(30)
        self.quick_add_now_playing_mini_btn = QPushButton("Now Playing Mini")
        self.quick_add_now_playing_mini_btn.setObjectName("quickAddButton")
        self.quick_add_now_playing_mini_btn.setMinimumHeight(30)
        quick_buttons = [
            self.quick_add_text_btn,
            self.quick_add_stat_btn,
            self.quick_add_image_btn,
            self.quick_add_panel_btn,
            self.quick_add_now_playing_btn,
            self.quick_add_now_playing_hero_btn,
            self.quick_add_now_playing_mini_btn,
        ]
        for i, btn in enumerate(quick_buttons):
            quick_grid.addWidget(btn, i // 3, i % 3)
        quick_container_layout.addLayout(quick_grid)
        layout.addWidget(self.designer_quick_add_container)
        self.quick_add_text_btn.clicked.connect(lambda: self.quick_add_designer_element("texts"))
        self.quick_add_stat_btn.clicked.connect(lambda: self.quick_add_designer_element("stats"))
        self.quick_add_image_btn.clicked.connect(lambda: self.quick_add_designer_element("images"))
        self.quick_add_panel_btn.clicked.connect(lambda: self.quick_add_designer_element("panels"))
        self.quick_add_now_playing_btn.clicked.connect(self.add_now_playing_widget)
        self.quick_add_now_playing_hero_btn.clicked.connect(self.add_now_playing_widget_hero)
        self.quick_add_now_playing_mini_btn.clicked.connect(self.add_now_playing_widget_mini)
        self.designer_quick_add_toggle_btn.toggled.connect(self._apply_designer_aux_visibility)
        
        self.designer_element_list.setMinimumHeight(170)
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
        
        move_box = QGroupBox("Przesuwanie zaznaczenia")
        move_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        move_layout = QVBoxLayout(move_box)
        move_layout.setContentsMargins(6, 6, 6, 6)
        move_layout.setSpacing(2)
        move_step_row = QHBoxLayout()
        move_step_row.setSpacing(5)
        move_step_row.addWidget(QLabel("Krok:"))
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
        self.designer_nudge_up_btn = QPushButton("↑")
        self.designer_nudge_left_btn = QPushButton("←")
        self.designer_nudge_right_btn = QPushButton("→")
        self.designer_nudge_down_btn = QPushButton("↓")
        for btn in (
            self.designer_nudge_up_btn,
            self.designer_nudge_left_btn,
            self.designer_nudge_right_btn,
            self.designer_nudge_down_btn,
        ):
            btn.setMinimumHeight(18)
            btn.setMaximumHeight(30)
            btn.setMinimumWidth(28)
            btn.setMaximumWidth(88)
        dpad.addWidget(self.designer_nudge_up_btn, 0, 1)
        dpad.addWidget(self.designer_nudge_left_btn, 1, 0)
        dpad.addWidget(self.designer_nudge_right_btn, 1, 2)
        dpad.addWidget(self.designer_nudge_down_btn, 2, 1)
        move_layout.addLayout(dpad)
        self.designer_nudge_up_btn.clicked.connect(lambda: self.nudge_selected_elements(0, -1, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_nudge_left_btn.clicked.connect(lambda: self.nudge_selected_elements(-1, 0, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_nudge_right_btn.clicked.connect(lambda: self.nudge_selected_elements(1, 0, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        self.designer_nudge_down_btn.clicked.connect(lambda: self.nudge_selected_elements(0, 1, step_override=self._selected_nudge_step(), require_keyboard_focus=False))
        move_box.setMaximumHeight(180)
        layout.addWidget(move_box)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        self.designer_raise_selected_btn = QPushButton("Wyżej")
        self.designer_lower_selected_btn = QPushButton("Niżej")
        self.designer_remove_btn = QPushButton("Usuń")
        for btn in (self.designer_raise_selected_btn, self.designer_lower_selected_btn, self.designer_remove_btn):
            btn.setMinimumHeight(28)
        self.designer_raise_selected_btn.clicked.connect(self.raise_designer_layer)
        self.designer_lower_selected_btn.clicked.connect(self.lower_designer_layer)
        self.designer_remove_btn.clicked.connect(self.remove_designer_element)
        ctrl_row.addWidget(self.designer_raise_selected_btn)
        ctrl_row.addWidget(self.designer_lower_selected_btn)
        ctrl_row.addStretch(1)
        ctrl_row.addWidget(self.designer_remove_btn)
        layout.addLayout(ctrl_row)
        parent_layout.addWidget(box, 2)

    def _setup_inspector_tabs(self, container_layout: QVBoxLayout) -> None:
        """Konfiguruje prawy panel właściwości z zakładkami."""
        box = QGroupBox("Właściwości Elementu")
        box.setObjectName("designerSectionBox")
        self.props_box = box
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.inspector_selection_summary = QLabel("Wybierz element, aby edytować jego właściwości.")
        self.inspector_selection_summary.setObjectName("selectionSummaryLabel")
        self.inspector_selection_summary.setWordWrap(True)
        layout.addWidget(self.inspector_selection_summary)

        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setDocumentMode(True)
        self.inspector_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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

        self.inspector_general, self.inspector_general_layout = make_tab()
        self.inspector_content, self.inspector_content_layout = make_tab()
        self.inspector_appearance, self.inspector_appearance_layout = make_tab()
        self.inspector_geometry, self.inspector_geometry_layout = make_tab()
        self.inspector_image, self.inspector_image_layout = make_tab()
        self.inspector_media, self.inspector_media_layout = make_tab()
        self.inspector_animation, self.inspector_animation_layout = make_tab()

        for l in [
            self.inspector_general_layout,
            self.inspector_content_layout,
            self.inspector_appearance_layout,
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

        self.row_panel_fill = make_label("Wypełnienie panelu")
        self.panel_fill_row = wrap_row(self.panel_fill_edit, self.panel_fill_btn, stretch_first=True)
        self.panel_fill_btn.clicked.connect(lambda _checked=False: self.pick_color_for_edit(self.panel_fill_edit))
        self.inspector_appearance_layout.addRow(self.row_panel_fill, self.panel_fill_row)
        self.row_panel_opacity = make_label("Przezroczystość panelu")
        self.inspector_appearance_layout.addRow(self.row_panel_opacity, self.panel_opacity_spin)
        self.row_panel_radius = make_label("Promień narożników")
        self.inspector_appearance_layout.addRow(self.row_panel_radius, self.panel_radius_spin)

        self.row_geometry_x = make_label("X")
        self.inspector_geometry_layout.addRow(self.row_geometry_x, self.designer_x_spin)
        self.row_geometry_y = make_label("Y")
        self.inspector_geometry_layout.addRow(self.row_geometry_y, self.designer_y_spin)
        self.row_geometry_w = make_label("Szerokość")
        self.inspector_geometry_layout.addRow(self.row_geometry_w, self.designer_w_spin)
        self.row_geometry_h = make_label("Wysokość")
        self.inspector_geometry_layout.addRow(self.row_geometry_h, self.designer_h_spin)
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
        self.row_image_fit = make_label("Dopasowanie")
        self.inspector_image_layout.addRow(self.row_image_fit, self.designer_fit_combo)
        self.row_image_opacity = make_label("Przezroczystość")
        self.inspector_image_layout.addRow(self.row_image_opacity, self.designer_opacity_spin)
        self.row_image_rotation = make_label("Obrót")
        self.inspector_image_layout.addRow(self.row_image_rotation, self.designer_rotation_spin)
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
        self.designer_image_preview_label = QLabel("Podgląd obrazu")
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
        self.inspector_media_layout.addRow(make_label("Tryb tła"), self.bg_kind_combo)
        self.inspector_media_layout.addRow(make_label("Plik / import"), self.media_background_path_row)
        self.inspector_media_layout.addRow(make_label("Dopasowanie"), self.bg_fit_combo)
        self.inspector_media_layout.addRow(make_label("Przezroczystość"), self.bg_opacity_spin)
        self.inspector_media_layout.addRow(make_label("Obrót"), self.bg_rotation_spin)
        media_colors_row = wrap_row(self.bg_base_color_edit, self.bg_base_color_btn, self.bg_accent_color_edit, self.bg_accent_color_btn)
        self.inspector_media_layout.addRow(make_label("Kolory"), media_colors_row)
        media_presets_row = wrap_row(
            self.bg_cover_btn,
            self.bg_contain_btn,
            self.bg_preset_ocean_btn,
            self.bg_preset_amber_btn,
            self.bg_preset_mono_btn,
            self.bg_preset_neon_btn,
        )
        self.inspector_media_layout.addRow(make_label("Presety"), media_presets_row)
        self.inspector_media_layout.addRow(make_label("Tekstura"), self.bg_texture_alpha_spin)
        self.inspector_media_layout.addRow(make_label("Podgląd tła"), self.background_preview_label)

        self.bg_animation_list.setMinimumHeight(120)
        animation_flags_row = wrap_row(self.bg_animation_enabled_chk, self.bg_animation_use_bg_chk)
        animation_speed_row = wrap_row(
            self.bg_animation_fps_spin,
            self.bg_animation_frame_spin,
            self.bg_animation_duration_spin,
        )
        animation_nav_row = wrap_row(
            self.bg_animation_prev_btn,
            self.bg_animation_next_btn,
            self.bg_animation_play_btn,
            self.bg_animation_count_label,
        )
        animation_import_row = wrap_row(
            self.bg_animation_import_btn,
            self.bg_animation_add_btn,
            self.bg_animation_blank_btn,
            self.bg_animation_export_btn,
        )
        animation_edit_row = wrap_row(
            self.bg_animation_duplicate_btn,
            self.bg_animation_remove_btn,
            self.bg_animation_up_btn,
            self.bg_animation_down_btn,
            self.bg_animation_clear_btn,
        )
        self.inspector_animation_layout.addRow(make_label("Aktywność"), animation_flags_row)
        self.inspector_animation_layout.addRow(make_label("FPS / klatka / czas"), animation_speed_row)
        self.inspector_animation_layout.addRow(make_label("Sterowanie"), animation_nav_row)
        self.inspector_animation_layout.addRow(make_label("Import / eksport"), animation_import_row)
        self.inspector_animation_layout.addRow(make_label("Edycja"), animation_edit_row)
        self.inspector_animation_layout.addRow(make_label("Oś czasu"), self.bg_animation_timeline)
        self.inspector_animation_layout.addRow(make_label("Klatki"), self.bg_animation_list)

        self.inspector_tabs.addTab(self.inspector_general, "Ogólne")
        self.inspector_tabs.addTab(self.inspector_content, "Treść")
        self.inspector_tabs.addTab(self.inspector_appearance, "Styl")
        self.inspector_tabs.addTab(self.inspector_geometry, "Pozycja")
        self.inspector_tabs.addTab(self.inspector_image, "Obraz")
        self.inspector_tabs.addTab(self.inspector_media, "Multimedia")
        self.inspector_tabs.addTab(self.inspector_animation, "Animacja")

        compact_widgets = [
            self.designer_id_edit,
            self.designer_text_edit,
            self.designer_label_edit,
            self.designer_format_edit,
            self.designer_source_combo,
            self.designer_align_combo,
            self.designer_font_family_combo,
            self.designer_font_size_spin,
            self.designer_color_edit,
            self.designer_label_color_edit,
            self.designer_value_color_edit,
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
            self.panel_radius_spin,
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
                    self.quick_add_now_playing_btn,
                    self.quick_add_now_playing_hero_btn,
                    self.quick_add_now_playing_mini_btn,
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
        if hasattr(self, "designer_raise_selected_btn"):
            self._apply_equal_width_for_group(
                [
                    self.designer_raise_selected_btn,
                    self.designer_lower_selected_btn,
                    self.designer_remove_btn,
                ],
                extra_px=int(22 * scale),
                min_px=int(88 * scale),
                max_px=int(160 * scale),
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
            self.designer_component_search.setMaximumHeight(30 if short else 32)
        if hasattr(self, "designer_quick_add_toggle_btn"):
            self.designer_quick_add_toggle_btn.setMaximumHeight(30 if short else 32)
        if hasattr(self, "props_box"):
            self.props_box.setMinimumWidth(max(270, int((300 if compact else 360) * scale)))
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
        compact_quick_add = compact_window or short
        show_quick_add = not compact_quick_add or bool(getattr(self, "designer_quick_add_toggle_btn", None) and self.designer_quick_add_toggle_btn.isChecked())
        self._set_designer_inspector_docked_bottom(dock_inspector_bottom)
        if hasattr(self, "designer_elements_box"):
            self.designer_elements_box.setVisible(True)
        if hasattr(self, "designer_quick_add_container"):
            self.designer_quick_add_container.setVisible(show_quick_add)
        if hasattr(self, "designer_quick_add_toggle_btn"):
            self.designer_quick_add_toggle_btn.setVisible(True)
            self.designer_quick_add_toggle_btn.setText(
                "Ukryj +" if compact_quick_add and show_quick_add else ("+ komponent" if compact_quick_add else "Komponenty")
            )
        if hasattr(self, "designer_inspector_container"):
            self.designer_inspector_container.setVisible(True)
        if hasattr(self, "designer_collection_hint"):
            self.designer_collection_hint.setVisible(not short)
        if hasattr(self, "designer_selection_label"):
            self.designer_selection_label.setVisible(not short)
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
            self.designer_assets_toggle_btn.setText("Ukryj multi" if assets_expanded and not animation_mode else "Multimedia")
            self.designer_assets_toggle_btn.setVisible(True)
        if hasattr(self, "designer_animation_mode_btn"):
            self.designer_animation_mode_btn.setText("Wyjdź z anim." if animation_mode else "Animacja")
        if hasattr(self, "designer_details_toggle_btn"):
            self.designer_details_toggle_btn.setText("Ukryj wsk." if details_expanded else "Wsk.")
        if short and hasattr(self, "preview_info_label"):
            self.preview_info_label.setText("Kliknij, przeciągnij lub zaznacz element na podglądzie.")

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
            self.header_donate_btn.setText(self._tr("Donate / Support", "Donate / Wspomóż"))
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
            self.studio_sections_tabs.setTabText(1, "Designer")
        if hasattr(self, "appearance_box"):
            self.appearance_box.setTitle(self._tr("App Appearance", "Wygląd Aplikacji"))
        if hasattr(self, "paths_box"):
            self.paths_box.setTitle(self._tr("Paths and Integration", "Ścieżki i Integracja"))
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
                    self.header_language_combo.setCurrentIndex(idx)
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
        if hasattr(self, "studio_toolbar_apply_btn"):
            self.studio_toolbar_apply_btn.setToolTip("Renderuje motyw i wysyła go na LCD.")
        if hasattr(self, "designer_import_image_btn"):
            self.designer_import_image_btn.setToolTip("Importuje obraz, przygotowuje go pod LCD i dodaje jako warstwę Image.")
        if hasattr(self, "bg_prepare_btn"):
            self.bg_prepare_btn.setToolTip("Importuje i przygotowuje obraz tła w katalogu assetów motywu.")
        QMessageBox.information(
            self,
            "Pierwsze kroki",
            "1. Biblioteka Motywów: zacznij od szablonu albo galerii motywów.\n"
            "2. Designer: klikaj i przeciągaj elementy bezpośrednio na preview.\n"
            "3. Importuj tło / obraz: assety zapisują się automatycznie do katalogu bieżącego motywu.",
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
            if self.studio_sections_tabs.currentIndex() == 0:
                self._set_shell_nav_active(getattr(self, "nav_library_btn", None))
            else:
                self._set_shell_nav_active(getattr(self, "nav_designer_btn", None))

    def _go_library(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(1)
        if hasattr(self, "studio_sections_tabs"):
            self.studio_sections_tabs.setCurrentIndex(0)
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
        self._sync_shell_navigation()

    def _go_logs(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(3)
        self._sync_shell_navigation()

    def _go_config(self) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(2)
        self._sync_shell_navigation()

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
            QMessageBox.warning(self, "Brak Pillow", "Moduł przygotowania obrazów nie jest dostępny.")
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

    def _current_animation_effect(self) -> dict[str, object]:
        if self.theme_doc_model is None:
            return {}
        effects = self.theme_doc_model.setdefault("effects", {})
        animation = effects.setdefault("animation", {})
        if not isinstance(animation, dict):
            animation = {}
            effects["animation"] = animation
        animation.setdefault("enabled", False)
        animation.setdefault("use_as_background", True)
        animation.setdefault("fps", 12.0)
        animation.setdefault("current_frame", 0)
        animation.setdefault("loop", True)
        animation.setdefault("frame_paths", [])
        animation.setdefault("frame_durations_ms", [])
        return animation

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
            self.bg_animation_count_label.setText(f"{count} klatek")
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
        copied_paths: list[str] = []
        if len(sources) == 1 and sources[0].suffix.lower() == ".zt":
            if extract_ttcr_zt_frames is None:
                return []
            target_dir = self._theme_assets_dir() / "animation_frames"
            target_dir.mkdir(parents=True, exist_ok=True)
            theme_stem = Path(self.theme_doc_path_edit.text() or "theme").stem
            frames = extract_ttcr_zt_frames(sources[0], target_dir, f"{theme_stem}_anim")
            for frame in frames:
                copied_paths.append(self._theme_display_path(frame))
            return copied_paths
        for source in sources:
            if not source.exists():
                continue
            copied = self._copy_animation_frame_asset(source, prefix="anim")
            copied_paths.append(self._theme_display_path(copied))
        return copied_paths

    def _render_current_animation_frame_image(self) -> "Image.Image | None":
        if render_theme_document is None or self.theme_doc_model is None:
            return None
        try:
            document = normalize_theme_document(self.theme_doc_model)
            return render_theme_document(ThemeDocument(document), base_dir=self._theme_base_dir())
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
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            self._refresh_animation_controls()
            return
        clamped = min(max(0, int(index)), len(frame_paths) - 1)
        animation["current_frame"] = clamped
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
            empty_text="Podgląd tła",
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
                f"Wybrano klatkę {clamped + 1}/{len(frame_paths)}. W trybie zwykłym pełny render uruchamiasz ręcznie."
            )

    def _refresh_animation_frame_list(self) -> None:
        if not hasattr(self, "bg_animation_list"):
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        current = min(max(0, int(animation.get("current_frame", 0))), max(0, len(frame_paths) - 1))
        self.bg_animation_list.blockSignals(True)
        self.bg_animation_list.clear()
        for idx, raw in enumerate(frame_paths):
            resolved = self._resolve_theme_asset_path(str(raw))
            duration_ms = frame_durations[idx] if idx < len(frame_durations) else max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
            item = QListWidgetItem(f"{idx + 1:03d}  {Path(str(raw)).name}  ·  {duration_ms} ms")
            item.setData(Qt.UserRole, str(raw))
            if resolved.exists():
                pixmap = QPixmap(str(resolved))
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap.scaled(96, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            item.setToolTip(str(resolved))
            self.bg_animation_list.addItem(item)
        if frame_paths:
            self.bg_animation_list.setCurrentRow(current)
        self.bg_animation_list.blockSignals(False)
        if hasattr(self, "bg_animation_timeline"):
            self.bg_animation_timeline.set_timeline(frame_durations[: len(frame_paths)], current)
        has_selection = self.bg_animation_list.currentRow() >= 0
        self.bg_animation_remove_btn.setEnabled(has_selection)
        self.bg_animation_duplicate_btn.setEnabled(has_selection)
        self.bg_animation_up_btn.setEnabled(has_selection and self.bg_animation_list.currentRow() > 0)
        self.bg_animation_down_btn.setEnabled(has_selection and self.bg_animation_list.currentRow() < len(frame_paths) - 1)

    def _update_animation_preview_timer(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        should_run = (
            bool(self._animation_preview_active)
            and self._animation_edit_mode_enabled()
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
            self.bg_animation_play_btn.setText("⏸ Pauza" if should_run else "▶ Odtwórz")

    def append_background_animation_frames(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Dodaj klatki animacji",
            str(Path.cwd()),
            "Animacje/ramki (*.zt *.jpg *.jpeg *.png *.webp *.bmp);;All files (*)",
        )
        if not selected:
            return
        sources = [Path(item).expanduser() for item in selected]
        copied_paths = self._collect_animation_frame_paths(sources)
        if not copied_paths:
            QMessageBox.warning(self, "Animacja", "Nie udało się dodać nowych klatek.")
            return
        self.push_designer_history()
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        default_duration = max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0))))))
        frame_paths.extend(copied_paths)
        frame_durations.extend([default_duration] * len(copied_paths))
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations
        animation["enabled"] = True
        if len(frame_paths) == len(copied_paths):
            animation["current_frame"] = 0
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._animation_preview_active = False
        self._refresh_animation_frame_list()
        self._rebuild_theme_asset_gallery()
        self.preview_info_label.setText(f"Dodano {len(copied_paths)} klatek animacji.")
        self.schedule_preview_theme_doc()

    def duplicate_selected_animation_frame(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        if not frame_paths:
            return
        row = self.bg_animation_list.currentRow()
        if row < 0 or row >= len(frame_paths):
            return
        source = self._resolve_theme_asset_path(str(frame_paths[row]))
        if not source.exists():
            QMessageBox.warning(self, "Animacja", f"Nie znaleziono klatki źródłowej:\n{source}")
            return
        copied = self._copy_animation_frame_asset(source, prefix="dup")
        duration_ms = frame_durations[row] if row < len(frame_durations) else max(1, int(self.bg_animation_duration_spin.value()))
        self.push_designer_history()
        frame_paths.insert(row + 1, self._theme_display_path(copied))
        frame_durations.insert(row + 1, duration_ms)
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations
        animation["current_frame"] = row + 1
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self.bg_animation_list.setCurrentRow(row + 1)
        self._rebuild_theme_asset_gallery()
        self.preview_info_label.setText("Zduplikowano klatkę animacji.")
        self.schedule_preview_theme_doc()

    def insert_blank_animation_frame(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        blank = self._create_blank_animation_frame_asset()
        if blank is None:
            QMessageBox.warning(self, "Animacja", "Nie udało się utworzyć pustej klatki.")
            return
        insert_at = self.bg_animation_list.currentRow()
        if insert_at < 0:
            insert_at = len(frame_paths)
        else:
            insert_at += 1
        self.push_designer_history()
        frame_paths.insert(insert_at, self._theme_display_path(blank))
        frame_durations.insert(insert_at, max(1, int(self.bg_animation_duration_spin.value())))
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations
        animation["enabled"] = True
        animation["use_as_background"] = True
        animation["current_frame"] = insert_at
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self.bg_animation_list.setCurrentRow(insert_at)
        self._rebuild_theme_asset_gallery()
        self.preview_info_label.setText("Dodano pustą klatkę animacji.")
        self.schedule_preview_theme_doc()

    def remove_selected_animation_frames(self) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            return
        rows = sorted({idx.row() for idx in self.bg_animation_list.selectedIndexes()})
        if not rows:
            row = self.bg_animation_list.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            return
        self.push_designer_history()
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        for row in reversed(rows):
            if 0 <= row < len(frame_paths):
                del frame_paths[row]
            if 0 <= row < len(frame_durations):
                del frame_durations[row]
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations
        if not frame_paths:
            animation["enabled"] = False
            animation["current_frame"] = 0
        else:
            animation["current_frame"] = min(int(animation.get("current_frame", 0)), len(frame_paths) - 1)
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self.schedule_preview_theme_doc()

    def move_selected_animation_frames(self, delta: int) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            return
        rows = sorted({idx.row() for idx in self.bg_animation_list.selectedIndexes()})
        if len(rows) != 1:
            return
        row = rows[0]
        target = row + int(delta)
        if target < 0 or target >= len(frame_paths):
            return
        self.push_designer_history()
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        frame_paths[row], frame_paths[target] = frame_paths[target], frame_paths[row]
        if row < len(frame_durations) and target < len(frame_durations):
            frame_durations[row], frame_durations[target] = frame_durations[target], frame_durations[row]
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations
        animation["current_frame"] = target
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._refresh_animation_frame_list()
        self.bg_animation_list.setCurrentRow(target)
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
        if self.theme_doc_model is None:
            return
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            QMessageBox.information(self, "Eksport animacji", "Brak klatek animacji do eksportu.")
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Zapisz eksport animacji",
            str((Path.cwd() / "exports" / f"{Path(self.theme_doc_path_edit.text() or 'motyw').stem}_animation.zip").resolve()),
            "ZIP (*.zip)",
        )
        if not selected:
            return
        target = Path(selected).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        document = normalize_theme_document(self.theme_doc_model)
        frame_durations = animation.get("frame_durations_ms", []) if isinstance(animation.get("frame_durations_ms", []), list) else []
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "type": "trofeo-animation-export",
                "theme_name": document.get("meta", {}).get("name", "Motyw"),
                "fps": float(animation.get("fps", 12.0)),
                "loop": bool(animation.get("loop", True)),
                "frame_count": len(frame_paths),
                "frame_durations_ms": frame_durations[: len(frame_paths)],
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for idx in range(len(frame_paths)):
                theme_frame = json.loads(json.dumps(document))
                theme_frame.setdefault("effects", {}).setdefault("animation", {})
                theme_frame["effects"]["animation"]["current_frame"] = idx
                image = render_theme_document(ThemeDocument(normalize_theme_document(theme_frame)), base_dir=self._theme_base_dir())
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                zf.writestr(f"frames/frame_{idx:04d}.png", buffer.getvalue())
        self.preview_info_label.setText(f"Wyeksportowano animację: {target.name}")
        self.append_log(f"[animation-export] {target}")

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
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if len(frame_paths) <= 1:
            self._animation_preview_active = False
            self._update_animation_preview_timer()
            return
        current = int(animation.get("current_frame", 0))
        next_index = current + 1
        if next_index >= len(frame_paths):
            if bool(animation.get("loop", True)):
                next_index = 0
            else:
                self._animation_preview_active = False
                self._update_animation_preview_timer()
                return
        self._set_current_animation_frame(next_index, persist=False)

    def import_background_animation(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
            if self.theme_doc_model is None:
                return
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Wybierz klatki animacji lub kontener TTCR",
            str(Path.cwd()),
            "Animacje/ramki (*.zt *.jpg *.jpeg *.png *.webp *.bmp);;All files (*)",
        )
        if not selected:
            return
        sources = [Path(item).expanduser() for item in selected]
        copied_paths = self._collect_animation_frame_paths(sources)
        if not copied_paths:
            QMessageBox.warning(self, "Import animacji", "Nie udało się przygotować klatek animacji.")
            return
        self.push_designer_history()
        animation = self._current_animation_effect()
        animation["frame_paths"] = copied_paths
        animation["frame_durations_ms"] = [max(1, int(round(1000.0 / max(1.0, float(animation.get("fps", 12.0)))))) for _ in copied_paths]
        animation["enabled"] = True
        animation["use_as_background"] = True
        animation["fps"] = float(animation.get("fps", 12.0))
        animation["current_frame"] = 0
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._animation_preview_active = False
        self._refresh_animation_frame_list()
        self._set_image_preview_label(self.background_preview_label, copied_paths[0], empty_text="Podgląd tła")
        self._rebuild_theme_asset_gallery()
        self.preview_info_label.setText(f"Zaimportowano animację: {len(copied_paths)} klatek.")
        self.schedule_preview_theme_doc()

    def clear_background_animation(self) -> None:
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        animation = self._current_animation_effect()
        animation["frame_paths"] = []
        animation["frame_durations_ms"] = []
        animation["enabled"] = False
        animation["current_frame"] = 0
        self.write_designer_to_json()
        self._refresh_animation_controls()
        self._sync_designer_preview_policy()
        self._animation_preview_active = False
        self._refresh_animation_frame_list()
        self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text="Podgląd tła")
        self.schedule_preview_theme_doc()

    def nudge_animation_frame(self, delta: int) -> None:
        animation = self._current_animation_effect()
        frame_paths = animation.get("frame_paths", []) if isinstance(animation.get("frame_paths", []), list) else []
        if not frame_paths:
            return
        current = int(animation.get("current_frame", 0))
        animation["current_frame"] = min(max(0, current + delta), len(frame_paths) - 1)
        self._refresh_animation_controls()
        self._set_current_animation_frame(int(animation["current_frame"]), persist=True)

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
        if action == "status":
            self._status_in_flight = False
        if is_designer_preview:
            self._preview_request_in_flight = False
        if action in {"theme-doc-load", "studio-theme-save", "studio-theme-apply"} or is_designer_preview:
            self._set_designer_toolbar_busy("theme-doc-preview" if is_designer_preview else action, False)
        is_template_preview = action.startswith("template-preview::")
        quiet_actions = {
            "theme-schema",
            "themes",
            "playlist",
            "theme-doc-preview",
        }

        if not ok:
            self.append_log(f"[{action}] ERROR: {payload}")
            if action in {"theme-doc-load", "studio-theme-save", "studio-theme-apply"} or is_designer_preview:
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
                        QMessageBox.warning(self, "Błąd motywu", str(exc))
                        normalized = None
                    if normalized is not None:
                        self.theme_doc_model = deepcopy(normalized)
                        self._set_theme_doc_editor_document(normalized)
                        self.refresh_designer_element_list()
                        self._load_background_fields()
                        self._sync_designer_preview_policy()
                        self.load_selected_designer_item()
                        self._update_preview_canvas_overlay()
                resolved_path = result.get("resolved_path")
                if resolved_path:
                    self.theme_doc_path_edit.setText(str(resolved_path))
                self._rebuild_theme_asset_gallery()
                if action == "theme-doc-load":
                    self._set_designer_toolbar_feedback(f"Wczytano motyw: {Path(str(resolved_path or self.theme_doc_path_edit.text())).name}")
                    self.preview_theme_doc()
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
                if image_path:
                    pixmap = QPixmap(image_path)
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
        self._rebuild_runtime_theme_cards()
        self._rebuild_library_theme_browser()
        self._apply_startup_theme_if_needed()

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
        self.api_call("config", "POST", "/v1/config", payload)

    def browse_image(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz obraz",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All files (*)",
        )
        if selected:
            self.image_edit.setText(selected)

    def send_image(self) -> None:
        image_path = self.image_edit.text().strip()
        if not image_path:
            QMessageBox.information(self, "Info", "Podaj ścieżkę do obrazu.")
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
            "Wybierz plik theme",
            str(Path.cwd()),
            "Theme files (*.json *.png *.jpg *.jpeg *.bmp *.webp *.gif);;JSON (*.json);;Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All files (*)",
        )
        if selected:
            self.theme_path_edit.setText(selected)

    def add_or_update_theme(self) -> None:
        name = self.theme_name_edit.text().strip()
        path = self.theme_path_edit.text().strip()
        if not name or not path:
            QMessageBox.information(self, "Info", "Podaj nazwę i plik theme.")
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
            QMessageBox.information(self, "Info", "Brak wybranego theme.")
            return
        payload = {"name": name}
        self.api_call("theme-remove", "POST", "/v1/themes/remove", payload, timeout=10.0)

    def apply_theme(self) -> None:
        name = self.theme_combo.currentText().strip()
        if not name:
            QMessageBox.information(self, "Info", "Brak wybranego theme.")
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
            image = render_theme_file(template_path)
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
            pixmap = self._render_template_thumbnail(path)
            if pixmap is not None and not pixmap.isNull():
                return pixmap
        if path:
            resolved = self._resolve_theme_asset_path(path)
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self._render_template_placeholder(str(item.get("name", "Theme")), "#5ec8ff", size)

    def _render_theme_preview_pixmap(self, item: dict[str, Any], size: QSize) -> QPixmap:
        path = str(item.get("path", "")).strip()
        theme_name = str(item.get("name", "Theme")).strip() or "Theme"
        theme_type = str(item.get("type", "image")).strip()
        if theme_type == "theme-doc" and render_theme_file is not None and path:
            try:
                image = render_theme_file(path)
                try:
                    raw = json.loads(Path(path).read_text(encoding="utf-8"))
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
        viewport_width = 0
        if hasattr(self, "theme_browser_scroll"):
            try:
                viewport_width = self.theme_browser_scroll.viewport().width()
            except Exception:
                viewport_width = 0
        container_width = max(
            720,
            viewport_width or (self.library_theme_cards_container.width() if hasattr(self, "library_theme_cards_container") else 960),
        )
        if container_width >= 1450:
            columns = 4
        elif container_width >= 1040:
            columns = 3
        elif container_width >= 720:
            columns = 2
        else:
            columns = 1
        for idx, (name, item) in enumerate(items):
            asset_count, animation_count = self._theme_card_stats(item)
            category = self._theme_card_category(item)
            card = AnimatedCardFrame("libraryCard")
            card.setObjectName("libraryCard")
            card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            card.setMinimumHeight(228)
            card.setMaximumHeight(228)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(6)
            thumb = QLabel()
            thumb.setObjectName("templateCardThumb")
            thumb.setMinimumSize(220, 92)
            thumb.setMaximumHeight(92)
            thumb.setAlignment(Qt.AlignCenter)
            thumb.setPixmap(
                self._runtime_theme_card_pixmap(item, thumb.size()).scaled(
                    thumb.size(),
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
            if name == current:
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
            actions = QHBoxLayout()
            actions.setSpacing(6)
            select_btn = QPushButton(self._tr("Edit", "Edytuj") if str(item.get("type", "")) == "theme-doc" else self._tr("Select", "Wybierz"))
            preview_btn = QPushButton(self._tr("Preview", "Podgląd"))
            apply_btn = QPushButton(self._tr("Apply", "Zastosuj"))
            duplicate_btn = QPushButton(self._tr("Duplicate", "Duplikuj"))
            remove_btn = QPushButton(self._tr("Remove", "Usuń"))
            apply_btn.setObjectName("primaryButton" if name == current else "secondaryAccentButton")
            for btn in (select_btn, preview_btn, apply_btn, duplicate_btn, remove_btn):
                btn.setMinimumHeight(28)
                btn.setCursor(Qt.PointingHandCursor)
            select_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item: self._library_select_theme(theme_name, theme_item))
            preview_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item: self._open_theme_preview_dialog(theme_name, theme_item))
            apply_btn.clicked.connect(lambda _checked=False, theme_name=name: self._apply_runtime_theme_card(theme_name))
            duplicate_btn.clicked.connect(lambda _checked=False, theme_name=name, theme_item=item: self._duplicate_theme_card(theme_name, theme_item))
            remove_btn.clicked.connect(lambda _checked=False, theme_name=name: self._remove_runtime_theme_card(theme_name))
            actions.addWidget(select_btn, 2)
            actions.addWidget(preview_btn, 1)
            actions.addWidget(apply_btn, 2)
            actions.addWidget(duplicate_btn, 1)
            actions.addWidget(remove_btn, 1)
            layout.addLayout(actions)
            row = idx // columns
            col = idx % columns
            self.library_theme_cards_layout.addWidget(card, row, col)
        for col in range(columns):
            self.library_theme_cards_layout.setColumnStretch(col, 1)
        row_count = max(1, (len(items) + columns - 1) // columns)
        visible_rows = min(row_count, 3)
        card_height = 228
        row_gap = self.library_theme_cards_layout.verticalSpacing()
        viewport_height = 14 + (visible_rows * card_height) + (max(0, visible_rows - 1) * row_gap) + 10
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
            raw = json.loads(resolved.read_text(encoding="utf-8"))
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
        edit_action = menu.addAction("Edytuj")
        preview_action = menu.addAction("Podgląd")
        apply_action = menu.addAction("Zastosuj")
        duplicate_action = menu.addAction("Duplikuj")
        remove_action = menu.addAction("Usuń")
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
            QMessageBox.information(self, "Duplikowanie motywu", "Duplikowanie jest dostępne tylko dla zapisanych motywów edytowalnych.")
            return
        try:
            src_path = self._resolve_theme_asset_path(path)
            document = json.loads(src_path.read_text(encoding="utf-8"))
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
            QMessageBox.warning(self, "Duplikowanie motywu", str(exc))

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
        self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text="Podgląd tła")
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
            QMessageBox.warning(self, "Import TTCR", f"Nie udało się zapisać poprawionego mapowania statystyk:\n{exc}")

    def import_ttcr_theme_bundle(self) -> None:
        if import_ttcr_theme is None:
            QMessageBox.warning(self, "Import TTCR", "Moduł importu TTCR nie jest dostępny.")
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
            QMessageBox.warning(self, "Import TTCR", str(exc))
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
        self._set_image_preview_label(self.designer_image_preview_label, new_item["path"], empty_text="Podgląd obrazu")
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
                document = json.loads(Path(path).read_text(encoding="utf-8"))
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
            "Zapisz nowy motyw",
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
            document = json.loads(src_path.read_text(encoding="utf-8"))
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
            raw = json.loads(resolved.read_text(encoding="utf-8"))
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
        if preview_after:
            self.preview_theme_doc()

    def browse_theme_doc_path(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik motywu",
            str(Path.cwd() / "themes"),
            "JSON (*.json);;All files (*)",
        )
        if selected:
            self.theme_doc_path_edit.setText(selected)

    def use_selected_theme_doc(self) -> None:
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
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "Błąd motywu", f"Nie udało się odczytać danych motywu: {exc}")
            return None
        if not isinstance(document, dict):
            QMessageBox.warning(self, "Błąd motywu", "Plik motywu ma niepoprawny format.")
            return None
        return document

    def _set_theme_doc_editor_document(self, document: dict[str, Any]) -> None:
        self.theme_doc_editor.setPlainText(json.dumps(document, ensure_ascii=False, indent=2))

    def _current_theme_document(self, *, allow_editor_fallback: bool = True) -> dict[str, Any] | None:
        if isinstance(self.theme_doc_model, dict):
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
            QMessageBox.warning(self, "Błąd motywu", str(exc))
            return None
        self.theme_doc_model = deepcopy(normalized)
        self._set_theme_doc_editor_document(normalized)
        return deepcopy(normalized)

    def load_theme_doc(self) -> None:
        theme_path = self.theme_doc_path_edit.text().strip()
        if not theme_path:
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
            QMessageBox.information(self, "Info", "Najpierw wybierz lub utwórz motyw.")
            return
        document = self._current_theme_document()
        if document is None:
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
        return self._designer_animation_frame_count() >= 40

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
        if frame_count >= 200:
            return 2200
        if frame_count >= 80:
            return 1600
        if frame_count >= 40:
            return 1000
        return 300

    def _designer_preview_timeout_s(self) -> float:
        frame_count = self._designer_animation_frame_count()
        if frame_count >= 200:
            return 180.0
        if frame_count >= 80:
            return 120.0
        if frame_count >= 40:
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
        return {
            "id": f"image_{index}",
            "path": "reference_frame_trcc.jpg",
            "rect": [100, 100, 240, 120],
            "fit": "contain",
            "opacity": 1.0,
            "rotation": 0,
            "z_index": 100,
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
        background = self.theme_doc_model.setdefault("background", {})
        panels = background.setdefault("panels", [])
        panel_id = self._next_item_id("panels", "panel_media")
        panels.append(
            {
                "id": panel_id,
                "rect": [40, 320, 760, 128],
                "radius": 16,
                "fill": [10, 16, 26, 210],
                "z_index": 95,
                "visible": True,
                "locked": False,
            }
        )
        images = self.theme_doc_model.setdefault("images", [])
        images.append(
            {
                "id": self._next_item_id("images", "img_media_cover"),
                "path": "",
                "source": "media_cover",
                "rect": [52, 332, 104, 104],
                "fit": "cover",
                "opacity": 1.0,
                "radius": 18,
                "border_width": 2,
                "border_color": [235, 246, 255, 170],
                "glow_radius": 16,
                "glow_opacity": 0.42,
                "rotation": 0,
                "z_index": 208,
                "visible": True,
                "locked": False,
            }
        )
        stats = self.theme_doc_model.setdefault("stats", [])
        items = [
            ("media_title", "", 176, 336, 586, 32, 28, True),
            ("media_artist", "", 176, 374, 586, 28, 22, False),
            ("media_app", "App", 176, 406, 240, 24, 18, False),
            ("media_state", "State", 434, 406, 328, 24, 18, False),
        ]
        for source, label, x, y, w, h, size, bold in items:
            stats.append(
                {
                    "id": self._next_item_id("stats", f"stat_{source}"),
                    "label": label,
                    "source": source,
                    "format": "Now Playing: {value}" if source == "media_title" else "{value}",
                    "x": x,
                    "y": y,
                    "box_width": w,
                    "box_height": h,
                    "font_family": "DejaVu Sans",
                    "font_size": size,
                    "font_bold": bold,
                    "font_italic": False,
                    "font_underline": False,
                    "marquee": source == "media_title",
                    "marquee_speed": 60.0,
                    "label_color": [160, 196, 232],
                    "value_color": [235, 246, 255],
                    "align": "left",
                    "z_index": 210 if source == "media_title" else 209,
                    "visible": True,
                    "locked": False,
                }
            )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText("Dodano widget Now Playing (MPRIS): cover, title, artist, app, state.")
        self.schedule_preview_theme_doc()

    def add_now_playing_widget_hero(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        background = self.theme_doc_model.setdefault("background", {})
        panels = background.setdefault("panels", [])
        panels.append(
            {
                "id": self._next_item_id("panels", "panel_media_hero"),
                "rect": [36, 250, 932, 176],
                "radius": 26,
                "fill": [6, 10, 18, 220],
                "z_index": 94,
                "visible": True,
                "locked": False,
            }
        )
        images = self.theme_doc_model.setdefault("images", [])
        images.append(
            {
                "id": self._next_item_id("images", "img_media_video_backdrop"),
                "path": "",
                "source": "media_video_frame",
                "rect": [44, 258, 916, 160],
                "fit": "cover",
                "opacity": 0.22,
                "radius": 24,
                "border_width": 0,
                "border_color": [0, 0, 0, 0],
                "glow_radius": 22,
                "glow_opacity": 0.24,
                "rotation": 0,
                "z_index": 205,
                "visible": True,
                "locked": False,
            }
        )
        images.append(
            {
                "id": self._next_item_id("images", "img_media_cover_hero"),
                "path": "",
                "source": "media_cover",
                "rect": [64, 270, 136, 136],
                "fit": "cover",
                "opacity": 1.0,
                "radius": 24,
                "border_width": 2,
                "border_color": [235, 246, 255, 170],
                "glow_radius": 18,
                "glow_opacity": 0.42,
                "rotation": 0,
                "z_index": 208,
                "visible": True,
                "locked": False,
            }
        )
        stats = self.theme_doc_model.setdefault("stats", [])
        items = [
            ("media_title", "", 224, 278, 700, 38, 32, True, "Now Playing: {value}"),
            ("media_artist", "", 224, 320, 700, 30, 24, False, "{value}"),
            ("media_app", "App", 224, 358, 260, 24, 18, False, "{value}"),
            ("media_state", "State", 508, 358, 240, 24, 18, False, "{value}"),
        ]
        for source, label, x, y, w, h, size, bold, fmt in items:
            stats.append(
                {
                    "id": self._next_item_id("stats", f"stat_{source}_hero"),
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
                    "marquee": source == "media_title",
                    "marquee_speed": 64.0,
                    "label_color": [160, 196, 232],
                    "value_color": [244, 248, 255],
                    "align": "left",
                    "z_index": 210 if source == "media_title" else 209,
                    "visible": True,
                    "locked": False,
                }
            )
        self.write_designer_to_json()
        self.refresh_designer_element_list()
        self.preview_info_label.setText(
            "Dodano widget Now Playing Hero: duża okładka + szeroki media-backdrop. Dla lokalnych playerów wideo tło użyje realnej klatki, a w pozostałych przypadkach fallbacku do okładki."
        )
        self.schedule_preview_theme_doc()

    def add_now_playing_widget_mini(self) -> None:
        if self.theme_doc_model is None:
            self.reload_designer_from_json()
        if self.theme_doc_model is None:
            return
        self.push_designer_history()
        background = self.theme_doc_model.setdefault("background", {})
        panels = background.setdefault("panels", [])
        panels.append(
            {
                "id": self._next_item_id("panels", "panel_media_mini"),
                "rect": [1520, 24, 360, 96],
                "radius": 14,
                "fill": [8, 14, 24, 200],
                "z_index": 96,
                "visible": True,
                "locked": False,
            }
        )
        stats = self.theme_doc_model.setdefault("stats", [])
        stats.append(
            {
                "id": self._next_item_id("stats", "stat_media_title_mini"),
                "label": "",
                "source": "media_title",
                "format": "♫ {value}",
                "x": 1540,
                "y": 42,
                "box_width": 320,
                "box_height": 26,
                "font_family": "DejaVu Sans",
                "font_size": 20,
                "font_bold": True,
                "font_italic": False,
                "font_underline": False,
                "marquee": True,
                "marquee_speed": 68.0,
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
                "id": self._next_item_id("stats", "stat_media_artist_mini"),
                "label": "",
                "source": "media_artist",
                "format": "{value}",
                "x": 1540,
                "y": 74,
                "box_width": 320,
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
        self.preview_info_label.setText("Dodano widget Now Playing Mini.")
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
        for collection in ("panels", "images", "texts", "stats"):
            if collection == "panels":
                items = self.theme_doc_model.get("background", {}).get("panels", [])
            else:
                items = self.theme_doc_model.get(collection, [])
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                if collection in {"images", "panels"}:
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
            QMessageBox.warning(self, "Brak Pillow", "Moduł przygotowania obrazów nie jest dostępny.")
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
            QMessageBox.warning(self, "Brak pliku", f"Nie znaleziono obrazu:\n{resolved}")
            return
        dlg = ImagePrepDialog(self, resolved)
        if dlg.exec() != QDialog.Accepted or dlg.output_path is None:
            return
        source_edit.setText(str(dlg.output_path))
        self.append_log(f"[image-prep] {resolved} -> {dlg.output_path}")

    def import_background_image(self) -> None:
        if not self._image_tools_available():
            QMessageBox.warning(self, "Brak Pillow", "Moduł przygotowania obrazów nie jest dostępny.")
            return
        if not self._ensure_theme_doc_model():
            QMessageBox.warning(self, "Błąd motywu", "Najpierw wczytaj poprawny motyw w projektancie.")
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
            QMessageBox.warning(self, "Brak pliku", f"Nie znaleziono obrazu:\n{source}")
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
        self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text="Podgląd tła")

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
        self._set_image_preview_label(self.background_preview_label, "", empty_text="Podgląd tła")

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
            self.bg_animation_count_label.setText(f"{len(frame_paths)} klatek")
        finally:
            self._designer_updating = False
        self._refresh_all_color_previews()
        self._refresh_animation_controls()
        preview_path = self._current_animation_preview_path() if bool(animation.get("enabled", False)) and bool(animation.get("use_as_background", True)) else str(background.get("path", ""))
        self._set_image_preview_label(
            self.background_preview_label,
            preview_path,
            empty_text="Podgląd tła",
        )

    def reload_designer_from_json(self) -> None:
        document = self._parse_theme_doc_editor()
        if document is None:
            return
        try:
            self.push_designer_history()
            self.theme_doc_model = normalize_theme_document(document)
        except Exception as exc:
            QMessageBox.warning(self, "Błąd motywu", str(exc))
            return
        self._sync_designer_preview_policy()
        self._load_background_fields()
        self.refresh_designer_element_list()
        self._update_preview_canvas_overlay()
        self.preview_theme_doc()

    def write_designer_to_json(self) -> None:
        if self.theme_doc_model is None:
            QMessageBox.information(self, "Info", "Designer nie ma jeszcze wczytanego theme.")
            return
        self._set_theme_doc_editor_document(self.theme_doc_model)
        self._schedule_theme_autosave()

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
        }.get(collection, collection[:3].upper())
        prefix = f"[{type_tag}{':' + ''.join(flags) if flags else ''}] "
        if collection == "texts":
            text = str(item.get("text", "")).strip() or "Tekst"
            return f"{prefix}{text[:30]}"
        if collection == "stats":
            label = str(item.get("label", "")).strip()
            source = str(item.get("source", "")).strip() or "stat"
            title = f"{label} [{source}]" if label else source
            return f"{prefix}{title[:34]}"
        if collection == "panels":
            rect = item.get("rect", [0, 0, 0, 0])
            size = f"{rect[2]}x{rect[3]}" if isinstance(rect, list) and len(rect) == 4 else "panel"
            return f"{prefix}Panel {idx + 1} [{size}]"
        source = str(item.get("source", "")).strip()
        if source == "media_cover":
            return f"{prefix}Okładka Now Playing"
        if source == "media_video_frame":
            return f"{prefix}Kadr Media / Video"
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
        if source.startswith("media_") or source == "media_cover":
            return True
        if ident.startswith("panel_media") or ident.startswith("stat_media") or ident.startswith("img_media"):
            return True
        return "media" in ident or "now playing" in label

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
            item.setHidden(bool(needle) and needle not in hay)
        self._update_designer_element_list_height()

    def _update_designer_element_list_height(self) -> None:
        if not hasattr(self, "designer_element_list"):
            return
        row_heights: list[int] = []
        for row in range(self.designer_element_list.count()):
            item = self.designer_element_list.item(row)
            if item is None or item.isHidden():
                continue
            hint = item.sizeHint()
            row_heights.append(max(40, hint.height()))
        visible_rows = len(row_heights)
        spacing = max(0, self.designer_element_list.spacing())
        frame = max(6, self.designer_element_list.frameWidth() * 2)
        if visible_rows <= 0:
            target_height = 190
        else:
            body_height = sum(row_heights[:6]) + max(0, min(visible_rows, 6) - 1) * spacing
            target_height = frame + body_height + 8
        target_height = max(190, min(420, target_height))
        self.designer_element_list.setMinimumHeight(target_height)
        self.designer_element_list.setMaximumHeight(target_height)

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
                top_splitter.setSizes([1040, 300])
            elif preset_name == "compact":
                top_splitter.setSizes([900, 250])
            else:
                top_splitter.setSizes([980, 320])

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
            geometry_idx = self.inspector_tabs.indexOf(self.inspector_geometry)
            image_idx = self.inspector_tabs.indexOf(self.inspector_image)
            if general_idx >= 0:
                self.inspector_tabs.setTabVisible(general_idx, True)
            if content_idx >= 0:
                self.inspector_tabs.setTabVisible(content_idx, True)
            if appearance_idx >= 0:
                self.inspector_tabs.setTabVisible(appearance_idx, True)
            if geometry_idx >= 0:
                self.inspector_tabs.setTabVisible(geometry_idx, not simple)
            if image_idx >= 0:
                current_collection = self._selected_collection() if hasattr(self, "designer_kind_combo") else ""
                self.inspector_tabs.setTabVisible(image_idx, (not simple) or current_collection == "images")

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
        if collection in {"images", "panels"}:
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
            if selected_collection in {"images", "panels"}:
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
        visible_action = menu.addAction("Pokaż / Ukryj")
        lock_action = menu.addAction("Blokuj / Odblokuj")
        menu.addSeparator()
        up_action = menu.addAction("Warstwa +")
        down_action = menu.addAction("Warstwa -")
        menu.addSeparator()
        dup_action = menu.addAction("Duplikuj")
        del_action = menu.addAction("Usuń")
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

    def preview_zoom_fit(self) -> None:
        self.preview_label.set_zoom_mode("fit")

    def preview_zoom_set(self, percent: int) -> None:
        self.preview_label.set_zoom_percent(percent)

    def _apply_visibility_for_collection(self, collection: str) -> None:
        is_text = collection == "texts"
        is_stat = collection == "stats"
        is_image = collection == "images"
        is_panel = collection == "panels"
        supports_motion = collection in {"texts", "stats", "images", "panels"}

        self._set_tab_enabled_if_present(self.inspector_general, True)
        self._set_tab_enabled_if_present(self.inspector_content, is_text or is_stat)
        self._set_tab_enabled_if_present(self.inspector_appearance, is_text or is_stat or is_image or is_panel)
        self._set_tab_enabled_if_present(self.inspector_geometry, True)
        self._set_tab_enabled_if_present(self.inspector_image, is_image)

        self._set_form_row_visible(inspector_content_layout := self.inspector_content.layout(), self.row_content_text, self.designer_text_edit, is_text)
        self._set_form_row_visible(inspector_content_layout, self.row_content_label, self.designer_label_edit, is_stat)
        self._set_form_row_visible(inspector_content_layout, self.row_content_source, self.designer_source_combo, is_stat)
        self._set_form_row_visible(inspector_content_layout, self.row_content_format, self.designer_format_edit, is_stat)
        self.designer_source_combo.setToolTip("Źródło danych dla tej statystyki.")
        self.designer_format_edit.setPlaceholderText("{value}")
        self.designer_label_edit.setPlaceholderText("Np. CPU, RAM, Temp")

        appearance_layout = self.inspector_appearance.layout()
        self._set_form_row_visible(appearance_layout, self.row_appearance_font, self.font_row, is_text or is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_font_style, self.font_style_row, is_text or is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_align, self.designer_align_combo, is_text or is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_color, self.designer_color_row, is_text)
        self._set_form_row_visible(appearance_layout, self.row_appearance_label_color, self.designer_label_color_row, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_appearance_value_color, self.designer_value_color_row, is_stat)
        self._set_form_row_visible(appearance_layout, self.row_panel_fill, self.panel_fill_row, is_panel)
        self._set_form_row_visible(appearance_layout, self.row_panel_opacity, self.panel_opacity_spin, is_panel)
        self._set_form_row_visible(appearance_layout, self.row_panel_radius, self.panel_radius_spin, is_panel)

        geometry_layout = self.inspector_geometry.layout()
        self._set_form_row_visible(geometry_layout, self.row_geometry_x, self.designer_x_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_geometry_y, self.designer_y_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_geometry_w, self.designer_w_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_geometry_h, self.designer_h_spin, True)
        self._set_form_row_visible(geometry_layout, self.row_motion_enabled, self.motion_enabled_chk, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_range, self.motion_range_row, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_target_x, self.motion_target_x_spin, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_target_y, self.motion_target_y_spin, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_target_opacity, self.motion_target_opacity_spin, supports_motion)
        self._set_form_row_visible(geometry_layout, self.row_motion_actions, self.motion_actions_row, supports_motion)
        image_layout = self.inspector_image.layout()
        self._set_form_row_visible(image_layout, self.row_image_path, self.designer_path_row, is_image)
        self._set_form_row_visible(image_layout, self.row_image_fit, self.designer_fit_combo, is_image)
        self._set_form_row_visible(image_layout, self.row_image_opacity, self.designer_opacity_spin, is_image)
        self._set_form_row_visible(image_layout, self.row_image_rotation, self.designer_rotation_spin, is_image)
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
        else:
            self.preview_info_label.setText("Obraz: kliknij na podglądzie, aby ustawić pozycję albo zmień parametry w zakładce Obraz.")
            self.inspector_tabs.setCurrentWidget(self.inspector_image)

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
                    f"Grupa: {group_label or 'Wieloselekcja'} • {len(selected_multi_any)} elementów • {meta}"
                )
                self.inspector_selection_summary.setText(
                    "Dostępne są wspólne ustawienia: widoczność, blokada, warstwa i przesuwanie całej grupy."
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
                self._load_motion_track_fields(None, collection)
                self.inspector_tabs.setCurrentWidget(self.inspector_general)
                return

            if active_item is None:
                self.designer_selection_label.setText(
                    "Brak zaznaczenia. Wybierz warstwę z listy po lewej albo kliknij element na podglądzie. "
                    "Szybki start: Tekst, Statystyka, Obraz, Panel."
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
                self.designer_label_color_edit.clear()
                self.designer_value_color_edit.clear()
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
                return

            self.designer_selection_label.setText(
                f"Aktywny: {self._display_name_for_item(active_item, active_collection, active_row)}"
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
            self.designer_label_color_edit.setText(json.dumps(active_item.get("label_color", [220, 220, 220]), ensure_ascii=False))
            self.designer_value_color_edit.setText(json.dumps(active_item.get("value_color", [220, 220, 220]), ensure_ascii=False))
            self.designer_path_edit.setText(str(active_item.get("path", "")))
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
            else:
                self.panel_fill_edit.clear()
                self.panel_opacity_spin.setValue(1.0)
                self.panel_radius_spin.setValue(0)
            self._load_motion_track_fields(active_item, active_collection)
        finally:
            self._designer_updating = False
        self._refresh_all_color_previews()
        preview_image_path = ""
        if active_item is not None:
            preview_image_path = str(active_item.get("path", ""))
            if active_collection == "images" and str(active_item.get("source", "")).strip() in {"media_cover", "media_video_frame"}:
                preview_image_path = self._current_media_dynamic_path(str(active_item.get("source", "")).strip())
        self._set_image_preview_label(
            self.designer_image_preview_label,
            preview_image_path,
            empty_text="Podgląd obrazu",
        )
        self._update_preview_canvas_overlay()

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
        enabled_types = {"texts", "stats", "images", "panels"}
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
        if collection not in {"texts", "stats", "images", "panels"}:
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
            item["label"] = self.designer_label_edit.text()
            item["source"] = str(self.designer_source_combo.currentData() or self.designer_source_combo.currentText()).strip()
            item["format"] = self.designer_format_edit.text().strip() or "{value}"
            item["label_color"] = self._parse_color_line(
                self.designer_label_color_edit.text(),
                item.get("label_color", [220, 220, 220]),
            )
            item["value_color"] = self._parse_color_line(
                self.designer_value_color_edit.text(),
                item.get("value_color", [220, 220, 220]),
            )
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
            self._set_image_preview_label(self.designer_image_preview_label, preview_path, empty_text="Podgląd obrazu")
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
            QMessageBox.warning(self, "Brak Pillow", "Moduł przygotowania obrazów nie jest dostępny.")
            return
        if not self._ensure_theme_doc_model():
            QMessageBox.warning(self, "Błąd motywu", "Najpierw wczytaj poprawny motyw w projektancie.")
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
            QMessageBox.warning(self, "Brak pliku", f"Nie znaleziono obrazu:\n{source}")
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
                QMessageBox.warning(self, "Błąd motywu", "Najpierw wczytaj poprawny motyw w projektancie.")
                return
            if source.exists() and self._image_tools_available():
                prepared_path = self._run_theme_image_import(source, asset_kind="image", button_text="Importuj obraz")
                if prepared_path is not None:
                    self.designer_path_edit.setText(self._theme_display_path(prepared_path))
            else:
                self.designer_path_edit.setText(self._theme_display_path(source))
            self._set_image_preview_label(self.designer_image_preview_label, self.designer_path_edit.text(), empty_text="Podgląd obrazu")

    def browse_background_path(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz obraz tła",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All files (*)",
        )
        if selected:
            source = Path(selected).expanduser()
            if not source.is_absolute():
                source = (Path.cwd() / source).resolve()
            if not self._ensure_theme_doc_model():
                QMessageBox.warning(self, "Błąd motywu", "Najpierw wczytaj poprawny motyw w projektancie.")
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
            self._set_image_preview_label(self.background_preview_label, self.bg_path_edit.text(), empty_text="Podgląd tła")

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
        preview_path = self._current_animation_preview_path() if bool(animation.get("enabled", False)) and bool(animation.get("use_as_background", True)) else background.get("path", "")
        self._set_image_preview_label(self.background_preview_label, str(preview_path), empty_text="Podgląd tła")
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
            delta_x = int(x) - int(current_rect[0])
            delta_y = int(y) - int(current_rect[1])
            if delta_x or delta_y:
                for selected_collection, _row, selected_item in selected:
                    if bool(selected_item.get("locked", False)):
                        continue
                    if selected_collection in {"images", "panels"}:
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
            self._sync_drag_editor_state(collection, index)
            return
        if collection in {"images", "panels"}:
            rect = item.get("rect", [0, 0, 1, 1])
            if isinstance(rect, list) and len(rect) == 4:
                item["rect"] = [self._snap_value(int(x)), self._snap_value(int(y)), int(rect[2]), int(rect[3])]
        else:
            item["x"] = self._snap_value(int(x))
            item["y"] = self._snap_value(int(y))
        self._sync_drag_editor_state(collection, index)

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
        if collection in {"images", "panels"}:
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
            if selected_collection in {"images", "panels"}:
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
        for collection in ("texts", "stats", "images"):
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
                QMessageBox.warning(self, "Błąd motywu", str(exc))
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
