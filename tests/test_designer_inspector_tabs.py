import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from designer.inspector_tabs import (
    add_inspector_tabs,
    apply_inspector_compact_sizing,
    configure_inspector_form_layouts,
    create_inspector_tabs,
    refresh_inspector_tab_labels,
)
from designer.inspector_widgets import make_inspector_tab

_APP = QApplication.instance() or QApplication([])


def _make_owner_with_compact_controls() -> SimpleNamespace:
    names = [
        "designer_id_edit",
        "designer_text_edit",
        "designer_label_edit",
        "designer_format_edit",
        "designer_source_combo",
        "designer_stat_display_combo",
        "designer_stat_min_spin",
        "designer_stat_max_spin",
        "designer_align_combo",
        "designer_font_family_combo",
        "designer_font_size_spin",
        "designer_color_edit",
        "designer_label_color_edit",
        "designer_value_color_edit",
        "designer_track_color_edit",
        "designer_fill_color_edit",
        "designer_x_spin",
        "designer_y_spin",
        "designer_w_spin",
        "designer_h_spin",
        "designer_z_spin",
        "designer_path_edit",
        "designer_fit_combo",
        "designer_opacity_spin",
        "designer_rotation_spin",
        "panel_fill_edit",
        "panel_opacity_spin",
        "panel_radius_spin",
        "designer_stat_stroke_width_spin",
        "designer_gauge_ring_spin",
        "designer_gauge_value_layout_combo",
        "designer_gauge_inner_alpha_spin",
        "designer_sparkline_points_spin",
        "designer_sparkline_fill_opacity_spin",
        "motion_start_spin",
        "motion_end_spin",
        "motion_target_x_spin",
        "motion_target_y_spin",
        "motion_target_opacity_spin",
    ]
    buttons = [
        "designer_font_minus_btn",
        "designer_font_plus_btn",
        "designer_path_browse_btn",
        "designer_path_prepare_btn",
        "designer_import_image_btn",
        "motion_capture_current_btn",
        "motion_remove_btn",
        "bg_path_browse_btn",
        "bg_prepare_btn",
        "bg_cover_btn",
        "bg_contain_btn",
        "bg_preset_ocean_btn",
        "bg_preset_amber_btn",
        "bg_preset_mono_btn",
        "bg_preset_neon_btn",
        "bg_animation_prev_btn",
        "bg_animation_next_btn",
        "bg_animation_play_btn",
        "bg_animation_import_btn",
        "bg_animation_add_btn",
        "bg_animation_blank_btn",
        "bg_animation_export_btn",
        "bg_animation_duplicate_btn",
        "bg_animation_repeat_all_btn",
        "bg_animation_remove_btn",
        "bg_animation_up_btn",
        "bg_animation_down_btn",
        "bg_animation_clear_btn",
    ]
    checks = [
        "designer_visible_chk",
        "designer_locked_chk",
        "designer_font_bold_chk",
        "designer_font_italic_chk",
        "designer_font_underline_chk",
        "motion_enabled_chk",
    ]
    values = {name: QSpinBox() for name in names}
    values.update({name: QPushButton(name) for name in buttons})
    values.update({name: QCheckBox(name) for name in checks})
    return SimpleNamespace(**values)


class InspectorTabsTests(unittest.TestCase):
    def test_create_and_register_inspector_tabs_in_expected_order(self) -> None:
        changed: list[int] = []
        owner = SimpleNamespace()

        create_inspector_tabs(owner, make_inspector_tab, make_inspector_tab, changed.append)
        add_inspector_tabs(owner)

        self.assertEqual(owner.inspector_tabs.count(), 10)
        self.assertEqual(
            [owner.inspector_tabs.tabText(idx) for idx in range(owner.inspector_tabs.count())],
            ["General", "Content", "Music", "Weather", "Style", "Gauge", "Position", "Image", "Media", "Animation"],
        )
        self.assertIsInstance(owner.inspector_general_layout, QFormLayout)
        owner.inspector_tabs.setCurrentIndex(1)
        self.assertEqual(changed[-1], 1)

    def test_refresh_inspector_tab_labels_updates_shell_and_tabs(self) -> None:
        owner = SimpleNamespace(props_box=QGroupBox("old"), inspector_selection_summary=QLabel("old"))
        create_inspector_tabs(owner, make_inspector_tab, make_inspector_tab, lambda _idx: None)
        add_inspector_tabs(owner)

        refresh_inspector_tab_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.props_box.title(), "Właściwości elementu")
        self.assertEqual(owner.inspector_selection_summary.text(), "Wybierz element, aby edytować jego właściwości.")
        self.assertEqual(owner.inspector_tabs.tabText(0), "Ogólne")
        self.assertEqual(owner.inspector_tabs.tabText(2), "Muzyka")
        self.assertEqual(owner.inspector_tabs.tabText(8), "Tło")

    def test_configure_layouts_and_compact_sizing(self) -> None:
        widget_a = QWidget()
        widget_b = QWidget()
        layout_a = QFormLayout(widget_a)
        layout_b = QFormLayout(widget_b)
        configure_inspector_form_layouts([layout_a, layout_b])

        self.assertEqual(layout_a.spacing(), 4)
        self.assertEqual(layout_b.contentsMargins().left(), 4)

        owner = _make_owner_with_compact_controls()
        apply_inspector_compact_sizing(owner)

        self.assertEqual(owner.designer_id_edit.maximumHeight(), 32)
        self.assertEqual(owner.designer_font_minus_btn.minimumHeight(), 28)
        self.assertEqual(owner.designer_font_minus_btn.maximumHeight(), 30)
        self.assertEqual(owner.motion_enabled_chk.maximumHeight(), 26)


if __name__ == "__main__":
    unittest.main()
