import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from designer.inspector_appearance import refresh_appearance_inspector_labels, setup_appearance_inspector
from designer.inspector_widgets import make_color_row, make_compact_labeled_row, make_field_label, wrap_inspector_row

_APP = QApplication.instance() or QApplication([])


class AppearanceInspectorTests(unittest.TestCase):
    def test_setup_appearance_inspector_populates_rows_and_controls(self) -> None:
        picked: list[QLineEdit] = []
        container = QWidget()
        owner = SimpleNamespace(
            inspector_appearance_layout=QFormLayout(container),
            designer_font_family_combo=QFontComboBox(),
            designer_font_size_spin=QSpinBox(),
            designer_font_bold_chk=QCheckBox("B"),
            designer_font_italic_chk=QCheckBox("I"),
            designer_font_underline_chk=QCheckBox("U"),
            designer_align_combo=QComboBox(),
            designer_color_edit=QLineEdit(),
            designer_label_color_edit=QLineEdit(),
            designer_value_color_edit=QLineEdit(),
            designer_track_color_edit=QLineEdit(),
            designer_fill_color_edit=QLineEdit(),
            designer_equalizer_transparent_bg_chk=QCheckBox(),
            designer_equalizer_preset_combo=QComboBox(),
            designer_equalizer_threshold_spin=QSpinBox(),
            designer_equalizer_threshold_color_edit=QLineEdit(),
            designer_sparkline_points_spin=QSpinBox(),
            designer_sparkline_fill_opacity_spin=QDoubleSpinBox(),
            designer_sparkline_show_points_chk=QCheckBox(),
            panel_fill_edit=QLineEdit(),
            panel_fill_btn=QPushButton("Color"),
            panel_opacity_spin=QDoubleSpinBox(),
            panel_radius_spin=QSpinBox(),
            pick_color_for_edit=picked.append,
        )
        owner.designer_font_size_spin.setRange(6, 120)
        owner.designer_font_size_spin.setValue(20)

        setup_appearance_inspector(
            owner,
            make_field_label,
            wrap_inspector_row,
            lambda edit: make_color_row(edit, picked.append),
            make_compact_labeled_row,
        )

        self.assertEqual(owner.inspector_appearance_layout.rowCount(), 14)
        self.assertEqual(owner.row_appearance_font.objectName(), "headerFieldLabel")
        self.assertEqual(owner.panel_opacity_spin.maximumWidth(), 84)
        owner.designer_font_plus_btn.click()
        self.assertEqual(owner.designer_font_size_spin.value(), 21)
        owner.designer_font_minus_btn.click()
        self.assertEqual(owner.designer_font_size_spin.value(), 20)
        owner.designer_color_btn.click()
        self.assertEqual(picked, [owner.designer_color_edit])

        refresh_appearance_inspector_labels(owner, lambda _en, pl: pl)
        self.assertEqual(owner.designer_equalizer_transparent_bg_chk.text(), "Przezroczyste tło")


if __name__ == "__main__":
    unittest.main()
