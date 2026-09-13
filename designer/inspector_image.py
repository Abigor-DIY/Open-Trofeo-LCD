"""Image inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QWidget


def setup_image_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
    make_compact_labeled_row: Callable[..., QWidget],
) -> None:
    """Populate the Theme Designer image inspector tab on ``owner``."""
    owner.designer_path_browse_btn = QPushButton("Wybierz")
    owner.designer_path_browse_btn.clicked.connect(owner.browse_designer_image_path)
    owner.designer_path_prepare_btn = QPushButton("Przygotuj")
    owner.designer_path_prepare_btn.clicked.connect(owner.browse_designer_image_path)
    owner.designer_image_fullscreen_btn = QPushButton("Ustaw fullscreen")
    owner.designer_image_fullscreen_btn.clicked.connect(lambda: owner.apply_image_rect_preset("fullscreen"))
    owner.designer_image_left_half_btn = QPushButton("Lewa połowa")
    owner.designer_image_left_half_btn.clicked.connect(lambda: owner.apply_image_rect_preset("left-half"))
    owner.designer_image_right_half_btn = QPushButton("Prawa połowa")
    owner.designer_image_right_half_btn.clicked.connect(lambda: owner.apply_image_rect_preset("right-half"))
    owner.designer_image_reset_btn = QPushButton("Reset kadru")
    owner.designer_image_reset_btn.clicked.connect(lambda: owner.apply_image_rect_preset("contain-full"))
    owner.designer_import_image_btn = QPushButton("Importuj obraz do motywu")
    owner.designer_import_image_btn.clicked.connect(owner.import_image_as_designer_element)
    owner.designer_path_row = wrap_row(
        owner.designer_path_edit,
        owner.designer_path_browse_btn,
        owner.designer_path_prepare_btn,
        stretch_first=True,
    )
    owner.row_image_path = make_label("Plik obrazu")
    owner.inspector_image_layout.addRow(owner.row_image_path, owner.designer_path_row)

    owner.row_image_fit = make_label("Transform")
    owner.image_fit_compact_label = QLabel("Fit")
    owner.image_opacity_compact_label = QLabel("Opacity")
    owner.image_rotation_compact_label = QLabel("Rotation")
    owner.designer_opacity_spin.setMaximumWidth(84)
    owner.designer_rotation_spin.setMaximumWidth(84)
    owner.image_transform_row = make_compact_labeled_row(
        (owner.image_fit_compact_label, owner.designer_fit_combo),
        (owner.image_opacity_compact_label, owner.designer_opacity_spin),
        (owner.image_rotation_compact_label, owner.designer_rotation_spin),
        stretch_first=True,
    )
    owner.inspector_image_layout.addRow(owner.row_image_fit, owner.image_transform_row)
    owner.row_image_opacity = make_label("Opacity")
    owner.row_image_rotation = make_label("Rotation")

    owner.row_image_import = make_label("Import")
    owner.inspector_image_layout.addRow(owner.row_image_import, owner.designer_import_image_btn)
    owner.row_image_actions = make_label("Szybkie akcje")
    owner.designer_image_actions_row = wrap_row(
        owner.designer_image_fullscreen_btn,
        owner.designer_image_left_half_btn,
        owner.designer_image_right_half_btn,
        owner.designer_image_reset_btn,
    )
    owner.inspector_image_layout.addRow(owner.row_image_actions, owner.designer_image_actions_row)

    owner.row_image_preview = make_label("Podgląd")
    owner.designer_image_preview_label = QLabel("Image preview")
    owner.designer_image_preview_label.setAlignment(Qt.AlignCenter)
    owner.designer_image_preview_label.setMinimumHeight(104)
    owner.designer_image_preview_label.setObjectName("selectionSummaryLabel")
    owner.inspector_image_layout.addRow(owner.row_image_preview, owner.designer_image_preview_label)
