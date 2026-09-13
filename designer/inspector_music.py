"""Music inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QLineEdit, QWidget

TranslateFn = Callable[[str, str], str]


def setup_music_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
    add_color_row: Callable[[QLineEdit], tuple[QWidget, QPushButton]],
) -> None:
    """Populate the Theme Designer music inspector tab on ``owner``."""
    owner.inspector_music_spectrum_placeholder = QLabel(
        "Animated spectrum / EQ visualizer: reserved for a future update."
    )
    owner.inspector_music_spectrum_placeholder.setWordWrap(True)
    owner.inspector_music_spectrum_placeholder.setObjectName("selectionSummaryLabel")

    owner.inspector_music_tools_row = QWidget()
    music_tools_layout = QHBoxLayout(owner.inspector_music_tools_row)
    music_tools_layout.setContentsMargins(0, 0, 0, 0)
    music_tools_layout.setSpacing(6)
    owner.music_tool_now_playing_btn = QPushButton("Now Playing")
    owner.music_tool_hero_btn = QPushButton("Hero")
    owner.music_tool_mini_btn = QPushButton("Mini")
    owner.music_tool_volume_btn = QPushButton("Volume")
    owner.music_tool_eq_btn = QPushButton("Graphic EQ")
    for btn in (
        owner.music_tool_now_playing_btn,
        owner.music_tool_hero_btn,
        owner.music_tool_mini_btn,
        owner.music_tool_volume_btn,
        owner.music_tool_eq_btn,
    ):
        btn.setObjectName("quickAddButton")
        btn.setMinimumHeight(24)
        music_tools_layout.addWidget(btn)
    owner.music_tool_now_playing_btn.clicked.connect(owner.add_now_playing_widget)
    owner.music_tool_hero_btn.clicked.connect(owner.add_now_playing_widget_hero)
    owner.music_tool_mini_btn.clicked.connect(owner.add_now_playing_widget_mini)
    owner.music_tool_volume_btn.clicked.connect(owner.add_volume_widget)
    owner.music_tool_eq_btn.clicked.connect(owner.add_graphic_equalizer_widget)

    owner.row_music_tools = make_label("Music tools")
    owner.inspector_music_layout.addRow(owner.row_music_tools, owner.inspector_music_tools_row)
    owner.row_music_equalizer_bars = make_label("EQ bars")
    owner.row_music_equalizer_gap = make_label("Bar gap")
    owner.row_music_equalizer_mirror = make_label("Mirror mode")
    owner.inspector_music_layout.addRow(owner.row_music_equalizer_bars, owner.designer_equalizer_bars_spin)
    owner.inspector_music_layout.addRow(owner.row_music_equalizer_gap, owner.designer_equalizer_gap_spin)
    owner.inspector_music_layout.addRow(owner.row_music_equalizer_mirror, owner.designer_equalizer_mirror_chk)

    owner.row_music_widget_options = make_label("Options")
    owner.music_widget_options_row = wrap_row(
        owner.widget_cover_enabled_chk,
        owner.widget_backdrop_enabled_chk,
        owner.widget_title_marquee_chk,
        owner.widget_equalizer_enabled_chk,
    )
    owner.row_music_widget_title_font = make_label("Title font")
    owner.row_music_widget_artist_font = make_label("Artist font")
    owner.row_music_widget_detail_font = make_label("Detail font")
    owner.row_music_widget_title_color = make_label("Title color")
    owner.row_music_widget_artist_color = make_label("Artist color")
    owner.row_music_widget_detail_color = make_label("Detail color")
    owner.row_music_widget_panel_color = make_label("Panel color")
    owner.widget_title_color_row, _ = add_color_row(owner.widget_title_color_edit)
    owner.widget_body_color_row, _ = add_color_row(owner.widget_body_color_edit)
    owner.widget_detail_color_row, _ = add_color_row(owner.widget_detail_color_edit)
    owner.widget_panel_color_row, _ = add_color_row(owner.widget_panel_color_edit)
    owner.inspector_music_layout.addRow(owner.row_music_widget_options, owner.music_widget_options_row)
    owner.inspector_music_layout.addRow(owner.row_music_widget_title_font, owner.widget_title_font_spin)
    owner.inspector_music_layout.addRow(owner.row_music_widget_artist_font, owner.widget_body_font_spin)
    owner.inspector_music_layout.addRow(owner.row_music_widget_detail_font, owner.widget_detail_font_spin)
    owner.inspector_music_layout.addRow(owner.row_music_widget_title_color, owner.widget_title_color_row)
    owner.inspector_music_layout.addRow(owner.row_music_widget_artist_color, owner.widget_body_color_row)
    owner.inspector_music_layout.addRow(owner.row_music_widget_detail_color, owner.widget_detail_color_row)
    owner.inspector_music_layout.addRow(owner.row_music_widget_panel_color, owner.widget_panel_color_row)

    owner.inspector_music_hint = QLabel("")
    owner.inspector_music_hint.setWordWrap(True)
    owner.inspector_music_hint.setObjectName("selectionSummaryLabel")
    owner.inspector_music_layout.addRow(owner.inspector_music_spectrum_placeholder)
    owner.inspector_music_layout.addRow(owner.inspector_music_hint)


def refresh_music_inspector_labels(owner: Any, translate: TranslateFn) -> None:
    """Refresh labels for music-related inspector tools."""
    if hasattr(owner, "music_tool_now_playing_btn"):
        owner.music_tool_now_playing_btn.setText(translate("Now Playing", "Now Playing"))
    if hasattr(owner, "music_tool_hero_btn"):
        owner.music_tool_hero_btn.setText(translate("Hero", "Hero"))
    if hasattr(owner, "music_tool_mini_btn"):
        owner.music_tool_mini_btn.setText(translate("Mini", "Mini"))
    if hasattr(owner, "music_tool_volume_btn"):
        owner.music_tool_volume_btn.setText(translate("Volume", "Głośność"))
    if hasattr(owner, "music_tool_eq_btn"):
        owner.music_tool_eq_btn.setText(translate("Graphic EQ", "Korektor"))
    if hasattr(owner, "designer_equalizer_mirror_chk"):
        owner.designer_equalizer_mirror_chk.setText(translate("Mirror from center", "Lustro od środka"))
