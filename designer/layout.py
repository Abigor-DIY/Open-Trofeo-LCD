"""Layout helpers for Theme Designer UI.

These helpers keep splitter sizing rules deterministic and testable outside Qt.
"""

from __future__ import annotations


def designer_splitter_limits(window_height: int) -> tuple[int, int]:
    """Return minimum canvas height and maximum inspector height."""
    height = max(760, int(window_height or 0))
    compact_height = height < 1040
    min_canvas = 280 if compact_height else 320
    max_inspector = 380 if compact_height else 460
    return min_canvas, max_inspector


def designer_inspector_min_height(window_height: int) -> int:
    """Return a stable minimum inspector height for the current window profile."""
    height = max(760, int(window_height or 0))
    return 340 if height < 1040 else 400


def designer_canvas_max_height(window_height: int, content_height: int, min_canvas: int) -> int:
    """Return the maximum canvas height for the current window and content."""
    max_canvas = 430 if int(window_height or 0) < 1040 else 500
    if int(content_height or 0) > 0:
        max_canvas = min(max_canvas, max(int(min_canvas), int(content_height)))
    return max_canvas


def clamp_designer_splitter_sizes(
    sizes: list[int] | tuple[int, ...],
    *,
    min_canvas: int,
    max_canvas: int,
    max_inspector: int,
    min_inspector: int = 180,
    change_threshold: int = 8,
) -> list[int] | None:
    """Return clamped splitter sizes, or None when no visible update is needed."""
    if len(sizes) < 2:
        return None
    current = [int(sizes[0]), int(sizes[1])]
    min_canvas = int(min_canvas)
    max_canvas = max(min_canvas, int(max_canvas))
    min_inspector = int(min_inspector)
    max_inspector = max(min_inspector, int(max_inspector))
    total = max(sum(current), min_canvas + min_inspector)

    target_inspector = min(max_inspector, max(min_inspector, current[1]))
    target_canvas = max(min_canvas, min(max_canvas, total - target_inspector))
    target_inspector = max(min_inspector, min(max_inspector, total - target_canvas))
    if target_canvas + target_inspector < total and target_inspector < max_inspector:
        target_inspector = min(max_inspector, target_inspector + (total - target_canvas - target_inspector))

    next_sizes = [target_canvas, target_inspector]
    if any(abs(current[idx] - next_sizes[idx]) > int(change_threshold) for idx in range(2)):
        return next_sizes
    return None


def should_switch_inspector_tab(
    *,
    current_visible: bool,
    preferred_visible: bool,
    force: bool = False,
) -> bool:
    """Return whether automatic inspector navigation should change tabs."""
    if force:
        return bool(preferred_visible)
    return bool(preferred_visible and not current_visible)
