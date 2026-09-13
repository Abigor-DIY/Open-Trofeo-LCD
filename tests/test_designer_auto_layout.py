import unittest

from designer.auto_layout import (
    apply_bounded_layout_rect,
    auto_layout_bottom_row_rects,
    auto_layout_clock_rects,
    auto_layout_eq_rects,
    auto_layout_flow_rects,
    auto_layout_forecast_rects,
    auto_layout_gauge_rects,
    auto_layout_kind,
    auto_layout_media_rects,
    auto_layout_metrics,
    auto_layout_plan,
    auto_layout_right_column_rects,
    auto_layout_weather_rects,
    bucket_auto_layout_entries,
)


class DesignerAutoLayoutTests(unittest.TestCase):
    def test_auto_layout_metrics_for_lcd_canvas(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        self.assertEqual(metrics.canvas_width, 1920)
        self.assertEqual(metrics.canvas_height, 462)
        self.assertGreaterEqual(metrics.margin_x, 32)
        self.assertGreaterEqual(metrics.margin_y, 18)
        self.assertGreater(metrics.center_w, 420)
        self.assertGreater(metrics.right_x, metrics.center_x)
        self.assertLess(metrics.bottom_y, metrics.canvas_height)

    def test_auto_layout_metrics_for_small_canvas_stay_positive(self) -> None:
        metrics = auto_layout_metrics(640, 180)
        self.assertGreater(metrics.usable_w, 0)
        self.assertGreaterEqual(metrics.left_w, 360)
        self.assertGreaterEqual(metrics.right_w, 360)
        self.assertGreaterEqual(metrics.center_w, 420)
        self.assertGreaterEqual(metrics.bottom_y, metrics.margin_y)

    def test_auto_layout_kind_classifies_widgets_and_stats(self) -> None:
        self.assertEqual(auto_layout_kind("widgets", {"kind": "media_now_playing"}), "media")
        self.assertEqual(auto_layout_kind("widgets", {"kind": "weather_current"}), "weather")
        self.assertEqual(auto_layout_kind("widgets", {"kind": "weather_forecast_7d"}), "forecast")
        self.assertEqual(auto_layout_kind("widgets", {"kind": "weather_forecast_hourly"}), "forecast_hourly")
        self.assertEqual(auto_layout_kind("stats", {"display": "gauge"}), "gauge")
        self.assertEqual(auto_layout_kind("stats", {"source": "audio_eq_bars"}), "eq")
        self.assertEqual(auto_layout_kind("stats", {"display": "sparkline"}), "sparkline")

    def test_bucket_auto_layout_entries_preserves_supported_groups(self) -> None:
        media = ("widgets", 0, {"kind": "media_now_playing"})
        gauge = ("stats", 1, {"display": "gauge"})
        hourly = ("widgets", 2, {"kind": "weather_forecast_hourly"})
        generic = ("widgets", 3, {"kind": "custom_panel"})

        buckets = bucket_auto_layout_entries([media, gauge, hourly, generic])

        self.assertEqual(buckets["media"], [media])
        self.assertEqual(buckets["gauge"], [gauge])
        self.assertEqual(buckets["forecast_hourly"], [hourly])
        self.assertEqual(buckets["widget"], [generic])

    def test_auto_layout_gauge_rects_keep_gauges_in_left_cluster(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        rects = auto_layout_gauge_rects(metrics, 3)

        self.assertEqual(len(rects), 3)
        self.assertTrue(all(width == height for _x, _y, width, height in rects))
        self.assertTrue(all(x >= metrics.margin_x for x, _y, _width, _height in rects))
        self.assertTrue(all(x + width <= metrics.margin_x + metrics.left_w for x, _y, width, _height in rects))
        self.assertGreaterEqual(rects[0][2], 168)
        self.assertEqual(rects[0][1], rects[1][1])
        self.assertLess(rects[0][0], rects[1][0])

    def test_auto_layout_gauge_rects_scale_up_sparse_gauges(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        one_rect = auto_layout_gauge_rects(metrics, 1)[0]
        two_rects = auto_layout_gauge_rects(metrics, 2)
        three_rects = auto_layout_gauge_rects(metrics, 3)

        self.assertGreaterEqual(one_rect[2], 220)
        self.assertGreaterEqual(two_rects[0][2], 200)
        self.assertGreater(three_rects[0][2], 154)
        self.assertLess(two_rects[0][0], two_rects[1][0])
        self.assertEqual(two_rects[0][1], two_rects[1][1])

    def test_auto_layout_gauge_rects_four_items_use_two_readable_rows(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        rects = auto_layout_gauge_rects(metrics, 4)

        self.assertEqual(len(rects), 4)
        self.assertEqual(rects[0][2], rects[1][2])
        self.assertEqual(rects[0][1], rects[1][1])
        self.assertEqual(rects[2][1], rects[3][1])
        self.assertGreater(rects[2][1], rects[0][1])

    def test_auto_layout_gauge_rects_wrap_and_stay_on_canvas(self) -> None:
        metrics = auto_layout_metrics(640, 180)
        rects = auto_layout_gauge_rects(metrics, 5)

        self.assertEqual(len(rects), 5)
        self.assertGreater(rects[3][1], rects[0][1])
        for x, y, width, height in rects:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + width, metrics.canvas_width)
            self.assertLessEqual(y + height, metrics.canvas_height)

    def test_auto_layout_media_rects_use_center_band(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        compact_rects = auto_layout_media_rects(metrics, 2, has_flow_items=True)
        standalone_rects = auto_layout_media_rects(metrics, 1, has_flow_items=False)

        self.assertEqual(len(compact_rects), 2)
        self.assertEqual(compact_rects[0][0], metrics.center_x)
        self.assertEqual(compact_rects[0][2], metrics.center_w)
        self.assertEqual(compact_rects[0][3], 124)
        self.assertEqual(compact_rects[1][2], 620)
        self.assertGreater(compact_rects[1][0], metrics.center_x)
        self.assertEqual(compact_rects[1][1], compact_rects[0][1] + compact_rects[0][3] + 10)
        self.assertEqual(standalone_rects[0][3], 148)

    def test_auto_layout_flow_rects_use_columns_and_sparkline_height(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        rects = auto_layout_flow_rects(metrics, ["progress", "sparkline", "stat"], has_media_items=True)

        self.assertEqual(len(rects), 3)
        self.assertEqual(rects[0][0], metrics.center_x)
        self.assertGreater(rects[1][0], rects[0][0])
        self.assertEqual(rects[0][1], metrics.margin_y + 206)
        self.assertEqual(rects[0][3], 42)
        self.assertEqual(rects[1][3], 74)
        self.assertEqual(rects[2][1], rects[0][1] + 74 + 10)

    def test_auto_layout_flow_rects_start_after_media_stack(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        media_rects = auto_layout_media_rects(metrics, 2, has_flow_items=True)
        media_bottom_y = max(y + height for _x, y, _width, height in media_rects)
        rects = auto_layout_flow_rects(
            metrics,
            ["progress", "sparkline"],
            has_media_items=True,
            media_bottom_y=media_bottom_y,
        )

        self.assertEqual(rects[0][1], media_bottom_y + 12)
        self.assertEqual(rects[1][1], media_bottom_y + 12)

    def test_auto_layout_flow_rects_stay_above_reserved_bottom_band(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        media_rects = auto_layout_media_rects(metrics, 1, has_flow_items=True)
        media_bottom_y = max(y + height for _x, y, _width, height in media_rects)
        rects = auto_layout_flow_rects(
            metrics,
            ["progress", "sparkline", "stat"],
            has_media_items=True,
            media_bottom_y=media_bottom_y,
            reserved_bottom_y=345,
        )

        self.assertEqual(rects[0][1], 211)
        self.assertLessEqual(rects[-1][1] + rects[-1][3], 345 - 8)

    def test_auto_layout_weather_and_forecast_rects_use_right_column(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        weather_rects = auto_layout_weather_rects(metrics, 2)
        forecast_after_weather = auto_layout_forecast_rects(metrics, 1, has_weather_items=True)
        forecast_alone = auto_layout_forecast_rects(metrics, 1, has_weather_items=False)

        self.assertEqual(weather_rects[0], (metrics.right_x, metrics.margin_y + 52, metrics.right_w, 116))
        self.assertEqual(weather_rects[1][1], weather_rects[0][1] + 118)
        self.assertEqual(forecast_after_weather[0], (metrics.right_x, metrics.margin_y + 188, metrics.right_w, 118))
        self.assertEqual(forecast_alone[0], (metrics.right_x, metrics.margin_y + 76, metrics.right_w, 118))

    def test_auto_layout_clock_and_eq_rects_anchor_to_right_edge(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        clock_rects = auto_layout_clock_rects(metrics, 2)
        eq_rects = auto_layout_eq_rects(metrics, 2)

        self.assertEqual(clock_rects[0][0] + clock_rects[0][2], metrics.right_x + metrics.right_w)
        self.assertEqual(clock_rects[0][2], clock_rects[0][3])
        self.assertEqual(clock_rects[1][1], clock_rects[0][1] + clock_rects[0][3] + 8)
        self.assertEqual(eq_rects[0][0] + eq_rects[0][2], metrics.right_x + metrics.right_w)
        self.assertEqual(eq_rects[0][3], 72)
        self.assertEqual(eq_rects[1][1], eq_rects[0][1] - 82)

    def test_auto_layout_right_column_rects_do_not_overlap(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        grouped = auto_layout_right_column_rects(
            metrics,
            weather_count=1,
            forecast_count=1,
            clock_count=1,
            eq_count=1,
        )
        rects = grouped["weather"] + grouped["forecast"] + grouped["clock"] + grouped["eq"]

        self.assertEqual(len(rects), 4)
        previous_bottom = metrics.margin_y
        for x, y, width, height in rects:
            self.assertGreaterEqual(y, previous_bottom)
            self.assertGreaterEqual(x, metrics.right_x)
            self.assertLessEqual(x + width, metrics.right_x + metrics.right_w)
            self.assertLessEqual(y + height, metrics.canvas_height - metrics.margin_y)
            previous_bottom = y + height

    def test_auto_layout_right_column_rects_compress_dense_stack(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        grouped = auto_layout_right_column_rects(
            metrics,
            weather_count=2,
            forecast_count=2,
            clock_count=1,
            eq_count=2,
        )
        rects = grouped["weather"] + grouped["forecast"] + grouped["clock"] + grouped["eq"]

        self.assertEqual(len(rects), 7)
        for idx in range(1, len(rects)):
            self.assertGreaterEqual(rects[idx][1], rects[idx - 1][1] + rects[idx - 1][3])
        self.assertLess(rects[0][3], 116)
        self.assertLessEqual(rects[-1][1] + rects[-1][3], metrics.canvas_height - metrics.margin_y)

    def test_auto_layout_bottom_row_rects_size_text_and_images(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        rects = auto_layout_bottom_row_rects(metrics, ["texts", "images", "images"])

        self.assertEqual(len(rects), 3)
        self.assertEqual(rects[0][0], metrics.margin_x)
        self.assertEqual(rects[0][3], 44)
        self.assertEqual(rects[1][3], 96)
        self.assertEqual(rects[0][2], 360)
        self.assertEqual(rects[1][0], rects[0][0] + rects[0][2] + 8)
        self.assertEqual(rects[0][1], metrics.canvas_height - metrics.margin_y - 44)
        self.assertEqual(rects[1][1], metrics.canvas_height - metrics.margin_y - 96)

    def test_auto_layout_bottom_row_rects_do_not_exceed_canvas_width(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        rects = auto_layout_bottom_row_rects(metrics, ["texts", "images", "images", "texts", "images", "texts"])

        self.assertEqual(len(rects), 6)
        self.assertLess(rects[0][2], 360)
        self.assertLessEqual(rects[-1][0] + rects[-1][2], metrics.canvas_width - metrics.margin_x)
        for idx in range(1, len(rects)):
            self.assertGreaterEqual(rects[idx][0], rects[idx - 1][0] + rects[idx - 1][2])

    def test_auto_layout_bottom_row_rects_collapse_gap_for_extreme_counts(self) -> None:
        metrics = auto_layout_metrics(640, 180)
        rects = auto_layout_bottom_row_rects(metrics, ["texts"] * 40)

        self.assertEqual(len(rects), 40)
        self.assertLessEqual(rects[-1][0] + rects[-1][2], metrics.canvas_width - metrics.margin_x)

    def test_auto_layout_plan_returns_all_sections(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        entries = [
            ("stats", 0, {"display": "gauge"}),
            ("stats", 1, {"display": "gauge"}),
            ("widgets", 2, {"kind": "media_now_playing"}),
            ("stats", 3, {"display": "sparkline"}),
            ("widgets", 4, {"kind": "weather_current"}),
            ("widgets", 5, {"kind": "weather_forecast_7d"}),
            ("images", 6, {"source": "analog_clock"}),
            ("stats", 7, {"source": "audio_eq_bars"}),
            ("texts", 8, {"text": "Label"}),
        ]
        buckets = bucket_auto_layout_entries(entries)
        plan = auto_layout_plan(metrics, buckets)

        self.assertEqual(len(plan["gauge"]), 2)
        self.assertEqual(len(plan["media"]), 1)
        self.assertEqual(len(plan["flow"]), 1)
        self.assertEqual(len(plan["weather"]), 1)
        self.assertEqual(len(plan["forecast"]), 1)
        self.assertEqual(len(plan["clock"]), 1)
        self.assertEqual(len(plan["eq"]), 1)
        self.assertEqual(len(plan["bottom"]), 1)
        for rects in plan.values():
            for x, y, width, height in rects:
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + width, metrics.canvas_width)
                self.assertLessEqual(y + height, metrics.canvas_height)

    def test_auto_layout_plan_keeps_flow_above_bottom_row(self) -> None:
        metrics = auto_layout_metrics(1920, 462)
        entries = [
            ("widgets", 0, {"kind": "media_now_playing"}),
            ("stats", 1, {"display": "progress"}),
            ("stats", 2, {"display": "sparkline"}),
            ("stats", 3, {"display": "text"}),
            ("texts", 4, {"text": "Label"}),
            ("images", 5, {"source": "media_cover"}),
        ]
        buckets = bucket_auto_layout_entries(entries)
        plan = auto_layout_plan(metrics, buckets)
        bottom_y = min(y for _x, y, _width, _height in plan["bottom"])

        for _x, y, _width, height in plan["flow"]:
            self.assertLessEqual(y + height, bottom_y - 8)

    def test_apply_bounded_layout_rect_clamps_to_canvas_for_widget(self) -> None:
        item: dict[str, object] = {}
        rect = apply_bounded_layout_rect(item, "widgets", -10, 90, 500, 80, 320, 120)
        self.assertEqual(rect, (0, 40, 320, 80))
        self.assertEqual(item["rect"], [0, 40, 320, 80])

    def test_apply_bounded_layout_rect_sets_text_align_and_snaps(self) -> None:
        item: dict[str, object] = {}
        snap = lambda value: int(round(value / 8) * 8)
        rect = apply_bounded_layout_rect(item, "texts", 13, 21, 75, 19, 320, 120, align="center", snap=snap)
        self.assertEqual(rect, (16, 24, 72, 16))
        self.assertEqual(item["x"], 16)
        self.assertEqual(item["y"], 24)
        self.assertEqual(item["box_width"], 72)
        self.assertEqual(item["box_height"], 16)
        self.assertEqual(item["align"], "center")


if __name__ == "__main__":
    unittest.main()
