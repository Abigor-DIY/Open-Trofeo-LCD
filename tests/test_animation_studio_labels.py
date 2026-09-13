import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QPushButton, QSpinBox

from animation_studio import refresh_animation_studio_labels

_APP = QApplication.instance() or QApplication([])


class AnimationStudioLabelTests(unittest.TestCase):
    def test_refresh_animation_studio_labels_updates_controls_and_preserves_combos(self) -> None:
        refreshed: list[str] = []
        owner = SimpleNamespace(
            animation_studio_open_json_btn=QPushButton("old"),
            animation_studio_save_as_btn=QPushButton("old"),
            animation_studio_back_btn=QPushButton("old"),
            animation_studio_quick_export_btn=QPushButton("old"),
            animation_studio_title_label=QLabel("old"),
            animation_studio_subtitle_label=QLabel("old"),
            animation_worker_status_label=QLabel("old"),
            _refresh_animation_worker_status=lambda: refreshed.append("worker"),
            animation_cancel_worker_btn=QPushButton("old"),
            animation_preview_title_label=QLabel("old"),
            animation_auto_composite_chk=QCheckBox("old"),
            animation_refresh_composite_btn=QPushButton("old"),
            animation_onion_skin_chk=QCheckBox("old"),
            bg_animation_export_btn=QPushButton("old"),
            animation_export_loop_btn=QPushButton("old"),
            animation_export_selection_btn=QPushButton("old"),
            bg_animation_import_btn=QPushButton("old"),
            bg_animation_add_btn=QPushButton("old"),
            bg_animation_duplicate_btn=QPushButton("old"),
            bg_animation_hold_repeat_btn=QPushButton("old"),
            animation_bulk_apply_duration_btn=QPushButton("old"),
            animation_stabilize_btn=QPushButton("old"),
            animation_stabilize_mode_combo=QComboBox(),
            bg_animation_normalize_duration_btn=QPushButton("old"),
            bg_animation_reverse_btn=QPushButton("old"),
            bg_animation_pingpong_btn=QPushButton("old"),
            animation_select_range_btn=QPushButton("old"),
            animation_invert_selection_btn=QPushButton("old"),
            animation_clear_selection_btn=QPushButton("old"),
            animation_timeline_home_btn=QPushButton("old"),
            animation_timeline_end_btn=QPushButton("old"),
            animation_loop_from_selection_btn=QPushButton("old"),
            animation_trim_selection_btn=QPushButton("old"),
            animation_timeline_label=QLabel("old"),
            animation_timeline_hint_label=QLabel("old"),
            animation_loop_in_btn=QPushButton("old"),
            animation_loop_out_btn=QPushButton("old"),
            animation_loop_clear_btn=QPushButton("old"),
            bg_animation_repeat_all_btn=QPushButton("old"),
            bg_animation_enabled_chk=QCheckBox("old"),
            bg_animation_use_bg_chk=QCheckBox("old"),
            animation_studio_fps_label=QLabel("old"),
            animation_studio_frame_index_label=QLabel("old"),
            animation_studio_duration_label=QLabel("old"),
            animation_studio_bulk_duration_label=QLabel("old"),
            animation_onion_skin_opacity_label=QLabel("old"),
            animation_loop_close_seam_btn=QPushButton("old"),
            animation_preview_scale_combo=QComboBox(),
            animation_duplicate_repeat_spin=QSpinBox(),
        )
        for label, data in (
            ("safe", "safe_translation"),
            ("auto", "auto_safe"),
            ("affine", "affine"),
        ):
            owner.animation_stabilize_mode_combo.addItem(label, data)
        owner.animation_stabilize_mode_combo.setCurrentIndex(2)
        for label in ("fit", "100", "150", "200"):
            owner.animation_preview_scale_combo.addItem(label)
        owner.animation_preview_scale_combo.setCurrentIndex(2)

        refresh_animation_studio_labels(owner, lambda _en, pl: pl)

        self.assertEqual(refreshed, ["worker"])
        self.assertEqual(owner.animation_studio_open_json_btn.text(), "Otwórz JSON…")
        self.assertEqual(owner.animation_studio_title_label.text(), "Studio animacji")
        self.assertEqual(owner.animation_auto_composite_chk.text(), "Auto kompozycja")
        self.assertEqual(owner.bg_animation_export_btn.text(), "Eksportuj")
        self.assertEqual(owner.animation_export_loop_btn.text(), "Eksport pętli")
        self.assertEqual(owner.bg_animation_import_btn.text(), "Importuj")
        self.assertEqual(owner.animation_stabilize_btn.text(), "Stabilizuj")
        self.assertEqual(owner.animation_stabilize_mode_combo.currentData(), "affine")
        self.assertEqual(owner.animation_timeline_label.text(), "Oś czasu")
        self.assertEqual(owner.animation_loop_clear_btn.text(), "Wyczyść pętlę")
        self.assertEqual(owner.bg_animation_enabled_chk.text(), "Animacja aktywna")
        self.assertEqual(owner.animation_studio_frame_index_label.text(), "Klatka")
        self.assertEqual(owner.animation_preview_scale_combo.currentIndex(), 2)
        self.assertEqual(owner.animation_preview_scale_combo.itemText(0), "Dopasuj szerokość")
        self.assertIn("kopiuje pliki", owner.animation_duplicate_repeat_spin.toolTip())


if __name__ == "__main__":
    unittest.main()
