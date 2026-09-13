import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from designer.quick_add import populate_quick_add_menu, refresh_quick_add_groups, refresh_quick_add_labels, setup_quick_add_controls

_APP = QApplication.instance() or QApplication([])


class _Owner:
    def __init__(self) -> None:
        self.designer_quick_add_toggle_btn = QPushButton("+")
        self.populated = 0
        self.refreshed = 0
        self.calls: list[tuple[str, str]] = []

    def _populate_designer_quick_add_menu(self) -> None:
        self.populated += 1

    def _refresh_designer_quick_add_groups(self) -> None:
        self.refreshed += 1

    def quick_add_designer_element(self, collection: str) -> None:
        self.calls.append(("quick", collection))

    def add_stat_visual_widget(self, kind: str) -> None:
        self.calls.append(("visual", kind))

    def add_now_playing_widget(self) -> None:
        self.calls.append(("music", "now"))

    def add_now_playing_widget_hero(self) -> None:
        self.calls.append(("music", "hero"))

    def add_now_playing_widget_mini(self) -> None:
        self.calls.append(("music", "mini"))

    def add_analog_clock_widget(self, style: str) -> None:
        self.calls.append(("clock", style))

    def add_gauge_ring_bundle(self, style: str) -> None:
        self.calls.append(("gauge", style))

    def add_game_fps_widget(self) -> None:
        self.calls.append(("game", "fps"))

    def add_volume_widget(self) -> None:
        self.calls.append(("music", "volume"))

    def add_graphic_equalizer_widget(self) -> None:
        self.calls.append(("music", "eq"))

    def add_weather_current_widget(self, style: str = "compact") -> None:
        self.calls.append(("weather", style))

    def add_weather_forecast_widget(self) -> None:
        self.calls.append(("weather", "forecast"))


class DesignerQuickAddTests(unittest.TestCase):
    def test_setup_quick_add_controls_wires_groups_menu_and_buttons(self) -> None:
        owner = _Owner()

        container = setup_quick_add_controls(owner)

        self.assertIs(container, owner.designer_quick_add_container)
        self.assertEqual(owner.quick_add_group_basics.title(), "Basics")
        self.assertEqual(owner.quick_add_group_music.title(), "Music & audio")
        self.assertEqual(owner.quick_add_group_weather.title(), "Weather")
        self.assertEqual(owner.quick_add_group_widgets.title(), "Widgets")
        self.assertIs(owner.designer_quick_add_toggle_btn.menu(), owner.designer_quick_add_menu)
        self.assertEqual(owner.populated, 1)
        self.assertEqual(owner.refreshed, 1)

        owner.quick_add_text_btn.click()
        owner.quick_add_gauge_cyber_btn.click()

        self.assertIn(("quick", "texts"), owner.calls)
        self.assertIn(("gauge", "cyber"), owner.calls)

    def test_populate_quick_add_menu_filters_by_domain(self) -> None:
        owner = _Owner()
        setup_quick_add_controls(owner)
        translate = lambda en, _pl: en

        populate_quick_add_menu(owner, translate=translate, domain="music")
        music_labels = [action.text() for action in owner.designer_quick_add_menu.actions() if action.text()]
        self.assertIn("Music & audio", music_labels)
        self.assertIn("Now Playing", music_labels)
        self.assertNotIn("Text", music_labels)
        self.assertNotIn("Weather Current", music_labels)
        self.assertNotIn("Widgets", music_labels)

        populate_quick_add_menu(owner, translate=translate, domain="weather")
        weather_labels = [action.text() for action in owner.designer_quick_add_menu.actions() if action.text()]
        self.assertIn("Weather", weather_labels)
        self.assertIn("Weather Wide", weather_labels)
        self.assertIn("Widgets", weather_labels)
        self.assertNotIn("Music & audio", weather_labels)

        populate_quick_add_menu(owner, translate=translate, domain="system")
        system_labels = [action.text() for action in owner.designer_quick_add_menu.actions() if action.text()]
        self.assertIn("Basics", system_labels)
        self.assertIn("Text", system_labels)
        self.assertIn("Widgets", system_labels)
        self.assertNotIn("Now Playing", system_labels)

    def test_refresh_quick_add_groups_filters_by_domain(self) -> None:
        owner = _Owner()
        setup_quick_add_controls(owner)

        refresh_quick_add_groups(owner, domain="music")
        self.assertTrue(owner.quick_add_group_basics.isHidden())
        self.assertFalse(owner.quick_add_group_music.isHidden())
        self.assertTrue(owner.quick_add_group_weather.isHidden())
        self.assertTrue(owner.quick_add_group_widgets.isHidden())

        refresh_quick_add_groups(owner, domain="weather")
        self.assertTrue(owner.quick_add_group_basics.isHidden())
        self.assertTrue(owner.quick_add_group_music.isHidden())
        self.assertFalse(owner.quick_add_group_weather.isHidden())
        self.assertTrue(owner.quick_add_group_widgets.isHidden())

        refresh_quick_add_groups(owner, domain="all")
        self.assertFalse(owner.quick_add_group_basics.isHidden())
        self.assertFalse(owner.quick_add_group_music.isHidden())
        self.assertFalse(owner.quick_add_group_weather.isHidden())
        self.assertFalse(owner.quick_add_group_widgets.isHidden())

    def test_refresh_quick_add_labels_updates_group_and_button_texts(self) -> None:
        owner = _Owner()
        setup_quick_add_controls(owner)

        refresh_quick_add_labels(owner, lambda _en, pl: pl)

        self.assertEqual(owner.quick_add_group_basics.title(), "Podstawowe")
        self.assertEqual(owner.quick_add_group_weather.title(), "Pogoda")
        self.assertEqual(owner.designer_quick_add_toggle_btn.toolTip(), "Dodaj komponent")
        self.assertEqual(owner.quick_add_text_btn.text(), "Tekst")
        self.assertEqual(owner.quick_add_weather_forecast_btn.text(), "Prognoza 7 dni")
        self.assertEqual(owner.quick_add_game_fps_btn.text(), "FPS gry")


if __name__ == "__main__":
    unittest.main()
