"""Reusable Qt widgets for the Theme Designer inspector."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)


def make_inspector_tab() -> tuple[QWidget, QFormLayout]:
    tab = QWidget()
    tab_layout = _make_form_layout(tab)
    return tab, tab_layout


def make_scrolled_inspector_tab() -> tuple[QScrollArea, QFormLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    inner = QWidget()
    tab_layout = _make_form_layout(inner)
    scroll.setWidget(inner)
    return scroll, tab_layout


def make_field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("headerFieldLabel")
    return label


def wrap_inspector_row(*widgets: QWidget, stretch_first: bool = False) -> QWidget:
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    for idx, widget in enumerate(widgets):
        row_layout.addWidget(widget, 1 if stretch_first and idx == 0 else 0)
    if stretch_first:
        row_layout.setStretch(0, 1)
    return row


def make_color_row(
    target_edit: QLineEdit,
    pick_color: Callable[[QLineEdit], None],
) -> tuple[QWidget, QPushButton]:
    button = QPushButton("🎨")
    button.setMinimumWidth(40)
    button.clicked.connect(lambda _checked=False, edit=target_edit: pick_color(edit))
    row = wrap_inspector_row(target_edit, button, stretch_first=True)
    return row, button


def make_compact_color_cell(
    caption: str,
    target_edit: QLineEdit,
    pick_color: Callable[[QLineEdit], None],
) -> QWidget:
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
    button.clicked.connect(lambda _checked=False, edit=target_edit: pick_color(edit))
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


def _make_form_layout(parent: QWidget) -> QFormLayout:
    tab_layout = QFormLayout(parent)
    tab_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    tab_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    tab_layout.setFormAlignment(Qt.AlignTop)
    tab_layout.setHorizontalSpacing(6)
    tab_layout.setVerticalSpacing(4)
    tab_layout.setContentsMargins(4, 4, 4, 4)
    return tab_layout
