"""Media / background inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


def setup_media_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
) -> None:
    """Populate the Theme Designer media/background inspector tab on ``owner``."""
    owner.background_preview_label.setAlignment(Qt.AlignCenter)
    owner.background_preview_label.setMinimumHeight(92)
    owner.background_preview_label.setObjectName("selectionSummaryLabel")
    owner.media_background_path_row = wrap_row(
        owner.bg_path_edit,
        owner.bg_path_browse_btn,
        owner.bg_prepare_btn,
        stretch_first=True,
    )
    owner.row_media_bg_mode = make_label("Background mode")
    owner.inspector_media_layout.addRow(owner.row_media_bg_mode, owner.bg_kind_combo)
    owner.row_media_bg_path = make_label("File / import")
    owner.inspector_media_layout.addRow(owner.row_media_bg_path, owner.media_background_path_row)
    owner.row_media_bg_fit = make_label("Fit")
    owner.inspector_media_layout.addRow(owner.row_media_bg_fit, owner.bg_fit_combo)
    owner.row_media_bg_opacity = make_label("Opacity")
    owner.inspector_media_layout.addRow(owner.row_media_bg_opacity, owner.bg_opacity_spin)
    owner.row_media_bg_rotation = make_label("Rotation")
    owner.inspector_media_layout.addRow(owner.row_media_bg_rotation, owner.bg_rotation_spin)
    owner.media_colors_row = wrap_row(
        owner.bg_base_color_edit,
        owner.bg_base_color_btn,
        owner.bg_accent_color_edit,
        owner.bg_accent_color_btn,
    )
    owner.row_media_bg_colors = make_label("Colors")
    owner.inspector_media_layout.addRow(owner.row_media_bg_colors, owner.media_colors_row)
    owner.media_presets_row = wrap_row(
        owner.bg_cover_btn,
        owner.bg_contain_btn,
        owner.bg_preset_ocean_btn,
        owner.bg_preset_amber_btn,
        owner.bg_preset_mono_btn,
        owner.bg_preset_neon_btn,
    )
    owner.row_media_bg_presets = make_label("Presets")
    owner.inspector_media_layout.addRow(owner.row_media_bg_presets, owner.media_presets_row)
    owner.row_media_bg_texture = make_label("Texture")
    owner.inspector_media_layout.addRow(owner.row_media_bg_texture, owner.bg_texture_alpha_spin)
    owner.row_media_bg_preview = make_label("Background preview")
    owner.inspector_media_layout.addRow(owner.row_media_bg_preview, owner.background_preview_label)
