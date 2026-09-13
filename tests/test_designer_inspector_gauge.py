import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from designer.inspector_gauge import setup_gauge_inspector
from designer.inspector_widgets import make_color_row, make_field_label

_APP = QApplication.instance() or QApplication([])


class GaugeInspectorTests(unittest.TestCase):
    def test_setup_gauge_inspector_populates_rows_and_color_controls(self) -> None:
        picked: list[QLineEdit] = []
        container = QWidget()
        owner = SimpleNamespace(
            inspector_gauge_layout=QFormLayout(container),
            designer_stat_stroke_width_spin=QSpinBox(),
            designer_gauge_ring_spin=QSpinBox(),
            designer_gauge_value_layout_combo=QComboBox(),
            designer_gauge_inner_alpha_spin=QDoubleSpinBox(),
            designer_stat_gauge_preset_combo=QComboBox(),
            designer_gauge_low_edit=QLineEdit(),
            designer_gauge_mid_edit=QLineEdit(),
            designer_gauge_high_edit=QLineEdit(),
            designer_gauge_smooth_spin=QDoubleSpinBox(),
            designer_gauge_match_value_chk=QCheckBox(),
        )

        setup_gauge_inspector(
            owner,
            make_field_label,
            lambda edit: make_color_row(edit, picked.append),
        )

        self.assertEqual(owner.inspector_gauge_layout.rowCount(), 10)
        self.assertEqual(owner.row_gauge_preset.objectName(), "headerFieldLabel")
        self.assertIn("opcjonalnie", owner.designer_gauge_low_edit.placeholderText())
        owner.designer_gauge_low_btn.click()
        self.assertEqual(picked, [owner.designer_gauge_low_edit])


if __name__ == "__main__":
    unittest.main()
