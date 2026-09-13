import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFormLayout, QWidget

from designer.inspector_animation import refresh_animation_inspector_labels, setup_animation_inspector
from designer.inspector_widgets import make_field_label

_APP = QApplication.instance() or QApplication([])


class AnimationInspectorTests(unittest.TestCase):
    def test_setup_animation_inspector_populates_rows_and_action(self) -> None:
        called: list[str] = []
        container = QWidget()
        owner = SimpleNamespace(
            inspector_animation_layout=QFormLayout(container),
            _go_animation_studio=lambda: called.append("studio"),
        )

        setup_animation_inspector(owner, make_field_label)

        self.assertEqual(owner.inspector_animation_layout.rowCount(), 2)
        self.assertEqual(owner.row_animation_overview.objectName(), "headerFieldLabel")
        self.assertEqual(owner.inspector_animation_details_hint.objectName(), "selectionSummaryLabel")
        self.assertTrue(owner.inspector_animation_details_hint.wordWrap())
        self.assertEqual(owner.open_animation_studio_btn.objectName(), "secondaryAccentButton")
        owner.open_animation_studio_btn.click()
        self.assertEqual(called, ["studio"])

        refresh_animation_inspector_labels(owner, lambda _en, pl: pl)
        self.assertIn("Studio animacji", owner.inspector_animation_details_hint.text())
        self.assertEqual(owner.open_animation_studio_btn.text(), "Otwórz Studio animacji")


if __name__ == "__main__":
    unittest.main()
