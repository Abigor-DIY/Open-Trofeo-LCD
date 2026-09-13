"""Auto-layout helpers for Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .geometry import apply_item_rect


AutoLayoutEntry = tuple[str, int, dict[str, Any]]
AutoLayoutPlan = dict[str, list[tuple[int, int, int, int]]]

DEFAULT_AUTO_LAYOUT_BUCKETS = (
    "media",
    "weather",
    "forecast",
    "forecast_hourly",
    "clock",
    "gauge",
    "progress",
    "sparkline",
    "eq",
    "stat",
    "text",
    "widget",
    "image",
    "media_image",
)


@dataclass(frozen=True)
class AutoLayoutMetrics:
    canvas_width: int
    canvas_height: int
    margin_x: int
    margin_y: int
    gap: int
    usable_w: int
    left_w: int
    right_w: int
    center_x: int
    right_x: int
    center_w: int
    bottom_y: int


def auto_layout_metrics(canvas_width: int, canvas_height: int) -> AutoLayoutMetrics:
    """Return reusable geometry metrics for the designer auto-arranger."""
    canvas_width = max(1, int(canvas_width or 1920))
    canvas_height = max(1, int(canvas_height or 462))
    margin_x = max(32, int(round(canvas_width * 0.026)))
    margin_y = max(18, int(round(canvas_height * 0.045)))
    gap = max(12, int(round(canvas_width * 0.010)))
    usable_w = max(1, canvas_width - (2 * margin_x))
    left_w = min(560, max(360, int(usable_w * 0.30)))
    right_w = min(500, max(360, int(usable_w * 0.25)))
    center_x = margin_x + left_w + gap
    right_x = canvas_width - margin_x - right_w
    center_w = max(420, right_x - gap - center_x)
    bottom_y = max(margin_y, canvas_height - margin_y - 82)
    return AutoLayoutMetrics(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_x=margin_x,
        margin_y=margin_y,
        gap=gap,
        usable_w=usable_w,
        left_w=left_w,
        right_w=right_w,
        center_x=center_x,
        right_x=right_x,
        center_w=center_w,
        bottom_y=bottom_y,
    )


def auto_layout_kind(collection: str, item: dict[str, Any]) -> str:
    """Classify a designer element for automatic layout buckets."""
    collection = str(collection)
    if collection == "widgets":
        kind = str(item.get("kind", "")).strip().lower()
        if kind == "media_now_playing":
            return "media"
        if kind == "weather_current":
            return "weather"
        if kind == "weather_forecast_7d":
            return "forecast"
        if kind == "weather_forecast_hourly":
            return "forecast_hourly"
        return "widget"
    if collection == "images":
        source = str(item.get("source", "")).strip().lower()
        if source == "analog_clock":
            return "clock"
        if source in {"media_cover", "media_video_frame"}:
            return "media_image"
        return "image"
    if collection == "stats":
        display = str(item.get("display", "text")).strip().lower()
        source = str(item.get("source", "")).strip().lower()
        if display == "gauge":
            return "gauge"
        if display == "equalizer" or source.startswith("audio_eq"):
            return "eq"
        if display in {"progress", "sparkline"}:
            return display
        return "stat"
    if collection == "texts":
        return "text"
    return collection


def bucket_auto_layout_entries(entries: list[AutoLayoutEntry]) -> dict[str, list[AutoLayoutEntry]]:
    """Group designer entries into automatic layout buckets."""
    buckets: dict[str, list[AutoLayoutEntry]] = {key: [] for key in DEFAULT_AUTO_LAYOUT_BUCKETS}
    for entry in entries:
        kind = auto_layout_kind(entry[0], entry[2])
        buckets.setdefault(kind, []).append(entry)
    return buckets


def auto_layout_gauge_rects(metrics: AutoLayoutMetrics, count: int) -> list[tuple[int, int, int, int]]:
    """Return left telemetry gauge rectangles for automatic layout."""
    count = max(0, int(count))
    if count <= 0:
        return []

    if count == 1:
        gauge_cols = 1
        max_gauge_size = 240
    elif count == 2:
        gauge_cols = 2
        max_gauge_size = 204
    elif count == 3:
        gauge_cols = 3
        max_gauge_size = 176
    elif count == 4:
        gauge_cols = 2
        max_gauge_size = 154
    else:
        gauge_cols = min(3, count)
        max_gauge_size = 154
    gauge_rows = (count + gauge_cols - 1) // gauge_cols
    max_size_for_width = int((metrics.left_w - metrics.gap * (gauge_cols - 1)) / gauge_cols)
    max_size_for_rows = max(
        24,
        int(
            (
                metrics.canvas_height
                - 2 * metrics.margin_y
                - metrics.gap * (gauge_rows - 1)
            )
            / gauge_rows
        ),
    )
    gauge_size = min(max_gauge_size, max_size_for_width, max_size_for_rows)
    if gauge_size >= 88:
        gauge_size = max(88, gauge_size)
    start_x = metrics.margin_x + max(
        0,
        (metrics.left_w - (gauge_cols * gauge_size + (gauge_cols - 1) * metrics.gap)) // 2,
    )
    start_y = metrics.margin_y + max(
        8,
        int(
            (
                metrics.canvas_height
                - 2 * metrics.margin_y
                - (gauge_rows * gauge_size + (gauge_rows - 1) * metrics.gap)
            )
            * 0.40
        ),
    )
    return [
        (
            start_x + (idx % gauge_cols) * (gauge_size + metrics.gap),
            start_y + (idx // gauge_cols) * (gauge_size + metrics.gap),
            gauge_size,
            gauge_size,
        )
        for idx in range(count)
    ]


def auto_layout_media_rects(
    metrics: AutoLayoutMetrics,
    count: int,
    *,
    has_flow_items: bool,
) -> list[tuple[int, int, int, int]]:
    """Return center Now Playing widget rectangles for automatic layout."""
    count = max(0, int(count))
    if count <= 0:
        return []

    media_h = 124 if has_flow_items else 148
    rects: list[tuple[int, int, int, int]] = []
    item_y = metrics.margin_y + 46
    for idx in range(count):
        item_h = media_h if idx == 0 else 92
        item_w = min(metrics.center_w, 860 if idx == 0 else 620)
        rects.append(
            (
                metrics.center_x + max(0, (metrics.center_w - item_w) // 2),
                item_y,
                item_w,
                item_h,
            )
        )
        item_y += item_h + 10
    return rects


def auto_layout_flow_rects(
    metrics: AutoLayoutMetrics,
    kinds: list[str],
    *,
    has_media_items: bool,
    media_bottom_y: int | None = None,
    reserved_bottom_y: int | None = None,
) -> list[tuple[int, int, int, int]]:
    """Return center flow rectangles for progress, sparkline, stat and widget rows."""
    if not kinds:
        return []

    flow_cols = 2 if len(kinds) > 1 and metrics.center_w >= 620 else 1
    flow_w = int((metrics.center_w - metrics.gap * (flow_cols - 1)) / flow_cols)
    rects: list[tuple[int, int, int, int]] = []
    row_heights = [
        max(74 if kind == "sparkline" else 42 for kind in kinds[row_start : row_start + flow_cols])
        for row_start in range(0, len(kinds), flow_cols)
    ]
    flow_height = sum(row_heights) + 10 * max(0, len(row_heights) - 1)
    min_start_y = int(media_bottom_y) + 12 if media_bottom_y is not None else metrics.margin_y
    flow_start_y = metrics.margin_y + 206 if has_media_items else metrics.margin_y + 72
    flow_start_y = max(flow_start_y, min_start_y)
    if reserved_bottom_y is not None:
        max_start_y = int(reserved_bottom_y) - 8 - flow_height
        flow_start_y = max(min_start_y, min(flow_start_y, max_start_y))
    row_y = flow_start_y
    for idx, kind in enumerate(kinds):
        item_h = 74 if kind == "sparkline" else 42
        col = idx % flow_cols
        row = idx // flow_cols
        if col == 0 and row > 0:
            row_y += row_heights[row - 1] + 10
        rects.append(
            (
                metrics.center_x + col * (flow_w + metrics.gap),
                row_y,
                flow_w,
                item_h,
            )
        )
    return rects


def auto_layout_weather_rects(metrics: AutoLayoutMetrics, count: int) -> list[tuple[int, int, int, int]]:
    """Return right-column current weather widget rectangles."""
    return [
        (
            metrics.right_x,
            metrics.margin_y + 52 + idx * 118,
            metrics.right_w,
            116,
        )
        for idx in range(max(0, int(count)))
    ]


def auto_layout_forecast_rects(
    metrics: AutoLayoutMetrics,
    count: int,
    *,
    has_weather_items: bool,
) -> list[tuple[int, int, int, int]]:
    """Return right-column weather forecast widget rectangles."""
    start_y = metrics.margin_y + 188 if has_weather_items else metrics.margin_y + 76
    return [
        (
            metrics.right_x,
            start_y + idx * 118,
            metrics.right_w,
            118,
        )
        for idx in range(max(0, int(count)))
    ]


def auto_layout_clock_rects(metrics: AutoLayoutMetrics, count: int) -> list[tuple[int, int, int, int]]:
    """Return right-column clock rectangles."""
    size = min(136, max(96, metrics.right_w // 3))
    return [
        (
            metrics.right_x + metrics.right_w - size,
            metrics.margin_y + idx * (size + 8),
            size,
            size,
        )
        for idx in range(max(0, int(count)))
    ]


def auto_layout_eq_rects(metrics: AutoLayoutMetrics, count: int) -> list[tuple[int, int, int, int]]:
    """Return right-column equalizer rectangles."""
    eq_w = min(metrics.right_w, 360)
    return [
        (
            metrics.right_x + metrics.right_w - eq_w,
            metrics.bottom_y - idx * 82,
            eq_w,
            72,
        )
        for idx in range(max(0, int(count)))
    ]


def auto_layout_right_column_rects(
    metrics: AutoLayoutMetrics,
    *,
    weather_count: int = 0,
    forecast_count: int = 0,
    clock_count: int = 0,
    eq_count: int = 0,
) -> dict[str, list[tuple[int, int, int, int]]]:
    """Return non-overlapping right-column rectangles for weather, clock and EQ."""
    counts = {
        "weather": max(0, int(weather_count)),
        "forecast": max(0, int(forecast_count)),
        "clock": max(0, int(clock_count)),
        "eq": max(0, int(eq_count)),
    }
    clock_base = min(136, max(96, metrics.right_w // 3))
    specs = {
        "weather": (116, 72),
        "forecast": (118, 72),
        "clock": (clock_base, 56),
        "eq": (72, 44),
    }
    ordered_kinds = ["weather", "forecast", "clock", "eq"]
    items = [
        (kind, specs[kind][0], specs[kind][1])
        for kind in ordered_kinds
        for _idx in range(counts[kind])
    ]
    rects: dict[str, list[tuple[int, int, int, int]]] = {kind: [] for kind in ordered_kinds}
    if not items:
        return rects

    available_h = max(1, metrics.canvas_height - (2 * metrics.margin_y))
    gap = min(10, max(4, metrics.gap // 2))
    total_base_h = sum(base_h for _kind, base_h, _min_h in items) + gap * (len(items) - 1)
    if total_base_h <= available_h:
        heights = [base_h for _kind, base_h, _min_h in items]
    else:
        height_budget = max(len(items), available_h - gap * (len(items) - 1))
        min_total = sum(min_h for _kind, _base_h, min_h in items)
        if min_total > height_budget:
            scale = height_budget / min_total
            heights = [max(18, int(min_h * scale)) for _kind, _base_h, min_h in items]
        else:
            scale = height_budget / sum(base_h for _kind, base_h, _min_h in items)
            heights = [max(min_h, int(base_h * scale)) for _kind, base_h, min_h in items]
    total_h = sum(heights) + gap * (len(heights) - 1)
    y = metrics.margin_y + max(0, (available_h - total_h) // 2)
    for (kind, _base_h, _min_h), height in zip(items, heights):
        if kind == "clock":
            width = min(metrics.right_w, height)
            x = metrics.right_x + metrics.right_w - width
        elif kind == "eq":
            width = min(metrics.right_w, 360)
            x = metrics.right_x + metrics.right_w - width
        else:
            width = metrics.right_w
            x = metrics.right_x
        rects[kind].append((x, y, width, height))
        y += height + gap
    return rects


def auto_layout_bottom_row_rects(
    metrics: AutoLayoutMetrics,
    collections: list[str],
) -> list[tuple[int, int, int, int]]:
    """Return bottom-row rectangles for selected text and image leftovers."""
    if not collections:
        return []

    count = len(collections)
    gap = 8 if count > 1 else 0
    min_item_w = 24
    if count * min_item_w + gap * (count - 1) > metrics.usable_w:
        gap = 0
    available_w = max(1, metrics.usable_w - gap * (count - 1))
    item_w = min(360, max(1, int(available_w / count)))
    rects: list[tuple[int, int, int, int]] = []
    for idx, collection in enumerate(collections):
        height = 44 if collection == "texts" else 96
        rects.append(
            (
                metrics.margin_x + idx * (item_w + gap),
                metrics.canvas_height - metrics.margin_y - height,
                item_w,
                height,
            )
        )
    return rects


def auto_layout_plan(
    metrics: AutoLayoutMetrics,
    buckets: dict[str, list[AutoLayoutEntry]],
) -> AutoLayoutPlan:
    """Return the full automatic layout rectangle plan for all designer buckets."""
    plan: AutoLayoutPlan = {key: [] for key in DEFAULT_AUTO_LAYOUT_BUCKETS}
    plan["flow"] = []
    plan["bottom"] = []

    gauges = buckets.get("gauge", [])
    plan["gauge"] = auto_layout_gauge_rects(metrics, len(gauges))

    media_items = buckets.get("media", [])
    has_flow_items = bool(
        buckets.get("progress")
        or buckets.get("sparkline")
        or buckets.get("eq")
        or buckets.get("stat")
    )
    media_rects = auto_layout_media_rects(metrics, len(media_items), has_flow_items=has_flow_items)
    plan["media"] = media_rects

    flow_items = buckets.get("progress", []) + buckets.get("sparkline", []) + buckets.get("stat", []) + buckets.get("widget", [])
    flow_kinds = [auto_layout_kind(collection, item) for collection, _row, item in flow_items]
    media_bottom_y = max((y + height for _x, y, _width, height in media_rects), default=None)
    leftovers = buckets.get("text", []) + buckets.get("image", []) + buckets.get("media_image", [])
    bottom_rects = auto_layout_bottom_row_rects(metrics, [collection for collection, _row, _item in leftovers])
    reserved_bottom_y = min((y for _x, y, _width, _height in bottom_rects), default=None)
    plan["flow"] = auto_layout_flow_rects(
        metrics,
        flow_kinds,
        has_media_items=bool(media_items),
        media_bottom_y=media_bottom_y,
        reserved_bottom_y=reserved_bottom_y,
    )

    right_rects = auto_layout_right_column_rects(
        metrics,
        weather_count=len(buckets.get("weather", [])),
        forecast_count=len(buckets.get("forecast", [])),
        clock_count=len(buckets.get("clock", [])),
        eq_count=len(buckets.get("eq", [])),
    )
    plan.update(right_rects)

    plan["bottom"] = bottom_rects
    return plan


def apply_bounded_layout_rect(
    item: dict[str, Any],
    collection: str,
    x: int,
    y: int,
    width: int,
    height: int,
    canvas_width: int,
    canvas_height: int,
    *,
    align: str | None = None,
    snap: Callable[[int], int] | None = None,
) -> tuple[int, int, int, int]:
    """Clamp a layout rect to the canvas and write it to the element."""
    width = max(24, min(int(width), int(canvas_width)))
    height = max(18, min(int(height), int(canvas_height)))
    x = max(0, min(int(x), int(canvas_width) - width))
    y = max(0, min(int(y), int(canvas_height) - height))
    rect = apply_item_rect(item, collection, (x, y, width, height), snap=snap)
    if collection not in {"images", "panels", "widgets"} and align is not None:
        item["align"] = align
    return rect
