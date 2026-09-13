import unittest

from designer.canvas import compute_snap_guides, resize_rect_from_drag, snap_rect_position
from designer.geometry import (
    apply_item_position,
    apply_item_rect,
    group_bounds,
    item_rect,
    move_drag_target,
    move_items_by_delta,
    resize_item_rect,
    theme_items_for_collection,
)
from designer.selection import (
    adjust_selected_z,
    canvas_elements,
    current_selected_items,
    move_selected_z_to_edge,
    normalize_selection,
    reorder_items_by_ids,
    replacement_visible_row,
    row_activation_selection,
    rows_for_collection,
    selected_items,
    selection_entries,
    selection_group_label,
    toggle_item_bool,
)


class DesignerGeometryTests(unittest.TestCase):
    def test_resize_rect_from_drag_handles_edges_and_min_size(self) -> None:
        self.assertEqual(resize_rect_from_drag("resize-br", (10, 20, 100, 50), 15, 5), (10, 20, 115, 55))
        self.assertEqual(resize_rect_from_drag("resize-tl", (10, 20, 100, 50), 15, 5), (25, 25, 85, 45))
        self.assertEqual(resize_rect_from_drag("resize-l", (10, 20, 100, 50), 140, 0), (109, 20, 1, 50))

    def test_compute_snap_guides_matches_canvas_and_other_elements(self) -> None:
        elements = [
            {"collection": "texts", "index": 0, "rect": (90, 20, 80, 40), "label": "Title", "visible": True},
            {"collection": "stats", "index": 1, "rect": (300, 120, 100, 40), "label": "CPU", "visible": True},
        ]
        guides = compute_snap_guides(
            (286, 76, 28, 40),
            collection="texts",
            index=0,
            elements=elements,
            canvas_size=(640, 240),
            threshold=8,
        )
        labels = {(guide["axis"], guide["value"], guide["label"]) for guide in guides}
        self.assertIn(("x", 300, "CPU left"), labels)
        self.assertIn(("y", 120, "canvas middle"), labels)
        self.assertEqual(len(guides), len({(guide["axis"], guide["value"]) for guide in guides}))

    def test_snap_rect_position_matches_canvas_and_other_elements(self) -> None:
        elements = [
            {"collection": "texts", "index": 0, "rect": (90, 20, 80, 40), "label": "Title", "visible": True},
            {"collection": "stats", "index": 1, "rect": (300, 120, 100, 40), "label": "CPU", "visible": True},
        ]

        x, y, guides = snap_rect_position(
            (286, 76, 28, 40),
            collection="texts",
            index=0,
            elements=elements,
            canvas_size=(640, 240),
            threshold=8,
        )

        self.assertEqual((x, y), (286, 80))
        labels = {(guide["axis"], guide["value"], guide["label"]) for guide in guides}
        self.assertIn(("x", 300, "CPU left"), labels)
        self.assertIn(("y", 120, "canvas middle"), labels)

    def test_snap_rect_position_ignores_current_element(self) -> None:
        elements = [
            {"collection": "texts", "index": 0, "rect": (90, 20, 80, 40), "label": "Title", "visible": True},
        ]

        x, y, guides = snap_rect_position(
            (83, 13, 80, 40),
            collection="texts",
            index=0,
            elements=elements,
            canvas_size=(640, 240),
            threshold=8,
        )

        self.assertEqual((x, y), (83, 18))
        self.assertNotIn(("x", 90), {(guide["axis"], guide["value"]) for guide in guides})

    def test_item_rect_uses_rect_for_widget_like_collections(self) -> None:
        self.assertEqual(item_rect({"rect": [10, 20, 30, 40]}, "widgets"), (10, 20, 30, 40))
        self.assertEqual(item_rect({"rect": [10, 20, 0, -2]}, "images"), (10, 20, 1, 1))

    def test_item_rect_uses_box_for_text_and_stats(self) -> None:
        self.assertEqual(item_rect({"x": 7, "y": 8, "box_width": 90, "box_height": 24}, "texts"), (7, 8, 90, 24))
        self.assertEqual(item_rect({"x": 7, "y": 8}, "stats"), (7, 8, 320, 48))

    def test_apply_item_rect_writes_matching_shape_and_snaps(self) -> None:
        widget: dict[str, object] = {}
        text: dict[str, object] = {}
        snap = lambda value: int(round(value / 8) * 8)

        self.assertEqual(apply_item_rect(widget, "widgets", (5, 9, 21, 31), snap=snap), (8, 8, 24, 32))
        self.assertEqual(widget["rect"], [8, 8, 24, 32])

        self.assertEqual(apply_item_rect(text, "texts", (5, 9, 21, 31), snap=snap), (8, 8, 24, 32))
        self.assertEqual(text["x"], 8)
        self.assertEqual(text["y"], 8)
        self.assertEqual(text["box_width"], 24)
        self.assertEqual(text["box_height"], 32)

    def test_resize_item_rect_applies_unlocked_and_skips_locked(self) -> None:
        widget: dict[str, object] = {"rect": [10, 20, 30, 40]}
        locked: dict[str, object] = {"rect": [1, 2, 3, 4], "locked": True}
        snap = lambda value: int(round(value / 8) * 8)

        result = resize_item_rect(widget, "widgets", (5, 9, 21, 31), snap=snap)
        skipped = resize_item_rect(locked, "widgets", (10, 10, 20, 20), snap=snap)

        self.assertTrue(result.applied)
        self.assertEqual(result.next_rect, (8, 8, 24, 32))
        self.assertEqual(widget["rect"], [8, 8, 24, 32])
        self.assertFalse(skipped.applied)
        self.assertIsNone(skipped.next_rect)
        self.assertEqual(locked["rect"], [1, 2, 3, 4])

    def test_apply_item_position_preserves_size_while_snapping_position(self) -> None:
        widget: dict[str, object] = {"rect": [10, 20, 31, 47]}
        text: dict[str, object] = {"x": 10, "y": 20, "box_width": 31, "box_height": 47}
        snap = lambda value: int(round(value / 8) * 8)

        self.assertEqual(apply_item_position(widget, "widgets", 21, 29, snap=snap), (24, 32, 31, 47))
        self.assertEqual(widget["rect"], [24, 32, 31, 47])

        self.assertEqual(apply_item_position(text, "texts", 21, 29, snap=snap), (24, 32, 31, 47))
        self.assertEqual(text["x"], 24)
        self.assertEqual(text["y"], 32)
        self.assertEqual(text["box_width"], 31)
        self.assertEqual(text["box_height"], 47)

    def test_move_items_by_delta_skips_locked_items(self) -> None:
        widget: dict[str, object] = {"rect": [10, 20, 31, 47]}
        text: dict[str, object] = {"x": 50, "y": 60, "box_width": 90, "box_height": 24}
        locked: dict[str, object] = {"x": 1, "y": 2, "locked": True}
        selected = [("widgets", 0, widget), ("texts", 1, text), ("texts", 2, locked)]

        moved = move_items_by_delta(selected, 7, -5, snap=lambda value: int(round(value / 8) * 8))

        self.assertEqual(moved, 2)
        self.assertEqual(widget["rect"], [16, 16, 31, 47])
        self.assertEqual(text["x"], 56)
        self.assertEqual(text["y"], 56)
        self.assertEqual(locked["x"], 1)
        self.assertEqual(locked["y"], 2)

    def test_move_drag_target_moves_single_item(self) -> None:
        widget: dict[str, object] = {"rect": [10, 20, 31, 47]}

        result = move_drag_target(
            selected=[],
            target_collection="widgets",
            target_index=0,
            target_item=widget,
            target_x=21,
            target_y=29,
            snap=lambda value: int(round(value / 8) * 8),
        )

        self.assertFalse(result.group_move)
        self.assertEqual((result.delta_x, result.delta_y), (14, 12))
        self.assertEqual(widget["rect"], [24, 32, 31, 47])

    def test_move_drag_target_moves_selected_group(self) -> None:
        widget: dict[str, object] = {"rect": [10, 20, 31, 47]}
        text: dict[str, object] = {"x": 50, "y": 60, "box_width": 90, "box_height": 24}
        selected = [("widgets", 0, widget), ("texts", 1, text)]

        result = move_drag_target(
            selected=selected,
            target_collection="widgets",
            target_index=0,
            target_item=widget,
            target_x=18,
            target_y=15,
            snap=lambda value: int(round(value / 8) * 8),
        )

        self.assertTrue(result.group_move)
        self.assertEqual((result.delta_x, result.delta_y), (8, -5))
        self.assertEqual(result.moved_count, 2)
        self.assertEqual(widget["rect"], [16, 16, 31, 47])
        self.assertEqual((text["x"], text["y"]), (56, 56))

    def test_group_bounds_spans_mixed_collections(self) -> None:
        selected = [
            ("widgets", 0, {"rect": [50, 40, 100, 50]}),
            ("texts", 1, {"x": 20, "y": 10, "box_width": 40, "box_height": 20}),
        ]
        self.assertEqual(group_bounds(selected), (20, 10, 130, 80))

    def test_theme_items_for_collection_handles_panels(self) -> None:
        doc = {"background": {"panels": [{"id": "panel"}]}, "texts": [{"id": "text"}]}
        self.assertEqual(theme_items_for_collection(doc, "panels"), [{"id": "panel"}])
        self.assertEqual(theme_items_for_collection(doc, "texts"), [{"id": "text"}])
        self.assertEqual(theme_items_for_collection(doc, "stats"), [])

    def test_normalize_selection_deduplicates_and_drops_invalid_rows(self) -> None:
        doc = {"texts": [{"id": "a"}, {"id": "b"}], "widgets": [{"id": "w"}]}
        self.assertEqual(
            normalize_selection(doc, [("texts", 1), ("texts", 1), ("widgets", 0), ("texts", 9)]),
            [("texts", 1), ("widgets", 0)],
        )

    def test_selection_entries_prefers_cross_selection_then_current_rows(self) -> None:
        doc = {"texts": [{"id": "a"}], "widgets": [{"id": "w"}]}
        self.assertEqual(selection_entries(doc, [("widgets", 0)], "texts", [0]), [("widgets", 0)])
        self.assertEqual(selection_entries(doc, [], "texts", [0]), [("texts", 0)])

    def test_selected_items_and_current_selected_items_resolve_mutable_items(self) -> None:
        text = {"id": "text"}
        widget = {"id": "widget"}
        doc = {"texts": [text], "widgets": [widget]}

        self.assertEqual(selected_items(doc, [("texts", 0), ("widgets", 0)]), [("texts", 0, text), ("widgets", 0, widget)])
        self.assertEqual(current_selected_items([text, widget], [1, 9]), [(1, widget)])

    def test_rows_for_collection_filters_cross_selection(self) -> None:
        entries = [("texts", 2), ("widgets", 0), ("texts", 1)]
        self.assertEqual(rows_for_collection(entries, "texts"), [2, 1])
        self.assertEqual(rows_for_collection(entries, "stats"), [])

    def test_row_activation_selection_handles_single_ctrl_shift_and_invalid(self) -> None:
        self.assertEqual(
            row_activation_selection(row=2, count=5, current_row=0, selected_rows=[0]),
            ([2], 2),
        )
        self.assertEqual(
            row_activation_selection(row=2, count=5, current_row=0, selected_rows=[0], ctrl=True),
            ([0, 2], 2),
        )
        self.assertEqual(
            row_activation_selection(row=0, count=5, current_row=0, selected_rows=[0, 2], ctrl=True),
            ([2], 0),
        )
        self.assertEqual(
            row_activation_selection(row=3, count=5, current_row=1, selected_rows=[1], shift=True),
            ([1, 2, 3], 3),
        )
        self.assertEqual(
            row_activation_selection(row=9, count=5, current_row=1, selected_rows=[2, 1]),
            ([1, 2], 1),
        )

    def test_replacement_visible_row_keeps_current_or_picks_first_visible(self) -> None:
        self.assertEqual(replacement_visible_row(2, {0, 1}, 4), 2)
        self.assertEqual(replacement_visible_row(2, {0, 2}, 4), 1)
        self.assertEqual(replacement_visible_row(0, {0, 1, 2}, 3), -1)

    def test_toggle_item_bool_and_reorder_items_by_ids(self) -> None:
        items = [{"id": "a", "visible": True}, {"id": "b"}, {"id": "c"}]

        self.assertTrue(toggle_item_bool(items, 0, "visible", True))
        self.assertFalse(items[0]["visible"])
        self.assertTrue(toggle_item_bool(items, 1, "locked", False))
        self.assertTrue(items[1]["locked"])
        self.assertFalse(toggle_item_bool(items, 9, "visible", True))

        reordered = reorder_items_by_ids(items, ["c", "a", "b"])
        self.assertIsNotNone(reordered)
        assert reordered is not None
        self.assertEqual([item["id"] for item in reordered], ["c", "a", "b"])
        self.assertEqual([item["z_index"] for item in reordered], [0, 1, 2])
        self.assertIsNone(reorder_items_by_ids(items, ["c", "missing", "b"]))

    def test_adjust_selected_z_and_move_selected_z_to_edge(self) -> None:
        a = {"id": "a", "z_index": 3}
        b = {"id": "b", "z_index": 7}
        selected = [("texts", 0, a), ("stats", 1, b)]

        self.assertTrue(adjust_selected_z(selected, 2))
        self.assertEqual((a["z_index"], b["z_index"]), (5, 9))

        all_items = [{"z_index": -2}, {"z_index": 20}, a, b]
        self.assertTrue(move_selected_z_to_edge(selected, all_items, "front"))
        self.assertEqual((a["z_index"], b["z_index"]), (21, 22))
        self.assertTrue(move_selected_z_to_edge(selected, all_items, "back"))
        self.assertEqual((a["z_index"], b["z_index"]), (-4, -3))
        self.assertFalse(adjust_selected_z([], 1))
        self.assertFalse(move_selected_z_to_edge([], all_items, "front"))

    def test_canvas_elements_are_sorted_and_include_rect_metadata(self) -> None:
        doc = {
            "background": {"panels": [{"id": "panel", "rect": [1, 2, 3, 4], "z_index": 20}]},
            "texts": [{"id": "text", "x": 5, "y": 6, "box_width": 7, "box_height": 8, "z_index": 10}],
        }
        self.assertEqual(
            [(item["collection"], item["label"], item["rect"]) for item in canvas_elements(doc)],
            [("texts", "text", (5, 6, 7, 8)), ("panels", "panel", (1, 2, 3, 4))],
        )

    def test_selection_group_label_detects_media_group_and_mixed_group(self) -> None:
        doc = {"texts": [{"id": "title"}], "images": [{"id": "cover"}], "widgets": [{"id": "weather"}]}
        media = lambda item, collection: collection in {"texts", "images"}  # noqa: E731

        self.assertEqual(selection_group_label(doc, [("texts", 0), ("images", 0)], media_predicate=media), "Media Player")
        self.assertEqual(selection_group_label(doc, [("texts", 0), ("widgets", 0)], media_predicate=media), "Grupa warstw")


if __name__ == "__main__":
    unittest.main()
