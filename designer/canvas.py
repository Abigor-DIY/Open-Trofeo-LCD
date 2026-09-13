"""Canvas interaction helpers for Theme Designer.

This module contains geometry-only logic used by the Qt preview canvas. Keeping
it separate makes drag/resize behavior testable without running the GUI.
"""

from __future__ import annotations

from typing import Any


Rect = tuple[int, int, int, int]
Guide = dict[str, Any]


def resize_rect_from_drag(mode: str, rect: Rect, dx: int, dy: int, *, min_size: int = 1) -> Rect:
    """Return a rectangle resized by dragging one of its resize handles."""
    handle = str(mode).replace("resize-", "", 1)
    x, y, width, height = rect
    left = x
    top = y
    right = x + width
    bottom = y + height
    if "l" in handle:
        left += dx
    if "r" in handle:
        right += dx
    if "t" in handle:
        top += dy
    if "b" in handle:
        bottom += dy

    min_size = max(1, int(min_size))
    if right - left < min_size:
        if "l" in handle:
            left = right - min_size
        else:
            right = left + min_size
    if bottom - top < min_size:
        if "t" in handle:
            top = bottom - min_size
        else:
            bottom = top + min_size
    return int(left), int(top), int(right - left), int(bottom - top)


def compute_snap_guides(
    rect: Rect,
    *,
    collection: str,
    index: int,
    elements: list[dict[str, Any]],
    canvas_size: tuple[int, int],
    threshold: int,
) -> list[Guide]:
    """Return snap guides near canvas safe bounds, center lines and elements."""
    x, y, w, h = rect
    canvas_w, canvas_h = max(1, int(canvas_size[0])), max(1, int(canvas_size[1]))
    guides: list[Guide] = []
    current_x = [("left", x), ("center", x + w // 2), ("right", x + w)]
    current_y = [("top", y), ("center", y + h // 2), ("bottom", y + h)]
    safe_left = 24
    safe_right = max(0, canvas_w - 24)
    safe_top = 18
    safe_bottom = max(0, canvas_h - 18)
    canvas_guides_x = [
        (canvas_w // 2, "canvas center"),
        (safe_left, "safe left"),
        (safe_right, "safe right"),
    ]
    canvas_guides_y = [
        (canvas_h // 2, "canvas middle"),
        (safe_top, "safe top"),
        (safe_bottom, "safe bottom"),
    ]
    threshold = max(4, int(threshold))
    for _edge, cx in current_x:
        for ox, label in canvas_guides_x:
            if abs(cx - ox) <= threshold:
                guides.append({"axis": "x", "value": ox, "label": label})
    for _edge, cy in current_y:
        for oy, label in canvas_guides_y:
            if abs(cy - oy) <= threshold:
                guides.append({"axis": "y", "value": oy, "label": label})

    for item in elements:
        if item.get("collection") == collection and int(item.get("index", -1)) == int(index):
            continue
        if not bool(item.get("visible", True)):
            continue
        rx, ry, rw, rh = item.get("rect", (0, 0, 1, 1))
        rx, ry, rw, rh = int(rx), int(ry), int(rw), int(rh)
        other_label = str(item.get("label", item.get("collection", "element"))).strip()[:18]
        other_x = [
            (rx, f"{other_label} left"),
            (rx + rw // 2, f"{other_label} center"),
            (rx + rw, f"{other_label} right"),
        ]
        other_y = [
            (ry, f"{other_label} top"),
            (ry + rh // 2, f"{other_label} middle"),
            (ry + rh, f"{other_label} bottom"),
        ]
        for _edge, cx in current_x:
            for ox, label in other_x:
                if abs(cx - ox) <= threshold:
                    guides.append({"axis": "x", "value": ox, "label": label})
                    break
        for _edge, cy in current_y:
            for oy, label in other_y:
                if abs(cy - oy) <= threshold:
                    guides.append({"axis": "y", "value": oy, "label": label})
                    break

    unique: list[Guide] = []
    seen: set[tuple[str, int]] = set()
    for item in guides:
        key = (str(item.get("axis", "")), int(item.get("value", 0)))
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique


def snap_rect_position(
    rect: Rect,
    *,
    collection: str,
    index: int,
    elements: list[dict[str, Any]],
    canvas_size: tuple[int, int],
    threshold: int,
) -> tuple[int, int, list[Guide]]:
    """Snap a rectangle position to nearby canvas or element guide targets."""
    x, y, w, h = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
    canvas_w, canvas_h = max(1, int(canvas_size[0])), max(1, int(canvas_size[1]))
    threshold = max(4, int(threshold))
    candidates_x = [("left", x), ("center", x + w // 2), ("right", x + w)]
    candidates_y = [("top", y), ("center", y + h // 2), ("bottom", y + h)]
    targets_x = [24, max(0, canvas_w - 24), canvas_w // 2]
    targets_y = [18, max(0, canvas_h - 18), canvas_h // 2]

    for item in elements:
        if item.get("collection") == collection and int(item.get("index", -1)) == int(index):
            continue
        if not bool(item.get("visible", True)):
            continue
        rx, ry, rw, rh = item.get("rect", (0, 0, 1, 1))
        rx, ry, rw, rh = int(rx), int(ry), int(rw), int(rh)
        targets_x.extend([rx, rx + rw // 2, rx + rw])
        targets_y.extend([ry, ry + rh // 2, ry + rh])

    best_x: tuple[int, int] | None = None
    best_y: tuple[int, int] | None = None
    for _kind, candidate in candidates_x:
        for target in targets_x:
            delta = target - candidate
            if abs(delta) <= threshold and (best_x is None or abs(delta) < abs(best_x[1])):
                best_x = (target, delta)
    for _kind, candidate in candidates_y:
        for target in targets_y:
            delta = target - candidate
            if abs(delta) <= threshold and (best_y is None or abs(delta) < abs(best_y[1])):
                best_y = (target, delta)

    snapped_x = int(x + (best_x[1] if best_x is not None else 0))
    snapped_y = int(y + (best_y[1] if best_y is not None else 0))
    guides = compute_snap_guides(
        (snapped_x, snapped_y, w, h),
        collection=collection,
        index=index,
        elements=elements,
        canvas_size=(canvas_w, canvas_h),
        threshold=threshold,
    )
    return snapped_x, snapped_y, guides
