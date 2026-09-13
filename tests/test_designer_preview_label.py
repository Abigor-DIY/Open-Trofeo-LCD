import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from designer.preview_label import PreviewLabel
from trofeo_gui import load_uncached_pixmap

_APP = QApplication.instance() or QApplication([])


class DesignerPreviewLabelTests(unittest.TestCase):
    def test_render_pending_message_toggles(self) -> None:
        label = PreviewLabel()

        label.set_render_pending(True, "Render oczekuje...")
        self.assertEqual(label._render_pending_message, "Render oczekuje...")

        label.set_render_pending(False)
        self.assertEqual(label._render_pending_message, "")

    def test_canvas_metadata_can_preserve_temporary_guides(self) -> None:
        label = PreviewLabel()

        label.set_temporary_guides([{"axis": "x", "value": 120, "label": "120"}], "dx")
        label.set_canvas_metadata(
            canvas_width=1920,
            canvas_height=462,
            elements=[],
            selected=[],
            preserve_temporary_guides=True,
        )
        self.assertEqual(label._movement_badge, "dx • 120")
        self.assertEqual(len(label._guide_lines), 1)

        label.set_canvas_metadata(canvas_width=1920, canvas_height=462, elements=[], selected=[])
        self.assertEqual(label._movement_badge, "")
        self.assertEqual(label._guide_lines, [])

    def test_load_uncached_pixmap_reads_current_file_contents(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            image = QImage(2, 2, QImage.Format_RGB32)
            image.fill(QColor("#ff0000"))
            self.assertTrue(image.save(tmp.name))
            red = load_uncached_pixmap(tmp.name).toImage().pixelColor(0, 0)

            image.fill(QColor("#0000ff"))
            self.assertTrue(image.save(tmp.name))
            blue = load_uncached_pixmap(tmp.name).toImage().pixelColor(0, 0)

        self.assertEqual(red.name(), "#ff0000")
        self.assertEqual(blue.name(), "#0000ff")


if __name__ == "__main__":
    unittest.main()
