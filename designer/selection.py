"""Selection helpers for Theme Designer.

The functions here avoid Qt dependencies so selection and canvas metadata can be
tested without constructing the main window.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .geometry import item_rect, theme_items_for_collection

SelectionEntry = tuple[str, int]
SelectedItem = tuple[str, int, dict[str, Any]]


def normalize_selection(theme_doc: dict[str, Any] | None, entries: list[SelectionEntry] | None) -> list[SelectionEntry]:
    """Deduplicate selection entries and keep only rows that exist."""
    if theme_doc is None or not entries:
        return []
    normalized: list[SelectionEntry] = []
    seen: set[SelectionEntry] = set()
    for collection, row in entries:
        key = (str(collection), int(row))
        if key in seen:
            continue
        items = theme_items_for_collection(theme_doc, key[0])
        if 0 <= key[1] < len(items):
            normalized.append(key)
            seen.add(key)
    return normalized


def selection_entries(
    theme_doc: dict[str, Any] | None,
    cross_selection: list[SelectionEntry] | None,
    current_collection: str,
    selected_rows: list[int],
) -> list[SelectionEntry]:
    """Return active cross-collection selection or current-list selection."""
    selected = normalize_selection(theme_doc, cross_selection)
    if selected:
        return selected
    return normalize_selection(theme_doc, [(current_collection, row) for row in selected_rows])


def selected_items(theme_doc: dict[str, Any] | None, entries: list[SelectionEntry]) -> list[SelectedItem]:
    """Resolve selection entries into mutable theme items."""
    out: list[SelectedItem] = []
    for collection, row in normalize_selection(theme_doc, entries):
        items = theme_items_for_collection(theme_doc, collection)
        if 0 <= row < len(items):
            item = items[row]
            if isinstance(item, dict):
                out.append((collection, row, item))
    return out


def current_selected_items(items: list[dict[str, Any]], rows: list[int]) -> list[tuple[int, dict[str, Any]]]:
    """Resolve row selections inside a single collection."""
    out: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        if 0 <= row < len(items):
            item = items[row]
            if isinstance(item, dict):
                out.append((row, item))
    return out


def rows_for_collection(entries: list[SelectionEntry], collection: str) -> list[int]:
    """Return selected rows that belong to one Theme Designer collection."""
    return [row for selected_collection, row in entries if selected_collection == collection]


def row_activation_selection(
    *,
    row: int,
    count: int,
    current_row: int,
    selected_rows: list[int],
    ctrl: bool = False,
    shift: bool = False,
) -> tuple[list[int], int]:
    """Return list-row selection after a click with optional Ctrl/Shift semantics."""
    if row < 0 or row >= count:
        return sorted(set(selected_rows)), current_row
    selected = set(selected_rows)
    if ctrl:
        if row in selected:
            selected.remove(row)
        else:
            selected.add(row)
        return sorted(selected), row
    if shift and current_row >= 0:
        start = min(current_row, row)
        end = max(current_row, row)
        return list(range(start, end + 1)), row
    return [row], row


def replacement_visible_row(current_row: int, hidden_rows: set[int], count: int) -> int:
    """Keep current row if visible, otherwise return the first visible row."""
    if 0 <= current_row < count and current_row not in hidden_rows:
        return current_row
    for row in range(count):
        if row not in hidden_rows:
            return row
    return -1


def toggle_item_bool(items: list[dict[str, Any]], row: int, key: str, default: bool) -> bool:
    """Toggle a boolean item flag and report whether the row existed."""
    if not (0 <= row < len(items)):
        return False
    items[row][key] = not bool(items[row].get(key, default))
    return True


def reorder_items_by_ids(items: list[dict[str, Any]], ordered_ids: list[str]) -> list[dict[str, Any]] | None:
    """Return items reordered by their id values, preserving all items exactly once."""
    by_id = {str(item.get("id", "")): item for item in items}
    reordered: list[dict[str, Any]] = []
    for ident in ordered_ids:
        target = by_id.get(str(ident))
        if target is not None:
            reordered.append(target)
    if len(reordered) != len(items):
        return None
    for idx, item in enumerate(reordered):
        item["z_index"] = idx
    return reordered


def adjust_selected_z(selected: list[SelectedItem], delta: int) -> bool:
    """Move selected layers up/down in z order by a relative delta."""
    if not selected:
        return False
    for _collection, _row, item in selected:
        item["z_index"] = int(item.get("z_index", 0)) + int(delta)
    return True


def move_selected_z_to_edge(
    selected: list[SelectedItem],
    all_items: list[dict[str, Any]],
    edge: str,
) -> bool:
    """Move selected layers in front of or behind all canvas items."""
    if not selected or not all_items:
        return False
    z_values = [int(entry.get("z_index", 0)) for entry in all_items]
    edge_key = str(edge).strip().lower()
    if edge_key == "back":
        next_z = min(z_values) - len(selected)
    else:
        next_z = max(z_values) + 1
    for _collection, _row, item in selected:
        item["z_index"] = next_z
        next_z += 1
    return True


def selection_group_label(
    theme_doc: dict[str, Any] | None,
    entries: list[SelectionEntry],
    *,
    media_predicate: Callable[[dict[str, Any], str], bool],
) -> str:
    """Return the designer label for a multi-item selection group."""
    normalized = normalize_selection(theme_doc, entries)
    if len(normalized) <= 1:
        return ""
    if all(
        media_predicate(theme_items_for_collection(theme_doc, collection)[row], collection)
        for collection, row in normalized
    ):
        return "Media Player"
    return "Grupa warstw" if len({collection for collection, _row in normalized}) > 1 else ""


def canvas_elements(theme_doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build canvas overlay metadata from a theme document."""
    if theme_doc is None:
        return []
    out: list[dict[str, Any]] = []
    for collection in ("panels", "images", "texts", "stats", "widgets"):
        items = theme_items_for_collection(theme_doc, collection)
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            rect_tuple = item_rect(item, collection)
            label = str(item.get("id", f"{collection}_{idx}"))
            out.append(
                {
                    "collection": collection,
                    "index": idx,
                    "rect": rect_tuple,
                    "label": label,
                    "z_index": int(item.get("z_index", 0)),
                    "visible": bool(item.get("visible", True)),
                    "locked": bool(item.get("locked", False)),
                }
            )
    return sorted(out, key=lambda item: int(item.get("z_index", 0)))
