"""Wrapping flow layout for dense Qt toolbars.

``QHBoxLayout`` does not wrap, so on narrow windows (or with fractional/HiDPI
scaling) its widgets get clipped or force a horizontal scrollbar. ``FlowLayout``
lays items out left to right and moves them to a new line when they no longer
fit, which keeps toolbars usable at any window width.
"""

from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QSpacerItem


class FlowLayout(QLayout):
    """A left-to-right layout that wraps items onto additional lines."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 6, v_spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list = []
        self._h_spacing = int(h_spacing)
        self._v_spacing = int(v_spacing)
        self.setContentsMargins(QMargins(margin, margin, margin, margin))

    def setSpacing(self, spacing: int) -> None:  # type: ignore[override]
        self._h_spacing = int(spacing)
        self._v_spacing = int(spacing)
        super().setSpacing(spacing)

    def addSpacing(self, px: int) -> None:
        self.addItem(QSpacerItem(int(px), 1, QSizePolicy.Fixed, QSizePolicy.Minimum))

    def addStretch(self, stretch: int = 0) -> None:
        # Flow layouts left-align items; a stretch has no meaning here.
        return None

    def addItem(self, item) -> None:  # type: ignore[override]
        self._items.append(item)

    def addWidget(self, widget, stretch: int = 0, alignment=Qt.Alignment()) -> None:  # type: ignore[override]
        # QBoxLayout accepts a stretch/alignment triple; a flow layout ignores
        # both and relies on the item's own size hint.
        super().addWidget(widget)

    def count(self) -> int:  # type: ignore[override]
        return len(self._items)

    def itemAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # type: ignore[override]
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        return self._do_layout(QRect(0, 0, int(width), 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # type: ignore[override]
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            if hint.width() <= 0:
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), hint))
                x += hint.width() + self._h_spacing
                continue
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()
