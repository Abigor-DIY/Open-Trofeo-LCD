import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from designer.inspector_widgets import (
    make_color_row,
    make_compact_labeled_row,
    make_field_label,
    make_inspector_tab,
    make_scrolled_inspector_tab,
    wrap_inspector_row,
)

_APP = QApplication.instance() or QApplication([])


class InspectorWidgetHelperTests(unittest.TestCase):
    def test_field_label_uses_inspector_object_name(self) -> None:
        label = make_field_label("Title")

        self.assertEqual(label.text(), "Title")
        self.assertEqual(label.objectName(), "headerFieldLabel")

    def test_inspector_tabs_use_compact_form_spacing(self) -> None:
        tab, layout = make_inspector_tab()
        scrolled, scrolled_layout = make_scrolled_inspector_tab()

        self.assertIs(tab.layout(), layout)
        self.assertEqual(layout.horizontalSpacing(), 6)
        self.assertEqual(layout.verticalSpacing(), 4)
        self.assertTrue(scrolled.widget().layout() is scrolled_layout)

    def test_row_can_stretch_first_widget(self) -> None:
        row = wrap_inspector_row(QLineEdit(), QLabel("Button"), stretch_first=True)

        self.assertEqual(row.layout().stretch(0), 1)
        self.assertEqual(row.layout().stretch(1), 0)

    def test_color_row_calls_picker_with_target_edit(self) -> None:
        picked: list[QLineEdit] = []
        target = QLineEdit()
        _row, button = make_color_row(target, picked.append)

        button.click()

        self.assertEqual(picked, [target])

    def test_compact_labeled_row_marks_captions(self) -> None:
        caption = QLabel("Source")
        row = make_compact_labeled_row((caption, QLineEdit()), stretch_last=True)

        self.assertIsNotNone(row.layout())
        self.assertEqual(caption.objectName(), "selectionSummaryLabel")


if __name__ == "__main__":
    unittest.main()
