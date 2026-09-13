import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from designer.control_widgets import initialize_designer_control_widgets


class _Owner(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def _populate_designer_source_combo(self) -> None:
        self.calls.append("sources")
        self.designer_source_combo.addItem("CPU", "cpu_percent")

    def _populate_designer_stat_gauge_preset_combo(self) -> None:
        self.calls.append("gauge-presets")
        self.designer_stat_gauge_preset_combo.addItem("Default", "default")

    def _populate_designer_theme_gauge_style_combo(self) -> None:
        self.calls.append("theme-gauge")
        self.designer_theme_gauge_style_combo.addItem("Default", "default")


class DesignerControlWidgetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_initialize_designer_control_widgets_creates_expected_defaults(self) -> None:
        owner = _Owner()

        initialize_designer_control_widgets(
            owner,
            font_families=["Sans", "Mono"],
            known_stat_display={"text", "gauge", "equalizer"},
            equalizer_color_presets={"rainbow": {"label": "Rainbow"}},
        )

        self.assertEqual(owner.calls, ["sources", "gauge-presets", "theme-gauge"])
        self.assertEqual(owner.designer_kind_combo.count(), 5)
        self.assertEqual(owner.designer_source_combo.currentData(), "cpu_percent")
        self.assertEqual(owner.designer_stat_display_combo.count(), 3)
        self.assertEqual(owner.designer_font_family_combo.count(), 2)
        self.assertEqual(owner.designer_stat_max_spin.value(), 100.0)
        self.assertEqual(owner.designer_equalizer_preset_combo.currentData(), "rainbow")
        self.assertTrue(owner.widget_cover_enabled_chk.isChecked())
        self.assertTrue(owner.weather_widget_animate_icons_chk.isChecked())
        self.assertTrue(owner.designer_snap_chk.isChecked())
        self.assertEqual(owner.motion_target_x_spin.minimum(), -5000)


if __name__ == "__main__":
    unittest.main()
