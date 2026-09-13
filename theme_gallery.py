"""Pure helpers for Theme Gallery card metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from theme_json_with_comments import parse_theme_json_text

TranslateFn = Callable[[str, str], str]
ResolvePathFn = Callable[[str], Path]
DocumentLoaderFn = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True)
class ThemeCardEntry:
    name: str
    item: dict[str, Any]
    category: str
    asset_count: int
    animation_count: int


@dataclass(frozen=True)
class ThemeCardGridMetrics:
    columns: int
    card_width: int
    compact_cards: bool
    card_height_base: int
    row_count: int
    viewport_height: int
    scroll_max_height: int
    box_height: int
    box_max_height: int


def sanitize_theme_name_for_filename(name: str) -> str:
    sanitized = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
    return sanitized or "nowy_motyw"


def new_theme_filename(theme_name: str, template_path: str) -> str:
    base_name = sanitize_theme_name_for_filename(theme_name)
    template_stem = Path(template_path or "themes/nowy_motyw.json").stem.replace("_monitor", "")
    suffix = template_stem if template_stem and template_stem not in {"nowy_motyw", base_name} else ""
    return f"{base_name}.json" if not suffix else f"{base_name}_{suffix}.json"


def default_new_theme_path(themes_dir: Path, theme_name: str, template_path: str) -> Path:
    return themes_dir / new_theme_filename(theme_name, template_path)


def theme_type_badge(theme_item: dict[str, Any], translate: TranslateFn) -> str:
    theme_type = str(theme_item.get("type", "image")).strip()
    if theme_type == "theme-doc":
        return translate("Theme", "Motyw")
    if theme_type == "image":
        return translate("Image", "Obraz")
    return theme_type or translate("Theme", "Motyw")


def read_theme_document_for_card(theme_item: dict[str, Any], resolve_path: ResolvePathFn) -> dict[str, Any] | None:
    theme_type = str(theme_item.get("type", "")).strip()
    path = str(theme_item.get("path", "")).strip()
    if theme_type != "theme-doc" or not path:
        return None
    try:
        resolved = resolve_path(path)
        raw = parse_theme_json_text(resolved.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def theme_card_category(theme_item: dict[str, Any], document: dict[str, Any] | None = None) -> str:
    if isinstance(document, dict):
        effects = document.get("effects", {})
        animation = effects.get("animation", {}) if isinstance(effects, dict) else {}
        frame_paths = animation.get("frame_paths", []) if isinstance(animation, dict) else []
        if bool(animation.get("enabled", False)) and isinstance(frame_paths, list) and len(frame_paths) > 1:
            return "Animated"
        meta = document.get("meta", {})
        tags = meta.get("tags", []) if isinstance(meta, dict) else []
        if isinstance(tags, list) and any(str(tag).strip().lower() == "ttcr-import" for tag in tags):
            return "TTCR"
        if isinstance(effects, dict) and isinstance(effects.get("import_report"), dict):
            source_path = str(effects["import_report"].get("source_path", "")).lower()
            if "ttcr" in source_path:
                return "TTCR"
    path = str(theme_item.get("path", "")).lower()
    if "ttcr" in path:
        return "TTCR"
    return "Local"


def theme_card_stats(document: dict[str, Any] | None) -> tuple[int, int]:
    if not isinstance(document, dict):
        return 0, 0
    asset_count = 0
    background = document.get("background", {})
    if isinstance(background, dict) and str(background.get("path", "")).strip():
        asset_count += 1
    images = document.get("images", [])
    if isinstance(images, list):
        asset_count += sum(1 for item in images if isinstance(item, dict) and str(item.get("path", "")).strip())
    effects = document.get("effects", {})
    animation = effects.get("animation", {}) if isinstance(effects, dict) else {}
    frame_paths = animation.get("frame_paths", []) if isinstance(animation, dict) else []
    animation_count = len(frame_paths) if isinstance(frame_paths, list) else 0
    return asset_count, animation_count


def filtered_theme_card_entries(
    theme_items: dict[str, dict[str, Any]],
    *,
    needle: str = "",
    type_filter: str = "All",
    sort_mode: str = "Name A-Z",
    resolve_path: ResolvePathFn | None = None,
    document_loader: DocumentLoaderFn | None = None,
) -> list[ThemeCardEntry]:
    search = needle.strip().lower()
    selected_type = type_filter.strip() or "All"
    entries: list[ThemeCardEntry] = []

    for name, item in theme_items.items():
        theme_type = str(item.get("type", "image"))
        haystack = " ".join([name, theme_type, str(item.get("path", ""))]).lower()
        if search and search not in haystack:
            continue

        document = document_loader(item) if document_loader is not None else None
        category = theme_card_category(item, document)
        if selected_type == "Image" and theme_type != "image":
            continue
        if selected_type == "Theme" and theme_type != "theme-doc":
            continue
        if selected_type in {"Local", "TTCR", "Animated"} and category != selected_type:
            continue

        asset_count, animation_count = theme_card_stats(document)
        entries.append(
            ThemeCardEntry(
                name=name,
                item=item,
                category=category,
                asset_count=asset_count,
                animation_count=animation_count,
            )
        )

    if sort_mode in {"Newest", "Oldest"}:

        def _mtime(entry: ThemeCardEntry) -> float:
            if resolve_path is None:
                return 0.0
            try:
                resolved = resolve_path(str(entry.item.get("path", "")))
                return resolved.stat().st_mtime if resolved.exists() else 0.0
            except Exception:
                return 0.0

        entries.sort(key=_mtime, reverse=(sort_mode == "Newest"))
    else:
        entries.sort(key=lambda entry: entry.name.lower(), reverse=(sort_mode == "Name Z-A"))
    return entries


def theme_card_grid_metrics(
    *,
    viewport_width: int,
    spacing: int,
    entry_names: list[str],
    current_name: str,
    controls_height: int = 110,
) -> ThemeCardGridMetrics:
    available_width = max(260, viewport_width - 4)
    min_card_width = 300
    columns = max(1, min(4, (available_width + spacing) // (min_card_width + spacing)))
    card_width = max(260, int((available_width - ((columns - 1) * spacing)) / columns))
    compact_cards = card_width < 430
    card_height_base = 268 if compact_cards else 228
    row_count = max(1, (len(entry_names) + columns - 1) // columns)
    visible_rows = min(row_count, 3)
    visible_heights = [
        card_height_base + (24 if compact_cards and name == current_name else 0)
        for name in entry_names[: visible_rows * columns]
    ]
    viewport_card_height = max(visible_heights or [card_height_base])
    row_gap = spacing
    viewport_height = 14 + (visible_rows * viewport_card_height) + (max(0, visible_rows - 1) * row_gap) + 10
    box_height = controls_height + viewport_height
    return ThemeCardGridMetrics(
        columns=columns,
        card_width=card_width,
        compact_cards=compact_cards,
        card_height_base=card_height_base,
        row_count=row_count,
        viewport_height=viewport_height,
        scroll_max_height=viewport_height if row_count <= 3 else 760,
        box_height=box_height,
        box_max_height=box_height if row_count <= 3 else 900,
    )


def theme_modified_label(theme_item: dict[str, Any], resolve_path: ResolvePathFn) -> str:
    path = str(theme_item.get("path", "")).strip()
    if not path:
        return "Brak pliku"
    try:
        resolved = resolve_path(path)
        if resolved.exists():
            stamp = datetime.fromtimestamp(resolved.stat().st_mtime)
            return f"Zmieniono: {stamp.strftime('%Y-%m-%d %H:%M')}"
    except Exception:
        pass
    return "Brak daty"
