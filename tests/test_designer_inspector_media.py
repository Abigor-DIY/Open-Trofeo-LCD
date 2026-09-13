import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from designer.inspector_media import setup_media_inspector
from designer.inspector_widgets import make_field_label, wrap_inspector_row

_APP = QApplication.instance() or QApplication([])


class MediaInspectorTests(unittest.TestCase):
    def test_setup_media_inspector_populates_background_rows(self) -> None:
        container = QWidget()
        owner = SimpleNamespace(
            inspector_media_layout=QFormLayout(container),
            background_preview_label=QLabel("Background preview"),
            bg_path_edit=QLineEdit(),
            bg_path_browse_btn=QPushButton("..."),
            bg_prepare_btn=QPushButton("Import background"),
            bg_kind_combo=QComboBox(),
            bg_fit_combo=QComboBox(),
            bg_opacity_spin=QDoubleSpinBox(),
            bg_rotation_spin=QSpinBox(),
            bg_base_color_edit=QLineEdit(),
            bg_base_color_btn=QPushButton("Color"),
            bg_accent_color_edit=QLineEdit(),
            bg_accent_color_btn=QPushButton("Color"),
            bg_cover_btn=QPushButton("Cover"),
            bg_contain_btn=QPushButton("Contain"),
            bg_preset_ocean_btn=QPushButton("Ocean"),
            bg_preset_amber_btn=QPushButton("Amber"),
            bg_preset_mono_btn=QPushButton("Mono"),
            bg_preset_neon_btn=QPushButton("Neon"),
            bg_texture_alpha_spin=QDoubleSpinBox(),
        )

        setup_media_inspector(owner, make_field_label, wrap_inspector_row)

        self.assertEqual(owner.inspector_media_layout.rowCount(), 9)
        self.assertEqual(owner.row_media_bg_mode.objectName(), "headerFieldLabel")
        self.assertEqual(owner.background_preview_label.objectName(), "selectionSummaryLabel")
        self.assertEqual(owner.background_preview_label.minimumHeight(), 92)
        self.assertEqual(owner.media_background_path_row.layout().stretch(0), 1)
        self.assertIsNotNone(owner.media_colors_row.layout())
        self.assertIsNotNone(owner.media_presets_row.layout())


if __name__ == "__main__":
    unittest.main()
