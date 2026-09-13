from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QLabel, QWidget

from designer.canvas import compute_snap_guides, resize_rect_from_drag


class PreviewLabel(QLabel):
    image_clicked = Signal(int, int)
    element_selected = Signal(str, int)
    element_moved = Signal(str, int, int, int)
    element_resized = Signal(str, int, int, int, int, int)
    elements_box_selected = Signal(object)
    crop_rect_selected = Signal(object)
    cursor_changed = Signal(object)
    drag_started = Signal()
    drag_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(680, 190)
        self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.setStyleSheet("border: 1px solid #555; background: #111;")
        self._source_pixmap: QPixmap | None = None
        self._draw_offset_x = 0
        self._draw_offset_y = 0
        self._draw_width = 0
        self._draw_height = 0
        self._canvas_size = QSize(1920, 462)
        self._display_rotation = 0
        self._elements: list[dict[str, Any]] = []
        self._selected: tuple[str, int] | None = None
        self._selected_many: set[tuple[str, int]] = set()
        self._drag_mode: str | None = None
        self._drag_origin = QPoint()
        self._drag_start_rect: tuple[int, int, int, int] | None = None
        self._had_drag_motion = False
        self._selection_origin_widget: QPoint | None = None
        self._selection_current_widget: QPoint | None = None
        self._zoom_mode = "fit"
        self._zoom_percent = 100
        self._guide_lines: list[dict[str, Any]] = []
        self._movement_badge: str = ""
        self._render_pending_message = ""
        self._tool_mode = "auto"
        self._snap_threshold = 8

    def set_preview_pixmap(self, pixmap: QPixmap | None, *, display_rotation: int = 0) -> None:
        self._display_rotation = int(display_rotation) % 360
        if pixmap is not None and not pixmap.isNull() and self._display_rotation:
            transform = QTransform().rotate(self._display_rotation)
            pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self._source_pixmap = pixmap
        self._refresh_scaled_pixmap()

    def set_canvas_metadata(
        self,
        *,
        canvas_width: int,
        canvas_height: int,
        elements: list[dict[str, Any]],
        selected: list[tuple[str, int]] | tuple[str, int] | None,
        preserve_temporary_guides: bool = False,
    ) -> None:
        self._canvas_size = QSize(max(1, canvas_width), max(1, canvas_height))
        self._elements = elements
        normalized: list[tuple[str, int]] = []
        if isinstance(selected, tuple) and len(selected) == 2:
            normalized = [(str(selected[0]), int(selected[1]))]
        elif isinstance(selected, list):
            for entry in selected:
                if (
                    isinstance(entry, tuple)
                    and len(entry) == 2
                    and isinstance(entry[0], str)
                    and isinstance(entry[1], int)
                ):
                    normalized.append((str(entry[0]), int(entry[1])))
        self._selected = normalized[0] if normalized else None
        self._selected_many = set(normalized)
        if not preserve_temporary_guides:
            self._guide_lines = []
            self._movement_badge = ""
        self.update()

    def set_temporary_guides(self, guides: list[object], badge: str = "") -> None:
        normalized_guides: list[dict[str, Any]] = []
        for guide in guides:
            entry = self._normalize_guide_entry(guide)
            if entry is not None:
                normalized_guides.append(entry)
        self._guide_lines = normalized_guides
        self._movement_badge = self._compose_guide_badge(badge, self._guide_lines)
        self.update()

    def clear_temporary_guides(self) -> None:
        self._guide_lines = []
        self._movement_badge = ""
        self.update()

    def set_render_pending(self, pending: bool, message: str = "Renderuję podgląd...") -> None:
        self._render_pending_message = str(message).strip() if pending else ""
        self.update()

    def set_zoom_mode(self, mode: str) -> None:
        self._zoom_mode = mode
        self._refresh_scaled_pixmap()

    def set_zoom_percent(self, percent: int) -> None:
        self._zoom_mode = "manual"
        self._zoom_percent = max(25, min(300, int(percent)))
        self._refresh_scaled_pixmap()

    def set_snap_threshold(self, value: int) -> None:
        self._snap_threshold = max(4, min(32, int(value)))

    def set_tool_mode(self, mode: str) -> None:
        normalized = str(mode).strip().lower() or "auto"
        if normalized not in {"auto", "select", "move", "scale", "crop"}:
            normalized = "auto"
        self._tool_mode = normalized
        self.setCursor(self._cursor_for_tool_or_hit(None))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._source_pixmap is None or self._draw_width <= 0 or self._draw_height <= 0:
            return
        pos = event.position().toPoint()
        local_x = pos.x() - self._draw_offset_x
        local_y = pos.y() - self._draw_offset_y
        if local_x < 0 or local_y < 0 or local_x >= self._draw_width or local_y >= self._draw_height:
            return
        src_w = max(1, self._source_pixmap.width())
        src_h = max(1, self._source_pixmap.height())
        img_x = int(round(local_x * src_w / self._draw_width))
        img_y = int(round(local_y * src_h / self._draw_height))
        img_x = max(0, min(src_w - 1, img_x))
        img_y = max(0, min(src_h - 1, img_y))
        if self._tool_mode == "crop":
            self._selection_origin_widget = pos
            self._selection_current_widget = pos
            self._drag_mode = None
            self.update()
            return
        hit = self._hit_test(event.position().toPoint())
        if self._tool_mode == "select":
            if hit is not None:
                collection, index, _mode = hit
                target = (collection, index)
                preserve_multi = target in self._selected_many and len(self._selected_many) > 1
                self._selected = target
                if not preserve_multi:
                    self._selected_many = {target}
                    self.element_selected.emit(collection, index)
                self.update()
                return
            self._selection_origin_widget = pos
            self._selection_current_widget = pos
            return
        if hit is not None:
            collection, index, mode = hit
            target = (collection, index)
            preserve_multi = target in self._selected_many and len(self._selected_many) > 1
            self._selected = target
            if not preserve_multi:
                self._selected_many = {target}
                self.element_selected.emit(collection, index)
            rect = self._element_rect_for_canvas(collection, index)
            if rect is not None:
                forced_mode = mode
                if self._tool_mode == "move":
                    forced_mode = "move"
                elif self._tool_mode == "scale":
                    if forced_mode.startswith("resize-"):
                        pass
                    else:
                        forced_mode = self._preferred_resize_mode(self._canvas_rect_to_widget_rect(rect), pos)
                self._drag_mode = forced_mode
                self._drag_origin = QPoint(img_x, img_y)
                self._drag_start_rect = rect
                self._had_drag_motion = False
                self.drag_started.emit()
            self.update()
            return
        self._selection_origin_widget = pos
        self._selection_current_widget = pos

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_mode is None or self._selected is None or self._drag_start_rect is None:
            pos = event.position().toPoint()
            if self._selection_origin_widget is not None:
                self._selection_current_widget = pos
                self.update()
            hit_mode: str | None = None
            if self._tool_mode in {"auto", "move", "scale"}:
                hit = self._hit_test(pos)
                if hit is not None:
                    hit_mode = str(hit[2])
                    if self._tool_mode == "move" and hit_mode.startswith("resize-"):
                        hit_mode = "move"
                    elif self._tool_mode == "scale" and hit_mode == "move":
                        rect = self._element_rect_for_canvas(str(hit[0]), int(hit[1]))
                        hit_mode = self._preferred_resize_mode(self._canvas_rect_to_widget_rect(rect), pos) if rect is not None else "resize-br"
            self.setCursor(self._cursor_for_tool_or_hit(hit_mode))
            self.cursor_changed.emit(img_pos if (img_pos := self._widget_to_image_point(pos)) is not None else None)
            return
        pos = event.position().toPoint()
        img_pos = self._widget_to_image_point(pos)
        if img_pos is None:
            return
        start_x, start_y, start_w, start_h = self._drag_start_rect
        dx = img_pos.x() - self._drag_origin.x()
        dy = img_pos.y() - self._drag_origin.y()
        self._had_drag_motion = self._had_drag_motion or bool(dx or dy)
        collection, index = self._selected
        self.cursor_changed.emit(img_pos)
        if self._drag_mode == "move":
            self._guide_lines = self._compute_snap_guides(start_x + dx, start_y + dy, start_w, start_h, collection, index)
            self.element_moved.emit(collection, index, start_x + dx, start_y + dy)
        elif self._drag_mode.startswith("resize"):
            next_x, next_y, next_w, next_h = self._resize_rect_from_drag(
                self._drag_mode,
                start_x,
                start_y,
                start_w,
                start_h,
                dx,
                dy,
            )
            self._guide_lines = self._compute_snap_guides(next_x, next_y, next_w, next_h, collection, index)
            self.element_resized.emit(
                collection,
                index,
                next_x,
                next_y,
                next_w,
                next_h,
            )

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.cursor_changed.emit(None)
        self.setCursor(self._cursor_for_tool_or_hit(None))
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        had_drag = self._drag_mode is not None and self._had_drag_motion
        self._drag_mode = None
        self._drag_start_rect = None
        self._had_drag_motion = False
        self._guide_lines = []
        if had_drag:
            self.drag_finished.emit()
        elif self._selection_origin_widget is not None and self._selection_current_widget is not None:
            selection_rect = QRect(self._selection_origin_widget, self._selection_current_widget).normalized()
            if selection_rect.width() >= 8 or selection_rect.height() >= 8:
                if self._tool_mode == "crop":
                    start_img = self._widget_to_image_point(self._selection_origin_widget)
                    end_img = self._widget_to_image_point(self._selection_current_widget)
                    if start_img is not None and end_img is not None:
                        left = min(start_img.x(), end_img.x())
                        top = min(start_img.y(), end_img.y())
                        right = max(start_img.x(), end_img.x())
                        bottom = max(start_img.y(), end_img.y())
                        if right - left >= 4 and bottom - top >= 4:
                            self.crop_rect_selected.emit((left, top, right, bottom))
                else:
                    selected = self._elements_in_widget_rect(selection_rect)
                    if selected:
                        self.elements_box_selected.emit(selected)
            else:
                img_pos = self._widget_to_image_point(event.position().toPoint())
                if img_pos is not None:
                    self.image_clicked.emit(img_pos.x(), img_pos.y())
        self._selection_origin_widget = None
        self._selection_current_widget = None
        self.cursor_changed.emit(None)
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self._draw_width <= 0 or self._draw_height <= 0:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            if self._elements:
                for item in self._elements:
                    if not bool(item.get("visible", True)):
                        continue
                    rect = self._canvas_rect_to_widget_rect(item["rect"])
                    if rect.width() <= 0 or rect.height() <= 0:
                        continue
                    key = (str(item["collection"]), int(item["index"]))
                    is_selected = key in self._selected_many or self._selected == key
                    color = "#888888" if bool(item.get("locked", False)) else ("#5ec8ff" if is_selected else "#ffb347")
                    pen = QPen(QColor(color))
                    pen.setWidth(2 if is_selected else 1)
                    painter.setPen(pen)
                    painter.drawRect(rect)
                    painter.drawText(rect.topLeft() + QPoint(4, 14), str(item["label"]))
                    if is_selected:
                        self._paint_selection_handles(painter, rect, key == self._selected)
                if len(self._selected_many) > 1:
                    group_rect = self._group_bounds_rect()
                    if group_rect is not None:
                        painter.setPen(QPen(QColor("#5ec8ff"), 1, Qt.DashLine))
                        painter.drawRoundedRect(group_rect.adjusted(-8, -8, 8, 8), 10, 10)
                        painter.drawText(group_rect.topLeft() + QPoint(6, -6), "Group")
            if self._selection_origin_widget is not None and self._selection_current_widget is not None:
                select_rect = QRect(self._selection_origin_widget, self._selection_current_widget).normalized()
                painter.setPen(QPen(QColor("#89ddff"), 1, Qt.DashLine))
                painter.fillRect(select_rect, QColor(94, 200, 255, 36))
                painter.drawRect(select_rect)
            if self._guide_lines:
                guide_pen = QPen(QColor("#45d0ff"), 1, Qt.DashLine)
                painter.setPen(guide_pen)
                for guide in self._guide_lines:
                    axis = str(guide.get("axis", ""))
                    value = int(guide.get("value", 0))
                    if axis == "x":
                        x = self._draw_offset_x + int(round(value * self._draw_width / max(1, self._canvas_size.width())))
                        painter.drawLine(x, self._draw_offset_y, x, self._draw_offset_y + self._draw_height)
                        self._paint_guide_label(painter, QPoint(x + 6, self._draw_offset_y + 24), str(guide.get("label", value)))
                    else:
                        y = self._draw_offset_y + int(round(value * self._draw_height / max(1, self._canvas_size.height())))
                        painter.drawLine(self._draw_offset_x, y, self._draw_offset_x + self._draw_width, y)
                        self._paint_guide_label(painter, QPoint(self._draw_offset_x + 30, y - 6), str(guide.get("label", value)))
            if self._movement_badge:
                badge_rect = QRect(self._draw_offset_x + 18, self._draw_offset_y + 22, 180, 34)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(12, 18, 28, 220))
                painter.drawRoundedRect(badge_rect, 8, 8)
                painter.setPen(QColor("#7dd3fc"))
                painter.drawText(badge_rect.adjusted(12, 0, -12, 0), Qt.AlignVCenter | Qt.AlignLeft, self._movement_badge)
            if self._render_pending_message:
                self._paint_preview_status_badge(painter, self._render_pending_message)
            self._paint_rulers(painter)
        finally:
            painter.end()

    def _widget_to_image_point(self, pos: QPoint) -> QPoint | None:
        local_x = pos.x() - self._draw_offset_x
        local_y = pos.y() - self._draw_offset_y
        if local_x < 0 or local_y < 0 or local_x >= self._draw_width or local_y >= self._draw_height:
            return None
        src_w = max(1, self._canvas_size.width())
        src_h = max(1, self._canvas_size.height())
        img_x = int(round(local_x * src_w / self._draw_width))
        img_y = int(round(local_y * src_h / self._draw_height))
        return QPoint(max(0, min(src_w - 1, img_x)), max(0, min(src_h - 1, img_y)))

    def _canvas_rect_to_widget_rect(self, rect: tuple[int, int, int, int]) -> QRect:
        src_w = max(1, self._canvas_size.width())
        src_h = max(1, self._canvas_size.height())
        x, y, w, h = rect
        wx = self._draw_offset_x + int(round(x * self._draw_width / src_w))
        wy = self._draw_offset_y + int(round(y * self._draw_height / src_h))
        ww = max(1, int(round(w * self._draw_width / src_w)))
        wh = max(1, int(round(h * self._draw_height / src_h)))
        return QRect(wx, wy, ww, wh)

    def _resize_handle_rects(self, rect: QRect) -> dict[str, QRect]:
        size = 12
        center_x = rect.center().x()
        center_y = rect.center().y()
        return {
            "resize-tl": QRect(rect.left() - size // 2, rect.top() - size // 2, size, size),
            "resize-t": QRect(center_x - size // 2, rect.top() - size // 2, size, size),
            "resize-tr": QRect(rect.right() - size // 2, rect.top() - size // 2, size, size),
            "resize-l": QRect(rect.left() - size // 2, center_y - size // 2, size, size),
            "resize-r": QRect(rect.right() - size // 2, center_y - size // 2, size, size),
            "resize-bl": QRect(rect.left() - size // 2, rect.bottom() - size // 2, size, size),
            "resize-b": QRect(center_x - size // 2, rect.bottom() - size // 2, size, size),
            "resize-br": QRect(rect.right() - size // 2, rect.bottom() - size // 2, size, size),
        }

    def _paint_selection_handles(self, painter: QPainter, rect: QRect, active: bool) -> None:
        fill = QColor("#5ec8ff" if active else "#cfeeff")
        outline = QColor("#0f172a")
        painter.setPen(QPen(outline, 1))
        painter.setBrush(fill)
        for handle in self._resize_handle_rects(rect).values():
            painter.drawRect(handle)

    def _preferred_resize_mode(self, rect: QRect, pos: QPoint) -> str:
        edge_band = max(10, min(rect.width(), rect.height()) // 4)
        near_left = abs(pos.x() - rect.left()) <= edge_band
        near_right = abs(pos.x() - rect.right()) <= edge_band
        near_top = abs(pos.y() - rect.top()) <= edge_band
        near_bottom = abs(pos.y() - rect.bottom()) <= edge_band
        if near_top and not (near_left or near_right):
            return "resize-t"
        if near_bottom and not (near_left or near_right):
            return "resize-b"
        if near_left and not (near_top or near_bottom):
            return "resize-l"
        if near_right and not (near_top or near_bottom):
            return "resize-r"
        horizontal = "l" if pos.x() <= rect.center().x() else "r"
        vertical = "t" if pos.y() <= rect.center().y() else "b"
        return f"resize-{vertical}{horizontal}"

    def _resize_rect_from_drag(
        self,
        mode: str,
        x: int,
        y: int,
        width: int,
        height: int,
        dx: int,
        dy: int,
    ) -> tuple[int, int, int, int]:
        return resize_rect_from_drag(mode, (x, y, width, height), dx, dy)

    def _cursor_for_tool_or_hit(self, hit_mode: str | None) -> Qt.CursorShape:
        if hit_mode:
            if hit_mode in {"resize-tl", "resize-br"}:
                return Qt.SizeFDiagCursor
            if hit_mode in {"resize-tr", "resize-bl"}:
                return Qt.SizeBDiagCursor
            if hit_mode in {"resize-l", "resize-r"}:
                return Qt.SizeHorCursor
            if hit_mode in {"resize-t", "resize-b"}:
                return Qt.SizeVerCursor
            if hit_mode == "move":
                return Qt.SizeAllCursor
        if self._tool_mode == "move":
            return Qt.SizeAllCursor
        if self._tool_mode == "scale":
            return Qt.SizeFDiagCursor
        if self._tool_mode == "crop":
            return Qt.CrossCursor
        return Qt.ArrowCursor

    def _group_bounds_rect(self) -> QRect | None:
        selected_rects: list[QRect] = []
        for item in self._elements:
            key = (str(item["collection"]), int(item["index"]))
            if key not in self._selected_many:
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            if rect.width() > 0 and rect.height() > 0:
                selected_rects.append(rect)
        if not selected_rects:
            return None
        group_rect = QRect(selected_rects[0])
        for rect in selected_rects[1:]:
            group_rect = group_rect.united(rect)
        return group_rect

    def _normalize_guide_entry(self, guide: object) -> dict[str, Any] | None:
        if isinstance(guide, dict):
            axis = str(guide.get("axis", "")).strip().lower()
            if axis not in {"x", "y"}:
                return None
            try:
                value = int(guide.get("value", 0))
            except Exception:
                return None
            label = str(guide.get("label", value)).strip() or str(value)
            return {"axis": axis, "value": value, "label": label}
        if isinstance(guide, tuple) and len(guide) >= 2:
            axis = str(guide[0]).strip().lower()
            if axis not in {"x", "y"}:
                return None
            try:
                value = int(guide[1])
            except Exception:
                return None
            label = str(guide[2]).strip() if len(guide) >= 3 else str(value)
            return {"axis": axis, "value": value, "label": label or str(value)}
        return None

    def _compose_guide_badge(self, badge: str, guides: list[dict[str, Any]]) -> str:
        labels: list[str] = []
        seen: set[str] = set()
        for guide in guides:
            label = str(guide.get("label", "")).strip()
            if not label or label in seen:
                continue
            labels.append(label)
            seen.add(label)
            if len(labels) >= 2:
                break
        if not labels:
            return badge
        suffix = " • ".join(labels)
        return f"{badge} • {suffix}" if badge else suffix

    def _paint_guide_label(self, painter: QPainter, anchor: QPoint, text: str) -> None:
        if not text:
            return
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text) + 12
        text_height = metrics.height() + 4
        rect = QRect(anchor.x(), anchor.y(), text_width, text_height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(12, 18, 28, 220))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor("#7dd3fc"))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _paint_preview_status_badge(self, painter: QPainter, text: str) -> None:
        metrics = painter.fontMetrics()
        text_width = min(max(170, metrics.horizontalAdvance(text) + 34), max(170, self._draw_width - 28))
        rect = QRect(
            self._draw_offset_x + self._draw_width - text_width - 14,
            self._draw_offset_y + 24,
            text_width,
            metrics.height() + 14,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(12, 18, 28, 226))
        painter.drawRoundedRect(rect, 8, 8)
        dot_rect = QRect(rect.left() + 12, rect.center().y() - 4, 8, 8)
        painter.setBrush(QColor("#38bdf8"))
        painter.drawEllipse(dot_rect)
        painter.setPen(QColor("#dbeafe"))
        painter.drawText(rect.adjusted(26, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, text)

    def _hit_test(self, pos: QPoint) -> tuple[str, int, str] | None:
        for item in reversed(self._elements):
            if not bool(item.get("visible", True)):
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            for handle_name, handle_rect in self._resize_handle_rects(rect).items():
                if handle_rect.contains(pos):
                    return item["collection"], item["index"], handle_name
            hit_rect = rect.adjusted(-8, -8, 8, 8)
            if hit_rect.contains(pos):
                return item["collection"], item["index"], "move"
        return None

    def _element_rect_for_canvas(self, collection: str, index: int) -> tuple[int, int, int, int] | None:
        for item in self._elements:
            if item["collection"] == collection and item["index"] == index:
                return item["rect"]
        return None

    def _elements_in_widget_rect(self, selection_rect: QRect) -> list[tuple[str, int]]:
        selected: list[tuple[str, int]] = []
        for item in self._elements:
            if not bool(item.get("visible", True)):
                continue
            rect = self._canvas_rect_to_widget_rect(item["rect"])
            if selection_rect.intersects(rect):
                selected.append((str(item["collection"]), int(item["index"])))
        return selected

    def _compute_snap_guides(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        collection: str,
        index: int,
    ) -> list[dict[str, Any]]:
        return compute_snap_guides(
            (x, y, w, h),
            collection=collection,
            index=index,
            elements=self._elements,
            canvas_size=(self._canvas_size.width(), self._canvas_size.height()),
            threshold=int(getattr(self, "_snap_threshold", 8)),
        )

    def _paint_rulers(self, painter: QPainter) -> None:
        if self._draw_width <= 0 or self._draw_height <= 0:
            return
        painter.setPen(QPen(QColor("#344255"), 1))
        painter.fillRect(QRect(self._draw_offset_x, self._draw_offset_y, self._draw_width, 18), QColor(15, 20, 28, 190))
        painter.fillRect(QRect(self._draw_offset_x, self._draw_offset_y, 26, self._draw_height), QColor(15, 20, 28, 190))
        step_x = max(60, self._canvas_size.width() // 8)
        step_y = max(40, self._canvas_size.height() // 6)
        for x in range(0, self._canvas_size.width() + 1, step_x):
            wx = self._draw_offset_x + int(round(x * self._draw_width / max(1, self._canvas_size.width())))
            painter.drawLine(wx, self._draw_offset_y, wx, self._draw_offset_y + 10)
            painter.drawText(wx + 2, self._draw_offset_y + 14, str(x))
        for y in range(0, self._canvas_size.height() + 1, step_y):
            wy = self._draw_offset_y + int(round(y * self._draw_height / max(1, self._canvas_size.height())))
            painter.drawLine(self._draw_offset_x, wy, self._draw_offset_x + 10, wy)
            painter.drawText(self._draw_offset_x + 12, wy - 2, str(y))

    def _refresh_scaled_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            self.clear()
            self._draw_offset_x = 0
            self._draw_offset_y = 0
            self._draw_width = 0
            self._draw_height = 0
            return
        if self._zoom_mode == "fit":
            scaled = self._source_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            width = max(1, int(self._source_pixmap.width() * self._zoom_percent / 100))
            height = max(1, int(self._source_pixmap.height() * self._zoom_percent / 100))
            scaled = self._source_pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self._draw_width = scaled.width()
        self._draw_height = scaled.height()
        self._draw_offset_x = max(0, (self.width() - self._draw_width) // 2)
        self._draw_offset_y = 0 if self._zoom_mode == "fit" else max(0, (self.height() - self._draw_height) // 2)
        self.update()
