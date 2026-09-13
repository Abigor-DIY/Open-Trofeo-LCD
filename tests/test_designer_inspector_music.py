import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QFormLayout, QLineEdit, QSpinBox, QWidget

from designer.inspector_music import refresh_music_inspector_labels, setup_music_inspector
from designer.inspector_widgets import make_color_row, make_field_label, wrap_inspector_row

_APP = QApplication.instance() or QApplication([])


class MusicInspectorTests(unittest.TestCase):
    def test_setup_music_inspector_populates_rows_and_actions(self) -> None:
        called: list[str] = []

        container = QWidget()
        owner = SimpleNamespace(
            inspector_music_layout=QFormLayout(container),
            designer_equalizer_bars_spin=QSpinBox(),
            designer_equalizer_gap_spin=QSpinBox(),
            designer_equalizer_mirror_chk=QCheckBox(),
            widget_cover_enabled_chk=QCheckBox(),
            widget_backdrop_enabled_chk=QCheckBox(),
            widget_title_marquee_chk=QCheckBox(),
            widget_equalizer_enabled_chk=QCheckBox(),
            widget_title_font_spin=QSpinBox(),
            widget_body_font_spin=QSpinBox(),
            widget_detail_font_spin=QSpinBox(),
            widget_title_color_edit=QLineEdit(),
            widget_body_color_edit=QLineEdit(),
            widget_detail_color_edit=QLineEdit(),
            widget_panel_color_edit=QLineEdit(),
            add_now_playing_widget=lambda: called.append("now"),
            add_now_playing_widget_hero=lambda: called.append("hero"),
            add_now_playing_widget_mini=lambda: called.append("mini"),
            add_volume_widget=lambda: called.append("volume"),
            add_graphic_equalizer_widget=lambda: called.append("eq"),
        )

        setup_music_inspector(
            owner,
            make_field_label,
            wrap_inspector_row,
            lambda edit: make_color_row(edit, lambda _target: called.append("color")),
        )

        self.assertEqual(owner.inspector_music_layout.rowCount(), 14)
        self.assertEqual(owner.row_music_tools.objectName(), "headerFieldLabel")
        self.assertEqual(owner.inspector_music_hint.objectName(), "selectionSummaryLabel")
        owner.music_tool_eq_btn.click()
        self.assertEqual(called, ["eq"])

        refresh_music_inspector_labels(owner, lambda _en, pl: pl)
        self.assertEqual(owner.music_tool_volume_btn.text(), "Głośność")
        self.assertEqual(owner.music_tool_eq_btn.text(), "Korektor")
        self.assertEqual(owner.designer_equalizer_mirror_chk.text(), "Lustro od środka")


if __name__ == "__main__":
    unittest.main()
