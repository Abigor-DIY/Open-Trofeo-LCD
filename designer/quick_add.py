"""Quick Add controls for the Theme Designer layer panel."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

TranslateFn = Callable[[str, str], str]


def _quick_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("quickAddButton")
    btn.setMinimumHeight(24)
    return btn


def setup_quick_add_controls(owner: object) -> QWidget:
    """Create Quick Add groups and menu, wiring actions to the main window."""
    owner.designer_quick_add_container = QWidget()
    quick_container_layout = QVBoxLayout(owner.designer_quick_add_container)
    quick_container_layout.setContentsMargins(0, 0, 0, 0)
    quick_container_layout.setSpacing(6)
    owner.designer_quick_add_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

    owner.quick_add_group_basics = QGroupBox("Basics")
    owner.quick_add_group_basics.setFlat(True)
    basics_grid = QGridLayout(owner.quick_add_group_basics)
    basics_grid.setHorizontalSpacing(3)
    basics_grid.setVerticalSpacing(3)
    owner.quick_add_text_btn = _quick_button("Text")
    owner.quick_add_stat_btn = _quick_button("Stat")
    owner.quick_add_image_btn = _quick_button("Image")
    owner.quick_add_panel_btn = _quick_button("Panel")
    owner.quick_add_progress_btn = _quick_button("Progress")
    owner.quick_add_sparkline_btn = _quick_button("Sparkline")
    basics_grid.addWidget(owner.quick_add_text_btn, 0, 0)
    basics_grid.addWidget(owner.quick_add_stat_btn, 0, 1)
    basics_grid.addWidget(owner.quick_add_image_btn, 1, 0)
    basics_grid.addWidget(owner.quick_add_panel_btn, 1, 1)
    basics_grid.addWidget(owner.quick_add_progress_btn, 2, 0)
    basics_grid.addWidget(owner.quick_add_sparkline_btn, 2, 1)

    owner.quick_add_group_music = QGroupBox("Music & audio")
    owner.quick_add_group_music.setFlat(True)
    music_grid = QGridLayout(owner.quick_add_group_music)
    music_grid.setHorizontalSpacing(3)
    music_grid.setVerticalSpacing(3)
    owner.quick_add_now_playing_btn = _quick_button("Now Playing")
    owner.quick_add_now_playing_hero_btn = _quick_button("Now Playing Hero")
    owner.quick_add_now_playing_mini_btn = _quick_button("Now Playing Mini")
    owner.quick_add_volume_btn = _quick_button("Volume")
    owner.quick_add_equalizer_btn = _quick_button("Graphic EQ")
    music_grid.addWidget(owner.quick_add_now_playing_btn, 0, 0)
    music_grid.addWidget(owner.quick_add_now_playing_hero_btn, 0, 1)
    music_grid.addWidget(owner.quick_add_now_playing_mini_btn, 1, 0)
    music_grid.addWidget(owner.quick_add_volume_btn, 1, 1)
    music_grid.addWidget(owner.quick_add_equalizer_btn, 2, 0, 1, 2)

    owner.quick_add_group_weather = QGroupBox("Weather")
    owner.quick_add_group_weather.setFlat(True)
    weather_grid = QGridLayout(owner.quick_add_group_weather)
    weather_grid.setHorizontalSpacing(3)
    weather_grid.setVerticalSpacing(3)
    owner.quick_add_weather_current_btn = _quick_button("Weather Current")
    owner.quick_add_weather_forecast_btn = _quick_button("Weather 7D")
    weather_grid.addWidget(owner.quick_add_weather_current_btn, 0, 0)
    weather_grid.addWidget(owner.quick_add_weather_forecast_btn, 0, 1)

    owner.quick_add_group_widgets = QGroupBox("Widgets")
    owner.quick_add_group_widgets.setFlat(True)
    widgets_grid = QGridLayout(owner.quick_add_group_widgets)
    widgets_grid.setHorizontalSpacing(3)
    widgets_grid.setVerticalSpacing(3)
    owner.quick_add_analog_clock_btn = _quick_button("Analog Clock")
    owner.quick_add_clock_modern_btn = _quick_button("Clock Modern")
    owner.quick_add_clock_nordic_btn = _quick_button("Clock Nordic")
    owner.quick_add_gauge_set_btn = _quick_button("Gauge Set")
    owner.quick_add_gauge_cyber_btn = _quick_button("Gauge Cyber")
    owner.quick_add_gauge_thermal_btn = _quick_button("Gauge Thermal")
    owner.quick_add_game_fps_btn = _quick_button("Game FPS")
    widgets_grid.addWidget(owner.quick_add_analog_clock_btn, 0, 0)
    widgets_grid.addWidget(owner.quick_add_clock_modern_btn, 0, 1)
    widgets_grid.addWidget(owner.quick_add_clock_nordic_btn, 1, 0)
    widgets_grid.addWidget(owner.quick_add_gauge_set_btn, 1, 1)
    widgets_grid.addWidget(owner.quick_add_gauge_cyber_btn, 2, 0)
    widgets_grid.addWidget(owner.quick_add_gauge_thermal_btn, 2, 1)
    widgets_grid.addWidget(owner.quick_add_game_fps_btn, 3, 0, 1, 2)

    quick_container_layout.addWidget(owner.quick_add_group_basics)
    quick_container_layout.addWidget(owner.quick_add_group_music)
    quick_container_layout.addWidget(owner.quick_add_group_weather)
    quick_container_layout.addWidget(owner.quick_add_group_widgets)
    owner.designer_quick_add_container.hide()

    owner.quick_add_text_btn.clicked.connect(lambda: owner.quick_add_designer_element("texts"))
    owner.quick_add_stat_btn.clicked.connect(lambda: owner.quick_add_designer_element("stats"))
    owner.quick_add_image_btn.clicked.connect(lambda: owner.quick_add_designer_element("images"))
    owner.quick_add_panel_btn.clicked.connect(lambda: owner.quick_add_designer_element("panels"))
    owner.quick_add_progress_btn.clicked.connect(lambda: owner.add_stat_visual_widget("progress"))
    owner.quick_add_sparkline_btn.clicked.connect(lambda: owner.add_stat_visual_widget("sparkline"))
    owner.quick_add_now_playing_btn.clicked.connect(owner.add_now_playing_widget)
    owner.quick_add_now_playing_hero_btn.clicked.connect(owner.add_now_playing_widget_hero)
    owner.quick_add_now_playing_mini_btn.clicked.connect(owner.add_now_playing_widget_mini)
    owner.quick_add_analog_clock_btn.clicked.connect(lambda: owner.add_analog_clock_widget("classic"))
    owner.quick_add_clock_modern_btn.clicked.connect(lambda: owner.add_analog_clock_widget("modern"))
    owner.quick_add_clock_nordic_btn.clicked.connect(lambda: owner.add_analog_clock_widget("nordic"))
    owner.quick_add_gauge_set_btn.clicked.connect(lambda: owner.add_gauge_ring_bundle("system"))
    owner.quick_add_gauge_cyber_btn.clicked.connect(lambda: owner.add_gauge_ring_bundle("cyber"))
    owner.quick_add_gauge_thermal_btn.clicked.connect(lambda: owner.add_gauge_ring_bundle("thermal"))
    owner.quick_add_game_fps_btn.clicked.connect(owner.add_game_fps_widget)
    owner.quick_add_volume_btn.clicked.connect(owner.add_volume_widget)
    owner.quick_add_equalizer_btn.clicked.connect(owner.add_graphic_equalizer_widget)
    owner.quick_add_weather_current_btn.clicked.connect(owner.add_weather_current_widget)
    owner.quick_add_weather_forecast_btn.clicked.connect(owner.add_weather_forecast_widget)

    owner.designer_quick_add_menu = QMenu(owner.designer_quick_add_toggle_btn)
    owner.designer_quick_add_menu.setObjectName("designerQuickAddMenu")
    owner.designer_quick_add_menu.setStyleSheet(
        """
        QMenu#designerQuickAddMenu {
            background: #0f141b;
            border: 1px solid #3b82f6;
            border-radius: 10px;
            padding: 6px;
            color: #f8fafc;
        }
        QMenu#designerQuickAddMenu::item {
            padding: 7px 14px 7px 14px;
            border-radius: 7px;
            min-width: 190px;
        }
        QMenu#designerQuickAddMenu::item:selected {
            background: #2563eb;
            color: #ffffff;
        }
        QMenu#designerQuickAddMenu::item:pressed {
            background: #1d4ed8;
        }
        QMenu#designerQuickAddMenu::separator {
            height: 1px;
            background: #263242;
            margin: 6px 4px;
        }
        QMenu#designerQuickAddMenu::item:disabled {
            color: #60a5fa;
            background: transparent;
            font-weight: 800;
        }
        """
    )
    owner._populate_designer_quick_add_menu()
    owner.designer_quick_add_menu.aboutToShow.connect(owner._populate_designer_quick_add_menu)
    owner._refresh_designer_quick_add_groups()
    owner.designer_quick_add_toggle_btn.setMenu(owner.designer_quick_add_menu)
    return owner.designer_quick_add_container


def populate_quick_add_menu(owner: object, *, translate: TranslateFn, domain: str) -> None:
    """Populate the Quick Add menu for the active designer domain."""
    menu = getattr(owner, "designer_quick_add_menu", None)
    if menu is None:
        return
    menu.clear()
    domain_key = str(domain).strip().lower() or "all"

    def add_section(title: str) -> None:
        try:
            menu.addSection(title)
        except Exception:
            menu.addSeparator()

    basics: list[tuple[str, Callable[..., Any]]] = [
        (translate("Text", "Tekst"), lambda: owner.quick_add_designer_element("texts")),
        (translate("Stat", "Statystyka"), lambda: owner.quick_add_designer_element("stats")),
        (translate("Progress Bar", "Pasek postępu"), lambda: owner.add_stat_visual_widget("progress")),
        (translate("Sparkline", "Sparkline"), lambda: owner.add_stat_visual_widget("sparkline")),
        (translate("Image", "Obraz"), lambda: owner.quick_add_designer_element("images")),
        (translate("Panel", "Panel"), lambda: owner.quick_add_designer_element("panels")),
    ]
    music_audio: list[tuple[str, Callable[..., Any]]] = [
        (translate("Now Playing", "Now Playing"), owner.add_now_playing_widget),
        (translate("Now Playing Hero", "Now Playing Hero"), owner.add_now_playing_widget_hero),
        (translate("Now Playing Mini", "Now Playing Mini"), owner.add_now_playing_widget_mini),
        (translate("Volume", "Głośność"), owner.add_volume_widget),
        (translate("Graphic EQ", "Korektor graficzny"), owner.add_graphic_equalizer_widget),
    ]
    weather_widgets: list[tuple[str, Callable[..., Any]]] = [
        (translate("Weather Current", "Pogoda teraz"), owner.add_weather_current_widget),
        (translate("Weather Wide", "Pogoda szeroka"), lambda: owner.add_weather_current_widget("wide")),
        (translate("Weather Hero", "Pogoda hero"), lambda: owner.add_weather_current_widget("hero")),
        (translate("Weather 7D Forecast", "Prognoza 7 dni"), owner.add_weather_forecast_widget),
    ]
    widgets: list[tuple[str, Callable[..., Any]]] = [
        (translate("Analog Clock Classic", "Analog Clock Classic"), lambda: owner.add_analog_clock_widget("classic")),
        (translate("Analog Clock Modern", "Analog Clock Modern"), lambda: owner.add_analog_clock_widget("modern")),
        (translate("Analog Clock Nordic", "Analog Clock Nordic"), lambda: owner.add_analog_clock_widget("nordic")),
        (translate("Gauge Set: System Trio", "Gauge Set: System Trio"), lambda: owner.add_gauge_ring_bundle("system")),
        (translate("Gauge Set: Nordic Trio", "Gauge Set: Nordic Trio"), lambda: owner.add_gauge_ring_bundle("nordic")),
        (translate("Gauge Set: Cyber Trio", "Gauge Set: Cyber Trio"), lambda: owner.add_gauge_ring_bundle("cyber")),
        (translate("Gauge Set: Thermal Trio", "Gauge Set: Thermal Trio"), lambda: owner.add_gauge_ring_bundle("thermal")),
    ]

    if domain_key in {"all", "system"}:
        add_section(translate("Basics", "Podstawowe"))
        for label, handler in basics:
            action = menu.addAction(label)
            action.triggered.connect(handler)
    if domain_key in {"all", "weather"}:
        add_section(translate("Weather", "Pogoda"))
        for label, handler in weather_widgets:
            action = menu.addAction(label)
            action.triggered.connect(handler)
    if domain_key in {"all", "music"}:
        add_section(translate("Music & audio", "Muzyka i audio"))
        for label, handler in music_audio:
            action = menu.addAction(label)
            action.triggered.connect(handler)
    if domain_key != "music":
        add_section(translate("Widgets", "Widgety"))
        for label, handler in widgets:
            action = menu.addAction(label)
            action.triggered.connect(handler)


def refresh_quick_add_labels(owner: object, translate: TranslateFn) -> None:
    """Refresh visible labels for Quick Add controls."""
    if hasattr(owner, "quick_add_group_basics"):
        owner.quick_add_group_basics.setTitle(translate("Basics", "Podstawowe"))
    if hasattr(owner, "quick_add_group_music"):
        owner.quick_add_group_music.setTitle(translate("Music & audio", "Muzyka i audio"))
    if hasattr(owner, "quick_add_group_weather"):
        owner.quick_add_group_weather.setTitle(translate("Weather", "Pogoda"))
    if hasattr(owner, "quick_add_group_widgets"):
        owner.quick_add_group_widgets.setTitle(translate("Widgets", "Widgety"))
    if hasattr(owner, "designer_quick_add_toggle_btn"):
        owner.designer_quick_add_toggle_btn.setText("+")
        owner.designer_quick_add_toggle_btn.setToolTip(translate("Add component", "Dodaj komponent"))
    if hasattr(owner, "quick_add_text_btn"):
        owner.quick_add_text_btn.setText(translate("Text", "Tekst"))
    if hasattr(owner, "quick_add_stat_btn"):
        owner.quick_add_stat_btn.setText(translate("Stat", "Statystyka"))
    if hasattr(owner, "quick_add_image_btn"):
        owner.quick_add_image_btn.setText(translate("Image", "Obraz"))
    if hasattr(owner, "quick_add_panel_btn"):
        owner.quick_add_panel_btn.setText(translate("Panel", "Panel"))
    if hasattr(owner, "quick_add_progress_btn"):
        owner.quick_add_progress_btn.setText(translate("Progress", "Postęp"))
    if hasattr(owner, "quick_add_sparkline_btn"):
        owner.quick_add_sparkline_btn.setText(translate("Sparkline", "Wykres mini"))
    if hasattr(owner, "quick_add_now_playing_btn"):
        owner.quick_add_now_playing_btn.setText(translate("Now Playing", "Now Playing"))
    if hasattr(owner, "quick_add_now_playing_hero_btn"):
        owner.quick_add_now_playing_hero_btn.setText(translate("Now Playing Hero", "Now Playing Hero"))
    if hasattr(owner, "quick_add_now_playing_mini_btn"):
        owner.quick_add_now_playing_mini_btn.setText(translate("Now Playing Mini", "Now Playing Mini"))
    if hasattr(owner, "quick_add_volume_btn"):
        owner.quick_add_volume_btn.setText(translate("Volume", "Głośność"))
    if hasattr(owner, "quick_add_equalizer_btn"):
        owner.quick_add_equalizer_btn.setText(translate("Graphic EQ", "Korektor"))
    if hasattr(owner, "quick_add_weather_current_btn"):
        owner.quick_add_weather_current_btn.setText(translate("Weather Current", "Pogoda teraz"))
    if hasattr(owner, "quick_add_weather_forecast_btn"):
        owner.quick_add_weather_forecast_btn.setText(translate("Weather 7D", "Prognoza 7 dni"))
    if hasattr(owner, "quick_add_analog_clock_btn"):
        owner.quick_add_analog_clock_btn.setText(translate("Analog Clock", "Zegar analogowy"))
    if hasattr(owner, "quick_add_clock_modern_btn"):
        owner.quick_add_clock_modern_btn.setText(translate("Clock Modern", "Zegar modern"))
    if hasattr(owner, "quick_add_clock_nordic_btn"):
        owner.quick_add_clock_nordic_btn.setText(translate("Clock Nordic", "Zegar nordic"))
    if hasattr(owner, "quick_add_gauge_set_btn"):
        owner.quick_add_gauge_set_btn.setText(translate("Gauge Set", "Zestaw gauge"))
    if hasattr(owner, "quick_add_gauge_cyber_btn"):
        owner.quick_add_gauge_cyber_btn.setText(translate("Gauge Cyber", "Gauge cyber"))
    if hasattr(owner, "quick_add_gauge_thermal_btn"):
        owner.quick_add_gauge_thermal_btn.setText(translate("Gauge Thermal", "Gauge temp"))
    if hasattr(owner, "quick_add_game_fps_btn"):
        owner.quick_add_game_fps_btn.setText(translate("Game FPS", "FPS gry"))


def refresh_quick_add_groups(owner: object, *, domain: str) -> None:
    """Show Quick Add groups relevant to the active designer domain."""
    domain_key = str(domain).strip().lower() or "all"
    if hasattr(owner, "quick_add_group_basics"):
        owner.quick_add_group_basics.setVisible(domain_key in {"all", "system"})
    if hasattr(owner, "quick_add_group_music"):
        owner.quick_add_group_music.setVisible(domain_key in {"all", "music"})
    if hasattr(owner, "quick_add_group_weather"):
        owner.quick_add_group_weather.setVisible(domain_key in {"all", "weather"})
    if hasattr(owner, "quick_add_group_widgets"):
        owner.quick_add_group_widgets.setVisible(domain_key not in {"music", "weather"})
