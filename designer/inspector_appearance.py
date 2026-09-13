"""Style / appearance inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QWidget

TranslateFn = Callable[[str, str], str]


def setup_appearance_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
    add_color_row: Callable[[QLineEdit], tuple[QWidget, QPushButton]],
    make_compact_labeled_row: Callable[..., QWidget],
) -> None:
    """Populate the Theme Designer appearance inspector tab on ``owner``."""
    owner.designer_font_minus_btn = QPushButton("−")
    owner.designer_font_minus_btn.setMinimumWidth(36)
    owner.designer_font_plus_btn = QPushButton("+")
    owner.designer_font_plus_btn.setMinimumWidth(36)
    owner.designer_font_minus_btn.clicked.connect(
        lambda: owner.designer_font_size_spin.setValue(
            max(owner.designer_font_size_spin.minimum(), owner.designer_font_size_spin.value() - 1)
        )
    )
    owner.designer_font_plus_btn.clicked.connect(
        lambda: owner.designer_font_size_spin.setValue(
            min(owner.designer_font_size_spin.maximum(), owner.designer_font_size_spin.value() + 1)
        )
    )
    owner.font_row = wrap_row(
        owner.designer_font_family_combo,
        owner.designer_font_minus_btn,
        owner.designer_font_size_spin,
        owner.designer_font_plus_btn,
        stretch_first=True,
    )
    owner.row_appearance_font = make_label("Czcionka")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_font, owner.font_row)
    owner.font_style_row = wrap_row(
        owner.designer_font_bold_chk,
        owner.designer_font_italic_chk,
        owner.designer_font_underline_chk,
    )
    owner.row_appearance_font_style = make_label("Styl")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_font_style, owner.font_style_row)
    owner.row_appearance_align = make_label("Wyrównanie")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_align, owner.designer_align_combo)

    owner.designer_color_row, owner.designer_color_btn = add_color_row(owner.designer_color_edit)
    owner.row_appearance_color = make_label("Kolor")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_color, owner.designer_color_row)
    owner.designer_label_color_row, owner.designer_label_color_btn = add_color_row(owner.designer_label_color_edit)
    owner.row_appearance_label_color = make_label("Kolor etykiety")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_label_color, owner.designer_label_color_row)
    owner.designer_value_color_row, owner.designer_value_color_btn = add_color_row(owner.designer_value_color_edit)
    owner.row_appearance_value_color = make_label("Kolor wartości")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_value_color, owner.designer_value_color_row)
    owner.designer_track_color_row, owner.designer_track_color_btn = add_color_row(owner.designer_track_color_edit)
    owner.row_appearance_track_color = make_label("Kolor tła gauge / paska / wykresu")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_track_color, owner.designer_track_color_row)
    owner.designer_fill_color_row, owner.designer_fill_color_btn = add_color_row(owner.designer_fill_color_edit)
    owner.row_appearance_fill_color = make_label("Kolor linii / wypełnienia / wartości")
    owner.inspector_appearance_layout.addRow(owner.row_appearance_fill_color, owner.designer_fill_color_row)

    owner.equalizer_style_row = wrap_row(
        owner.designer_equalizer_transparent_bg_chk,
        owner.designer_equalizer_preset_combo,
        owner.designer_equalizer_threshold_spin,
        stretch_first=False,
    )
    owner.row_equalizer_style = make_label("EQ style")
    owner.inspector_appearance_layout.addRow(owner.row_equalizer_style, owner.equalizer_style_row)
    owner.designer_equalizer_threshold_color_row, owner.designer_equalizer_threshold_color_btn = add_color_row(
        owner.designer_equalizer_threshold_color_edit
    )
    owner.row_equalizer_threshold_color = make_label("EQ high color")
    owner.inspector_appearance_layout.addRow(
        owner.row_equalizer_threshold_color,
        owner.designer_equalizer_threshold_color_row,
    )

    owner.row_sparkline_points = make_label("Punkty historii")
    owner.inspector_appearance_layout.addRow(owner.row_sparkline_points, owner.designer_sparkline_points_spin)
    owner.row_sparkline_fill_opacity = make_label("Przezrocz. wypełnienia")
    owner.inspector_appearance_layout.addRow(owner.row_sparkline_fill_opacity, owner.designer_sparkline_fill_opacity_spin)
    owner.row_sparkline_show_points = make_label("Punkt końcowy")
    owner.inspector_appearance_layout.addRow(owner.row_sparkline_show_points, owner.designer_sparkline_show_points_chk)

    owner.row_panel_fill = make_label("Panel style")
    owner.panel_fill_row = wrap_row(owner.panel_fill_edit, owner.panel_fill_btn, stretch_first=True)
    owner.panel_fill_btn.clicked.connect(lambda _checked=False: owner.pick_color_for_edit(owner.panel_fill_edit))
    owner.panel_fill_compact_label = QLabel("Fill")
    owner.panel_opacity_compact_label = QLabel("Opacity")
    owner.panel_radius_compact_label = QLabel("Radius")
    owner.panel_opacity_spin.setMaximumWidth(84)
    owner.panel_radius_spin.setMaximumWidth(84)
    owner.panel_style_row = make_compact_labeled_row(
        (owner.panel_fill_compact_label, owner.panel_fill_row),
        (owner.panel_opacity_compact_label, owner.panel_opacity_spin),
        (owner.panel_radius_compact_label, owner.panel_radius_spin),
        stretch_first=True,
    )
    owner.inspector_appearance_layout.addRow(owner.row_panel_fill, owner.panel_style_row)
    owner.row_panel_opacity = make_label("Panel opacity")
    owner.row_panel_radius = make_label("Corner radius")


def refresh_appearance_inspector_labels(owner: Any, translate: TranslateFn) -> None:
    """Refresh labels for appearance inspector controls."""
    if hasattr(owner, "designer_equalizer_transparent_bg_chk"):
        owner.designer_equalizer_transparent_bg_chk.setText(translate("Transparent background", "Przezroczyste tło"))
