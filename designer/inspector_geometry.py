"""Position / geometry inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

TranslateFn = Callable[[str, str], str]


def setup_geometry_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
) -> None:
    """Populate the Theme Designer geometry inspector tab on ``owner``."""
    owner.row_geometry_x = make_label("X")
    owner.inspector_geometry_layout.addRow(owner.row_geometry_x, owner.designer_x_spin)
    owner.row_geometry_y = make_label("Y")
    owner.inspector_geometry_layout.addRow(owner.row_geometry_y, owner.designer_y_spin)
    owner.row_geometry_w = make_label("Szerokość")
    owner.inspector_geometry_layout.addRow(owner.row_geometry_w, owner.designer_w_spin)
    owner.row_geometry_h = make_label("Wysokość")
    owner.inspector_geometry_layout.addRow(owner.row_geometry_h, owner.designer_h_spin)

    owner.geometry_group_bounds_label = QLabel("Group bounds: -")
    owner.geometry_group_bounds_label.setObjectName("selectionSummaryLabel")
    owner.geometry_group_bounds_label.setWordWrap(True)
    owner.row_geometry_group_bounds = make_label("Group")
    owner.inspector_geometry_layout.addRow(owner.row_geometry_group_bounds, owner.geometry_group_bounds_label)

    owner.geometry_preset_top_btn = QPushButton("Top")
    owner.geometry_preset_bottom_btn = QPushButton("Bottom")
    owner.geometry_preset_left_btn = QPushButton("Left")
    owner.geometry_preset_right_btn = QPushButton("Right")
    owner.geometry_preset_center_btn = QPushButton("Center")
    for btn in (
        owner.geometry_preset_top_btn,
        owner.geometry_preset_bottom_btn,
        owner.geometry_preset_left_btn,
        owner.geometry_preset_right_btn,
        owner.geometry_preset_center_btn,
    ):
        btn.setObjectName("compactActionButton")
        btn.setMinimumHeight(24)
        btn.setMaximumHeight(28)
        btn.setMinimumWidth(58)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    owner.geometry_preset_top_btn.clicked.connect(lambda: owner.apply_geometry_rect_preset("top"))
    owner.geometry_preset_bottom_btn.clicked.connect(lambda: owner.apply_geometry_rect_preset("bottom"))
    owner.geometry_preset_left_btn.clicked.connect(lambda: owner.apply_geometry_rect_preset("left"))
    owner.geometry_preset_right_btn.clicked.connect(lambda: owner.apply_geometry_rect_preset("right"))
    owner.geometry_preset_center_btn.clicked.connect(lambda: owner.apply_geometry_rect_preset("center"))
    owner.geometry_preset_top_btn.setToolTip("Fit selection to the top band of the LCD canvas")
    owner.geometry_preset_bottom_btn.setToolTip("Fit selection to the bottom band of the LCD canvas")
    owner.geometry_preset_left_btn.setToolTip("Fit selection to the left side of the LCD canvas")
    owner.geometry_preset_right_btn.setToolTip("Fit selection to the right side of the LCD canvas")
    owner.geometry_preset_center_btn.setToolTip("Center and enlarge selection on the LCD canvas")
    owner.geometry_preset_row = wrap_row(
        owner.geometry_preset_top_btn,
        owner.geometry_preset_bottom_btn,
        owner.geometry_preset_left_btn,
        owner.geometry_preset_right_btn,
        owner.geometry_preset_center_btn,
    )
    owner.row_geometry_presets = make_label("Presets")
    owner.inspector_geometry_layout.addRow(owner.row_geometry_presets, owner.geometry_preset_row)

    owner.row_motion_enabled = make_label("Ruch")
    owner.inspector_geometry_layout.addRow(owner.row_motion_enabled, owner.motion_enabled_chk)
    owner.row_motion_range = make_label("Zakres klatek")
    owner.motion_range_row = wrap_row(owner.motion_start_spin, owner.motion_end_spin)
    owner.inspector_geometry_layout.addRow(owner.row_motion_range, owner.motion_range_row)
    owner.row_motion_target_x = make_label("Koniec X")
    owner.inspector_geometry_layout.addRow(owner.row_motion_target_x, owner.motion_target_x_spin)
    owner.row_motion_target_y = make_label("Koniec Y")
    owner.inspector_geometry_layout.addRow(owner.row_motion_target_y, owner.motion_target_y_spin)
    owner.row_motion_target_opacity = make_label("Końcowa przezr.")
    owner.inspector_geometry_layout.addRow(owner.row_motion_target_opacity, owner.motion_target_opacity_spin)
    owner.row_motion_actions = make_label("Akcje ruchu")
    owner.motion_actions_row = wrap_row(owner.motion_capture_current_btn, owner.motion_remove_btn)
    owner.inspector_geometry_layout.addRow(owner.row_motion_actions, owner.motion_actions_row)


def refresh_geometry_preset_labels(owner: Any, translate: TranslateFn) -> None:
    """Refresh geometry preset button labels and tooltips."""
    if hasattr(owner, "geometry_preset_top_btn"):
        owner.geometry_preset_top_btn.setText(translate("Top", "Góra"))
        owner.geometry_preset_top_btn.setToolTip(
            translate("Fit selection to the top band of the LCD canvas", "Dopasuj zaznaczenie do górnego pasa ekranu LCD")
        )
    if hasattr(owner, "geometry_preset_bottom_btn"):
        owner.geometry_preset_bottom_btn.setText(translate("Bottom", "Dół"))
        owner.geometry_preset_bottom_btn.setToolTip(
            translate("Fit selection to the bottom band of the LCD canvas", "Dopasuj zaznaczenie do dolnego pasa ekranu LCD")
        )
    if hasattr(owner, "geometry_preset_left_btn"):
        owner.geometry_preset_left_btn.setText(translate("Left", "Lewo"))
        owner.geometry_preset_left_btn.setToolTip(
            translate("Fit selection to the left side of the LCD canvas", "Dopasuj zaznaczenie do lewej strony ekranu LCD")
        )
    if hasattr(owner, "geometry_preset_right_btn"):
        owner.geometry_preset_right_btn.setText(translate("Right", "Prawo"))
        owner.geometry_preset_right_btn.setToolTip(
            translate("Fit selection to the right side of the LCD canvas", "Dopasuj zaznaczenie do prawej strony ekranu LCD")
        )
    if hasattr(owner, "geometry_preset_center_btn"):
        owner.geometry_preset_center_btn.setText(translate("Center", "Środek"))
        owner.geometry_preset_center_btn.setToolTip(
            translate("Center and enlarge selection on the LCD canvas", "Wyśrodkuj i powiększ zaznaczenie na ekranie LCD")
        )
