import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from flow_layout import FlowLayout


class FlowLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_items_wrap_and_increase_height_when_narrow(self) -> None:
        container = QWidget()
        layout = FlowLayout(container, h_spacing=6, v_spacing=6)
        for index in range(6):
            button = QPushButton(f"b{index}")
            button.setFixedSize(80, 30)
            layout.addWidget(button)

        single_row = layout.heightForWidth(1000)
        wrapped = layout.heightForWidth(200)

        self.assertGreaterEqual(single_row, 30)
        self.assertLessEqual(single_row, 40)
        self.assertGreater(wrapped, single_row)
        container.deleteLater()

    def test_add_widget_accepts_stretch_and_alignment(self) -> None:
        container = QWidget()
        layout = FlowLayout(container)
        button = QPushButton("x")
        layout.addWidget(button, 0, Qt.AlignVCenter)
        layout.addSpacing(8)
        layout.addStretch(1)

        self.assertEqual(layout.count(), 2)
        container.deleteLater()


if __name__ == "__main__":
    unittest.main()
