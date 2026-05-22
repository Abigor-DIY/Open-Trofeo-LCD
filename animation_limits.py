"""UI hints for background animation frame count (no hard schema cap)."""

from __future__ import annotations

# Beyond this, list thumbnails are skipped to keep the editor responsive.
ANIMATION_LIST_THUMB_MAX_FRAMES = 48

# Timeline thumbnails stay useful for longer clips; they are smaller and shared
# through the same cache, so this can be higher than the left-side list limit.
ANIMATION_TIMELINE_THUMB_MAX_FRAMES = 240

# TRCC loads every frame into device memory; many HD frames strain USB throughput and RAM.
ANIMATION_FRAMES_SOFT_WARN = 96
ANIMATION_FRAMES_STRONG_WARN = 180
ANIMATION_FRAMES_EXTREME_WARN = 300

# Video backgrounds are expanded to image frames before they are sent to the LCD.
# Keep automatic imports below the strong-warning level; users can still append
# more frames manually when they explicitly want a heavier animation.
VIDEO_IMPORT_MAX_FRAMES = ANIMATION_FRAMES_STRONG_WARN
