"""General and content inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QWidget


def setup_core_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
    wrap_row: Callable[..., QWidget],
) -> None:
    """Populate the basic General and Content inspector tabs on ``owner``."""
    owner.row_general_id = make_label("ID elementu")
    owner.inspector_general_layout.addRow(owner.row_general_id, owner.designer_id_edit)
    owner.row_general_visible = make_label("Widoczność")
    owner.inspector_general_layout.addRow(owner.row_general_visible, owner.designer_visible_chk)
    owner.row_general_locked = make_label("Zablokowany")
    owner.inspector_general_layout.addRow(owner.row_general_locked, owner.designer_locked_chk)
    owner.row_general_z = make_label("Warstwa")
    owner.inspector_general_layout.addRow(owner.row_general_z, owner.designer_z_spin)

    owner.row_content_text = make_label("Tekst")
    owner.inspector_content_layout.addRow(owner.row_content_text, owner.designer_text_edit)
    owner.row_content_label = make_label("Etykieta")
    owner.inspector_content_layout.addRow(owner.row_content_label, owner.designer_label_edit)
    owner.row_content_source = make_label("Źródło")
    owner.inspector_content_layout.addRow(owner.row_content_source, owner.designer_source_combo)
    owner.row_content_format = make_label("Format wartości")
    owner.inspector_content_layout.addRow(owner.row_content_format, owner.designer_format_edit)
    owner.row_content_stat_display = make_label("Tryb wyświetlania")
    owner.inspector_content_layout.addRow(owner.row_content_stat_display, owner.designer_stat_display_combo)
    owner.row_content_stat_range = make_label("Zakres")
    owner.designer_stat_range_row = wrap_row(owner.designer_stat_min_spin, owner.designer_stat_max_spin)
    owner.inspector_content_layout.addRow(owner.row_content_stat_range, owner.designer_stat_range_row)
    owner.row_content_stat_show_value = make_label("Tekst wartości")
    owner.inspector_content_layout.addRow(owner.row_content_stat_show_value, owner.designer_stat_show_value_chk)
    owner._stat_binding_rows_layout = owner.inspector_content_layout
