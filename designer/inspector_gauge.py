"""Gauge inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QWidget


def setup_gauge_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    add_color_row: Callable[[QLineEdit], tuple[QWidget, QPushButton]],
) -> None:
    """Populate the Theme Designer gauge inspector tab on ``owner``."""
    owner.row_appearance_stroke_width = make_label("Grubość linii / gauge (0 = auto)")
    owner.row_gauge_ring = make_label("Średnica pierścienia")
    owner.row_gauge_value_layout = make_label("Układ wartości")
    owner.designer_gauge_low_row, owner.designer_gauge_low_btn = add_color_row(owner.designer_gauge_low_edit)
    owner.designer_gauge_mid_row, owner.designer_gauge_mid_btn = add_color_row(owner.designer_gauge_mid_edit)
    owner.designer_gauge_high_row, owner.designer_gauge_high_btn = add_color_row(owner.designer_gauge_high_edit)
    owner.designer_gauge_low_edit.setPlaceholderText("[R,G,B,A] — opcjonalnie, puste = z presetu")
    owner.designer_gauge_mid_edit.setPlaceholderText("[R,G,B,A] — opcjonalnie")
    owner.designer_gauge_high_edit.setPlaceholderText("[R,G,B,A] — opcjonalnie")
    owner.row_gauge_preset = make_label("Preset kolorów")
    owner.row_gauge_grad_low = make_label("Łuk: kolor niski")
    owner.row_gauge_grad_mid = make_label("Łuk: środek")
    owner.row_gauge_grad_high = make_label("Łuk: wysoki")
    owner.row_gauge_smooth = make_label("Wygładzanie igły")
    owner.row_gauge_match_value = make_label("Kolor wartości jak łuk")
    owner.row_gauge_inner_alpha = make_label("Przezrocz. środka")

    owner.inspector_gauge_layout.addRow(owner.row_appearance_stroke_width, owner.designer_stat_stroke_width_spin)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_ring, owner.designer_gauge_ring_spin)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_value_layout, owner.designer_gauge_value_layout_combo)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_inner_alpha, owner.designer_gauge_inner_alpha_spin)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_preset, owner.designer_stat_gauge_preset_combo)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_grad_low, owner.designer_gauge_low_row)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_grad_mid, owner.designer_gauge_mid_row)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_grad_high, owner.designer_gauge_high_row)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_smooth, owner.designer_gauge_smooth_spin)
    owner.inspector_gauge_layout.addRow(owner.row_gauge_match_value, owner.designer_gauge_match_value_chk)
