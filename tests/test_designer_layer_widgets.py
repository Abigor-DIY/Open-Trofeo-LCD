import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLabel, QLineEdit, QListWidgetItem, QStyle

from designer.layer_widgets import LayerListWidget, LayerRowWidget, refresh_layer_panel_labels

_APP = QApplication.instance() or QApplication([])


class DesignerLayerWidgetTests(unittest.TestCase):
    def test_layer_list_selection_visible_rows_and_ids(self) -> None:
        layer_list = LayerListWidget()
        for row, ident in enumerate(("a", "b", "c")):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, ident)
            layer_list.addItem(item)
            if row == 1:
                item.setHidden(True)

        self.assertEqual(layer_list.visible_rows(), [0, 2])
        self.assertEqual(layer_list.row_ids(), ["a", "b", "c"])

        layer_list.select_rows([1, 2])
        self.assertEqual(layer_list.selected_rows_or_current(), [2])

        layer_list.select_rows([1], current_row=1, skip_hidden=False)
        self.assertEqual(layer_list.selected_rows_or_current(), [1])

        layer_list.select_rows([], current_row=-1)
        self.assertEqual(layer_list.selected_rows_or_current(), [])

    def test_layer_row_search_text_includes_badge_title_and_subtitle(self) -> None:
        icon = _APP.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        row = LayerRowWidget(
            title="[TXT] Main Title",
            subtitle="24 px center",
            icon=icon,
            visible=True,
            locked=False,
        )

        search_text = row.search_text()

        self.assertIn("main title", search_text)
        self.assertIn("24 px center", search_text)
        self.assertIn("txt", search_text)

    def test_refresh_layer_panel_labels_preserves_combo_selection(self) -> None:
        class _Owner:
            def __init__(self) -> None:
                self.designer_elements_box = QGroupBox("old")
                self.designer_elements_title_label = QLabel("old")
                self.designer_component_search = QLineEdit()
                self.designer_kind_combo = QComboBox()
                self.designer_domain_combo = QComboBox()
                self.designer_source_combo = QComboBox()
                self.source_refreshes: list[str] = []

            def _populate_designer_source_combo(self, current_source: str) -> None:
                self.source_refreshes.append(current_source)

        owner = _Owner()
        owner.designer_kind_combo.addItem("Stats", "stats")
        owner.designer_kind_combo.setCurrentIndex(0)
        owner.designer_domain_combo.addItem("Weather", "weather")
        owner.designer_domain_combo.setCurrentIndex(0)
        owner.designer_source_combo.addItem("CPU", "cpu")
        owner.designer_source_combo.setCurrentIndex(0)

        refresh_layer_panel_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.designer_elements_box.title(), "")
        self.assertEqual(owner.designer_elements_title_label.text(), "Warstwy i komponenty")
        self.assertEqual(owner.designer_component_search.placeholderText(), "Szukaj warstwy lub tekstu…")
        self.assertEqual(owner.designer_kind_combo.currentData(), "stats")
        self.assertEqual(owner.designer_kind_combo.currentText(), "Statystyki")
        self.assertEqual(owner.designer_domain_combo.currentData(), "weather")
        self.assertEqual(owner.designer_domain_combo.currentText(), "Pogoda")
        self.assertEqual(owner.source_refreshes, ["cpu"])


if __name__ == "__main__":
    unittest.main()
