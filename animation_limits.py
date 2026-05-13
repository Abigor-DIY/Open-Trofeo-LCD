"""UI hints for background animation frame count (no hard schema cap)."""

from __future__ import annotations

# Beyond this, list thumbnails are skipped to keep the editor responsive.
ANIMATION_LIST_THUMB_MAX_FRAMES = 36

# Timeline thumbnails stay useful for longer clips; they are smaller and shared
# through the same cache, so this can be higher than the left-side list limit.
ANIMATION_TIMELINE_THUMB_MAX_FRAMES = 160

# TRCC loads every frame into device memory; many HD frames strain USB throughput and RAM.
ANIMATION_FRAMES_SOFT_WARN = 48
ANIMATION_FRAMES_STRONG_WARN = 72
ANIMATION_FRAMES_EXTREME_WARN = 96
