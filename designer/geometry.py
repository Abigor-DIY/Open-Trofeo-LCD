"""Geometry helpers for Theme Designer elements.

These functions are intentionally UI-free so the designer model can be moved
out of the main Qt window incrementally.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

RECT_COLLECTIONS = {"images", "panels", "widgets"}


@dataclass(frozen=True)
class MoveResult:
    """Result of a designer drag move."""

    delta_x: int
    delta_y: int
    next_rect: tuple[int, int, int, int]
    moved_count: int
    group_move: bool


@dataclass(frozen=True)
class ResizeResult:
    """Result of a designer resize operation."""

    applied: bool
    next_rect: tuple[int, int, int, int] | None


def item_rect(item: dict[str, Any], collection: str) -> tuple[int, int, int, int]:
    """Return an element rectangle in canvas coordinates."""
    if collection in RECT_COLLECTIONS:
        rect = item.get("rect", [0, 0, 1, 1])
        if isinstance(rect, list) and len(rect) == 4:
            return int(rect[0]), int(rect[1]), max(1, int(rect[2])), max(1, int(rect[3]))
        return 0, 0, 1, 1
    return (
        int(item.get("x", 0)),
        int(item.get("y", 0)),
        max(1, int(item.get("box_width", 320))),
        max(1, int(item.get("box_height", 48))),
    )


def apply_item_rect(
    item: dict[str, Any],
    collection: str,
    rect: tuple[int, int, int, int],
    *,
    snap: Callable[[int], int] | None = None,
) -> tuple[int, int, int, int]:
    """Apply a rectangle to an element and return the normalized rectangle."""
    snap_value = snap or (lambda value: int(value))
    x, y, width, height = rect
    normalized = (
        snap_value(int(x)),
        snap_value(int(y)),
        max(1, snap_value(int(width))),
        max(1, snap_value(int(height))),
    )
    nx, ny, nw, nh = normalized
    if collection in RECT_COLLECTIONS:
        item["rect"] = [nx, ny, nw, nh]
    else:
        item["x"] = nx
        item["y"] = ny
        item["box_width"] = nw
        item["box_height"] = nh
    return normalized


def apply_item_position(
    item: dict[str, Any],
    collection: str,
    x: int,
    y: int,
    *,
    snap: Callable[[int], int] | None = None,
) -> tuple[int, int, int, int]:
    """Move an element while preserving its current size."""
    _old_x, _old_y, width, height = item_rect(item, collection)
    snap_value = snap or (lambda value: int(value))
    nx = snap_value(int(x))
    ny = snap_value(int(y))
    if collection in RECT_COLLECTIONS:
        item["rect"] = [nx, ny, width, height]
    else:
        item["x"] = nx
        item["y"] = ny
    return nx, ny, width, height


def resize_item_rect(
    item: dict[str, Any],
    collection: str,
    rect: tuple[int, int, int, int],
    *,
    snap: Callable[[int], int] | None = None,
) -> ResizeResult:
    """Resize an unlocked item and return the normalized rectangle."""
    if bool(item.get("locked", False)):
        return ResizeResult(False, None)
    return ResizeResult(True, apply_item_rect(item, collection, rect, snap=snap))


def move_items_by_delta(
    selected: list[tuple[str, int, dict[str, Any]]],
    dx: int,
    dy: int,
    *,
    snap: Callable[[int], int] | None = None,
) -> int:
    """Move unlocked selected elements by a shared delta and return moved count."""
    moved = 0
    for collection, _row, item in selected:
        if bool(item.get("locked", False)):
            continue
        x, y, _width, _height = item_rect(item, collection)
        apply_item_position(item, collection, x + int(dx), y + int(dy), snap=snap)
        moved += 1
    return moved


def move_drag_target(
    *,
    selected: list[tuple[str, int, dict[str, Any]]],
    target_collection: str,
    target_index: int,
    target_item: dict[str, Any],
    target_x: int,
    target_y: int,
    snap: Callable[[int], int] | None = None,
) -> MoveResult:
    """Move a drag target, preserving grouped selection behavior."""
    current_rect = item_rect(target_item, target_collection)
    delta_x = int(target_x) - int(current_rect[0])
    delta_y = int(target_y) - int(current_rect[1])
    selected_keys = {(collection, row) for collection, row, _item in selected}
    group_move = len(selected) > 1 and (target_collection, int(target_index)) in selected_keys
    if group_move:
        moved_count = move_items_by_delta(selected, delta_x, delta_y, snap=snap) if (delta_x or delta_y) else 0
        next_rect = item_rect(target_item, target_collection)
        return MoveResult(delta_x, delta_y, next_rect, moved_count, True)
    next_rect = apply_item_position(target_item, target_collection, int(target_x), int(target_y), snap=snap)
    moved_count = 1 if next_rect != current_rect else 0
    return MoveResult(
        int(next_rect[0]) - int(current_rect[0]),
        int(next_rect[1]) - int(current_rect[1]),
        next_rect,
        moved_count,
        False,
    )


def group_bounds(selected: list[tuple[str, int, dict[str, Any]]]) -> tuple[int, int, int, int] | None:
    """Return bounds for a multi-selection."""
    rects = [item_rect(item, collection) for collection, _row, item in selected]
    if not rects:
        return None
    left = min(rect[0] for rect in rects)
    top = min(rect[1] for rect in rects)
    right = max(rect[0] + rect[2] for rect in rects)
    bottom = max(rect[1] + rect[3] for rect in rects)
    return int(left), int(top), max(1, int(right - left)), max(1, int(bottom - top))


def theme_items_for_collection(theme_doc: dict[str, Any] | None, collection: str) -> list[dict[str, Any]]:
    """Return the mutable list for a theme collection."""
    if theme_doc is None:
        return []
    if collection == "panels":
        items = theme_doc.get("background", {}).get("panels", [])
    else:
        items = theme_doc.get(collection, [])
    return items if isinstance(items, list) else []
