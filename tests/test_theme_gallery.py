import tempfile
import unittest
from os import utime
from pathlib import Path

from theme_gallery import (
    default_new_theme_path,
    filtered_theme_card_entries,
    new_theme_filename,
    read_theme_document_for_card,
    sanitize_theme_name_for_filename,
    theme_card_grid_metrics,
    theme_card_category,
    theme_card_stats,
    theme_modified_label,
    theme_type_badge,
)


class ThemeGalleryTests(unittest.TestCase):
    def test_theme_type_badge_uses_translated_known_types(self) -> None:
        translate = lambda _en, pl: pl

        self.assertEqual(theme_type_badge({"type": "theme-doc"}, translate), "Motyw")
        self.assertEqual(theme_type_badge({"type": "image"}, translate), "Obraz")
        self.assertEqual(theme_type_badge({"type": "custom"}, translate), "custom")

    def test_new_theme_path_helpers_sanitize_name_and_template_suffix(self) -> None:
        self.assertEqual(sanitize_theme_name_for_filename("My Dashboard!"), "my_dashboard")
        self.assertEqual(sanitize_theme_name_for_filename(""), "nowy_motyw")
        self.assertEqual(new_theme_filename("My Dashboard", "themes/focus_monitor.json"), "my_dashboard_focus.json")
        self.assertEqual(new_theme_filename("Nowy Motyw", "themes/nowy_motyw.json"), "nowy_motyw.json")
        self.assertEqual(
            default_new_theme_path(Path("/tmp/themes"), "Matrix", "themes/dashboard.json"),
            Path("/tmp/themes/matrix_dashboard.json"),
        )

    def test_theme_card_category_detects_animation_ttcr_and_local(self) -> None:
        animated = {"effects": {"animation": {"enabled": True, "frame_paths": ["a.png", "b.png"]}}}
        ttcr_tag = {"meta": {"tags": ["ttcr-import"]}}

        self.assertEqual(theme_card_category({"path": "themes/a.json"}, animated), "Animated")
        self.assertEqual(theme_card_category({"path": "themes/a.json"}, ttcr_tag), "TTCR")
        self.assertEqual(theme_card_category({"path": "themes/foo_ttcr.json"}, None), "TTCR")
        self.assertEqual(theme_card_category({"path": "themes/foo.json"}, None), "Local")

    def test_theme_card_stats_counts_background_images_and_animation_frames(self) -> None:
        document = {
            "background": {"path": "background.png"},
            "images": [{"path": "a.png"}, {"path": ""}, {"path": "b.png"}],
            "effects": {"animation": {"frame_paths": ["1.png", "2.png", "3.png"]}},
        }

        self.assertEqual(theme_card_stats(document), (3, 3))
        self.assertEqual(theme_card_stats(None), (0, 0))

    def test_read_theme_document_for_card_loads_theme_doc_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            theme = root / "theme.json"
            theme.write_text('{"meta": {"name": "Test"}}', encoding="utf-8")

            loaded = read_theme_document_for_card(
                {"type": "theme-doc", "path": "theme.json"},
                lambda raw: root / raw,
            )
            skipped = read_theme_document_for_card({"type": "image", "path": "theme.json"}, lambda raw: root / raw)

        self.assertEqual(loaded, {"meta": {"name": "Test"}})
        self.assertIsNone(skipped)

    def test_theme_modified_label_formats_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            theme = root / "theme.json"
            theme.write_text("{}", encoding="utf-8")

            label = theme_modified_label({"path": "theme.json"}, lambda raw: root / raw)

        self.assertIn("Zmieniono:", label)
        self.assertEqual(theme_modified_label({}, lambda raw: Path(raw)), "Brak pliku")

    def test_filtered_theme_card_entries_filters_by_search_and_type(self) -> None:
        items = {
            "Alpha": {"type": "theme-doc", "path": "alpha.json"},
            "Beta Image": {"type": "image", "path": "beta.png"},
            "Gamma": {"type": "theme-doc", "path": "gamma.json"},
        }

        by_search = filtered_theme_card_entries(items, needle="beta")
        by_type = filtered_theme_card_entries(items, type_filter="Theme")

        self.assertEqual([entry.name for entry in by_search], ["Beta Image"])
        self.assertEqual([entry.name for entry in by_type], ["Alpha", "Gamma"])

    def test_filtered_theme_card_entries_filters_categories_and_exposes_stats(self) -> None:
        items = {
            "Animated": {"type": "theme-doc", "path": "animated.json"},
            "TTCR": {"type": "theme-doc", "path": "theme_ttcr.json"},
            "Local": {"type": "theme-doc", "path": "local.json"},
        }
        docs = {
            "animated.json": {
                "background": {"path": "bg.png"},
                "effects": {"animation": {"enabled": True, "frame_paths": ["1.png", "2.png"]}},
            },
            "theme_ttcr.json": {"meta": {"tags": ["ttcr-import"]}},
            "local.json": {"images": [{"path": "icon.png"}]},
        }

        animated = filtered_theme_card_entries(
            items,
            type_filter="Animated",
            document_loader=lambda item: docs[str(item["path"])],
        )

        self.assertEqual([entry.name for entry in animated], ["Animated"])
        self.assertEqual(animated[0].category, "Animated")
        self.assertEqual(animated[0].asset_count, 1)
        self.assertEqual(animated[0].animation_count, 2)

    def test_filtered_theme_card_entries_sorts_by_name(self) -> None:
        items = {
            "Bravo": {"type": "image", "path": "b.png"},
            "alpha": {"type": "image", "path": "a.png"},
        }

        self.assertEqual(
            [entry.name for entry in filtered_theme_card_entries(items, sort_mode="Name A-Z")],
            ["alpha", "Bravo"],
        )
        self.assertEqual(
            [entry.name for entry in filtered_theme_card_entries(items, sort_mode="Name Z-A")],
            ["Bravo", "alpha"],
        )

    def test_filtered_theme_card_entries_sorts_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "older.json"
            newer = root / "newer.json"
            older.write_text("{}", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            utime(older, (1_700_000_000, 1_700_000_000))
            utime(newer, (1_800_000_000, 1_800_000_000))
            items = {
                "Older": {"type": "theme-doc", "path": "older.json"},
                "Newer": {"type": "theme-doc", "path": "newer.json"},
            }

            newest = filtered_theme_card_entries(items, sort_mode="Newest", resolve_path=lambda raw: root / raw)
            oldest = filtered_theme_card_entries(items, sort_mode="Oldest", resolve_path=lambda raw: root / raw)

        self.assertEqual([entry.name for entry in newest], ["Newer", "Older"])
        self.assertEqual([entry.name for entry in oldest], ["Older", "Newer"])

    def test_theme_card_grid_metrics_matches_gallery_layout_rules(self) -> None:
        metrics = theme_card_grid_metrics(
            viewport_width=1800,
            spacing=12,
            entry_names=["A", "B", "C", "D", "E"],
            current_name="A",
        )

        self.assertEqual(metrics.columns, 4)
        self.assertFalse(metrics.compact_cards)
        self.assertEqual(metrics.card_height_base, 228)
        self.assertEqual(metrics.row_count, 2)
        self.assertEqual(metrics.scroll_max_height, metrics.viewport_height)
        self.assertEqual(metrics.box_height, 110 + metrics.viewport_height)

    def test_theme_card_grid_metrics_handles_compact_selected_card_height(self) -> None:
        metrics = theme_card_grid_metrics(
            viewport_width=720,
            spacing=12,
            entry_names=["A", "B", "C"],
            current_name="B",
        )

        self.assertEqual(metrics.columns, 2)
        self.assertTrue(metrics.compact_cards)
        self.assertEqual(metrics.card_height_base, 268)
        self.assertGreater(metrics.viewport_height, 14 + (2 * 268) + 12 + 10)


if __name__ == "__main__":
    unittest.main()
