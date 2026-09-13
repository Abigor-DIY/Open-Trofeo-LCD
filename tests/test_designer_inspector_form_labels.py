import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit, QPushButton

from designer.inspector_form_labels import refresh_designer_inspector_form_labels

_APP = QApplication.instance() or QApplication([])


class DesignerInspectorFormLabelTests(unittest.TestCase):
    def test_refresh_designer_inspector_form_labels_updates_rows_and_controls(self) -> None:
        owner = SimpleNamespace(
            row_general_id=QLabel("old"),
            row_content_text=QLabel("old"),
            row_appearance_font=QLabel("old"),
            row_gauge_ring=QLabel("old"),
            row_geometry_group_bounds=QLabel("old"),
            row_motion_enabled=QLabel("old"),
            row_image_preview=QLabel("old"),
            row_media_bg_preview=QLabel("old"),
            panel_fill_compact_label=QLabel("old"),
            image_fit_compact_label=QLabel("old"),
            weather_source_compact_label=QLabel("old"),
            motion_enabled_chk=QCheckBox("old"),
            motion_capture_current_btn=QPushButton("old"),
            motion_remove_btn=QPushButton("old"),
            designer_path_browse_btn=QPushButton("old"),
            designer_path_prepare_btn=QPushButton("old"),
            designer_image_fullscreen_btn=QPushButton("old"),
            designer_image_left_half_btn=QPushButton("old"),
            designer_image_right_half_btn=QPushButton("old"),
            designer_image_reset_btn=QPushButton("old"),
            designer_import_image_btn=QPushButton("old"),
            designer_image_preview_label=QLabel("old"),
            designer_gauge_low_edit=QLineEdit(),
            designer_gauge_mid_edit=QLineEdit(),
            designer_gauge_high_edit=QLineEdit(),
            preview_tools_label=QLabel("old"),
        )

        caption = refresh_designer_inspector_form_labels(owner, lambda _en, pl: pl)

        self.assertEqual(caption, "Podgląd tła")
        self.assertEqual(owner.row_general_id.text(), "ID elementu")
        self.assertEqual(owner.row_content_text.text(), "Tekst")
        self.assertEqual(owner.row_gauge_ring.text(), "Średnica pierścienia")
        self.assertEqual(owner.row_geometry_group_bounds.text(), "Grupa")
        self.assertEqual(owner.row_motion_enabled.text(), "Ruch")
        self.assertEqual(owner.panel_fill_compact_label.text(), "Kolor")
        self.assertEqual(owner.image_fit_compact_label.text(), "Dopas.")
        self.assertEqual(owner.weather_source_compact_label.text(), "Źródło")
        self.assertEqual(owner.motion_enabled_chk.text(), "Animuj element")
        self.assertEqual(owner.motion_capture_current_btn.text(), "Ustaw koniec z bieżącej")
        self.assertEqual(owner.designer_path_browse_btn.text(), "Wybierz…")
        self.assertEqual(owner.designer_image_fullscreen_btn.text(), "Ustaw fullscreen")
        self.assertEqual(owner.designer_import_image_btn.text(), "Importuj obraz do motywu")
        self.assertEqual(owner.designer_image_preview_label.text(), "Podgląd obrazu")
        self.assertEqual(owner.designer_gauge_low_edit.placeholderText(), "[R,G,B,A] — opcjonalnie, puste = z presetu")
        self.assertEqual(owner.designer_gauge_mid_edit.placeholderText(), "[R,G,B,A] — opcjonalnie")
        self.assertEqual(owner.preview_tools_label.text(), "Mysz:")


if __name__ == "__main__":
    unittest.main()
