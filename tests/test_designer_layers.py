import unittest

from designer.layers import (
    designer_item_display_name,
    designer_item_matches_domain,
    designer_item_subtitle,
    is_media_related_layer,
    is_weather_related_layer,
)


class DesignerLayerPresentationTests(unittest.TestCase):
    def test_display_name_includes_collection_and_flags(self) -> None:
        item = {"text": "LONG TEXT LAYER", "visible": False, "locked": True}

        self.assertEqual(designer_item_display_name(item, "texts", 0), "[TXT:HL] LONG TEXT LAYER")

    def test_stat_display_name_uses_humanized_source_when_label_missing(self) -> None:
        item = {"source": "cpu_percent"}

        self.assertEqual(
            designer_item_display_name(
                item,
                "stats",
                2,
                humanize_stat_source=lambda source: source.replace("_", " ").upper(),
            ),
            "[STA] CPU PERCENT",
        )

    def test_equalizer_stat_title_and_subtitle_are_stable(self) -> None:
        item = {"display": "equalizer", "equalizer_bars": 32}

        self.assertEqual(designer_item_display_name(item, "stats", 0), "[STA] Graphic EQ")
        self.assertEqual(designer_item_subtitle(item, "stats"), "music equalizer • 32 bars")

    def test_widget_weather_title_and_subtitle(self) -> None:
        item = {"kind": "weather_forecast_7d", "rect": [10, 20, 500, 120], "style": "wide"}

        self.assertEqual(designer_item_display_name(item, "widgets", 1), "[WID] Prognoza 7 dni")
        self.assertEqual(designer_item_subtitle(item, "widgets"), "500×120 • wide")

    def test_media_image_subtitle_uses_dynamic_copy(self) -> None:
        item = {"source": "media_cover", "rect": [0, 0, 80, 80]}

        self.assertEqual(designer_item_display_name(item, "images", 0), "[IMG] Okładka Now Playing")
        self.assertEqual(designer_item_subtitle(item, "images"), "dynamiczna okładka • 80×80")

    def test_media_related_layer_matches_sources_widgets_and_labels(self) -> None:
        is_music = lambda source: source in {"volume_percent", "media_title"}

        self.assertTrue(
            is_media_related_layer(
                {"source": "volume_percent"},
                "stats",
                is_music_stat_source=is_music,
                music_visual_displays=frozenset({"equalizer"}),
            )
        )
        self.assertTrue(
            is_media_related_layer(
                {"kind": "media_now_playing"},
                "widgets",
                is_music_stat_source=is_music,
                music_visual_displays=frozenset({"equalizer"}),
            )
        )
        self.assertFalse(
            is_media_related_layer(
                {"source": "cpu_percent", "label": "CPU"},
                "stats",
                is_music_stat_source=is_music,
                music_visual_displays=frozenset({"equalizer"}),
            )
        )

    def test_weather_related_layer_matches_source_and_widget(self) -> None:
        is_weather = lambda source: source.startswith("weather_")

        self.assertTrue(
            is_weather_related_layer(
                {"source": "weather_temp"},
                "stats",
                is_weather_stat_source=is_weather,
                weather_image_sources=frozenset({"weather_icon"}),
                weather_panel_prefixes=("panel_weather",),
            )
        )
        self.assertTrue(
            is_weather_related_layer(
                {"kind": "weather_forecast_7d"},
                "widgets",
                is_weather_stat_source=is_weather,
                weather_image_sources=frozenset({"weather_icon"}),
                weather_panel_prefixes=("panel_weather",),
            )
        )
        self.assertFalse(
            is_weather_related_layer(
                {"source": "cpu_percent", "label": "CPU"},
                "stats",
                is_weather_stat_source=is_weather,
                weather_image_sources=frozenset({"weather_icon"}),
                weather_panel_prefixes=("panel_weather",),
            )
        )

    def test_domain_filter_keeps_system_separate_from_music_and_weather(self) -> None:
        common = {
            "is_music_stat_source": lambda source: source == "media_title",
            "is_weather_stat_source": lambda source: source.startswith("weather_"),
            "music_visual_displays": frozenset({"equalizer"}),
            "weather_image_sources": frozenset({"weather_icon"}),
            "weather_panel_prefixes": ("panel_weather",),
        }

        self.assertTrue(designer_item_matches_domain({"source": "media_title"}, "stats", "music", **common))
        self.assertFalse(designer_item_matches_domain({"source": "media_title"}, "stats", "system", **common))
        self.assertTrue(designer_item_matches_domain({"source": "weather_temp"}, "stats", "weather", **common))
        self.assertTrue(designer_item_matches_domain({"source": "cpu_percent"}, "stats", "system", **common))


if __name__ == "__main__":
    unittest.main()
