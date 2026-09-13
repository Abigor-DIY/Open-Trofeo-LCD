import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui_dialogs import TTCRImportReviewDialog

_APP = QApplication.instance() or QApplication([])


class GuiDialogsTests(unittest.TestCase):
    def test_ttcr_review_dialog_returns_selected_sources(self) -> None:
        dialog = TTCRImportReviewDialog(
            None,
            theme_name="Imported",
            stat_sources=["cpu_percent", "gpu_temp"],
            stat_entries=[{"label": "CPU", "source": "cpu_percent", "x": 10, "y": 20, "box_width": 100, "box_height": 40}],
            unmapped_stats=[{"label": "GPU?", "x": 110, "y": 20, "box_width": 100, "box_height": 40}],
        )

        selected = dialog.selected_sources()

        self.assertIn((0, "cpu_percent", "CPU"), selected)
        self.assertTrue(dialog.remember_rules())


if __name__ == "__main__":
    unittest.main()
