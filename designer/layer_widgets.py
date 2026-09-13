"""Qt widgets used by the Theme Designer layer list."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

TranslateFn = Callable[[str, str], str]


def _replace_combo_items_preserve_data(combo: object, items: list[tuple[str, str]], fallback: str) -> None:
    current = str(combo.currentData() or fallback)
    combo.blockSignals(True)
    try:
        combo.clear()
        for text, data in items:
            combo.addItem(text, data)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
    finally:
        combo.blockSignals(False)


def refresh_layer_panel_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh labels for the layer list panel and its filters."""
    if hasattr(owner, "designer_elements_box"):
        owner.designer_elements_box.setTitle("")
    if hasattr(owner, "designer_elements_title_label"):
        owner.designer_elements_title_label.setText(translate("Layers & components", "Warstwy i komponenty"))
    if hasattr(owner, "designer_component_search"):
        owner.designer_component_search.setPlaceholderText(translate("Search layers or text…", "Szukaj warstwy lub tekstu…"))
    if hasattr(owner, "designer_kind_combo"):
        _replace_combo_items_preserve_data(
            owner.designer_kind_combo,
            [
                (translate("Texts", "Teksty"), "texts"),
                (translate("Stats", "Statystyki"), "stats"),
                (translate("Images", "Obrazy"), "images"),
                (translate("Panels", "Panele"), "panels"),
                (translate("Widgets", "Widgety"), "widgets"),
            ],
            "texts",
        )
    if hasattr(owner, "designer_domain_combo"):
        _replace_combo_items_preserve_data(
            owner.designer_domain_combo,
            [
                (translate("All", "Wszystko"), "all"),
                (translate("System", "System"), "system"),
                (translate("Music", "Muzyka"), "music"),
                (translate("Weather", "Pogoda"), "weather"),
            ],
            "all",
        )
    if hasattr(owner, "designer_source_combo") and hasattr(owner, "_populate_designer_source_combo"):
        current_source = str(owner.designer_source_combo.currentData() or "").strip()
        owner._populate_designer_source_combo(current_source)


class LayerListWidget(QListWidget):
    rows_reordered = Signal()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        super().dropEvent(event)
        self.rows_reordered.emit()

    def selected_rows_or_current(self) -> list[int]:
        """Return selected rows, falling back to the current row."""
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if rows:
            return rows
        row = self.currentRow()
        return [row] if row >= 0 else []

    def visible_rows(self) -> list[int]:
        """Return all rows not hidden by filtering."""
        rows: list[int] = []
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and not item.isHidden():
                rows.append(row)
        return rows

    def select_rows(self, rows: list[int], *, current_row: int | None = None, skip_hidden: bool = True) -> None:
        """Apply selection rows while blocking intermediate selection signals."""
        unique_rows = sorted(set(rows))
        selectable_rows: list[int] = []
        for row in unique_rows:
            item = self.item(row)
            if item is None:
                continue
            if skip_hidden and item.isHidden():
                continue
            selectable_rows.append(row)
        if current_row is None:
            target_row = min(selectable_rows) if selectable_rows else -1
        elif skip_hidden and current_row not in selectable_rows:
            target_row = min(selectable_rows) if selectable_rows else -1
        else:
            target_row = int(current_row)
        self.blockSignals(True)
        try:
            self.clearSelection()
            for row in selectable_rows:
                item = self.item(row)
                if item is not None:
                    item.setSelected(True)
            self.setCurrentRow(int(target_row))
        finally:
            self.blockSignals(False)

    def row_ids(self) -> list[str]:
        """Return model ids in the current visual order."""
        return [str(self.item(row).data(Qt.UserRole) or "") for row in range(self.count())]

    def row_search_text(self, row: int) -> str:
        """Return text used by the layer search filter."""
        item = self.item(row)
        if item is None:
            return ""
        widget = self.itemWidget(item)
        if isinstance(widget, LayerRowWidget):
            return widget.search_text()
        return (item.text() or "").lower()


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

    def search_text(self) -> str:
        """Return searchable text for this row."""
        return " ".join(
            [
                self.title_label.text(),
                self.subtitle_label.text(),
                self.badge_label.text(),
            ]
        ).lower()

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
