import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QFormLayout, QLineEdit, QSpinBox, QWidget

from designer.inspector_weather import refresh_weather_inspector_labels, setup_weather_inspector
from designer.inspector_widgets import (
    make_compact_color_cell,
    make_compact_color_grid,
    make_compact_labeled_row,
    make_field_label,
    wrap_inspector_row,
)

_APP = QApplication.instance() or QApplication([])


class WeatherInspectorTests(unittest.TestCase):
    def test_setup_weather_inspector_populates_rows_and_actions(self) -> None:
        called: list[str] = []
        container = QWidget()

        owner = SimpleNamespace(
            inspector_weather_layout=QFormLayout(container),
            weather_widget_title_font_spin=QSpinBox(),
            weather_widget_body_font_spin=QSpinBox(),
            weather_widget_detail_font_spin=QSpinBox(),
            weather_widget_title_color_edit=QLineEdit(),
            weather_widget_body_color_edit=QLineEdit(),
            weather_widget_detail_color_edit=QLineEdit(),
            weather_widget_panel_color_edit=QLineEdit(),
            weather_widget_transparent_bg_chk=QCheckBox(),
            weather_widget_animate_icons_chk=QCheckBox(),
            add_weather_current_widget=lambda style="compact": called.append(f"current:{style}"),
            add_weather_forecast_widget=lambda: called.append("forecast"),
            convert_legacy_weather_widgets=lambda: called.append("convert"),
            search_designer_weather_city=lambda: called.append("search"),
            _apply_selected_designer_weather_city=lambda _index: called.append("select"),
            apply_designer_weather_config=lambda: called.append("apply"),
            refresh_designer_weather_now=lambda: called.append("refresh"),
            _on_weather_source_changed=lambda _index: called.append("source"),
            _on_weather_format_changed=lambda _index: called.append("format"),
            _populate_weather_source_combo=lambda: called.append("populate"),
        )

        setup_weather_inspector(
            owner,
            make_field_label,
            wrap_inspector_row,
            make_compact_labeled_row,
            make_compact_color_grid,
            lambda caption, edit: make_compact_color_cell(caption, edit, lambda _target: called.append("color")),
        )

        self.assertEqual(owner.inspector_weather_layout.rowCount(), 8)
        self.assertEqual(owner.row_weather_tools.objectName(), "headerFieldLabel")
        self.assertEqual(owner.inspector_weather_hint.objectName(), "selectionSummaryLabel")
        self.assertEqual(owner.weather_format_combo.count(), 8)
        self.assertEqual(owner.weather_widget_title_font_spin.maximumWidth(), 84)
        owner.weather_tool_forecast_btn.click()
        self.assertIn("populate", called)
        self.assertIn("forecast", called)

        refresh_weather_inspector_labels(owner, lambda _en, pl: pl)
        self.assertEqual(owner.weather_tool_current_btn.text(), "Pogoda teraz")
        self.assertEqual(owner.weather_tool_forecast_btn.text(), "Prognoza 7 dni")
        self.assertEqual(owner.weather_tool_convert_legacy_btn.text(), "Konwertuj stare")
        self.assertEqual(owner.weather_designer_search_btn.text(), "Szukaj")
        self.assertIn("Komponenty pogody", owner.inspector_weather_hint.text())


if __name__ == "__main__":
    unittest.main()
