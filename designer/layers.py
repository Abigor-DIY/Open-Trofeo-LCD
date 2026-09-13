"""Layer list presentation helpers for Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def _type_tag(collection: str) -> str:
    return {
        "texts": "TXT",
        "stats": "STA",
        "images": "IMG",
        "panels": "PNL",
        "widgets": "WID",
    }.get(collection, collection[:3].upper())


def _layer_prefix(item: dict[str, Any], collection: str) -> str:
    flags = []
    if not bool(item.get("visible", True)):
        flags.append("H")
    if bool(item.get("locked", False)):
        flags.append("L")
    type_tag = _type_tag(collection)
    return f"[{type_tag}{':' + ''.join(flags) if flags else ''}] "


def designer_item_display_name(
    item: dict[str, Any],
    collection: str,
    idx: int,
    *,
    humanize_stat_source: Callable[[str], str] | None = None,
) -> str:
    """Return the compact layer title shown in the Designer layer list."""
    ident = str(item.get("id", f"{collection}_{idx}")).strip() or f"{collection}_{idx}"
    prefix = _layer_prefix(item, collection)
    if collection == "texts":
        text = str(item.get("text", "")).strip() or "Tekst"
        return f"{prefix}{text[:30]}"
    if collection == "stats":
        label = str(item.get("label", "")).strip()
        source = str(item.get("source", "")).strip() or "stat"
        display = str(item.get("display", "text")).strip().lower()
        if display == "equalizer":
            return f"{prefix}{(label or 'Graphic EQ')[:40]}"
        title = label or (humanize_stat_source(source) if humanize_stat_source else source)
        return f"{prefix}{title[:40]}"
    if collection == "panels":
        rect = item.get("rect", [0, 0, 0, 0])
        size = f"{rect[2]}x{rect[3]}" if isinstance(rect, list) and len(rect) == 4 else "panel"
        return f"{prefix}Panel {idx + 1} [{size}]"
    if collection == "widgets":
        kind = str(item.get("kind", "widget")).strip()
        label = {
            "weather_current": "Pogoda teraz",
            "weather_forecast_7d": "Prognoza 7 dni",
            "media_now_playing": "Now Playing",
        }.get(kind, kind or "Widget")
        return f"{prefix}{label[:40]}"
    source = str(item.get("source", "")).strip()
    if source == "media_cover":
        return f"{prefix}Okładka Now Playing"
    if source == "media_video_frame":
        return f"{prefix}Kadr Media / Video"
    if source == "analog_clock":
        style = str(item.get("clock_style", "classic")).strip().title() or "Classic"
        return f"{prefix}Zegar analogowy {style}"
    name = Path(str(item.get("path", ""))).name or ident
    return f"{prefix}{name[:34]}"


def designer_item_subtitle(item: dict[str, Any], collection: str) -> str:
    """Return the compact layer subtitle shown below the layer title."""
    if collection == "stats":
        source = str(item.get("source", "")).strip()
        label = str(item.get("label", "")).strip()
        display = str(item.get("display", "text")).strip().lower()
        if display == "equalizer":
            return f"music equalizer • {int(item.get('equalizer_bars', 18))} bars"
        source_text = label or source or "Statystyka"
        return f"{source_text} • {int(item.get('font_size', 22))} px"
    if collection == "images":
        rect = item.get("rect", [0, 0, 0, 0])
        fit = str(item.get("fit", "contain")).strip()
        source = str(item.get("source", "")).strip()
        if source == "media_cover":
            if isinstance(rect, list) and len(rect) == 4:
                return f"dynamiczna okładka • {rect[2]}×{rect[3]}"
            return "dynamiczna okładka"
        if source == "media_video_frame":
            if isinstance(rect, list) and len(rect) == 4:
                return f"dynamiczny media-backdrop • {rect[2]}×{rect[3]}"
            return "dynamiczny media-backdrop"
        if isinstance(rect, list) and len(rect) == 4:
            return f"{rect[2]}×{rect[3]} • {fit}"
        return fit
    if collection == "panels":
        rect = item.get("rect", [0, 0, 0, 0])
        if isinstance(rect, list) and len(rect) == 4:
            return f"{rect[2]}×{rect[3]} • radius {int(item.get('radius', 0))}"
    if collection == "widgets":
        rect = item.get("rect", [0, 0, 0, 0])
        style = str(item.get("style", "compact")).strip()
        if isinstance(rect, list) and len(rect) == 4:
            return f"{rect[2]}×{rect[3]} • {style}"
        return style
    if collection == "texts":
        text = str(item.get("text", "")).strip()
        return f"{int(item.get('font_size', 24))} px • {str(item.get('align', 'left'))} • {text[:24]}"
    return ""


def is_media_related_layer(
    item: dict[str, Any],
    collection: str,
    *,
    is_music_stat_source: Callable[[str], bool],
    music_visual_displays: set[str] | frozenset[str],
) -> bool:
    """Return whether a layer belongs to the Music / Now Playing domain."""
    ident = str(item.get("id", "")).strip().lower()
    source = str(item.get("source", "")).strip().lower()
    label = str(item.get("label", "")).strip().lower()
    display = str(item.get("display", "")).strip().lower()
    if source.startswith("media_") or source == "media_cover" or is_music_stat_source(source):
        return True
    if collection == "widgets" and str(item.get("kind", "")).strip().lower().startswith("media_"):
        return True
    if display in music_visual_displays:
        return True
    if ident.startswith("panel_media") or ident.startswith("stat_media") or ident.startswith("img_media"):
        return True
    if ident.startswith("panel_volume") or ident.startswith("stat_volume") or ident.startswith("panel_music_eq"):
        return True
    return "media" in ident or "now playing" in label or "equalizer" in ident or "graphic eq" in label


def is_weather_related_layer(
    item: dict[str, Any],
    collection: str,
    *,
    is_weather_stat_source: Callable[[str], bool],
    weather_image_sources: set[str] | frozenset[str],
    weather_panel_prefixes: tuple[str, ...],
) -> bool:
    """Return whether a layer belongs to the Weather domain."""
    ident = str(item.get("id", "")).strip().lower()
    source = str(item.get("source", "")).strip().lower()
    label = str(item.get("label", "")).strip().lower()
    if collection == "stats" and is_weather_stat_source(source):
        return True
    if collection == "images" and (
        source in weather_image_sources
        or (source.startswith("weather_day_") and source.endswith("_icon"))
    ):
        return True
    if collection == "panels" and any(ident.startswith(prefix) for prefix in weather_panel_prefixes):
        return True
    if collection == "widgets" and str(item.get("kind", "")).strip().lower().startswith("weather_"):
        return True
    return "weather" in ident or "pogoda" in label or "weather" in label


def designer_item_matches_domain(
    item: dict[str, Any],
    collection: str,
    domain: str,
    *,
    is_music_stat_source: Callable[[str], bool],
    is_weather_stat_source: Callable[[str], bool],
    music_visual_displays: set[str] | frozenset[str],
    weather_image_sources: set[str] | frozenset[str],
    weather_panel_prefixes: tuple[str, ...],
) -> bool:
    """Return whether a layer should be visible under the domain filter."""
    domain_key = str(domain).strip().lower() or "all"
    if domain_key == "all":
        return True
    is_music = is_media_related_layer(
        item,
        collection,
        is_music_stat_source=is_music_stat_source,
        music_visual_displays=music_visual_displays,
    )
    is_weather = is_weather_related_layer(
        item,
        collection,
        is_weather_stat_source=is_weather_stat_source,
        weather_image_sources=weather_image_sources,
        weather_panel_prefixes=weather_panel_prefixes,
    )
    if domain_key == "music":
        return is_music
    if domain_key == "weather":
        return is_weather
    if domain_key == "system":
        return not is_music and not is_weather
    return True
