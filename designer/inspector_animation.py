"""Animation inspector tab wiring for the Theme Designer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton

TranslateFn = Callable[[str, str], str]


def setup_animation_inspector(
    owner: Any,
    make_label: Callable[[str], QLabel],
) -> None:
    """Populate the Theme Designer animation inspector tab on ``owner``."""
    owner.inspector_animation_details_hint = QLabel(
        "Use Animation Studio for the timeline, multi-frame timing, and a large preview. "
        "After editing frames, switch to Theme Designer to place stats and widgets like on a static theme."
    )
    owner.inspector_animation_details_hint.setWordWrap(True)
    owner.inspector_animation_details_hint.setObjectName("selectionSummaryLabel")
    owner.row_animation_overview = make_label("Animation")
    owner.inspector_animation_layout.addRow(owner.row_animation_overview, owner.inspector_animation_details_hint)
    owner.open_animation_studio_btn = QPushButton("Open Animation Studio")
    owner.open_animation_studio_btn.setObjectName("secondaryAccentButton")
    owner.open_animation_studio_btn.clicked.connect(owner._go_animation_studio)
    owner.row_animation_editor = make_label("Editor")
    owner.inspector_animation_layout.addRow(owner.row_animation_editor, owner.open_animation_studio_btn)


def refresh_animation_inspector_labels(owner: Any, translate: TranslateFn) -> None:
    """Refresh labels for the compact Animation inspector tab."""
    if hasattr(owner, "inspector_animation_details_hint"):
        owner.inspector_animation_details_hint.setText(
            translate(
                "Use Animation Studio for the timeline, multi-frame timing, and a large preview. "
                "After editing frames, switch to Theme Designer to place stats and widgets like on a static theme.",
                "W Studio animacji masz oś czasu, zbiorcze czasy i duży podgląd. "
                "Po edycji klatek wróć do Projektanta, by ułożyć statystyki i widgety jak na statycznym motywie.",
            )
        )
    if hasattr(owner, "open_animation_studio_btn"):
        owner.open_animation_studio_btn.setText(translate("Open Animation Studio", "Otwórz Studio animacji"))
