import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QFormLayout, QPushButton, QSpinBox, QWidget

from designer.inspector_geometry import refresh_geometry_preset_labels, setup_geometry_inspector
from designer.inspector_widgets import make_field_label, wrap_inspector_row

_APP = QApplication.instance() or QApplication([])


class GeometryInspectorTests(unittest.TestCase):
    def test_setup_geometry_inspector_populates_rows_and_presets(self) -> None:
        applied: list[str] = []
        container = QWidget()
        owner = SimpleNamespace(
            inspector_geometry_layout=QFormLayout(container),
            designer_x_spin=QSpinBox(),
            designer_y_spin=QSpinBox(),
            designer_w_spin=QSpinBox(),
            designer_h_spin=QSpinBox(),
            motion_enabled_chk=QCheckBox(),
            motion_start_spin=QSpinBox(),
            motion_end_spin=QSpinBox(),
            motion_target_x_spin=QSpinBox(),
            motion_target_y_spin=QSpinBox(),
            motion_target_opacity_spin=QDoubleSpinBox(),
            motion_capture_current_btn=QPushButton("Set end from current"),
            motion_remove_btn=QPushButton("Remove motion"),
            apply_geometry_rect_preset=lambda name: applied.append(name),
        )

        setup_geometry_inspector(owner, make_field_label, wrap_inspector_row)

        self.assertEqual(owner.inspector_geometry_layout.rowCount(), 12)
        self.assertEqual(owner.row_geometry_presets.objectName(), "headerFieldLabel")
        self.assertEqual(owner.geometry_group_bounds_label.objectName(), "selectionSummaryLabel")
        self.assertEqual(owner.geometry_preset_top_btn.objectName(), "compactActionButton")
        self.assertEqual(owner.geometry_preset_top_btn.minimumWidth(), 58)
        owner.geometry_preset_center_btn.click()
        self.assertEqual(applied, ["center"])

        refresh_geometry_preset_labels(owner, lambda _en, pl: pl)
        self.assertEqual(owner.geometry_preset_top_btn.text(), "Góra")
        self.assertEqual(owner.geometry_preset_center_btn.text(), "Środek")
        self.assertEqual(owner.geometry_preset_right_btn.toolTip(), "Dopasuj zaznaczenie do prawej strony ekranu LCD")


if __name__ == "__main__":
    unittest.main()
