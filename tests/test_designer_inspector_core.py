import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from designer.inspector_core import setup_core_inspector
from designer.inspector_widgets import make_field_label, wrap_inspector_row

_APP = QApplication.instance() or QApplication([])


class CoreInspectorTests(unittest.TestCase):
    def test_setup_core_inspector_populates_general_and_content_rows(self) -> None:
        general_container = QWidget()
        content_container = QWidget()
        owner = SimpleNamespace(
            inspector_general_layout=QFormLayout(general_container),
            inspector_content_layout=QFormLayout(content_container),
            designer_id_edit=QLineEdit(),
            designer_visible_chk=QCheckBox(),
            designer_locked_chk=QCheckBox(),
            designer_z_spin=QSpinBox(),
            designer_text_edit=QLineEdit(),
            designer_label_edit=QLineEdit(),
            designer_source_combo=QComboBox(),
            designer_format_edit=QLineEdit(),
            designer_stat_display_combo=QComboBox(),
            designer_stat_min_spin=QSpinBox(),
            designer_stat_max_spin=QSpinBox(),
            designer_stat_show_value_chk=QCheckBox(),
        )

        setup_core_inspector(owner, make_field_label, wrap_inspector_row)

        self.assertEqual(owner.inspector_general_layout.rowCount(), 4)
        self.assertEqual(owner.inspector_content_layout.rowCount(), 7)
        self.assertEqual(owner.row_general_id.objectName(), "headerFieldLabel")
        self.assertEqual(owner.row_content_stat_range.text(), "Zakres")
        self.assertIs(owner._stat_binding_rows_layout, owner.inspector_content_layout)
        self.assertIsNotNone(owner.designer_stat_range_row.layout())


if __name__ == "__main__":
    unittest.main()
