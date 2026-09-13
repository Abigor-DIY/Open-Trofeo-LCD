import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from theme_gallery_preview import ThemeGalleryPreviewRenderer


class ThemeGalleryPreviewRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _renderer(self) -> ThemeGalleryPreviewRenderer:
        return ThemeGalleryPreviewRenderer(stats_provider=None, resolve_path=lambda raw: Path(raw))

    def test_render_template_placeholder_uses_stable_minimum_size(self) -> None:
        pixmap = self._renderer().render_template_placeholder("Demo", "#5ec8ff", QSize(10, 10))

        self.assertFalse(pixmap.isNull())
        self.assertGreaterEqual(pixmap.width(), 220)
        self.assertGreaterEqual(pixmap.height(), 88)

    def test_theme_card_fast_preview_asset_prefers_background_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            background = root / "background.png"
            pixmap = QPixmap(32, 16)
            pixmap.fill(QColor("#123456"))
            self.assertTrue(pixmap.save(str(background)))
            theme = root / "theme.json"
            theme.write_text(
                json.dumps({"background": {"path": "background.png"}, "effects": {}}),
                encoding="utf-8",
            )

            found = self._renderer().theme_card_fast_preview_asset(str(theme))

            self.assertEqual(found, background.resolve())

    def test_runtime_theme_card_pixmap_falls_back_to_image_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.png"
            pixmap = QPixmap(64, 24)
            pixmap.fill(QColor("#abcdef"))
            self.assertTrue(pixmap.save(str(path)))

            rendered = self._renderer().runtime_theme_card_pixmap({"type": "image", "path": str(path)}, QSize(32, 12))

            self.assertFalse(rendered.isNull())
            self.assertLessEqual(rendered.width(), 32)
            self.assertLessEqual(rendered.height(), 12)


if __name__ == "__main__":
    unittest.main()
