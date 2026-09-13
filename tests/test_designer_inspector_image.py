import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from designer.inspector_image import setup_image_inspector
from designer.inspector_widgets import make_compact_labeled_row, make_field_label, wrap_inspector_row

_APP = QApplication.instance() or QApplication([])


class ImageInspectorTests(unittest.TestCase):
    def test_setup_image_inspector_populates_rows_and_actions(self) -> None:
        called: list[str] = []
        container = QWidget()
        owner = SimpleNamespace(
            inspector_image_layout=QFormLayout(container),
            designer_path_edit=QLineEdit(),
            designer_fit_combo=QComboBox(),
            designer_opacity_spin=QDoubleSpinBox(),
            designer_rotation_spin=QDoubleSpinBox(),
            browse_designer_image_path=lambda: called.append("browse"),
            import_image_as_designer_element=lambda: called.append("import"),
            apply_image_rect_preset=lambda preset: called.append(preset),
        )

        setup_image_inspector(owner, make_field_label, wrap_inspector_row, make_compact_labeled_row)

        self.assertEqual(owner.inspector_image_layout.rowCount(), 5)
        self.assertEqual(owner.row_image_path.objectName(), "headerFieldLabel")
        self.assertEqual(owner.designer_image_preview_label.objectName(), "selectionSummaryLabel")
        self.assertEqual(owner.designer_opacity_spin.maximumWidth(), 84)
        self.assertEqual(owner.designer_rotation_spin.maximumWidth(), 84)
        owner.designer_image_right_half_btn.click()
        owner.designer_import_image_btn.click()
        self.assertEqual(called, ["right-half", "import"])


if __name__ == "__main__":
    unittest.main()
