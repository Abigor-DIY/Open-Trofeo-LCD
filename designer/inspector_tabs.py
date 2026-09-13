"""Theme Designer inspector tab container and sizing helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtWidgets import QFormLayout, QSizePolicy, QTabWidget, QWidget


TabFactory = Callable[[], tuple[QWidget, QFormLayout]]
TranslateFn = Callable[[str, str], str]


def create_inspector_tabs(
    owner: Any,
    make_tab: TabFactory,
    make_scrolled_tab: TabFactory,
    on_tab_changed: Callable[[int], None],
) -> None:
    """Create inspector tabs and their form layouts on ``owner``."""
    owner.inspector_tabs = QTabWidget()
    owner.inspector_tabs.setDocumentMode(True)
    owner.inspector_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    owner.inspector_tabs.currentChanged.connect(on_tab_changed)

    owner.inspector_general, owner.inspector_general_layout = make_tab()
    owner.inspector_content, owner.inspector_content_layout = make_tab()
    owner.inspector_music, owner.inspector_music_layout = make_scrolled_tab()
    owner.inspector_weather, owner.inspector_weather_layout = make_scrolled_tab()
    owner.inspector_appearance, owner.inspector_appearance_layout = make_scrolled_tab()
    owner.inspector_gauge, owner.inspector_gauge_layout = make_scrolled_tab()
    owner.inspector_geometry, owner.inspector_geometry_layout = make_scrolled_tab()
    owner.inspector_image, owner.inspector_image_layout = make_scrolled_tab()
    owner.inspector_media, owner.inspector_media_layout = make_scrolled_tab()
    owner.inspector_animation, owner.inspector_animation_layout = make_scrolled_tab()


def configure_inspector_form_layouts(layouts: Iterable[QFormLayout]) -> None:
    """Apply compact spacing to all inspector form layouts."""
    for layout in layouts:
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)


def add_inspector_tabs(owner: Any) -> None:
    """Register inspector tabs in their visible order."""
    for widget, title in (
        (owner.inspector_general, "General"),
        (owner.inspector_content, "Content"),
        (owner.inspector_music, "Music"),
        (owner.inspector_weather, "Weather"),
        (owner.inspector_appearance, "Style"),
        (owner.inspector_gauge, "Gauge"),
        (owner.inspector_geometry, "Position"),
        (owner.inspector_image, "Image"),
        (owner.inspector_media, "Media"),
        (owner.inspector_animation, "Animation"),
    ):
        owner.inspector_tabs.addTab(widget, title)


def refresh_inspector_tab_labels(owner: Any, translate: TranslateFn) -> None:
    """Refresh the inspector shell title, summary and tab names."""
    if hasattr(owner, "props_box"):
        owner.props_box.setTitle(translate("Element properties", "Właściwości elementu"))
    if hasattr(owner, "inspector_selection_summary"):
        owner.inspector_selection_summary.setText(
            translate("Select an element to edit its properties.", "Wybierz element, aby edytować jego właściwości.")
        )
    if hasattr(owner, "inspector_tabs"):
        labels = [
            ("General", "Ogólne"),
            ("Content", "Treść"),
            ("Music", "Muzyka"),
            ("Weather", "Pogoda"),
            ("Style", "Styl"),
            ("Gauge", "Gauge"),
            ("Position", "Pozycja"),
            ("Image", "Obraz"),
            ("Background", "Tło"),
            ("Animation", "Animacja"),
        ]
        for idx, (en, pl) in enumerate(labels):
            if idx < owner.inspector_tabs.count():
                owner.inspector_tabs.setTabText(idx, translate(en, pl))


def apply_inspector_compact_sizing(owner: Any) -> None:
    """Constrain noisy inspector controls so the panel remains dense."""
    compact_widgets = [
        owner.designer_id_edit,
        owner.designer_text_edit,
        owner.designer_label_edit,
        owner.designer_format_edit,
        owner.designer_source_combo,
        owner.designer_stat_display_combo,
        owner.designer_stat_min_spin,
        owner.designer_stat_max_spin,
        owner.designer_align_combo,
        owner.designer_font_family_combo,
        owner.designer_font_size_spin,
        owner.designer_color_edit,
        owner.designer_label_color_edit,
        owner.designer_value_color_edit,
        owner.designer_track_color_edit,
        owner.designer_fill_color_edit,
        owner.designer_x_spin,
        owner.designer_y_spin,
        owner.designer_w_spin,
        owner.designer_h_spin,
        owner.designer_z_spin,
        owner.designer_path_edit,
        owner.designer_fit_combo,
        owner.designer_opacity_spin,
        owner.designer_rotation_spin,
        owner.panel_fill_edit,
        owner.panel_opacity_spin,
        owner.panel_radius_spin,
        owner.designer_stat_stroke_width_spin,
        owner.designer_gauge_ring_spin,
        owner.designer_gauge_value_layout_combo,
        owner.designer_gauge_inner_alpha_spin,
        owner.designer_sparkline_points_spin,
        owner.designer_sparkline_fill_opacity_spin,
        owner.motion_start_spin,
        owner.motion_end_spin,
        owner.motion_target_x_spin,
        owner.motion_target_y_spin,
        owner.motion_target_opacity_spin,
    ]
    for widget in compact_widgets:
        widget.setMaximumHeight(32)

    for button in (
        owner.designer_font_minus_btn,
        owner.designer_font_plus_btn,
        owner.designer_path_browse_btn,
        owner.designer_path_prepare_btn,
        owner.designer_import_image_btn,
        owner.motion_capture_current_btn,
        owner.motion_remove_btn,
        owner.bg_path_browse_btn,
        owner.bg_prepare_btn,
        owner.bg_cover_btn,
        owner.bg_contain_btn,
        owner.bg_preset_ocean_btn,
        owner.bg_preset_amber_btn,
        owner.bg_preset_mono_btn,
        owner.bg_preset_neon_btn,
        owner.bg_animation_prev_btn,
        owner.bg_animation_next_btn,
        owner.bg_animation_play_btn,
        owner.bg_animation_import_btn,
        owner.bg_animation_add_btn,
        owner.bg_animation_blank_btn,
        owner.bg_animation_export_btn,
        owner.bg_animation_duplicate_btn,
        owner.bg_animation_repeat_all_btn,
        owner.bg_animation_remove_btn,
        owner.bg_animation_up_btn,
        owner.bg_animation_down_btn,
        owner.bg_animation_clear_btn,
    ):
        button.setMinimumHeight(28)
        button.setMaximumHeight(30)

    for check in (
        owner.designer_visible_chk,
        owner.designer_locked_chk,
        owner.designer_font_bold_chk,
        owner.designer_font_italic_chk,
        owner.designer_font_underline_chk,
        owner.motion_enabled_chk,
    ):
        check.setMaximumHeight(26)
