"""Image, TTCR import and theme preview dialogs for the Qt frontend."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    from image_prep import prepare_image_for_canvas, render_prepared_image
except Exception:
    prepare_image_for_canvas = None
    render_prepared_image = None

IMAGE_PRESETS_PATH = Path(".trofeo-image-presets.json")


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
        if lowered.startswith("game_"):
            return "Gaming"
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

