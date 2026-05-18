"""Animation timeline widget for Theme Designer / Animation Studio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class AnimationSequence:
    """Normalized view of effects.animation."""

    frame_paths: list[str]
    frame_durations_ms: list[int]
    current_frame: int
    fps: float
    enabled: bool
    use_as_background: bool
    loop: bool
    loop_start: int | None = None
    loop_end: int | None = None

    @property
    def frame_count(self) -> int:
        return len(self.frame_paths)

    @property
    def total_duration_ms(self) -> int:
        return sum(self.frame_durations_ms[: self.frame_count])


class AnimationSequenceController:
    """Pure helpers for mutating a theme document animation block."""

    DEFAULT_FPS = 12.0

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    def animation(self) -> dict[str, Any]:
        effects = self.document.setdefault("effects", {})
        if not isinstance(effects, dict):
            effects = {}
            self.document["effects"] = effects
        animation = effects.setdefault("animation", {})
        if not isinstance(animation, dict):
            animation = {}
            effects["animation"] = animation
        return animation

    def normalize(self) -> AnimationSequence:
        animation = self.animation()
        try:
            fps = max(1.0, float(animation.get("fps", self.DEFAULT_FPS)))
        except Exception:
            fps = self.DEFAULT_FPS
        default_duration = max(1, int(round(1000.0 / fps)))

        raw_paths = animation.get("frame_paths", [])
        frame_paths = [str(item) for item in raw_paths] if isinstance(raw_paths, list) else []

        raw_durations = animation.get("frame_durations_ms", [])
        frame_durations: list[int] = []
        if isinstance(raw_durations, list):
            for item in raw_durations[: len(frame_paths)]:
                try:
                    frame_durations.append(max(1, int(item)))
                except Exception:
                    frame_durations.append(default_duration)
        if len(frame_durations) < len(frame_paths):
            frame_durations.extend([default_duration] * (len(frame_paths) - len(frame_durations)))

        try:
            current = int(animation.get("current_frame", 0))
        except Exception:
            current = 0
        current = min(max(0, current), max(0, len(frame_paths) - 1))
        loop_start, loop_end = self._normalized_loop_range(animation, len(frame_paths))

        animation["enabled"] = bool(animation.get("enabled", False)) and bool(frame_paths)
        animation["use_as_background"] = bool(animation.get("use_as_background", True))
        animation["fps"] = fps
        animation["current_frame"] = current
        animation["loop"] = bool(animation.get("loop", True))
        animation["frame_paths"] = frame_paths
        animation["frame_durations_ms"] = frame_durations
        animation["smooth_loop"] = bool(animation.get("smooth_loop", True))
        if loop_start is not None and loop_end is not None:
            animation["loop_start"] = loop_start
            animation["loop_end"] = loop_end

        return AnimationSequence(
            frame_paths=frame_paths,
            frame_durations_ms=frame_durations,
            current_frame=current,
            fps=fps,
            enabled=bool(animation["enabled"]),
            use_as_background=bool(animation["use_as_background"]),
            loop=bool(animation["loop"]),
            loop_start=loop_start,
            loop_end=loop_end,
        )

    def set_current_frame(self, index: int) -> AnimationSequence:
        seq = self.normalize()
        current = min(max(0, int(index)), max(0, seq.frame_count - 1))
        self.animation()["current_frame"] = current
        return self.normalize()

    def replace_frames(self, frame_paths: list[str], *, duration_ms: int | None = None) -> AnimationSequence:
        seq = self.normalize()
        duration = max(1, int(duration_ms if duration_ms is not None else round(1000.0 / max(1.0, seq.fps))))
        animation = self.animation()
        animation["frame_paths"] = [str(item) for item in frame_paths]
        animation["frame_durations_ms"] = [duration] * len(frame_paths)
        animation["enabled"] = bool(frame_paths)
        animation["use_as_background"] = True
        animation["current_frame"] = 0
        return self.normalize()

    def insert_frames(self, frame_paths: list[str], index: int | None = None, *, duration_ms: int | None = None) -> AnimationSequence:
        seq = self.normalize()
        duration = max(1, int(duration_ms if duration_ms is not None else round(1000.0 / max(1.0, seq.fps))))
        insert_at = seq.frame_count if index is None else min(max(0, int(index)), seq.frame_count)
        paths = list(seq.frame_paths)
        durations = list(seq.frame_durations_ms)
        new_paths = [str(item) for item in frame_paths]
        paths[insert_at:insert_at] = new_paths
        durations[insert_at:insert_at] = [duration] * len(new_paths)
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["enabled"] = bool(paths)
        if new_paths:
            animation["current_frame"] = insert_at
        return self.normalize()

    def remove_indices(self, indices: list[int]) -> AnimationSequence:
        seq = self.normalize()
        remove = {int(item) for item in indices if 0 <= int(item) < seq.frame_count}
        if not remove:
            return seq
        paths = [path for idx, path in enumerate(seq.frame_paths) if idx not in remove]
        durations = [duration for idx, duration in enumerate(seq.frame_durations_ms) if idx not in remove]
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["enabled"] = bool(paths)
        animation["current_frame"] = min(seq.current_frame, max(0, len(paths) - 1))
        return self.normalize()

    def keep_indices(self, indices: list[int]) -> AnimationSequence:
        seq = self.normalize()
        keep = self._valid_indices(indices, seq.frame_count)
        if not keep:
            return seq
        paths = [seq.frame_paths[index] for index in keep]
        durations = [seq.frame_durations_ms[index] for index in keep]
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["enabled"] = bool(paths)
        animation["current_frame"] = 0
        animation.pop("loop_start", None)
        animation.pop("loop_end", None)
        return self.normalize()

    def move_single(self, index: int, delta: int) -> AnimationSequence:
        seq = self.normalize()
        source = int(index)
        target = source + int(delta)
        if source < 0 or source >= seq.frame_count or target < 0 or target >= seq.frame_count:
            return seq
        paths = list(seq.frame_paths)
        durations = list(seq.frame_durations_ms)
        paths[source], paths[target] = paths[target], paths[source]
        durations[source], durations[target] = durations[target], durations[source]
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["current_frame"] = target
        return self.normalize()

    def apply_duration(self, indices: list[int], duration_ms: int) -> AnimationSequence:
        seq = self.normalize()
        duration = max(1, int(duration_ms))
        durations = list(seq.frame_durations_ms)
        for index in indices:
            if 0 <= int(index) < len(durations):
                durations[int(index)] = duration
        self.animation()["frame_durations_ms"] = durations[: seq.frame_count]
        return self.normalize()

    def reverse_indices(self, indices: list[int] | None = None) -> AnimationSequence:
        seq = self.normalize()
        if seq.frame_count < 2:
            return seq
        rows = self._valid_indices(indices, seq.frame_count)
        if len(rows) < 2:
            rows = list(range(seq.frame_count))
        paths = list(seq.frame_paths)
        durations = list(seq.frame_durations_ms)
        reversed_paths = [paths[index] for index in rows][::-1]
        reversed_durations = [durations[index] for index in rows][::-1]
        for index, path, duration in zip(rows, reversed_paths, reversed_durations, strict=True):
            paths[index] = path
            durations[index] = duration
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["current_frame"] = rows[0]
        return self.normalize()

    def ping_pong(self, indices: list[int] | None = None) -> AnimationSequence:
        seq = self.normalize()
        if seq.frame_count < 2:
            return seq
        rows = self._valid_indices(indices, seq.frame_count)
        if len(rows) < 2:
            rows = list(range(seq.frame_count))
        # Mirror the selected run after its end. Avoid duplicating the last frame;
        # for two-frame clips append the first frame so A,B becomes A,B,A.
        mirror_rows = rows[-2:0:-1] if len(rows) > 2 else rows[:1]
        if not mirror_rows:
            return seq
        paths = list(seq.frame_paths)
        durations = list(seq.frame_durations_ms)
        insert_at = rows[-1] + 1
        mirrored_paths = [paths[index] for index in mirror_rows]
        mirrored_durations = [durations[index] for index in mirror_rows]
        paths[insert_at:insert_at] = mirrored_paths
        durations[insert_at:insert_at] = mirrored_durations
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["enabled"] = bool(paths)
        animation["current_frame"] = insert_at
        return self.normalize()

    def close_loop_seam(self, indices: list[int] | None = None) -> AnimationSequence:
        seq = self.normalize()
        if seq.frame_count < 2:
            return seq
        rows = self._valid_indices(indices, seq.frame_count)
        if len(rows) < 2:
            rows = list(range(seq.frame_count))
        first = rows[0]
        insert_at = rows[-1] + 1
        paths = list(seq.frame_paths)
        durations = list(seq.frame_durations_ms)
        paths.insert(insert_at, paths[first])
        durations.insert(insert_at, durations[first])
        animation = self.animation()
        animation["frame_paths"] = paths
        animation["frame_durations_ms"] = durations[: len(paths)]
        animation["enabled"] = bool(paths)
        animation["current_frame"] = insert_at
        loop_start, loop_end = self._normalized_loop_range(animation, seq.frame_count)
        if loop_start is not None and loop_end is not None and loop_start == rows[0] and loop_end == rows[-1]:
            animation["loop_end"] = insert_at
        return self.normalize()

    def repeat_timing(self, indices: list[int], multiplier: int) -> AnimationSequence:
        seq = self.normalize()
        repeat = max(1, int(multiplier))
        durations = list(seq.frame_durations_ms)
        for index in indices:
            if 0 <= int(index) < len(durations):
                durations[int(index)] = max(1, durations[int(index)] * repeat)
        self.animation()["frame_durations_ms"] = durations[: seq.frame_count]
        return self.normalize()

    def set_loop_range(self, start: int, end: int) -> AnimationSequence:
        seq = self.normalize()
        if seq.frame_count <= 0:
            return seq
        lo = min(max(0, int(start)), seq.frame_count - 1)
        hi = min(max(0, int(end)), seq.frame_count - 1)
        if lo > hi:
            lo, hi = hi, lo
        animation = self.animation()
        animation["loop_start"] = lo
        animation["loop_end"] = hi
        if seq.current_frame < lo or seq.current_frame > hi:
            animation["current_frame"] = lo
        return self.normalize()

    def clear_loop_range(self) -> AnimationSequence:
        animation = self.animation()
        animation.pop("loop_start", None)
        animation.pop("loop_end", None)
        return self.normalize()

    @staticmethod
    def _valid_indices(indices: list[int] | None, count: int) -> list[int]:
        if not indices:
            return []
        return sorted({int(item) for item in indices if 0 <= int(item) < count})

    @staticmethod
    def _normalized_loop_range(animation: dict[str, Any], count: int) -> tuple[int | None, int | None]:
        if count <= 1:
            return None, None
        if "loop_start" not in animation and "loop_end" not in animation:
            return None, None
        try:
            start = int(animation.get("loop_start", 0))
        except Exception:
            start = 0
        try:
            end = int(animation.get("loop_end", count - 1))
        except Exception:
            end = count - 1
        start = min(max(0, start), count - 1)
        end = min(max(0, end), count - 1)
        if start > end:
            start, end = end, start
        return start, end


class AnimationTimelineWidget(QWidget):
    """Horizontal timeline with per-frame durations, multi-select, and playhead."""

    _H_PAD = 8
    _GAP = 4
    # Minimum pixel width per segment so many frames scroll horizontally instead of crushing.
    _MIN_SEG_PX = 60

    frame_selected = Signal(int)
    selection_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._durations: list[int] = []
        self._current_index = 0
        self._playhead_index = 0
        self._selection: set[int] = set()
        self._anchor_index: int | None = None
        self._suppress_emit = False
        self._zoom = 1.0
        self._loop_range: tuple[int, int] | None = None
        self._thumbnails: dict[int, QPixmap] = {}
        self.setMinimumHeight(136)

    def _min_segment_px(self) -> int:
        return max(28, int(round(self._MIN_SEG_PX * self._zoom)))

    def _content_width(self) -> int:
        n = len(self._durations)
        if not n:
            return 320
        return self._H_PAD * 2 + n * (self._min_segment_px() + self._GAP) - self._GAP

    def _timeline_width(self) -> int:
        return max(self.width(), self._content_width())

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._content_width(), max(136, self.minimumHeight()))

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._content_width(), max(136, self.minimumHeight()))

    def set_timeline(
        self,
        durations: list[int],
        current_index: int,
        *,
        selection: list[int] | None = None,
        playhead: int | None = None,
        loop_range: tuple[int, int] | None = None,
        thumbnails: dict[int, QPixmap] | None = None,
    ) -> None:
        self._durations = [max(1, int(item)) for item in durations]
        n = len(self._durations)
        if thumbnails is not None:
            self._thumbnails = {
                int(index): pixmap
                for index, pixmap in thumbnails.items()
                if 0 <= int(index) < n and isinstance(pixmap, QPixmap) and not pixmap.isNull()
            }
        else:
            self._thumbnails = {index: pixmap for index, pixmap in self._thumbnails.items() if 0 <= index < n}
        self._current_index = max(0, min(int(current_index), n - 1)) if n else 0
        if playhead is not None:
            self._playhead_index = max(0, min(int(playhead), n - 1)) if n else 0
        else:
            self._playhead_index = self._current_index
        if selection is not None:
            self._selection = {i for i in selection if isinstance(i, int) and 0 <= i < n}
            if not self._selection and n:
                self._selection = {self._current_index}
        elif n and not self._selection:
            self._selection = {self._current_index}
        if loop_range is not None and n:
            a, b = loop_range
            a = max(0, min(int(a), n - 1))
            b = max(0, min(int(b), n - 1))
            self._loop_range = (min(a, b), max(a, b))
        else:
            self._loop_range = None
        self.setFixedWidth(self._content_width())
        self.updateGeometry()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.6, min(float(zoom), 4.0))
        self.setFixedWidth(self._content_width())
        self.updateGeometry()
        self.update()

    def update_thumbnails(self, thumbnails: dict[int, QPixmap]) -> None:
        n = len(self._durations)
        changed = False
        for index, pixmap in thumbnails.items():
            idx = int(index)
            if 0 <= idx < n and isinstance(pixmap, QPixmap) and not pixmap.isNull():
                self._thumbnails[idx] = pixmap
                changed = True
        if changed:
            self.update()

    def set_playhead(self, index: int) -> None:
        n = len(self._durations)
        if not n:
            return
        self._playhead_index = max(0, min(int(index), n - 1))
        self.update()

    def playhead_center_x(self) -> int | None:
        rects = self._segment_rects()
        i = self._playhead_index
        if rects and 0 <= i < len(rects):
            return int(rects[i].center().x())
        return None

    def set_selection(self, indices: list[int], *, emit_signal: bool = True) -> None:
        n = len(self._durations)
        self._selection = {i for i in indices if isinstance(i, int) and 0 <= i < n}
        if not self._selection and n:
            self._selection = {self._current_index}
        self.update()
        if emit_signal and not self._suppress_emit:
            self.selection_changed.emit(sorted(self._selection))

    def _hit_test(self, x: int) -> int | None:
        if not self._durations:
            return None
        total = sum(self._durations)
        if total <= 0:
            return None
        usable_width = max(1, self._timeline_width() - 2 * self._H_PAD)
        cursor = self._H_PAD
        for idx, duration in enumerate(self._durations):
            width = max(self._min_segment_px(), int(round(usable_width * duration / total)))
            if cursor <= x <= cursor + width:
                return idx
            cursor += width + self._GAP
        return None

    def _segment_rects(self) -> list[QRect]:
        rects: list[QRect] = []
        if not self._durations:
            return rects
        total = sum(self._durations)
        usable_width = max(1, self._timeline_width() - 2 * self._H_PAD)
        x = self._H_PAD
        for duration in self._durations:
            width = max(self._min_segment_px(), int(round(usable_width * duration / total)))
            rects.append(QRect(x, 22, width, 84))
            x += width + self._GAP
        return rects

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() != Qt.LeftButton or not self._durations:
            return
        idx = self._hit_test(int(event.position().x()))
        if idx is None:
            return
        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            if idx in self._selection:
                self._selection.discard(idx)
                if not self._selection:
                    self._selection.add(idx)
            else:
                self._selection.add(idx)
            self._anchor_index = idx
        elif mods & Qt.ShiftModifier:
            if self._anchor_index is None:
                self._anchor_index = idx
            a, b = sorted((self._anchor_index, idx))
            self._selection = set(range(a, b + 1))
        else:
            self._selection = {idx}
            self._anchor_index = idx
        self._current_index = idx
        self._playhead_index = idx
        self.update()
        self.frame_selected.emit(idx)
        if not self._suppress_emit:
            self.selection_changed.emit(sorted(self._selection))

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.fillRect(self.rect(), QColor("#151b24"))
            if not self._durations:
                painter.setPen(QColor("#7a8797"))
                painter.drawText(
                    self.rect().adjusted(12, 0, -12, 0),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    "Import frames to show the animation timeline.",
                )
                return
            total = sum(self._durations)
            usable_width = max(1, self._timeline_width() - 2 * self._H_PAD)
            x = self._H_PAD
            rects = self._segment_rects()
            if self._loop_range is not None and rects:
                start, end = self._loop_range
                if 0 <= start < len(rects) and 0 <= end < len(rects):
                    loop_rect = QRect(
                        rects[start].left(),
                        18,
                        rects[end].right() - rects[start].left(),
                        92,
                    )
                    painter.fillRect(loop_rect, QColor(34, 197, 94, 34))
                    painter.setPen(QPen(QColor("#22c55e"), 1))
                    painter.drawRect(loop_rect)
                    painter.drawText(loop_rect.adjusted(4, 0, -4, 0), Qt.AlignTop | Qt.AlignLeft, "IN")
                    painter.drawText(loop_rect.adjusted(4, 0, -4, 0), Qt.AlignTop | Qt.AlignRight, "OUT")
            for idx, duration in enumerate(self._durations):
                width = max(self._min_segment_px(), int(round(usable_width * duration / total)))
                rect = QRect(x, 22, width, 84)
                is_playhead = idx == self._playhead_index
                in_selection = idx in self._selection
                if in_selection:
                    fill = QColor("#2563eb" if is_playhead else "#1e3a5f")
                    border = QColor("#fbbf24")
                else:
                    fill = QColor("#2d6df6" if is_playhead else "#253244")
                    border = QColor("#7dd3fc" if is_playhead else "#42516a")
                painter.setPen(QPen(border, 2 if in_selection else 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 7, 7)
                thumb = self._thumbnails.get(idx)
                image_rect = rect.adjusted(4, 4, -4, -22)
                if thumb is not None and not thumb.isNull() and image_rect.width() > 12 and image_rect.height() > 12:
                    scaled = thumb.scaled(image_rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    source_x = max(0, (scaled.width() - image_rect.width()) // 2)
                    source_y = max(0, (scaled.height() - image_rect.height()) // 2)
                    painter.save()
                    painter.setClipRect(image_rect)
                    painter.drawPixmap(
                        image_rect.topLeft(),
                        scaled,
                        QRect(source_x, source_y, image_rect.width(), image_rect.height()),
                    )
                    painter.restore()
                    painter.fillRect(image_rect, QColor(0, 0, 0, 48 if is_playhead else 70))
                painter.fillRect(rect.adjusted(4, rect.height() - 22, -4, -4), QColor(5, 10, 18, 188))
                painter.setPen(QColor("#eef6ff" if is_playhead else "#c7d2e0"))
                label = f"{idx + 1}"
                if width >= 82:
                    label = f"{idx + 1} · {duration} ms"
                painter.drawText(rect.adjusted(7, rect.height() - 24, -7, -3), Qt.AlignCenter, label)
                x += width + self._GAP

            if rects and 0 <= self._playhead_index < len(rects):
                pr = rects[self._playhead_index]
                cx = pr.center().x()
                painter.setPen(QPen(QColor("#fca5a5"), 2))
                painter.drawLine(cx, 12, cx, self.height() - 8)

                painter.setPen(QColor("#8fa4bf"))
            painter.drawText(
                QRect(self._H_PAD + 2, 0, self._timeline_width() - 2 * self._H_PAD, 16),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"Frames: {len(self._durations)}  |  Total: {sum(self._durations)} ms  |  Playhead: {self._playhead_index + 1}",
            )
        finally:
            painter.end()
