import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QGroupBox, QLabel, QPushButton, QTabWidget, QWidget

from designer.theme_workbench_labels import refresh_theme_workbench_labels

_APP = QApplication.instance() or QApplication([])


class ThemeWorkbenchLabelTests(unittest.TestCase):
    def test_refresh_theme_workbench_labels_updates_json_and_designer_controls(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "old-designer")
        tabs.addTab(QWidget(), "old-json")
        gauge_combo = QComboBox()
        gauge_combo.addItem("old", "")
        owner = SimpleNamespace(
            preview_guides_chk=QCheckBox("old"),
            theme_doc_manual_json_label=QLabel("old"),
            theme_doc_open_external_btn=QPushButton("old"),
            theme_doc_insert_guide_btn=QPushButton("old"),
            designer_open_json_btn=QPushButton("old"),
            designer_save_as_btn=QPushButton("old"),
            theme_doc_box=QGroupBox("old"),
            theme_doc_path_caption=QLabel("old"),
            theme_doc_sources_caption=QLabel("old"),
            theme_doc_browse_btn=QPushButton("old"),
            theme_doc_use_selected_btn=QPushButton("old"),
            theme_doc_load_btn=QPushButton("old"),
            theme_doc_save_btn=QPushButton("old"),
            theme_doc_save_as_btn=QPushButton("old"),
            theme_doc_apply_btn=QPushButton("old"),
            theme_doc_stop_before_apply_chk=QCheckBox("old"),
            theme_doc_resume_chk=QCheckBox("old"),
            studio_toolbar_load_btn=QPushButton("old"),
            studio_toolbar_save_btn=QPushButton("old"),
            studio_toolbar_preview_btn=QPushButton("old"),
            studio_toolbar_apply_btn=QPushButton("old"),
            studio_toolbar_reload_btn=QPushButton("old"),
            studio_toolbar_export_btn=QPushButton("old"),
            studio_left_tabs=tabs,
            designer_theme_gauge_bar_label=QLabel("old"),
            designer_reload_btn=QPushButton("old"),
            designer_write_btn=QPushButton("old"),
            designer_animation_mode_btn=QPushButton("old"),
            designer_assets_toggle_btn=QPushButton("old"),
            designer_preview_btn=QPushButton("old"),
            designer_apply_btn=QPushButton("old"),
            designer_theme_gauge_style_combo=gauge_combo,
        )

        refresh_theme_workbench_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.preview_guides_chk.text(), "Pokaż ramki warstw")
        self.assertEqual(owner.theme_doc_manual_json_label.text(), "JSON ręczny:")
        self.assertEqual(owner.theme_doc_open_external_btn.text(), "Otwórz plik JSON…")
        self.assertIn("opisem pól", owner.theme_doc_open_external_btn.toolTip())
        self.assertEqual(owner.designer_open_json_btn.text(), "Otwórz JSON…")
        self.assertEqual(owner.designer_save_as_btn.text(), "Zapisz jako")
        self.assertIn("nowy plik", owner.designer_save_as_btn.toolTip())
        self.assertEqual(owner.theme_doc_box.title(), "Motyw")
        self.assertEqual(owner.theme_doc_load_btn.text(), "Wczytaj")
        self.assertEqual(owner.theme_doc_stop_before_apply_chk.text(), "Zatrzymaj runtime przed apply")
        self.assertEqual(owner.studio_toolbar_reload_btn.text(), "JSON → Projektant")
        self.assertEqual(owner.studio_toolbar_export_btn.text(), "Projektant → JSON")
        self.assertEqual(owner.studio_left_tabs.tabText(0), "Projektant")
        self.assertEqual(owner.designer_theme_gauge_bar_label.text(), "Domyślny preset gauge (meta.gauge_style):")
        self.assertEqual(owner.designer_reload_btn.text(), "Wczytaj motyw")
        self.assertEqual(owner.designer_assets_toggle_btn.text(), "Multimedia")
        self.assertEqual(owner.designer_theme_gauge_style_combo.itemText(0), "(domyślny z nazwy motywu)")


if __name__ == "__main__":
    unittest.main()
