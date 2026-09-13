"""Weather inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QWidget

TranslateFn = Callable[[str, str], str]


def setup_weather_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
    make_compact_labeled_row: Callable[..., QWidget],
    make_compact_color_grid: Callable[..., QWidget],
    add_compact_color_cell: Callable[[str, QLineEdit], QWidget],
) -> None:
    """Populate the Theme Designer weather inspector tab on ``owner``."""
    owner.inspector_weather_hint = QLabel(
        "Weather widgets use Open-Meteo data configured in Configuration > Weather."
    )
    owner.inspector_weather_hint.setWordWrap(True)
    owner.inspector_weather_hint.setObjectName("selectionSummaryLabel")

    owner.weather_tool_current_btn = QPushButton("Weather Current")
    owner.weather_tool_wide_btn = QPushButton("Wide")
    owner.weather_tool_hero_btn = QPushButton("Hero")
    owner.weather_tool_forecast_btn = QPushButton("Weather 7D")
    owner.weather_tool_convert_legacy_btn = QPushButton("Convert legacy")
    for btn in (
        owner.weather_tool_current_btn,
        owner.weather_tool_wide_btn,
        owner.weather_tool_hero_btn,
        owner.weather_tool_forecast_btn,
        owner.weather_tool_convert_legacy_btn,
    ):
        btn.setObjectName("quickAddButton")
        btn.setMinimumHeight(24)
    owner.weather_tool_current_btn.clicked.connect(owner.add_weather_current_widget)
    owner.weather_tool_wide_btn.clicked.connect(lambda: owner.add_weather_current_widget("wide"))
    owner.weather_tool_hero_btn.clicked.connect(lambda: owner.add_weather_current_widget("hero"))
    owner.weather_tool_forecast_btn.clicked.connect(owner.add_weather_forecast_widget)
    owner.weather_tool_convert_legacy_btn.clicked.connect(owner.convert_legacy_weather_widgets)
    owner.weather_tools_row = wrap_row(
        owner.weather_tool_current_btn,
        owner.weather_tool_wide_btn,
        owner.weather_tool_hero_btn,
        owner.weather_tool_forecast_btn,
        owner.weather_tool_convert_legacy_btn,
    )
    owner.row_weather_tools = make_label("Weather tools")
    owner.inspector_weather_layout.addRow(owner.row_weather_tools, owner.weather_tools_row)

    owner.weather_designer_city_search_edit = QLineEdit()
    owner.weather_designer_city_search_edit.setPlaceholderText("Search city, e.g. Warsaw")
    owner.weather_designer_search_btn = QPushButton("Search")
    owner.weather_designer_results_combo = QComboBox()
    owner.weather_designer_results_combo.addItem("No city selected", None)
    owner.weather_designer_apply_btn = QPushButton("Apply city")
    owner.weather_designer_refresh_btn = QPushButton("Refresh weather")
    owner.weather_designer_results_combo.setMinimumWidth(160)
    owner.weather_city_row = wrap_row(
        owner.weather_designer_city_search_edit,
        owner.weather_designer_search_btn,
        owner.weather_designer_results_combo,
        owner.weather_designer_apply_btn,
        owner.weather_designer_refresh_btn,
        stretch_first=True,
    )
    owner.weather_designer_search_row = owner.weather_city_row
    owner.weather_designer_actions_row = owner.weather_city_row
    owner.row_weather_city = make_label("City")
    owner.row_weather_city_search = owner.row_weather_city
    owner.row_weather_city_results = make_label("Results")
    owner.row_weather_city_actions = make_label("Weather config")
    owner.inspector_weather_layout.addRow(owner.row_weather_city, owner.weather_city_row)
    owner.weather_designer_search_btn.clicked.connect(owner.search_designer_weather_city)
    owner.weather_designer_city_search_edit.returnPressed.connect(owner.search_designer_weather_city)
    owner.weather_designer_results_combo.currentIndexChanged.connect(owner._apply_selected_designer_weather_city)
    owner.weather_designer_apply_btn.clicked.connect(owner.apply_designer_weather_config)
    owner.weather_designer_refresh_btn.clicked.connect(owner.refresh_designer_weather_now)

    owner.weather_source_combo = QComboBox()
    owner.weather_format_combo = QComboBox()
    owner.weather_format_combo.addItem("{value}", "{value}")
    owner.weather_format_combo.addItem("City: {value}", "City: {value}")
    owner.weather_format_combo.addItem("Temp: {value}", "Temp: {value}")
    owner.weather_format_combo.addItem("Weather: {value}", "Weather: {value}")
    owner.weather_format_combo.addItem("Wind: {value}", "Wind: {value}")
    owner.weather_format_combo.addItem("Humidity: {value}", "Humidity: {value}")
    owner.weather_format_combo.addItem("High: {value}", "High: {value}")
    owner.weather_format_combo.addItem("Low: {value}", "Low: {value}")
    owner.weather_source_compact_label = QLabel("Source")
    owner.weather_format_compact_label = QLabel("Format")
    owner.weather_binding_row = make_compact_labeled_row(
        (owner.weather_source_compact_label, owner.weather_source_combo),
        (owner.weather_format_compact_label, owner.weather_format_combo),
        stretch_first=True,
    )
    owner.row_weather_source = make_label("Weather binding")
    owner.row_weather_format = make_label("Weather format")
    owner.inspector_weather_layout.addRow(owner.row_weather_source, owner.weather_binding_row)

    for spin in (
        owner.weather_widget_title_font_spin,
        owner.weather_widget_body_font_spin,
        owner.weather_widget_detail_font_spin,
    ):
        spin.setMaximumWidth(84)
    owner.weather_widget_fonts_row = wrap_row(
        QLabel("Location"),
        owner.weather_widget_title_font_spin,
        QLabel("Temp"),
        owner.weather_widget_body_font_spin,
        QLabel("Detail"),
        owner.weather_widget_detail_font_spin,
    )
    owner.weather_widget_colors_row = make_compact_color_grid(
        add_compact_color_cell("Location", owner.weather_widget_title_color_edit),
        add_compact_color_cell("Temp", owner.weather_widget_body_color_edit),
        add_compact_color_cell("Detail", owner.weather_widget_detail_color_edit),
        add_compact_color_cell("Panel", owner.weather_widget_panel_color_edit),
    )
    owner.row_weather_widget_fonts = make_label("Fonts")
    owner.row_weather_widget_colors = make_label("Colors")
    owner.row_weather_widget_transparent_bg = make_label("Background")
    owner.row_weather_widget_animate_icons = make_label("Icon motion")
    owner.inspector_weather_layout.addRow(owner.row_weather_widget_fonts, owner.weather_widget_fonts_row)
    owner.inspector_weather_layout.addRow(owner.row_weather_widget_colors, owner.weather_widget_colors_row)
    owner.inspector_weather_layout.addRow(
        owner.row_weather_widget_transparent_bg,
        owner.weather_widget_transparent_bg_chk,
    )
    owner.inspector_weather_layout.addRow(
        owner.row_weather_widget_animate_icons,
        owner.weather_widget_animate_icons_chk,
    )
    owner.weather_source_combo.currentIndexChanged.connect(owner._on_weather_source_changed)
    owner.weather_format_combo.currentIndexChanged.connect(owner._on_weather_format_changed)
    owner._populate_weather_source_combo()
    owner.inspector_weather_layout.addRow(owner.inspector_weather_hint)


def refresh_weather_inspector_labels(owner: Any, translate: TranslateFn) -> None:
    """Refresh labels for weather inspector controls."""
    if hasattr(owner, "weather_tool_current_btn"):
        owner.weather_tool_current_btn.setText(translate("Weather Current", "Pogoda teraz"))
    if hasattr(owner, "weather_tool_wide_btn"):
        owner.weather_tool_wide_btn.setText(translate("Wide", "Szeroki"))
    if hasattr(owner, "weather_tool_hero_btn"):
        owner.weather_tool_hero_btn.setText(translate("Hero", "Hero"))
    if hasattr(owner, "weather_tool_forecast_btn"):
        owner.weather_tool_forecast_btn.setText(translate("Weather 7D", "Prognoza 7 dni"))
    if hasattr(owner, "weather_tool_convert_legacy_btn"):
        owner.weather_tool_convert_legacy_btn.setText(translate("Convert legacy", "Konwertuj stare"))
    if hasattr(owner, "weather_designer_search_btn"):
        owner.weather_designer_search_btn.setText(translate("Search", "Szukaj"))
    if hasattr(owner, "weather_designer_apply_btn"):
        owner.weather_designer_apply_btn.setText(translate("Apply", "Zastosuj"))
    if hasattr(owner, "weather_designer_refresh_btn"):
        owner.weather_designer_refresh_btn.setText(translate("Refresh", "Odśwież"))
    if hasattr(owner, "inspector_weather_hint"):
        owner.inspector_weather_hint.setText(
            translate(
                "Weather components use the city and refresh interval from Configuration > Weather. Use the buttons above to insert ready-made weather layouts.",
                "Komponenty pogody używają miasta i odświeżania z Konfiguracja > Pogoda. Przyciski powyżej dodają gotowe układy pogody.",
            )
        )
