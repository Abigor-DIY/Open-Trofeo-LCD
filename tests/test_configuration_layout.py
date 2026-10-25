import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

import trofeo_gui


class ConfigurationLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        # Plain functions keep Qt's signal introspection working; no requests
        # reach the real backend and no user preferences are written by tests.
        patches = (
            patch.object(trofeo_gui, "UI_STATE_PATH", Path(self.folder.name) / "ui.json"),
            patch.object(trofeo_gui.TrofeoGui, "_save_ui_state", new=lambda self: None),
            patch.object(trofeo_gui.TrofeoGui, "refresh_fps_layer_status", new=lambda self: None),
            patch.object(trofeo_gui.TrofeoGui, "api_call", new=lambda self, *args, **kwargs:
                         getattr(self, "_layout_test_calls", []).append(args)),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.window = trofeo_gui.TrofeoGui("http://127.0.0.1:18777", start_background_tasks=False)
        self.window._layout_test_calls = []
        self.panel = self.window.configuration_panel
        self.addCleanup(self._close)

    def _close(self):
        self.panel.close()
        self.window.close()
        self.panel.deleteLater()
        self.window.deleteLater()
        self.app.processEvents()

    def test_sections_fit_after_shrinking_and_keep_actions_on_screen(self):
        self.window._ui_language = "pl"
        self.window._refresh_localized_texts()
        self.panel.setParent(None)
        for scale in (100, 140):
            self.panel.setStyleSheet(self.window._build_app_stylesheet("Plasma Blue", scale))
            for width in (1800, 700, 1000):
                self.panel.resize(width, 580)
                self.panel.show()
                self.app.processEvents()
                for index, scroll in enumerate(self.panel.section_pages):
                    with self.subTest(scale=scale, width=width, section=index):
                        self.panel.sections.setCurrentIndex(index)
                        self.app.processEvents()
                        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                        position = self.panel.action_bar.pos()
                        for value in (0, scroll.verticalScrollBar().maximum()):
                            scroll.verticalScrollBar().setValue(value)
                            self.app.processEvents()
                            self.assertEqual(self.panel.action_bar.pos(), position)
                            for button in (self.window.cfg_apply_btn, self.window.cfg_save_btn,
                                           self.window.cfg_cancel_btn):
                                rectangle = QRect(button.mapTo(self.panel, QPoint()), button.size())
                                self.assertTrue(self.panel.rect().contains(rectangle))
                                self.assertTrue(button.isVisible())

    def test_apply_from_another_section_keeps_the_pending_lcd_selection(self):
        self.window._lcd_rotation = 0
        self.window.cfg_display_rotation_combo.setCurrentIndex(1)
        for index in range(self.panel.sections.count()):
            self.panel.sections.setCurrentIndex(index)
        self.assertEqual(self.window.cfg_display_rotation_combo.currentData(), 180)
        self.window.cfg_apply_btn.click()
        self.assertIn(("lcd-config", "POST", "/v1/config", {"display_rotation": 180}),
                      self.window._layout_test_calls)


if __name__ == "__main__":
    unittest.main()
